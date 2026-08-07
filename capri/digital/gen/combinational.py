# -*- coding: utf-8 -*-
"""组合逻辑生成器。

MVP 就靠这一个跑通全链路：它不需要 SPICE、不需要电路图、不需要多空，
纯 Python 就能出题+出答案，用来验证"生成 → 渲染 → 推送 → 判题"这条路是通的。
"""
from ...core import registry
from ...core.task import Blank, Task
from .. import minimize
from ..grading import BooleanEquiv

__all__ = ['SopSimplify']

_VARS = ['A', 'B', 'C', 'D']


class SopSimplify:
    """给一组最小项（可含无关项），要求化简成最简与或式。"""

    gid = 'sop-simplify'
    subject = '数电'
    topic = '逻辑代数化简'
    weight = 5

    def generate(self, rng):
        for _ in range(300):
            n = rng.choice([3, 4])
            var_list = _VARS[:n]
            total = 1 << n

            count = rng.randint(max(3, total // 3), max(4, total * 2 // 3))
            minterms = sorted(rng.sample(range(total), count))
            spare = [c for c in range(total) if c not in minterms]
            d_count = rng.randint(0, min(len(spare), max(1, total // 8)))
            dontcares = sorted(rng.sample(spare, d_count)) if d_count else []

            cover = minimize.minimize(set(minterms), set(dontcares), n)
            terms, literals = minimize.cost(cover, n)
            # 太简单（一项）或太啰嗦（五项以上）的都不要，题感不好
            if not (2 <= terms <= 4 and 3 <= literals <= 10):
                continue

            ref = minimize.to_expr(cover, var_list)
            return self._task(rng, n, var_list, minterms, dontcares,
                              ref, (terms, literals))

        raise RuntimeError('sop-simplify 连续 300 次没抽到合适的题，检查筛选条件')

    def _task(self, rng, n, var_list, minterms, dontcares, ref, cost):
        names = ','.join(var_list)
        # \textstyle：display 模式下 \sum 会被放得很大，课本里是正常字号的 Σ
        stem = ['化简下列逻辑函数为**最简与或式**：', '',
                rf'$$F({names}) = \textstyle\sum m({",".join(map(str, minterms))})$$']
        if dontcares:
            stem += ['', '约束条件（无关项）：',
                     rf'$$\textstyle\sum d({",".join(map(str, dontcares))})$$']
        # 例子里只用本题真有的变量，免得看见 D 以为漏抄了条件
        example = f"{var_list[0]}{var_list[1]}' + {''.join(var_list[2:])}"
        stem += ['', f'最小项编号以 ${var_list[0]}$ 为最高位。',
                 f"作答直接写表达式，例如 `{example}`；"
                 "非号用 `'`、`~`、`!`、`/` 或上划线都认。"]

        blank = Blank(
            key='F',
            prompt='最简与或式',
            grader=BooleanEquiv(ref, var_list,
                                require_minimal=True, minimal_cost=cost),
        )
        return Task(
            gid=self.gid,
            seed=0,  # 占位；真正的种子由 registry.build 盖回去
            subject=self.subject,
            topic=self.topic,
            stem='\n'.join(stem),
            blanks=(blank,),
            params={'n': n, 'vars': var_list, 'minterms': minterms,
                    'dontcares': dontcares, 'cost': list(cost)},
        )


registry.register(SopSimplify())
