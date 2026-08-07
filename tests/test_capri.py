# -*- coding: utf-8 -*-
"""CapriACD 骨架的自测。裸 assert，不引 pytest。

    python tests/test_capri.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capri import generators  # noqa: F401,E402  导入即注册生成器
from capri.core import grading, quantity, registry, session  # noqa: E402
from capri.core.task import Blank, Task  # noqa: E402
from capri.digital import boolean, minimize  # noqa: E402
from capri.digital.grading import BooleanEquiv  # noqa: E402

VARS2 = ['A', 'B']
VARS3 = ['A', 'B', 'C']
VARS4 = ['A', 'B', 'C', 'D']


# ---------------------------------------------------------------- 记号解析

def test_notation_all_negation_forms():
    """六种非号写法必须解析成同一个东西 —— 这是数电判题的地基。"""
    xor = boolean.parse("A'B + AB'", VARS2)
    for text in ["~A*B + A*~B", "!A B + A !B", "/A·B + A·/B",
                 "A̅B + AB̅", "ĀB + AB̄",
                 "A#B + AB#"]:
        got = boolean.parse(text, VARS2)
        assert boolean.equivalent(got, xor, VARS2), text


def test_notation_juxtaposition_is_and():
    assert boolean.equivalent(boolean.parse('AB', VARS2),
                              boolean.parse('A*B', VARS2), VARS2)
    assert boolean.equivalent(boolean.parse('A(B+C)', VARS3),
                              boolean.parse('AB+AC', VARS3), VARS3)


def test_notation_strips_question_head():
    """用户把题头一起抄进来是常态。"""
    e = boolean.parse('F(A,B,C) = AB + C', VARS3)
    assert boolean.equivalent(e, boolean.parse('AB+C', VARS3), VARS3)


def test_notation_rejects_unknown_variable():
    try:
        boolean.parse('AB + D', VARS3)
    except boolean.NotationError as exc:
        assert 'D' in str(exc)
    else:
        raise AssertionError('用了题目外的变量却没报错')


def test_notation_rejects_garbage():
    for bad in ['', 'A +', "'A", 'A)', '@']:
        try:
            boolean.parse(bad, VARS2)
        except boolean.NotationError:
            pass
        else:
            raise AssertionError(f'{bad!r} 应该报错')


# ---------------------------------------------------------------- 等价判定

def test_xor_forms_equivalent():
    """验收标准之一：A'B+AB' 与 A⊕B 判等价。"""
    a = boolean.parse("A'B + AB'", VARS2)
    b = boolean.parse('A^B', VARS2)
    assert boolean.equivalent(a, b, VARS2)
    assert boolean.counterexample(a, b, VARS2) is None


def test_pos_form_equivalent_to_sop():
    """或与式和与或式只要真值表一致就判对，形式无关。"""
    a = boolean.parse('(A+B)(A+C)', VARS3)
    b = boolean.parse('A + BC', VARS3)
    assert boolean.equivalent(a, b, VARS3)


def test_counterexample_points_at_a_real_row():
    a = boolean.parse('AB', VARS2)
    b = boolean.parse('A+B', VARS2)
    row = boolean.counterexample(a, b, VARS2)
    env = {k: bool(v) for k, v in row.items()}
    assert boolean.evaluate(a, env) != boolean.evaluate(b, env)


def test_is_sop():
    assert boolean.is_sop(boolean.parse("AB + A'C", VARS3))
    assert boolean.is_sop(boolean.parse('A', VARS2))
    assert not boolean.is_sop(boolean.parse('(A+B)(C+D)', VARS4))
    assert not boolean.is_sop(boolean.parse("(AB)'", VARS2))


# ---------------------------------------------------------------- QM 化简

def _check_minimal(minterms, dontcares, n, var_list, want_cost):
    cover = minimize.minimize(set(minterms), set(dontcares), n)
    expr = minimize.to_expr(cover, var_list)
    assert minimize.cost(cover, n) == want_cost, (
        minterms, dontcares, minimize.cost(cover, n), want_cost)
    # 化简结果在所有 care 行上必须和原最小项集合一致
    table = boolean.truth_table(expr, var_list)
    for i in range(1 << n):
        if i in dontcares:
            continue
        assert bool(table >> i & 1) == (i in minterms), (minterms, i)
    return expr


def test_minimize_known_cases():
    _check_minimal([1, 3, 5, 7], [], 3, VARS3, (1, 1))          # F = C
    _check_minimal([0, 1, 2, 3], [], 3, VARS3, (1, 1))          # F = A'
    _check_minimal([1, 2], [], 2, VARS2, (2, 4))                # A'B + AB'
    _check_minimal([1, 2, 3], [], 2, VARS2, (2, 2))             # A + B
    _check_minimal([0, 1, 4, 5], [], 4, VARS4, (1, 2))          # A'C'


def test_minimize_uses_dontcares():
    """无关项必须真的被用上：A'C(2字母) 应被压成 C(1字母)。"""
    _check_minimal([1, 3], [], 3, VARS3, (1, 2))
    _check_minimal([1, 3], [5, 7], 3, VARS3, (1, 1))


