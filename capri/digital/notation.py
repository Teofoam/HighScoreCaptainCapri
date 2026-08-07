# -*- coding: utf-8 -*-
"""把五花八门的逻辑记号收敛成统一 token 流。

数电的记号问题，对应模电的单位前缀问题：课本印的是 Ā，键盘上打不出来，
于是同一个"非"至少会以 A' / ~A / !A / /A / A# / A̅ 六种形态出现在答案里。
解析器必须全部接住 —— 判题应该因为逻辑错而判错，不该因为写法判错。

并置即与（AB 等于 A·B），而或用的是 +。这跟数学里 + 是加法的直觉冲突，
所以不能复用 problem_bank 里那套隐式乘法正则，得单独 tokenize。
"""
import enum
import re

__all__ = ['Kind', 'Token', 'tokenize', 'NotationError']


class NotationError(ValueError):
    """表达式里有不认识的字符或结构。"""


class Kind(enum.Enum):
    VAR = 'var'
    CONST = 'const'
    NOT = 'not'          # 前缀非：~A
    POSTNOT = 'postnot'  # 后缀非：A' 、A̅ 、(A+B)'
    AND = 'and'
    OR = 'or'
    XOR = 'xor'
    LPAR = 'lpar'
    RPAR = 'rpar'


class Token:
    __slots__ = ('kind', 'text')

    def __init__(self, kind, text=''):
        self.kind = kind
        self.text = text

    def __repr__(self):
        if self.text:
            return f'Token({self.kind.name}, {self.text!r})'
        return f'Token({self.kind.name})'

    def __eq__(self, other):
        return (isinstance(other, Token)
                and self.kind == other.kind and self.text == other.text)


# 前缀非。注意不收 '-'：它在"或"的语境里太容易和减号/连字符混
_NOT_PREFIX = set('~!¬/')
# 后缀非。'#' 是部分教材/讲义的写法；U+0304 组合上加符、U+0305 组合上划线是 Ā 的真身
_NOT_POSTFIX = set("'′’′#̄̅")
_AND = set('*·∧&×⋅∩')
_OR = set('+|∨∪')
_XOR = set('^⊕⊻')
_LPAR = set('([（【')
_RPAR = set(')]）】')

# 全角数字/字母 → 半角
_FULLWIDTH = str.maketrans(
    'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
    'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
    '０１２３４５６７８９',
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    'abcdefghijklmnopqrstuvwxyz'
    '0123456789')

# "F(A,B,C) =" / "Y =" 这种题头，用户会照抄，得先剥掉
_HEAD_RE = re.compile(r'^\s*[A-Za-z]\w*\s*(\([^)]*\))?\s*=')

_VAR_RE = re.compile(r'[A-Za-z]\d*')


def tokenize(expr):
    """把表达式串切成 token 列表，并补上并置省略的与。

    抛 NotationError 表示输入里有无法识别的字符。
    """
    if expr is None:
        raise NotationError('空表达式')
    s = str(expr).translate(_FULLWIDTH)
    # 用户常把整道题抄进来："F(A,B,C) = AB + C'"，只取等号右边
    head = _HEAD_RE.match(s)
    if head:
        s = s[head.end():]
    s = s.strip()
    if not s:
        raise NotationError('空表达式')

    tokens = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        m = _VAR_RE.match(s, i)
        if m:
            tokens.append(Token(Kind.VAR, m.group(0).upper()))
            i = m.end()
            continue
        if ch in '01':
            tokens.append(Token(Kind.CONST, ch))
            i += 1
            continue
        if ch in _NOT_POSTFIX:
            # 后缀非必须挂在某个东西后面，否则是笔误
            if not tokens or tokens[-1].kind not in (
                    Kind.VAR, Kind.CONST, Kind.RPAR, Kind.POSTNOT):
                raise NotationError(f'位置 {i} 的 {ch!r} 前面没有可取反的对象')
            tokens.append(Token(Kind.POSTNOT))
            i += 1
            continue
        if ch in _NOT_PREFIX:
            tokens.append(Token(Kind.NOT))
            i += 1
            continue
        if ch in _AND:
            tokens.append(Token(Kind.AND))
            i += 1
            continue
        if ch in _OR:
            tokens.append(Token(Kind.OR))
            i += 1
            continue
        if ch in _XOR:
            tokens.append(Token(Kind.XOR))
            i += 1
            continue
        if ch in _LPAR:
            tokens.append(Token(Kind.LPAR))
            i += 1
            continue
        if ch in _RPAR:
            tokens.append(Token(Kind.RPAR))
            i += 1
            continue
        raise NotationError(f'位置 {i} 有不认识的字符 {ch!r}')

    return _insert_implicit_and(tokens)


# 左边这些之后、右边这些之前，如果直接相邻，中间省略的是"与"
_LEFT = (Kind.VAR, Kind.CONST, Kind.RPAR, Kind.POSTNOT)
_RIGHT = (Kind.VAR, Kind.CONST, Kind.LPAR, Kind.NOT)


def _insert_implicit_and(tokens):
    out = []
    for tok in tokens:
        if out and out[-1].kind in _LEFT and tok.kind in _RIGHT:
            out.append(Token(Kind.AND))
        out.append(tok)
    return out
