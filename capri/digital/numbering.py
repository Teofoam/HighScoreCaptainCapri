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


# BCD 各码制相对 8421 的偏移。余 3 码就是 8421 加 3 —— 它的好处是
# 0 不再是全 0，且 9 的补正好是 0 的反码，做减法时不用额外判零
BCD_OFFSET = {'8421': 0, '余3': 3}


def encode_bcd(text, code='8421'):
    """十进制数串 → BCD 位串。小数点原样保留（64.27 → 01100100.00100111）。

    按"每个十进制位单独编码"来做，所以小数部分不需要任何特殊处理 ——
    这正是 BCD 相对纯二进制的卖点：十进制小数不会变成无限循环。
    """
    offset = BCD_OFFSET[code]
    out = []
    for ch in str(text).strip():
        if ch == '.':
            out.append('.')
            continue
        if not ch.isdigit():
            raise ValueError(f'{text!r} 不是十进制数串')
        out.append(format(int(ch) + offset, '04b'))
    return ''.join(out)


def decode_bcd(bits, code='8421'):
    """BCD 位串 → 十进制数串。位数不是 4 的倍数、或出现伪码时返回 None。"""
    offset = BCD_OFFSET[code]
    s = ''.join(str(bits).split())
    out = []
    for part in s.split('.'):
        if len(part) % 4 or any(c not in '01' for c in part):
            return None
        digits = []
        for i in range(0, len(part), 4):
            value = int(part[i:i + 4], 2) - offset
            if not 0 <= value <= 9:   # 8421 的 1010~1111、余3 的 0000~0010 都是伪码
                return None
            digits.append(str(value))
        out.append(''.join(digits))
    return '.'.join(out)


def to_bcd(value, code='8421'):
    """非负十进制整数 → BCD 位串。"""
    if value < 0:
        raise ValueError('BCD 不表示负数')
    return encode_bcd(int(value), code)


def from_bcd(bits, code='8421'):
    """BCD 位串 → 十进制整数；伪码或带小数点时返回 None。"""
    out = decode_bcd(bits, code)
    if out is None or '.' in out:
        return None
    return int(out)


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


def split_signed_binary(literal):
    """'-0.10101' → ('-', '0', '10101')；'-10110' → ('-', '10110', '')。"""
    s = str(literal).strip().replace(' ', '')
    sign = ''
    if s[:1] in '+-':
        sign, s = s[0], s[1:]
    intpart, _, fracpart = s.partition('.')
    intpart = intpart or '0'
    if any(c not in '01' for c in intpart + fracpart):
        raise ValueError(f'{literal!r} 不是二进制数')
    return (sign, intpart, fracpart)


def _invert(bits):
    return ''.join('1' if c == '0' else '0' for c in bits)


def machine_codes_binary(literal, width=8):
    """带符号二进制字面量 → (原码, 反码, 补码)。教材的两类写法都支持：

      · 整数 '-10110'，补零到 width 位（1 位符号 + width-1 位数值）
      · 定点小数 '-0.10101'，保留原位数，写成 '1.01011'（符号位 . 数值位）

    小数形态不补零也不截断 —— 教材里 [N]补 的位数就是原数的位数，
    随手补到 8 位反而会把 -0.1100 和 -0.11000000 变成两道不同的题。
    """
    sign, intpart, fracpart = split_signed_binary(literal)
    if not fracpart:
        return machine_codes(int(intpart, 2) * (-1 if sign == '-' else 1), width)

    if intpart.strip('0'):
        raise ValueError('定点小数的整数部分必须是 0')
    if not fracpart.strip('0'):
        raise ValueError('0 的机器数有正零负零之争，不出这种题')
    if sign != '-':
        return (f'0.{fracpart}',) * 3

    ones = _invert(fracpart)
    twos = format(int(ones, 2) + 1, '0{}b'.format(len(fracpart)))
    return (f'1.{fracpart}', f'1.{ones}', f'1.{twos}')


def twos_bits(value, width=8):
    """有符号整数 → 补码位串。跟 machine_codes 不同，这里收得下 -2^(n-1)。"""
    limit = 1 << (width - 1)
    if not -limit <= value <= limit - 1:
        raise ValueError(f'{value} 超出 {width} 位补码范围 [{-limit}, {limit - 1}]')
    return format(value & ((1 << width) - 1), '0{}b'.format(width))


def twos_add(a, b, width=8):
    """补码加法：减法转加法的那套。返回 (结果补码, 真值, 是否溢出)。

    符号位产生的进位直接丢掉 —— 这是补码能把减法做成加法的关键，
    也是教材例题里"由于符号位产生了进位，因此要将此进位丢掉"那句话。
    溢出另算：两个同号数相加得出异号结果，就是真溢出，丢进位救不回来。
    """
    mask = (1 << width) - 1
    raw = (int(twos_bits(a, width), 2) + int(twos_bits(b, width), 2)) & mask
    value = raw - (1 << width) if raw >> (width - 1) else raw
    return (format(raw, '0{}b'.format(width)), value, value != a + b)


def _frac_to_int(literal, n):
    """'-0.1100' + n=4 → -12：定点小数按 2^n 放大成整数，补码规则完全一样。"""
    sign, intpart, fracpart = split_signed_binary(literal)
    if intpart.strip('0'):
        raise ValueError('定点小数的整数部分必须是 0')
    value = int(fracpart.ljust(n, '0'), 2) if fracpart else 0
    return -value if sign == '-' else value


def twos_add_fraction(a, b):
    """定点小数的补码加法，输入形如 '-0.1100'。返回 (结果补码, 真值二进制, 是否溢出)。

    1 位符号 + n 位小数的定点补码，和 n+1 位整数补码是同一套算术 ——
    放大 2^n 倍做完再缩回来，不必单独写一遍进位逻辑。
    """
    n = max(len(split_signed_binary(x)[2]) for x in (a, b))
    ia, ib = _frac_to_int(a, n), _frac_to_int(b, n)
    total = ia + ib
    mask = (1 << (n + 1)) - 1
    raw = (ia & mask) + (ib & mask) & mask
    value = raw - (1 << (n + 1)) if raw >> n else raw
    bits = format(raw, '0{}b'.format(n + 1))
    truth = ('-' if value < 0 else '') + '0.' + format(abs(value), '0{}b'.format(n))
    return (f'{bits[0]}.{bits[1:]}', truth, value != total)
