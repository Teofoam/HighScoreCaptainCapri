# -*- coding: utf-8 -*-
"""数制与码制生成器。

一个生成器带五种变体，而不是拆成五个生成器：draw_daily 是按生成器铺开的，
拆开会让"数制"这一个知识点在每天的题里占掉五个名额，把别的题型挤没。

五种变体都是纯算术，不需要画图也不需要仿真 —— 这正是它排在第二个做的原因。
标准答案全部由 numbering 模块算出来，判题器解析用户输入走的也是同一个模块。
"""
from fractions import Fraction

from ...core import registry
from ...core.grading import Numeric, Text
from ...core.task import Blank, Task
from .. import numbering
from ..grading import RadixLiteral

__all__ = ['NumberSystem']

_BASES = [2, 8, 10, 16]
# 精度要求 → 题面里的写法。0.1% 是最经典的那道（答案 10 位）
_TOLERANCES = [(Fraction(1, 100), r'1\%'),
               (Fraction(5, 1000), r'0.5\%'),
               (Fraction(1, 1000), r'0.1\%'),
               (Fraction(1, 1000), r'0.1\%')]

# 位数上限：用户在"保留几位"那一空乱填时，别让 frac_digits 转着圈算下去
_MAX_DIGITS = 64

_CODE_NAME = {'8421': '8421 BCD 码', '余3': '余 3 BCD 码'}


def _group(bits, sep=' '):
    """位串按 4 位一组分隔，小数点两侧各自分组：便于人眼核对。

    进 LaTeX 时必须传 sep=r'\\;' —— 数学模式会把普通空格全部吃掉，
    一串十二位连写没人核得动。
    """
    out = [sep.join(part[i:i + 4] for i in range(0, len(part), 4))
           for part in str(bits).split('.')]
    return (sep + '.' + sep).join(out)



