# -*- coding: utf-8 -*-
"""题目的数据模型：Task 是一道生成出来的题，Blank 是其中一个待填的空。

一道题多个空（Q 点三件套那种），用户一条消息用 ; 分隔一次答完，
判题时按顺序逐空处理 —— 后面的空可以承接前面空的实际作答值（误差传递），
所以不需要多轮会话状态机。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 只为类型标注，运行时不导入，避免和 grading 循环引用
    from .grading import Grader

__all__ = ['Blank', 'Task']


@dataclass(frozen=True)
class Blank:
    key: str                       # 机器名，如 "IBQ"；误差传递靠它引用
    prompt: str                    # 人话，如 "静态基极电流 I_BQ"
    grader: Grader
    unit: str | None = None        # 期望单位，用户省略时按它补
    depends: tuple[str, ...] = ()  # 声明承接了哪些空，仅作文档与校验用


@dataclass(frozen=True)
class Task:
    gid: str                       # 生成器 id
    seed: int
    subject: str                   # "数电" / "模电"
    topic: str
    stem: str                      # 题面，markdown + LaTeX
    blanks: tuple[Blank, ...]
    assets: tuple[str, ...] = ()   # 电路图 / 波形图的路径
    params: dict = field(default_factory=dict)  # 生成参数，复现与调试用

    @property
    def ref(self) -> str:
        """caption 里带的会话态，judge 靠它把整道题原样重建出来。"""
        return f'{self.gid}#{self.seed:08x}'

    def blank(self, key: str) -> Blank | None:
        for b in self.blanks:
            if b.key == key:
                return b
        return None
