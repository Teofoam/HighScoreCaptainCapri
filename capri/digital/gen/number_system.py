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



class NumberSystem:
    """数制转换、精度截位、BCD、格雷码、机器数。"""

    gid = 'number-system'
    subject = '数电'
    topic = '数制与码制'
    weight = 5

    def generate(self, rng):
        variant = rng.choices(
            ['radix', 'precision', 'bcd', 'gray', 'complement'],
            weights=[3, 3, 2, 2, 3], k=1)[0]
        return getattr(self, f'_{variant}')(rng)

    def _wrap(self, topic, stem, blanks, params):
        return Task(gid=self.gid, seed=0,   # 种子由 registry.build 盖回
                    subject=self.subject, topic=topic,
                    stem='\n'.join(stem), blanks=tuple(blanks), params=params)

    # ---------------------------------------------------------- 进制转换

    def _radix(self, rng):
        src, dst = rng.sample(_BASES, 2)
        # 值域按目标进制挑：转二进制时太大会写到十几位，抄都抄错
        top = 255 if 2 in (src, dst) else 4095
        value = rng.randint(top // 8, top)
        shown = numbering.to_radix(value, src)
        answer = numbering.to_radix(value, dst)

        stem = [f'将下列{numbering.RADIX_NAME[src]}数转换为'
                f'**{numbering.RADIX_NAME[dst]}**：', '',
                rf'$$({shown})_{{{src}}} = (\;\;?\;\;)_{{{dst}}}$$', '',
                f'直接写{numbering.RADIX_NAME[dst]}结果即可，'
                f'如 `{answer}`；前导零、`0x` / `H` 之类的前后缀都认。']
        blank = Blank(key='value', prompt=f'{numbering.RADIX_NAME[dst]}结果',
                      grader=RadixLiteral(value, dst))
        return self._wrap('数制转换', stem, [blank],
                          {'variant': 'radix', 'src': src, 'dst': dst,
                           'value': value, 'answer': answer})

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
        value = rng.randint(10, 9999)
        bits = numbering.to_bcd(value)
        grouped = ' '.join(bits[i:i + 4] for i in range(0, len(bits), 4))
        if rng.random() < 0.5:
            stem = [f'写出十进制数 $({value})_{{10}}$ 的 **8421 BCD 码**。', '',
                    '每个十进制位写满 4 位，可以用空格分组（`0100 1001`），也可以连着写。']
            blank = Blank(key='bcd', prompt='8421 BCD 码',
                          grader=Text(bits, grouped))
            answer = grouped
        else:
            stem = ['下列 **8421 BCD 码**对应的十进制数是多少？', '',
                    rf'$$({grouped})_{{\text{{8421BCD}}}}$$', '',
                    '直接写十进制数。']
            blank = Blank(key='dec', prompt='十进制数',
                          grader=Numeric(value, rel_tol=1e-9))
            answer = str(value)
        return self._wrap('BCD 码', stem, [blank],
                          {'variant': 'bcd', 'value': value,
                           'bits': bits, 'answer': answer})

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
        width = 8
        limit = (1 << (width - 1)) - 1
        magnitude = rng.randint(1, limit)
        # 正数三码相同，本身是考点，但出多了没意思，压到三成
        value = magnitude if rng.random() < 0.3 else -magnitude
        codes = numbering.machine_codes(value, width)

        stem = [f'写出十进制数 ${value}$ 的 {width} 位**原码、反码、补码**。', '',
                '三空，按「原码 ; 反码 ; 补码」的顺序用 `;` 分隔一次答完。', '',
                f'> 最高位是符号位，数值位 {width - 1} 位；可以用空格分组。']
        blanks = [
            Blank(key='sign_mag', prompt='原码', grader=Text(codes[0])),
            Blank(key='ones', prompt='反码', grader=Text(codes[1])),
            Blank(key='twos', prompt='补码', grader=Text(codes[2])),
        ]
        return self._wrap('原码/反码/补码', stem, blanks,
                          {'variant': 'complement', 'value': value,
                           'width': width, 'answer': ' ; '.join(codes)})


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

