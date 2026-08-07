# -*- coding: utf-8 -*-
"""带单位的数值解析：把 "2.2k" / "1.5kΩ" / "10μA" / "-3dB" 归一到 SI 基本单位。

这是模电判题的命根子。老的 problem_bank.parse_number 只会兜底抠出第一个数字，
"1.5kΩ" 解析成 1.5、"10μA" 解析成 10 —— 而模电答案满屏都是 k/μ/m，
不认前缀就等于judge 全错。

三个必须写死的坑：
  · m 和 M 大小写敏感 —— 毫和兆差 10^9，错了不会报错，只会静默判错
  · E 一律当科学计数法而不是 exa 前缀（2E5 = 200000）
  · dB 是对数量纲，必须用绝对容差；相对容差在 0dB 附近会直接炸
"""
import ast
import math
import re

__all__ = ['Quantity', 'parse', 'close', 'format_value']


class Quantity:
    """归一到 SI 基本单位后的数值。unit 为 '' 表示纯数。"""
    __slots__ = ('value', 'unit')

    def __init__(self, value, unit=''):
        self.value = float(value)
        self.unit = unit

    def __repr__(self):
        return f'Quantity({self.value!r}, {self.unit!r})'

    def __eq__(self, other):
        return (isinstance(other, Quantity)
                and self.value == other.value and self.unit == other.unit)


# 大小写敏感，别为了"宽容"合并。K 收成 kilo 是向现实低头：
# 电子学语境里手打 2.2K 几乎不可能是开尔文
_PREFIX = {
    'T': 1e12, 'G': 1e9, 'M': 1e6, 'k': 1e3, 'K': 1e3,
    'm': 1e-3, 'u': 1e-6, 'μ': 1e-6, 'µ': 1e-6,  # U+03BC 和 U+00B5 是两个码位
    'n': 1e-9, 'p': 1e-12, 'f': 1e-15,
}

# 长的排前面，Hz 必须比 H 先匹配上
_UNITS = [
    ('dB', 'dB'), ('Hz', 'Hz'), ('ohm', 'Ω'), ('Ohm', 'Ω'), ('Ω', 'Ω'),
    ('V', 'V'), ('A', 'A'), ('F', 'F'), ('H', 'H'), ('W', 'W'), ('s', 's'),
    ('欧姆', 'Ω'), ('欧', 'Ω'), ('伏特', 'V'), ('伏', 'V'), ('安培', 'A'),
    ('安', 'A'), ('赫兹', 'Hz'), ('赫', 'Hz'), ('法拉', 'F'), ('法', 'F'),
    ('亨利', 'H'), ('亨', 'H'), ('瓦特', 'W'), ('瓦', 'W'), ('秒', 's'),
]
_UNITS.sort(key=lambda kv: -len(kv[0]))

_FULLWIDTH = str.maketrans('０１２３４５６７８９．－＋（）／＊，',
                           '0123456789.-+()/*,')
_SUPERSCRIPT = {'²': '**2', '³': '**3'}

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_NAMES = {'pi': math.pi, 'e': math.e}
_ALLOWED_FUNCS = {
    'sqrt': math.sqrt, 'ln': math.log, 'log': math.log10,
    'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
    'exp': math.exp, 'abs': abs,
}
_NUMBER_RE = re.compile(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')


def _safe_eval(expr):
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            return a ** b
        if isinstance(node, ast.Name) and node.id in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _ALLOWED_FUNCS and len(node.args) == 1
                and not node.keywords):
            return _ALLOWED_FUNCS[node.func.id](ev(node.args[0]))
        raise ValueError('unsupported expression')

    return ev(ast.parse(expr, mode='eval'))


