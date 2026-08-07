# -*- coding: utf-8 -*-
"""判题：Grader 协议与学科无关的几个实现。

学科专用的判题器（布尔等价、spec 验证）放各自学科目录下，core 不认识它们。

误差传递全靠 Numeric 的 expected 收 ctx 而不是收死值：
    Numeric(lambda ctx: -ctx.answered['ICQ'] * RL / ctx.answered['rbe'])
前面填错了，后面就按你自己的错值往下算，一步失手不连坐。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Protocol

from . import quantity

if TYPE_CHECKING:
    from .task import Blank, Task

__all__ = ['Verdict', 'GradeContext', 'Grader', 'Numeric', 'Choice', 'SetOf',
           'Text', 'grade_task', 'split_answers']


@dataclass
class Verdict:
    ok: bool
    parsed: Any = None      # 解析后的值，供后面的空承接
    detail: str = ''        # 给用户看的一句话


@dataclass
class GradeContext:
    task: Task
    answered: dict[str, Any] = field(default_factory=dict)


class Grader(Protocol):
    def grade(self, text: str, ctx: GradeContext) -> Verdict: ...


class Numeric:
    """数值判定。expected 可以是常数，也可以是 ctx -> 数值 的函数。"""

    def __init__(self, expected, rel_tol=0.05, unit=None):
        self.expected = expected
        self.rel_tol = rel_tol
        self.unit = unit

    def _expected_value(self, ctx):
        return self.expected(ctx) if callable(self.expected) else self.expected

    def grade(self, text, ctx):
        want = self._expected_value(ctx)
        if isinstance(want, quantity.Quantity):
            want_q = want
        else:
            want_q = quantity.Quantity(want, self.unit or '')
        got = quantity.parse(text, expect=self.unit)
        if got is None:
            return Verdict(False, None, f'读不懂 {text!r} 这个数')
        ok = quantity.close(want_q, got, self.rel_tol)
        shown = quantity.format_value(want_q.value, want_q.unit)
        return Verdict(ok, got.value, '' if ok else f'应为 {shown}')


_MC_LETTER_RE = re.compile(r'(?<![A-Za-z])([A-Da-d])(?![A-Za-z])')


class Choice:
    """选择题。宽容匹配 "A" / "a" / "(A)" / "选 A"。"""

    def __init__(self, letter):
        self.letter = str(letter).strip().upper()

    def grade(self, text, ctx):
        picked = {m.upper() for m in _MC_LETTER_RE.findall(str(text))}
        ok = picked == {self.letter}
        return Verdict(ok, picked, '' if ok else f'应选 {self.letter}')


class SetOf:
    """无序集合，如最小项 Σm(1,3,5)。顺序、重复、分隔符都不计较。"""

    def __init__(self, items, label=''):
        self.items = {str(x).strip() for x in items}
        self.label = label

    def grade(self, text, ctx):
        given = {t for t in re.split(r'[,\s，、;；]+', str(text).strip()) if t}
        ok = given == self.items
        detail = '' if ok else f'应为 {{{", ".join(sorted(self.items))}}}'
        return Verdict(ok, given, detail)


class Text:
    """文本比对，忽略大小写和空白。accept 里任一写法命中即算对。"""

    def __init__(self, *accept):
        self.accept = [re.sub(r'\s+', '', str(a)).casefold() for a in accept]

    def grade(self, text, ctx):
        got = re.sub(r'\s+', '', str(text)).casefold()
        ok = got in self.accept
        return Verdict(ok, text, '' if ok else '答案不对')


_SPLIT_RE = re.compile(r'[;；\n]+')


def split_answers(text, n):
    """把用户一条消息拆成 n 份。只有一个空时整条就是答案，不拆。"""
    if n <= 1:
        return [str(text).strip()]
    return [p.strip() for p in _SPLIT_RE.split(str(text)) if p.strip()]


def grade_task(task, user_text):
    """按顺序判完所有空，返回 [(Blank, Verdict), ...]。

    空数对不上时返回空列表，由调用方提示用户 —— 不猜哪个是哪个，
    猜错了给出的反馈比不给还糟。
    """
    parts = split_answers(user_text, len(task.blanks))
    if len(parts) != len(task.blanks):
        return []
    ctx = GradeContext(task=task)
    results = []
    for blank, part in zip(task.blanks, parts):
        verdict = blank.grader.grade(part, ctx)
        # 不论对错都记进 answered：后面的空承接的是"你填的值"，不是标准值
        ctx.answered[blank.key] = verdict.parsed
        results.append((blank, verdict))
    return results
