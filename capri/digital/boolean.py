# -*- coding: utf-8 -*-
"""布尔表达式：解析、求值、真值表、等价判定、渲染。

判题的核心在 equivalent()：把两个表达式各自枚举 2^n 行真值表再比对。
这是全项目唯一能做到"形式无关且完全严格"的判定 —— 与或式、或与式、
带异或的写法，只要真值表一致就全判对，不需要任何模式匹配或化简规则。

表达式用元组表示，天然可哈希、可比较：
    ('var', 'A') / ('const', True) / ('not', e) / ('and', a, b) / ('or', a, b) / ('xor', a, b)
"""
from .notation import Kind, NotationError, tokenize

__all__ = ['parse', 'evaluate', 'variables', 'truth_table', 'equivalent',
           'counterexample', 'literal_count', 'term_count', 'is_sop',
           'to_ascii', 'to_latex', 'NotationError']

VAR, CONST, NOT, AND, OR, XOR = 'var', 'const', 'not', 'and', 'or', 'xor'


# ---------------------------------------------------------------------------
# 解析：递归下降。优先级 非 > 与 > 异或 > 或
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def eat(self, kind):
        tok = self.peek()
        if tok is None or tok.kind is not kind:
            raise NotationError(f'第 {self.i + 1} 个符号处期待 {kind.name}')
        self.i += 1
        return tok

    def parse(self):
        e = self.p_or()
        if self.i != len(self.toks):
            raise NotationError(f'第 {self.i + 1} 个符号之后有多余内容')
        return e

    def p_or(self):
        e = self.p_xor()
        while (t := self.peek()) and t.kind is Kind.OR:
            self.i += 1
            e = (OR, e, self.p_xor())
        return e

    def p_xor(self):
        e = self.p_and()
        while (t := self.peek()) and t.kind is Kind.XOR:
            self.i += 1
            e = (XOR, e, self.p_and())
        return e

    def p_and(self):
        e = self.p_not()
        while (t := self.peek()) and t.kind is Kind.AND:
            self.i += 1
            e = (AND, e, self.p_not())
        return e

    def p_not(self):
        if (t := self.peek()) and t.kind is Kind.NOT:
            self.i += 1
            return (NOT, self.p_not())
        return self.p_postfix()

    def p_postfix(self):
        e = self.p_atom()
        while (t := self.peek()) and t.kind is Kind.POSTNOT:
            self.i += 1
            e = (NOT, e)
        return e

    def p_atom(self):
        tok = self.peek()
        if tok is None:
            raise NotationError('表达式在这里就断了，后面还缺东西')
        if tok.kind is Kind.VAR:
            self.i += 1
            return (VAR, tok.text)
        if tok.kind is Kind.CONST:
            self.i += 1
            return (CONST, tok.text == '1')
        if tok.kind is Kind.LPAR:
            self.i += 1
            e = self.p_or()
            self.eat(Kind.RPAR)
            return e
        raise NotationError(f'第 {self.i + 1} 个符号处不该出现 {tok.kind.name}')


def parse(text, allowed_vars=None):
    """解析表达式。allowed_vars 非空时，出现表外的变量直接报错。

    卡变量名很有必要：题目问 F(A,B,C)，答案里冒出个 D 多半是笔误或抄错题，
    此时判"不等价"会让人一头雾水，不如直接说清楚。
    """
    e = _Parser(tokenize(text)).parse()
    if allowed_vars is not None:
        extra = sorted(set(variables(e)) - set(allowed_vars))
        if extra:
            raise NotationError(
                f'出现了题目里没有的变量 {"、".join(extra)}'
                f'（本题变量是 {"、".join(allowed_vars)}）')
    return e


# ---------------------------------------------------------------------------
# 求值与真值表
# ---------------------------------------------------------------------------

def variables(e):
    """按首次出现顺序返回变量名列表。"""
    found = []

    def walk(node):
        op = node[0]
        if op == VAR:
            if node[1] not in found:
                found.append(node[1])
        elif op == CONST:
            pass
        elif op == NOT:
            walk(node[1])
        else:
            walk(node[1])
            walk(node[2])

    walk(e)
    return found


