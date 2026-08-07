# -*- coding: utf-8 -*-
"""生成器注册表与确定性重建。

build(gid, seed) 是整个无数据库方案的地基：判题进程不需要知道推题进程
算过什么，拿 caption 里的 gid#seed 重跑一遍就得到同一道题。

代价是生成器必须严格只从传入的 rng 取随机 —— 不许碰 random 全局函数、
不许读时间、不许遍历 set 后依赖顺序。破了这条，judge 会算出一道
跟用户看到的完全不同的题，而且报错时长得像判题逻辑写错了，极难查。
verify_deterministic() 就是拿来在测试里守住这条的。
"""
import dataclasses
import random

__all__ = ['register', 'get', 'all_generators', 'build', 'draw_daily',
           'fingerprint', 'verify_deterministic']

_REGISTRY = {}


def register(gen):
    if gen.gid in _REGISTRY:
        raise ValueError(f'生成器 id 撞了：{gen.gid}')
    _REGISTRY[gen.gid] = gen
    return gen


def get(gid):
    return _REGISTRY.get(gid)


def all_generators():
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def build(gid, seed):
    """按 (gid, seed) 重建题目。gid 不存在时返回 None。

    种子由这里盖回 Task —— 生成器只拿到 rng，不知道自己是被哪个种子播的，
    让它自己填 seed 一定会填错，而错了要到判题时才暴露。
    """
    gen = _REGISTRY.get(gid)
    if gen is None:
        return None
    return dataclasses.replace(gen.generate(random.Random(seed)), seed=seed)


def draw_daily(count, rng=None, subjects=None):
    """抽 count 道题。同一生成器可以出现多次（种子不同即不同题），
    但先把不同生成器铺开，保证题型多样。题库里有的学科至少各占一道。
    """
    rng = rng or random.Random()
    pool = [g for g in all_generators()
            if subjects is None or g.subject in subjects]
    if not pool:
        return []

    picked = []
    remaining = list(pool)
    while len(picked) < count:
        if not remaining:
            remaining = list(pool)  # 生成器用完一轮，再来一轮
        weights = [max(getattr(g, 'weight', 1), 1) for g in remaining]
        gen = rng.choices(remaining, weights=weights, k=1)[0]
        remaining.remove(gen)
        picked.append(gen)

    # 保证每个学科至少一道：拿题最多的学科匀一个名额出来
    for subject in sorted({g.subject for g in pool}):
        if any(g.subject == subject for g in picked):
            continue
        candidates = [g for g in pool if g.subject == subject]
        if not candidates:
            continue
        counts = {}
        for g in picked:
            counts[g.subject] = counts.get(g.subject, 0) + 1
        dominant = max(sorted(counts), key=counts.get)
        victim = next(g for g in reversed(picked) if g.subject == dominant)
        picked.remove(victim)
        weights = [max(getattr(g, 'weight', 1), 1) for g in candidates]
        picked.append(rng.choices(candidates, weights=weights, k=1)[0])

    rng.shuffle(picked)
    # 一律走 build()，题目才会带上能复现自己的种子
    return [build(gen.gid, rng.getrandbits(32)) for gen in picked]


def _canon(value):
    """把参数值转成顺序稳定的字符串，集合/字典的迭代顺序不计入指纹。"""
    if isinstance(value, dict):
        return '{' + ','.join(f'{k!r}:{_canon(v)}'
                              for k, v in sorted(value.items(), key=repr)) + '}'
    if isinstance(value, (set, frozenset)):
        return '{' + ','.join(sorted(_canon(v) for v in value)) + '}'
    if isinstance(value, (list, tuple)):
        return '[' + ','.join(_canon(v) for v in value) + ']'
    return repr(value)


def fingerprint(task):
    """题目的稳定指纹。判题器对象没有 __eq__，所以只比可序列化的部分。"""
    parts = [task.gid, str(task.seed), task.subject, task.topic, task.stem,
             _canon(task.params)]
    parts += [f'{b.key}|{b.prompt}|{b.unit}' for b in task.blanks]
    return ''.join(parts)


def verify_deterministic(gid, seed):
    """同一 (gid, seed) 连造两次必须一模一样。"""
    a, b = build(gid, seed), build(gid, seed)
    if a is None or b is None:
        raise ValueError(f'找不到生成器 {gid}')
    return fingerprint(a) == fingerprint(b)