class NumberSystem:
    """数制转换、精度截位、BCD、格雷码、机器数。"""

    gid = 'number-system'
    subject = '数电'
    topic = '数制与码制'
    weight = 5

    def generate(self, rng):
        variant = rng.choices(
            ['radix', 'precision', 'bcd', 'gray', 'complement', 'twos'],
            weights=[4, 2, 3, 2, 3, 3], k=1)[0]
        return getattr(self, f'_{variant}')(rng)

    def _wrap(self, topic, stem, blanks, params):
        return Task(gid=self.gid, seed=0,   # 种子由 registry.build 盖回
                    subject=self.subject, topic=topic,
                    stem='\n'.join(stem), blanks=tuple(blanks), params=params)

    # ---------------------------------------------------------- 进制转换

    def _radix(self, rng):
        if rng.random() < 0.45:
            return self._radix_fraction(rng)

        src, dst = rng.sample(_BASES, 2)
        # 值域按目标进制挑：转二进制时太大会写到十几位，抄都抄错
        top = 255 if 2 in (src, dst) else 4095
        value = rng.randint(top // 8, top)
        shown = numbering.to_radix(value, src)

        stem = [f'将下列{numbering.RADIX_NAME[src]}数转换为'
                f'**{numbering.RADIX_NAME[dst]}**：', '',
                rf'$$({shown})_{{{src}}} = (\;\;?\;\;)_{{{dst}}}$$', '',
                f'直接写{numbering.RADIX_NAME[dst]}结果即可；前导零、'
                '`0x` / `0b` 前缀和 `H` / `B` / `O` 后缀都认。']
        blank = Blank(key='value', prompt=f'{numbering.RADIX_NAME[dst]}结果',
                      grader=RadixLiteral(value, dst))
        return self._wrap('数制转换', stem, [blank],
                          {'variant': 'radix', 'src': src, 'dst': dst,
                           'value': value,
                           'answer': numbering.to_radix(value, dst)})

    def _radix_fraction(self, rng):
        """带小数的进制转换，两种形态对应两类考法。

        二进制↔八/十六进制是**精确**的（分组即得），十进制过来则必须截位 ——
        0.1 这种在二进制里是无限循环，不指定保留位数题目就没有唯一答案。
        """
        if rng.random() < 0.5:
            dst = rng.choice([8, 16])
            group = 3 if dst == 8 else 4
            int_bits = format(rng.randint(8, 255), 'b')
            frac_bits = ''.join(rng.choice('01')
                                for _ in range(rng.choice([4, 5, 6])))
            frac_bits = frac_bits[:-1] + '1'   # 末位钉成 1，免得尾零让位数含糊
            value = (Fraction(int(int_bits, 2))
                     + Fraction(int(frac_bits, 2), 1 << len(frac_bits)))
            digits = -(-len(frac_bits) // group)   # 向上取整：不足一组补零
            shown = f'{int_bits}.{frac_bits}'
            stem = [f'将下列二进制数转换为**{numbering.RADIX_NAME[dst]}**：', '',
                    rf'$$({shown})_{{2}} = (\;\;?\;\;)_{{{dst}}}$$', '',
                    f'> 每 {group} 位二进制对应 1 位{numbering.RADIX_NAME[dst]}：'
                    '以小数点为界，整数部分向左分组、小数部分向右分组，不足补零。']
            params = {'src': 2, 'shown': shown}
        else:
            dst = rng.choice([2, 8, 16])
            places = rng.choice([2, 3])
            value = (rng.randint(8, 63)
                     + Fraction(rng.randint(1, 10 ** places - 1), 10 ** places))
            digits = rng.choice([5, 6]) if dst == 2 else rng.choice([3, 4])
            shown = f'{float(value):.{places}f}'
            stem = [f'将下列十进制数转换为**{numbering.RADIX_NAME[dst]}**，'
                    f'小数点后保留 **{digits} 位**：', '',
                    rf'$$({shown})_{{10}} = (\;\;?\;\;)_{{{dst}}}$$', '',
                    f'> 整数部分除 {dst} 取余，小数部分乘 {dst} 取整；'
                    '多余位**截断**，不四舍五入。']
            params = {'src': 10, 'shown': shown}

        grader = RadixLiteral(value, dst, frac_digits=digits)
        blank = Blank(key='value', prompt=f'{numbering.RADIX_NAME[dst]}结果',
                      grader=grader)
        params.update({'variant': 'radix', 'dst': dst, 'digits': digits,
                       'value': str(value), 'answer': grader.answer_text})
        return self._wrap('数制转换（小数）', stem, [blank], params)

    # ---------------------------------------------------------- 精度截位

    def _precision(self, rng):
        tol, tol_tex = rng.choice(_TOLERANCES)
        places = rng.choice([2, 3, 4])
        frac = Fraction(rng.randint(1, 10 ** places - 1), 10 ** places)
        intpart = rng.choice([0, 0, 0, rng.randint(1, 31)])
        value = intpart + frac
        n = numbering.precision_digits(tol)
        decimal_text = f'{float(value):.{places}f}'
        answer = (numbering.to_radix(intpart, 2) + '.'
                  + numbering.frac_digits(value, 2, n))

        stem = [f'将十进制数 $({decimal_text})_{{10}}$ 转换为**二进制数**，'
                f'要求精度优于 ${tol_tex}$。', '',
                '两空，用 `;` 分隔：', '',
                '1. 二进制小数点后至少需要保留几位', '',
                '2. 该位数下的转换结果', '',
                '> 小数部分用「乘 2 取整」法，多余位**截断**，不四舍五入。',
                '> 保留 $n$ 位时误差小于 $2^{-n}$，让它小于给定精度即可。']
        blanks = [
            Blank(key='n', prompt='保留位数',
                  grader=Numeric(n, rel_tol=1e-9)),
            Blank(key='value', prompt='二进制结果', depends=('n',),
                  grader=RadixLiteral(value, 2,
                                      frac_digits=_carry_digits(n))),
        ]
        # answer 一律是"用户该打进去的整条消息"，多空的就带上分隔符 ——
        # 测试拿它回灌一遍就能验证"生成器出的答案自己判得对"
        return self._wrap('数制转换（精度）', stem, blanks,
                          {'variant': 'precision', 'value': str(value),
                           'tol': str(tol), 'n': n, 'binary': answer,
                           'answer': f'{n} ; {answer}'})

    # ---------------------------------------------------------- BCD

    def _bcd(self, rng):
        places = rng.choice([0, 0, 1, 2])
        whole = rng.randint(10, 999)
        text = (str(whole) if not places else
                '{}.{:0{}d}'.format(whole, rng.randint(1, 10 ** places - 1),
                                    places))
        shape = rng.random()

        if shape < 0.35:
            # 对照型：同一个数写两种码，考的就是"余 3 码比 8421 每位多 3"
            a, b = (numbering.encode_bcd(text, '8421'),
                    numbering.encode_bcd(text, '余3'))
            stem = [f'把十进制数 $({text})_{{10}}$ 分别写成 **8421 BCD 码**'
                    '和**余 3 BCD 码**。', '',
                    '两空，按「8421 ; 余3」的顺序用 `;` 分隔。', '',
                    '> 每个十进制位固定 4 位，小数点原样保留；'
                    '可以用空格分组，也可以连着写。']
            blanks = [Blank(key='bcd8421', prompt='8421 BCD 码', grader=Text(a)),
                      Blank(key='bcdx3', prompt='余 3 BCD 码', grader=Text(b))]
            answer = f'{_group(a)} ; {_group(b)}'
        elif shape < 0.7:
            code = rng.choice(['8421', '余3'])
            bits = numbering.encode_bcd(text, code)
            stem = [f'写出十进制数 $({text})_{{10}}$ 的 **{_CODE_NAME[code]}**。', '',
                    '> 每个十进制位固定 4 位，小数点原样保留；'
                    '可以用空格分组，也可以连着写。']
            blanks = [Blank(key='bcd', prompt=_CODE_NAME[code], grader=Text(bits))]
            answer = _group(bits)
        else:
            code = rng.choice(['8421', '余3'])
            bits = numbering.encode_bcd(text, code)
            stem = [f'下列 **{_CODE_NAME[code]}**对应的十进制数是多少？', '',
                    f'$$({_group(bits, chr(92) + ";")})'
                    f'_{{\\text{{{code}BCD}}}}$$', '',
                    '直接写十进制数。']
            blanks = [Blank(key='dec', prompt='十进制数',
                            grader=Numeric(float(text), rel_tol=1e-9))]
            answer = text

        topic = 'BCD 码' if shape < 0.35 else _CODE_NAME[code]
        return self._wrap(topic, stem, blanks,
                          {'variant': 'bcd', 'value': text, 'answer': answer})

    # ---------------------------------------------------------- 格雷码

    def _gray(self, rng):
        width = rng.choice([4, 4, 5])
        value = rng.randrange(1, 1 << width)
        binary = format(value, f'0{width}b')
        gray = numbering.bin_to_gray(binary)
        if rng.random() < 0.5:
            stem = [f'将 {width} 位自然二进制数 $({binary})_2$ 转换为**格雷码**。', '',
                    f'写满 {width} 位。']
            blank = Blank(key='gray', prompt='格雷码',
                          grader=Text(*_bit_forms(gray)))
            answer = gray
        else:
            stem = [f'下列 {width} 位**格雷码**对应的自然二进制数是多少？', '',
                    rf'$$({gray})_{{\text{{Gray}}}}$$', '',
                    f'写满 {width} 位。']
            blank = Blank(key='bin', prompt='自然二进制数',
                          grader=Text(*_bit_forms(binary)))
            answer = binary
        return self._wrap('格雷码', stem, [blank],
                          {'variant': 'gray', 'width': width,
                           'binary': binary, 'gray': gray, 'answer': answer})

    # ---------------------------------------------------------- 机器数

    def _complement(self, rng):
        shape = rng.random()
        if shape < 0.3:
            return self._complement_fraction(rng)
        width = 8
        limit = (1 << (width - 1)) - 1
        magnitude = rng.randint(1, limit)
        # 正数三码相同，本身是考点，但出多了没意思，压到三成
        value = magnitude if rng.random() < 0.3 else -magnitude
        codes = numbering.machine_codes(value, width)

        if shape < 0.55:
            # 题目给二进制真值、只问补码，字长另行指定
            literal = ('-' if value < 0 else '') + format(abs(value), 'b')
            stem = [f'若 $X = {literal}$，则 $[X]_{{补}} =$ ?', '',
                    f'> 假设字长为 {width} bit。X 给的是**二进制真值**，'
                    '不是机器数；可以用空格分组。']
            blanks = [Blank(key='twos', prompt='补码', grader=Text(codes[2]))]
            answer = codes[2]
        else:
            stem = [f'写出十进制数 ${value}$ 的 {width} 位**原码、反码、补码**。', '',
                    '三空，按「原码 ; 反码 ; 补码」的顺序用 `;` 分隔一次答完。', '',
                    f'> 最高位是符号位，数值位 {width - 1} 位；可以用空格分组。']
            blanks = [
                Blank(key='sign_mag', prompt='原码', grader=Text(codes[0])),
                Blank(key='ones', prompt='反码', grader=Text(codes[1])),
                Blank(key='twos', prompt='补码', grader=Text(codes[2])),
            ]
            answer = ' ; '.join(codes)
        return self._wrap('原码/反码/补码', stem, blanks,
                          {'variant': 'complement', 'value': value,
                           'width': width, 'answer': answer})

    def _complement_fraction(self, rng):
        """定点小数的机器数。教材写成 1.01011 —— 符号位、小数点、数值位。

        位数不补齐到 8 位：小数机器数的位数就是原数的位数，硬补零会把
        -0.1100 和 -0.11000000 变成两道答案不同的题。
        """
        n = rng.choice([4, 5, 5, 6])
        bits = ''.join(rng.choice('01') for _ in range(n - 1)) + '1'
        literal = f'-0.{bits}'
        codes = numbering.machine_codes_binary(literal)

        stem = [f'带符号二进制小数 ${literal}$ 的**反码**是 ?，**补码**是 ?', '',
                '两空，按「反码 ; 补码」的顺序用 `;` 分隔。', '',
                '> 写成 `1.0101` 这种形式：最高位是符号位，小数点后是数值位，'
                f'保留 {n} 位。']
        blanks = [Blank(key='ones', prompt='反码', grader=Text(codes[1])),
                  Blank(key='twos', prompt='补码', grader=Text(codes[2]))]
        return self._wrap('定点小数机器数', stem, blanks,
                          {'variant': 'complement', 'value': literal,
                           'width': n, 'answer': f'{codes[1]} ; {codes[2]}'})

    # ---------------------------------------------------------- 补码运算

    def _twos(self, rng):
        """补码运算：减法转加法，符号位的进位直接丢掉。

        只出不溢出的题。溢出时"结果真值"这一空根本没有正确答案可填，
        硬出就是一道逼人答错的题；溢出判定该单独成题，不该混在这里。
        """
        if rng.random() < 0.4:
            return self._twos_fraction(rng)

        for _ in range(200):
            a, b = rng.randint(-99, 99), rng.randint(-99, 99)
            op = rng.choice(['+', '-'])
            bits, value, overflow = numbering.twos_add(a, b if op == '+' else -b)
            if not overflow and a and b:
                break
        else:
            raise RuntimeError('twos 连续 200 次没抽到不溢出的题')

        shown_b = f'({b})' if b < 0 else str(b)
        stem = [f'用**补码运算**求 ${a} {op} {shown_b}$，字长 8 bit。', '',
                '两空，按「结果补码 ; 结果真值」的顺序用 `;` 分隔。', '',
                '> 减法转成加负数：$[X-Y]_{补} = [X]_{补} + [-Y]_{补}$。'
                '符号位产生的进位**直接丢掉**。',
                '> 结果真值写十进制；若结果为负，记得由补码还原回真值。']
        blanks = [Blank(key='bits', prompt='结果补码', grader=Text(bits)),
                  Blank(key='truth', prompt='结果真值', depends=('bits',),
                        grader=Numeric(value, rel_tol=1e-9))]
        return self._wrap('补码运算', stem, blanks,
                          {'variant': 'twos', 'a': a, 'b': b, 'op': op,
                           'answer': f'{bits} ; {value}'})

    def _twos_fraction(self, rng):
        def pick(n):
            body = ''.join(rng.choice('01') for _ in range(n - 1)) + '1'
            return ('-' if rng.random() < 0.6 else '') + '0.' + body

        n = rng.choice([4, 4, 5])
        for _ in range(200):
            a, b = pick(n), pick(n)
            op = rng.choice(['+', '-'])
            rhs = (b[1:] if b.startswith('-') else '-' + b) if op == '-' else b
            bits, truth, overflow = numbering.twos_add_fraction(a, rhs)
            # 只要结果为负的：正数的补码等于真值本身，两个空答案一样，
            # 白白少考一步"由补码还原真值"
            if not overflow and truth.startswith('-'):
                break
        else:
            raise RuntimeError('twos_fraction 连续 200 次没抽到不溢出的题')

        label = '[N_1+N_2]' if op == '+' else '[N_1-N_2]'
        stem = [f'已知 $N_1 = {a}$，$N_2 = {b}$，用**补码运算**求 '
                f'${label}_{{补}}$ 及其真值。', '',
                '两空，按「结果补码 ; 结果真值」的顺序用 `;` 分隔。', '',
                '> 写成 `1.0010` 这种形式。符号位产生的进位**直接丢掉**；'
                '结果真值写成带符号二进制小数，如 `-0.1110`。']
        blanks = [Blank(key='bits', prompt='结果补码', grader=Text(bits)),
                  Blank(key='truth', prompt='结果真值', depends=('bits',),
                        grader=Text(truth))]
        return self._wrap('补码运算（小数）', stem, blanks,
                          {'variant': 'twos', 'a': a, 'b': b, 'op': op,
                           'answer': f'{bits} ; {truth}'})


def _bit_forms(bits):
    """位串的可接受写法：原样，以及去掉前导零的版本。

    题面写了"写满 n 位"，但为一个前导零判错太苛刻 —— 判题该因为
    码错而判错，不该因为写法判错。
    """
    stripped = bits.lstrip('0')
    return (bits, stripped) if stripped and stripped != bits else (bits,)


def _carry_digits(default):
    """让"转换结果"那一空承接用户在"保留位数"里自己填的值。

    位数填错了，结果按你自己填的位数判 —— 一步失手不连坐（见 core/grading）。
    但要卡住范围：用户填个 10^9，frac_digits 会当场转晕。
    """
    def pick(ctx):
        got = ctx.answered.get('n')
        try:
            k = int(round(float(got)))
        except (TypeError, ValueError):
            return default
        return k if 1 <= k <= _MAX_DIGITS else default
    return pick


registry.register(NumberSystem())