def _normalize(text):
    s = str(text).strip().translate(_FULLWIDTH)
    for k, v in _SUPERSCRIPT.items():
        s = s.replace(k, v)
    s = s.replace('π', 'pi').replace('Π', 'pi')
    s = (s.replace('×', '*').replace('·', '*').replace('÷', '/')
          .replace('−', '-').replace('–', '-'))
    s = re.sub(r'√\s*\(', 'sqrt(', s)
    s = re.sub(r'√\s*(\d+(?:\.\d+)?)', r'sqrt(\1)', s)
    s = s.replace('^', '**')
    return re.sub(r'\s+', '', s)


def _implicit_mult(s):
    # 2pi -> 2*pi、3sqrt(2) -> 3*sqrt(2)、(1+2)pi -> (1+2)*pi。
    # 不碰 e：2e5 是科学计数法，不是 2*e*5
    s = re.sub(r'(pi)(\(|sqrt|ln|log|sin|cos|tan|exp)', r'\1*\2', s)
    s = re.sub(r'(\d|\))(pi\b|sqrt|ln|log|sin|cos|tan|exp|\()', r'\1*\2', s)
    return re.sub(r'(\))(\d)', r'\1*\2', s)


def _strip_unit(s):
    """剥掉末尾单位，返回 (剩余串, 单位)。没有单位时单位为 ''。"""
    for token, canon in _UNITS:
        if len(s) > len(token) and s.endswith(token):
            return s[:-len(token)], canon
    return s, ''


def _strip_prefix(s):
    """剥掉末尾的 SI 词头，返回 (剩余串, 倍率)。"""
    if len(s) > 1 and s[-1] in _PREFIX:
        # E/e 结尾不算词头：2e5 是科学计数法，让 _safe_eval 自己处理
        return s[:-1], _PREFIX[s[-1]]
    return s, 1.0


def parse(text, expect=None):
    """尽力解析成 Quantity；解析不了返回 None。

    expect 给出期望单位时，用户省略单位（"2.2k"）也会被认成该单位。
    """
    if text is None:
        return None
    s = _normalize(text)
    if not s:
        return None

    body, unit = _strip_unit(s)
    body, scale = _strip_prefix(body)
    body = _implicit_mult(body)

    value = None
    try:
        value = _safe_eval(body)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError):
        # 兜底：忽略认不出的尾巴，抠第一个数字。"166J"、"2e5N/C" 这类还能救
        m = _NUMBER_RE.search(body)
        if m:
            try:
                value = float(m.group(0))
            except ValueError:
                return None
    if value is None:
        return None

    # dB 是对数量纲，词头对它没有意义，硬套只会把 -3dB 变成 -3e-3
    if unit == 'dB':
        return Quantity(value, 'dB')
    return Quantity(value * scale, unit or (expect or ''))


def close(expected, given, rel_tol=0.05):
    """两个 Quantity 是否算相等。

    单位不一致直接判否 —— 5V 和 5A 数值相同但显然不是一个东西。
    一方没单位（用户偷懒没写）则不追究。
    """
    if expected is None or given is None:
        return False
    if expected.unit and given.unit and expected.unit != given.unit:
        return False
    if expected.unit == 'dB' or given.unit == 'dB':
        return abs(given.value - expected.value) <= 0.5  # 绝对容差 0.5dB
    return abs(given.value - expected.value) <= max(1e-12,
                                                    rel_tol * abs(expected.value))


_DISPLAY = [(1e12, 'T'), (1e9, 'G'), (1e6, 'M'), (1e3, 'k'),
            (1.0, ''), (1e-3, 'm'), (1e-6, 'μ'), (1e-9, 'n'), (1e-12, 'p')]


def format_value(value, unit=''):
    """把 0.0000223 A 显示成 22.3 μA，给判题回执用。"""
    if value == 0 or unit == 'dB':
        return f'{value:g} {unit}'.strip()
    magnitude = abs(value)
    for scale, prefix in _DISPLAY:
        if magnitude >= scale:
            return f'{value / scale:.4g} {prefix}{unit}'.strip()
    return f'{value:g} {unit}'.strip()