def test_minimize_constant_functions():
    assert minimize.minimize(set(), set(), 3) == []
    cover = minimize.minimize(set(range(8)), set(), 3)
    assert minimize.to_expr(cover, VARS3) == ('const', True)


# ---------------------------------------------------------------- 单位解析

def test_quantity_prefixes():
    assert quantity.parse('2.2k').value == 2200.0
    assert quantity.parse('1.5kΩ').value == 1500.0
    assert quantity.parse('1.5kΩ').unit == 'Ω'
    assert abs(quantity.parse('47pF').value - 47e-12) < 1e-24
    assert quantity.parse('47pF').unit == 'F'


def test_quantity_micro_both_codepoints():
    """μ(U+03BC) 和 µ(U+00B5) 是两个不同码位，输入法给哪个都得认。"""
    for text in ['10μA', '10µA', '10uA']:
        q = quantity.parse(text)
        assert abs(q.value - 10e-6) < 1e-18, text
        assert q.unit == 'A'


def test_quantity_milli_vs_mega_is_case_sensitive():
    """差 10^9，错了不会报错只会静默判错，必须钉死。"""
    assert quantity.parse('5M').value == 5e6
    assert quantity.parse('5m').value == 5e-3


def test_quantity_scientific_notation_not_a_prefix():
    assert quantity.parse('2e5').value == 200000.0
    assert quantity.parse('2E5').value == 200000.0


def test_quantity_expressions():
    assert abs(quantity.parse('-14/15').value + 14 / 15) < 1e-12
    assert abs(quantity.parse('-2*pi').value + 6.283185307) < 1e-6
    assert abs(quantity.parse('2π').value - 6.283185307) < 1e-6


def test_quantity_fallback_on_unknown_unit():
    """大物那批老题带 J、N/C 这类单位，旧通道要继续能判。"""
    assert quantity.parse('166 J').value == 166.0


def test_quantity_db_uses_absolute_tolerance():
    q = quantity.parse('-3dB')
    assert q.value == -3.0 and q.unit == 'dB'
    # 相对容差在 0dB 附近会炸，所以这里必须是绝对容差
    assert quantity.close(quantity.Quantity(0.0, 'dB'),
                          quantity.Quantity(0.3, 'dB'))
    assert not quantity.close(quantity.Quantity(0.0, 'dB'),
                              quantity.Quantity(0.8, 'dB'))


def test_quantity_close_rejects_unit_mismatch():
    assert not quantity.close(quantity.Quantity(5, 'V'),
                              quantity.Quantity(5, 'A'))
    assert quantity.close(quantity.Quantity(5, 'V'),
                          quantity.Quantity(5.2, 'V'), rel_tol=0.05)
    assert not quantity.close(quantity.Quantity(5, 'V'),
                              quantity.Quantity(5.6, 'V'), rel_tol=0.05)


def test_format_value():
    assert quantity.format_value(2.23e-5, 'A') == '22.3 μA'
    assert quantity.format_value(1500, 'Ω') == '1.5 kΩ'