def evaluate(e, env):
    op = e[0]
    if op == VAR:
        return bool(env[e[1]])
    if op == CONST:
        return e[1]
    if op == NOT:
        return not evaluate(e[1], env)
    a = evaluate(e[1], env)
    b = evaluate(e[2], env)
    if op == AND:
        return a and b
    if op == OR:
        return a or b
    if op == XOR:
        return a != b
    raise ValueError(f'未知节点 {op!r}')


def truth_table(e, var_list):
    """返回 2^n 位的位图：第 i 位为 1 表示第 i 个最小项使 e 为真。

    最小项编号约定 var_list[0] 是最高位，跟卡诺图/教材一致。
    用整数存而不是列表，等价判定就退化成一次 == ，n≤16 都快得不用考虑性能。
    """
    n = len(var_list)
    bits = 0
    for i in range(1 << n):
        env = {v: bool((i >> (n - 1 - k)) & 1) for k, v in enumerate(var_list)}
        if evaluate(e, env):
            bits |= 1 << i
    return bits


def equivalent(a, b, var_list):
    return truth_table(a, var_list) == truth_table(b, var_list)


def counterexample(a, b, var_list):
    """找一组让两个表达式取值不同的输入；完全等价时返回 None。

    判错时给出具体反例，比只说一句"不对"有用得多。
    """
    diff = truth_table(a, var_list) ^ truth_table(b, var_list)
    if diff == 0:
        return None
    i = (diff & -diff).bit_length() - 1  # 最低位的那个不同项
    n = len(var_list)
    return {v: int((i >> (n - 1 - k)) & 1) for k, v in enumerate(var_list)}


# ---------------------------------------------------------------------------
# 规模度量：判"最简"要用
# ---------------------------------------------------------------------------

def literal_count(e):
    """变量出现次数。AB + A'C 是 4。"""
    op = e[0]
    if op == VAR:
        return 1
    if op == CONST:
        return 0
    if op == NOT:
        return literal_count(e[1])
    return literal_count(e[1]) + literal_count(e[2])


def term_count(e):
    """顶层或的项数。AB + A'C + D 是 3。

    只在与或式下有意义，判最简前先用 is_sop 卡一道。
    """
    if e[0] == OR:
        return term_count(e[1]) + term_count(e[2])
    return 1


def is_sop(e):
    """是不是与或式（或之下只有与，与之下只有字母）。

    比最简判定先跑：(A+B)(C+D) 按项数只算 1 项、字母数也少，
    不拦住的话会被误判成"比最简还简"。
    """
    op = e[0]
    if op == OR:
        return is_sop(e[1]) and is_sop(e[2])
    return _is_product(e)


def _is_product(e):
    op = e[0]
    if op == AND:
        return _is_product(e[1]) and _is_product(e[2])
    if op == CONST:
        return True
    return op == VAR or (op == NOT and e[1][0] == VAR)


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

_PREC = {OR: 1, XOR: 2, AND: 3, NOT: 4, VAR: 5, CONST: 5}


def _render(e, wrap, prec_of_parent, sym):
    op = e[0]
    if op == VAR:
        return e[1]
    if op == CONST:
        return '1' if e[1] else '0'
    if op == NOT:
        return wrap(_render(e[1], wrap, _PREC[NOT], sym))
    body = sym[op].join(
        _render(x, wrap, _PREC[op], sym) for x in (e[1], e[2]))
    return f'({body})' if _PREC[op] < prec_of_parent else body


def to_ascii(e):
    """渲染成 A'B + AB' 这种 Telegram 里能原样打出来的写法。"""
    return _render(e, lambda s: (s if len(s) == 1 else f'({s})') + "'",
                   0, {AND: '', OR: ' + ', XOR: ' ⊕ '})


def to_latex(e):
    """渲染成带上划线的课本写法，给题目卡片用。"""
    return _render(e, lambda s: r'\overline{' + s + '}',
                   0, {AND: r' \cdot ', OR: ' + ', XOR: r' \oplus '})
