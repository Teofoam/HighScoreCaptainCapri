# -*- coding: utf-8 -*-
"""数电专用判题器。

BooleanEquiv 是全项目判得最硬的一个：两边各枚举 2^n 行真值表比位图，
写成与或式、或与式还是带异或的形式都不影响判定。判错时给出具体反例，
比只回一句"再想想"有用得多。
"""
from fractions import Fraction

from ..core.grading import Verdict
from . import boolean, numbering

__all__ = ['BooleanEquiv', 'RadixLiteral']


class BooleanEquiv:
    """判用户表达式与参考表达式是否等价，可选再判是否最简。

    minimal_cost 是 (项数, 字母数)，由生成器用 QM 算好传进来。
    """

    def __init__(self, ref, var_list, require_minimal=False, minimal_cost=None):
        self.ref = ref
        self.vars = list(var_list)
        self.require_minimal = require_minimal
        self.minimal_cost = minimal_cost

    @property
    def answer_text(self):
        """答对之后回执里报一下标准答案。答错时不报，留着让人再试。"""
        return boolean.to_ascii(self.ref)

    def grade(self, text, ctx):
        try:
            expr = boolean.parse(text, allowed_vars=self.vars)
        except boolean.NotationError as exc:
            return Verdict(False, None, f'表达式没读懂：{exc}')

        if not boolean.equivalent(expr, self.ref, self.vars):
            row = boolean.counterexample(expr, self.ref, self.vars)
            assignment = '、'.join(f'{k}={v}' for k, v in row.items())
            mine = int(boolean.evaluate(expr, {k: bool(v) for k, v in row.items()}))
            theirs = int(boolean.evaluate(self.ref, {k: bool(v) for k, v in row.items()}))
            return Verdict(False, expr,
                           f'不等价：{assignment} 时你的式子等于 {mine}，'
                           f'但 F 应该等于 {theirs}')

        if self.require_minimal:
            if not boolean.is_sop(expr):
                return Verdict(False, expr, '逻辑对了，但本题要求写成与或式')
            got = (boolean.term_count(expr), boolean.literal_count(expr))
            if self.minimal_cost is not None and got > self.minimal_cost:
                return Verdict(False, expr,
                               f'逻辑等价，但还能更简：你写了 {got[0]} 项 {got[1]} 个字母，'
                               f'最简是 {self.minimal_cost[0]} 项 {self.minimal_cost[1]} 个字母')

        return Verdict(True, expr, '')


class RadixLiteral:
    """判一个写在某个进制下的数。

    前导零、`0x`/`H` 前后缀、下标 `(1011)₂`、分位空格全都认 —— 这些是写法
    差异，跟 BooleanEquiv 认六种非号是一个道理。但二进制里写出个 2 会判错，
    那是真错了。

    frac_digits 给出时按"截断到该位数"比对：用户少写的尾零自动补齐，
    所以 0.1010111 和 0.1010111000 都算对；截断位数不够则判错。
    它可以是 ctx -> int 的函数，让位数承接上一空用户自己填的值 ——
    位数答错了，转换结果按你自己填的位数算，不连坐。
    """

    def __init__(self, value, base, frac_digits=None):
        self.value = Fraction(value)
        self.base = base
        self.frac_digits = frac_digits

    def _digits(self, ctx):
        n = self.frac_digits(ctx) if callable(self.frac_digits) else self.frac_digits
        try:
            n = int(n)
        except (TypeError, ValueError):
            return None
        # 上限是防呆：n 再大 base**n 就成了天文数字，判题进程会当场卡住
        return n if 0 <= n <= 64 else None

    @property
    def answer_text(self):
        return self._render(self.value, self.frac_digits
                            if isinstance(self.frac_digits, int) else None)

    def _render(self, value, n):
        sign = '-' if value < 0 else ''
        value = abs(value)
        head = numbering.to_radix(int(value), self.base)
        if not n:
            return sign + head
        return f'{sign}{head}.{numbering.frac_digits(value, self.base, n)}'

    def grade(self, text, ctx):
        got = numbering.parse_radix(text, self.base)
        if got is None:
            name = numbering.RADIX_NAME.get(self.base, f'{self.base} 进制')
            return Verdict(False, None, f'读不懂 {text!r} —— 本空要写{name}')

        n = self._digits(ctx)
        if n is None:
            ok = got == self.value
            want = self._render(self.value, None)
        else:
            # 双方都截断到 n 位再比：用户漏写的尾零不算错，位数不够才算错
            scale = self.base ** n
            ok = int(got * scale) == int(self.value * scale)
            want = self._render(self.value, n)
        return Verdict(ok, got, '' if ok else f'应为 {want}')