# ---------------------------------------------------------------- 判题编排

def _numeric_task():
    return Task(gid='fake', seed=1, subject='模电', topic='测试',
                stem='', blanks=(
                    Blank('x', '第一步', grading.Numeric(10.0)),
                    Blank('y', '第二步',
                          grading.Numeric(lambda ctx: ctx.answered['x'] * 2),
                          depends=('x',)),
                ))


def test_error_carry_forward():
    """第一步错了，第二步按用户自己的错值判 —— 一步失手不连坐。"""
    results = grading.grade_task(_numeric_task(), '3; 6')
    assert [v.ok for _, v in results] == [False, True]

    results = grading.grade_task(_numeric_task(), '10; 20')
    assert [v.ok for _, v in results] == [True, True]

    results = grading.grade_task(_numeric_task(), '3; 99')
    assert [v.ok for _, v in results] == [False, False]


def test_blank_count_mismatch_returns_empty():
    assert grading.grade_task(_numeric_task(), '10') == []


def test_choice_and_setof():
    task = Task(gid='f', seed=1, subject='数电', topic='t', stem='',
                blanks=(Blank('c', '选项', grading.Choice('B')),))
    for text in ['B', 'b', '(B)', '选 B']:
        assert grading.grade_task(task, text)[0][1].ok, text
    assert not grading.grade_task(task, 'C')[0][1].ok

    task = Task(gid='f', seed=1, subject='数电', topic='t', stem='',
                blanks=(Blank('s', '最小项', grading.SetOf([1, 3, 5])),))
    for text in ['1,3,5', '5 3 1', '3、1、5']:
        assert grading.grade_task(task, text)[0][1].ok, text
    assert not grading.grade_task(task, '1,3')[0][1].ok


# ---------------------------------------------------------------- 数电判题器

def test_boolean_equiv_accepts_any_equivalent_form():
    ref = boolean.parse('A + BC', VARS3)
    g = BooleanEquiv(ref, VARS3)
    ctx = grading.GradeContext(task=None)
    for text in ['A + BC', '(A+B)(A+C)', 'A+CB', 'A + B*C']:
        assert g.grade(text, ctx).ok, text


def test_boolean_equiv_reports_counterexample():
    g = BooleanEquiv(boolean.parse('A + B', VARS2), VARS2)
    v = g.grade('AB', grading.GradeContext(task=None))
    assert not v.ok and '不等价' in v.detail


def test_boolean_equiv_minimality():
    """验收标准之三：AB+A'B+AB' 判"对但不最简"。"""
    minterms = {1, 2, 3}
    cover = minimize.minimize(minterms, set(), 2)
    ref = minimize.to_expr(cover, VARS2)
    g = BooleanEquiv(ref, VARS2, require_minimal=True,
                     minimal_cost=minimize.cost(cover, 2))
    ctx = grading.GradeContext(task=None)

    v = g.grade("AB + A'B + AB'", ctx)
    assert not v.ok and '更简' in v.detail
    assert g.grade('A + B', ctx).ok


def test_boolean_equiv_requires_sop_form():
    ref = boolean.parse('A + BC', VARS3)
    g = BooleanEquiv(ref, VARS3, require_minimal=True, minimal_cost=(2, 3))
    v = g.grade('(A+B)(A+C)', grading.GradeContext(task=None))
    assert not v.ok and '与或式' in v.detail


# ---------------------------------------------------------------- 注册表

def test_build_is_deterministic():
    """验收标准之二：同一 (gid, seed) 造两次必须一模一样。

    这条是整个无数据库方案的地基 —— 破了的话 judge 会算出一道
    跟用户看到的完全不同的题。
    """
    assert registry.verify_deterministic('sop-simplify', 12345)
    for seed in (1, 7, 999, 2 ** 31):
        assert registry.verify_deterministic('sop-simplify', seed), seed


def test_build_stamps_the_real_seed():
    task = registry.build('sop-simplify', 0xDEADBEEF)
    assert task.seed == 0xDEADBEEF
    assert task.ref == 'sop-simplify#deadbeef'


