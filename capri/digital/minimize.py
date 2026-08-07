# -*- coding: utf-8 -*-
"""Quine-McCluskey 化简：求最简与或式，以及它的规模。

判"最简"必须知道真正的最小规模是多少，所以这里要的是精确解而不是近似解：
先求全部质蕴涵项，取出必要项，剩下的按子集规模递增穷举，第一个能全覆盖的
就是项数最少的解，同项数再挑字母数最少的。

自己写而不是拉 sympy：本仓库 Actions 分钟数吃紧，sympy 连 mpmath 几十兆，
而这里只需要 4~5 变量的最小覆盖，穷举快得可以忽略，还能自己定代价函数。

蕴涵项表示成 (value, dashes)：dashes 里为 1 的位表示该变量已被消去，
value 在这些位上恒为 0。变量顺序与 boolean.truth_table 一致 —— var_list[0] 是最高位。
"""
import itertools

from .boolean import AND, CONST, NOT, OR, VAR

__all__ = ['prime_implicants', 'minimize', 'cost', 'to_expr', 'minimal_cost']

# 候选质蕴涵项超过这个数就不穷举了。生成的题目远到不了，纯粹是防呆
_EXHAUSTIVE_LIMIT = 20


def _combine(a, b):
    """两个只差一位的同型蕴涵项合并成一个；不能合并返回 None。"""
    va, da = a
    vb, db = b
    if da != db:
        return None
    diff = va ^ vb
    if diff and not (diff & (diff - 1)):  # 恰好差一个 bit
        return (va & ~diff, da | diff)
    return None


def _covers(imp, m):
    value, dashes = imp
    return (m & ~dashes) == value


def prime_implicants(terms, n):
    """terms 是最小项 ∪ 无关项。逐轮两两合并，合不动的就是质蕴涵项。"""
    current = {(t, 0) for t in terms}
    primes = set()
    while current:
        cur = sorted(current)
        used = set()
        nxt = set()
        for i, a in enumerate(cur):
            for b in cur[i + 1:]:
                merged = _combine(a, b)
                if merged is not None:
                    nxt.add(merged)
                    used.add(a)
                    used.add(b)
        primes |= set(cur) - used
        current = nxt
    return primes


def cost(cover, n):
    """(项数, 字母数)。用元组直接比大小，天然实现"先比项数再比字母数"。"""
    return (len(cover), sum(n - bin(d).count('1') for _, d in cover))


def minimize(minterms, dontcares, n):
    """返回最简与或式的蕴涵项集合（列表）。F 恒为 0 时返回空列表。"""
    minterms = set(minterms)
    dontcares = set(dontcares) - minterms
    if not minterms:
        return []

    primes = sorted(prime_implicants(minterms | dontcares, n))

    # 只被一个质蕴涵项覆盖的最小项 → 那个质蕴涵项必选
    essential = set()
    for m in sorted(minterms):
        hits = [p for p in primes if _covers(p, m)]
        if not hits:  # 理论上不会发生，真发生了说明质蕴涵项算漏了
            raise AssertionError(f'最小项 {m} 没有任何质蕴涵项覆盖')
        if len(hits) == 1:
            essential.add(hits[0])

    rest = sorted(m for m in minterms
                  if not any(_covers(p, m) for p in essential))
    if not rest:
        return sorted(essential)

    candidates = [p for p in primes if p not in essential]
    if len(candidates) > _EXHAUSTIVE_LIMIT:
        return sorted(essential | _greedy(candidates, rest))

    best = None
    for size in range(1, len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            if all(any(_covers(p, m) for p in combo) for m in rest):
                cover = essential | set(combo)
                c = cost(cover, n)
                if best is None or c < best[0]:
                    best = (c, cover)
        if best is not None:
            break  # 项数已最小，同规模里也挑过字母数最少的了
    return sorted(best[1])


def _greedy(candidates, rest):
    """兜底：每次选覆盖剩余最小项最多的那个。不保证最优，但不会挂。"""
    chosen = set()
    remaining = set(rest)
    while remaining:
        pick = max(candidates,
                   key=lambda p: sum(1 for m in remaining if _covers(p, m)))
        chosen.add(pick)
        remaining -= {m for m in remaining if _covers(pick, m)}
        candidates = [p for p in candidates if p != pick]
    return chosen


def to_expr(cover, var_list):
    """蕴涵项集合 → boolean 模块的表达式元组。"""
    n = len(var_list)
    if not cover:
        return (CONST, False)
    terms = []
    for value, dashes in sorted(cover):
        literals = []
        for k, name in enumerate(var_list):
            bit = 1 << (n - 1 - k)
            if dashes & bit:
                continue
            lit = (VAR, name)
            if not value & bit:
                lit = (NOT, lit)
            literals.append(lit)
        if not literals:
            return (CONST, True)  # 全消光了，F 恒为 1
        node = literals[0]
        for lit in literals[1:]:
            node = (AND, node, lit)
        terms.append(node)
    expr = terms[0]
    for t in terms[1:]:
        expr = (OR, expr, t)
    return expr


def minimal_cost(minterms, dontcares, n):
    return cost(minimize(minterms, dontcares, n), n)
