# -*- coding: utf-8 -*-
"""数电专用判题器。

BooleanEquiv 是全项目判得最硬的一个：两边各枚举 2^n 行真值表比位图，
写成与或式、或与式还是带异或的形式都不影响判定。判错时给出具体反例，
比只回一句"再想想"有用得多。
"""
from ..core.grading import Verdict
from . import boolean

__all__ = ['BooleanEquiv']


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