def test_build_unknown_gid():
    assert registry.build('nope', 1) is None


def test_generated_task_is_gradeable():
    """随机造一批题，标准答案必须能被自己判对。"""
    for seed in range(40):
        task = registry.build('sop-simplify', seed)
        cover = minimize.minimize(set(task.params['minterms']),
                                  set(task.params['dontcares']),
                                  task.params['n'])
        answer = boolean.to_ascii(minimize.to_expr(cover, task.params['vars']))
        results = grading.grade_task(task, answer)
        assert results and results[0][1].ok, (seed, answer, results[0][1].detail)


def test_draw_daily():
    import random as _random
    tasks = registry.draw_daily(5, _random.Random(42))
    assert len(tasks) == 5
    assert all(t.seed and t.blanks for t in tasks)


# ---------------------------------------------------------------- 会话态

def test_session_roundtrip():
    assert session.decode('🆔 ID: sop-simplify#deadbeef') == (
        'sop-simplify', 0xDEADBEEF)
    assert session.encode('sop-simplify', 0xDEADBEEF) == 'sop-simplify#deadbeef'


def test_session_accepts_legacy_ids():
    """手录的 problems/*.md 那条通道不能断。"""
    assert session.decode('🆔 ID: limits-01') == ('limits-01', None)
    assert session.decode('没有 id 的消息') is None


# ---------------------------------------------------------------- 接驳层

def test_render_view_handles_both_shapes():
    import render
    task = registry.build('sop-simplify', 5)
    subject, topic, ident, body, base = render.view(task)
    assert subject == '数电' and ident == task.ref and body == task.stem

    problems = __import__('problem_bank').load_problems()
    if problems:  # 静态题库还在时顺带验一下老通道没被改坏
        subject, topic, ident, body, base = render.view(problems[0])
        assert ident == problems[0].id and body == problems[0].body


def test_render_filename_is_safe():
    import render
    assert render.safe_name('sop-simplify#0000002a') == 'sop-simplify-0000002a'
    assert render.safe_name('limits-01') == 'limits-01'


def test_caption_carries_the_ref():
    import push
    task = registry.build('sop-simplify', 42)
    caption = push.caption_for(task)
    assert f'ID: {task.ref}' in caption
    assert '数电' in caption
    # caption 是判题时唯一的线索来源，必须能被 decode 回去
    assert session.decode(caption) == ('sop-simplify', 42)


def test_collect_mixes_both_sources():
    import push
    items = push.collect(6, 2)
    assert len(items) == 6
    generated = [i for i in items if hasattr(i, 'blanks')]
    assert len(generated) >= 2


def test_collect_falls_back_to_generators():
    """静态题库空了也得凑够数 —— 老题全 disabled 之后就是这个场景。"""
    import push
    items = push.collect(4, 0)
    assert len(items) == 4


def test_listen_resolves_both_channels():
    import listen
    bank = __import__('problem_bank').load_problems()
    task = listen.resolve(bank, session.decode('ID: sop-simplify#0000002a'))
    assert task is not None and task.seed == 0x2a
    assert listen.resolve(bank, session.split_ref('sop-simplify#0000002a')) is not None
    assert listen.resolve(bank, ('nope-99', None)) is None


def test_listen_judges_a_generated_task():
    import listen
    task = registry.build('sop-simplify', 7)
    cover = minimize.minimize(set(task.params['minterms']),
                              set(task.params['dontcares']), task.params['n'])
    right = boolean.to_ascii(minimize.to_expr(cover, task.params['vars']))
    assert '正确' in listen.judge_reply(task, right)
    assert '❌' in listen.judge_reply(task, 'A')


def _main():
    # Windows 控制台默认 cp1252，中文和 emoji 会直接抛 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    tests = [(k, v) for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f'  ✅ {name}')
        except Exception as exc:  # noqa: BLE001 - 测试跑完再汇总
            failed.append((name, exc))
            print(f'  ❌ {name}: {type(exc).__name__}: {exc}')
    print(f'\n{len(tests) - len(failed)}/{len(tests)} 通过')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(_main())
