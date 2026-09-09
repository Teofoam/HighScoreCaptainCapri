# -*- coding: utf-8 -*-
"""数制与码制：进制转换、BCD、格雷码、机器数。

这一层只做纯计算，不碰题面也不碰判题 —— 生成器用它算标准答案，
判题器用它解析用户输入，两边跑的是同一份代码，不可能对不上。

小数转换全程走 Fraction 而不是 float：0.1 在二进制里是无限循环小数，
float 算到小数点后十几位就开始飘，而"精度优于 0.1%"这类题问的恰好
就是第 10 位。用 Fraction 连"乘 2 取整"都是精确的。
"""
from fractions import Fraction

__all__ = ['DIGITS', 'to_radix', 'parse_radix', 'frac_digits',
           'precision_digits', 'to_bcd', 'from_bcd', 'bin_to_gray',
           'gray_to_bin', 'machine_codes', 'RADIX_NAME']

DIGITS = '0123456789ABCDEF'

RADIX_NAME = {2: '二进制', 8: '八进制', 10: '十进制', 16: '十六进制'}

# 各进制惯用的后缀字母。只收不会和该进制数字撞车的那个：
# 十六进制里 B 和 D 本身就是数字，所以只认 H
_SUFFIX = {2: 'B', 8: 'OQ', 10: 'D', 16: 'H'}
_PREFIX = {2: ('0B',), 8: ('0O',), 16: ('0X',)}

_SUBSCRIPT = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
_FULLWIDTH = str.maketrans(
    'ＡＢＣＤＥＦａｂｃｄｅｆ０１２３４５６７８９．（）',
    'ABCDEFabcdef0123456789.()')


def to_radix(value, base, width=None):
    """非负整数 → 该进制的字符串。width 给出时左补零到该宽度。"""
    if value < 0:
        raise ValueError('to_radix 只处理非负整数，符号由调用方自己拼')
    s = ''
    v = int(value)
    while v:
        s = DIGITS[v % base] + s
        v //= base
    s = s or '0'
    return s.rjust(width, '0') if width else s


def parse_radix(text, base):
    """把用户写的某进制数读成 Fraction。读不出返回 None。

    宽容到什么程度是有讲究的：前导零、`0x`/`H` 前后缀、下标 `(1011)₂`、
    分位空格和下划线全认 —— 这些都是写法差异，不该判错。
    但超出该进制的数字（二进制里写了个 2）必须判错，那是真错了。
    """
    if text is None:
        return None
    s = str(text).translate(_FULLWIDTH).translate(_SUBSCRIPT)
    s = s.replace(' ', '').replace('_', '').replace(',', '').strip()
    if not s:
        return None

    # (1011)2 / (1011)₂ —— 括号里才是数，括号后面是进制标注
    if s.startswith('(') and ')' in s:
        head, _, tail = s.partition(')')
        if tail.isdigit() or tail == '':
            s = head[1:]
    s = s.upper()

    for prefix in _PREFIX.get(base, ()):
        if s.startswith(prefix) and len(s) > len(prefix):
            s = s[len(prefix):]
            break
    else:
        # 后缀字母只在剥掉之后仍然合法时才剥，否则 'B' 可能是十六进制的 11
        if len(s) > 1 and s[-1] in _SUFFIX.get(base, ''):
            if _all_digits(s[:-1], base):
                s = s[:-1]

    negative = s.startswith('-')
    if negative or s.startswith('+'):
        s = s[1:]
    if not s:
        return None

    intpart, dot, fracpart = s.partition('.')
    intpart = intpart or '0'
    if not _all_digits(intpart, base) or (dot and not _all_digits(fracpart, base)):
        return None

    value = Fraction(int(intpart, base) if intpart else 0)
    for k, ch in enumerate(fracpart, start=1):
        value += Fraction(DIGITS.index(ch), base ** k)
    return -value if negative else value


def _all_digits(s, base):
    return bool(s) and all(ch in DIGITS[:base] for ch in s)


def frac_digits(value, base, n):
    """小数部分按"乘基取整"法展开 n 位，多余位**截断**（不四舍五入）。

    截断是教材的做法，也是硬件里移位截位的实际行为；改成四舍五入会让
    "误差 < base^-n" 这个前提不成立，精度题的标准答案就跟着变了。
    """
    frac = Fraction(value) - int(Fraction(value))
    out = []
    for _ in range(n):
        frac *= base
        digit = int(frac)
        out.append(DIGITS[digit])
        frac -= digit
    return ''.join(out)


def precision_digits(tol, base=2):
    """要让量化误差小于 tol，小数点后至少要保留几位。

    截断到 n 位后误差 < base^-n，所以取最小的 n 使 base^-n < tol。
    经典考法：精度优于 0.1% → 2^-10 = 0.098% < 0.1%，而 2^-9 = 0.195%
    不够，所以答案是 10 位。
    """
    tol = Fraction(tol)
    if tol <= 0:
        raise ValueError('精度要求必须为正')
    n = 0
    while Fraction(1, base ** n) >= tol:
        n += 1
    return n


def to_bcd(value, group=4):
    """非负十进制整数 → 8421 BCD，每个十进制位固定 4 bit。"""
    if value < 0:
        raise ValueError('BCD 不表示负数')
    return ''.join(format(int(d), '04b') for d in str(int(value)))


def from_bcd(bits):
    """8421 BCD → 十进制整数。位数不是 4 的倍数、或出现 1010~1111 时返回 None。"""
    s = ''.join(str(bits).split())
    if not s or len(s) % 4 or any(c not in '01' for c in s):
        return None
    out = 0
    for i in range(0, len(s), 4):
        nibble = int(s[i:i + 4], 2)
        if nibble > 9:  # 1010~1111 是 BCD 的非法码（伪码）
            return None
        out = out * 10 + nibble
    return out


def bin_to_gray(bits):
    """自然二进制 → 格雷码。位宽保持不变（前导零不丢）。"""
    s = str(bits).strip()
    value = int(s, 2)
    return format(value ^ (value >> 1), '0{}b'.format(len(s)))


def gray_to_bin(bits):
    """格雷码 → 自然二进制。逐位异或前一位的结果，位宽不变。"""
    s = str(bits).strip()
    out = s[0]
    for ch in s[1:]:
        out += str(int(out[-1]) ^ int(ch))
    return out


def machine_codes(value, width=8):
    """有符号十进制 → (原码, 反码, 补码)，定点整数，位宽 width。

    取值范围卡在 ±(2^(width-1) - 1)：-128 在 8 位里只有补码 10000000，
    没有对应的原码和反码，让它进来会生成一道无解的题。
    """
    limit = (1 << (width - 1)) - 1
    if not -limit <= value <= limit:
        raise ValueError(f'{value} 超出 {width} 位原码/反码的表示范围 ±{limit}')
    magnitude = format(abs(value), '0{}b'.format(width - 1))
    if value >= 0:
        # 正数三码相同 —— 这本身就是个常考点
        return ('0' + magnitude,) * 3
    sign_mag = '1' + magnitude
    ones = '1' + ''.join('1' if c == '0' else '0' for c in magnitude)
    twos = format(int(ones, 2) + 1, '0{}b'.format(width))
    return (sign_mag, ones, twos)
