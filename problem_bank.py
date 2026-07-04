# -*- coding: utf-8 -*-
"""题库核心：读取 problems/*.md、按权重抽题、判答案。

题目文件格式（frontmatter + markdown 正文）：
---
subject: 高数            # 或 大物
topic: Limits
weight: 5                # 抽中概率权重，默认 1
answer: -1/6             # 标准答案，支持数字/分数/pi 等表达式，也可以是文本
tolerance: 0.01          # 数值判题的相对误差，默认 0.01
---
正文支持 $inline$ 与 $$block$$ LaTeX，以及 ![图](./images/xxx.png)
"""
import ast
import glob
import math
import os
import random
import re

DEFAULT_TOLERANCE = 0.01

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n?', re.DOTALL)
_IMG_RE = re.compile(r'!\[.*?\]\((.*?)\)')


class Problem:
    def __init__(self, pid, path, meta, body):
        self.id = pid
        self.path = path
        self.subject = meta.get('subject', '未分类')
        self.topic = meta.get('topic', '')
        self.weight = _to_int(meta.get('weight'), 1)
        self.answer = meta.get('answer')  # None 表示暂无标准答案
        self.tolerance = _to_float(meta.get('tolerance'), DEFAULT_TOLERANCE)
        self.body = body
        base = os.path.dirname(path)
        self.image_paths = [
            os.path.normpath(os.path.join(base, rel))
            for rel in _IMG_RE.findall(body)
            if not rel.startswith(('http://', 'https://'))
        ]


def _to_int(value, default):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _to_float(value, default):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_frontmatter(content):
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content.strip()
    meta = {}
    for line in m.group(1).splitlines():
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        meta[key.strip().lower()] = value.strip().strip('"\'')
    return meta, content[m.end():].strip()


def load_problems(root='problems'):
    problems = []
    for path in sorted(glob.glob(os.path.join(root, '*.md'))):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        meta, body = _parse_frontmatter(content)
        pid = os.path.splitext(os.path.basename(path))[0]
        problems.append(Problem(pid, path, meta, body))
    return problems


def get_problem(problems, pid):
    for p in problems:
        if p.id == pid:
            return p
    return None


def select_daily(problems, count):
    """按权重不放回抽取 count 道题；题库中出现过的学科至少各占一题。"""
    count = min(count, len(problems))
    remaining = list(problems)
    picked = []
    while len(picked) < count:
        weights = [max(p.weight, 1) for p in remaining]
        choice = random.choices(remaining, weights=weights, k=1)[0]
        remaining.remove(choice)
        picked.append(choice)

    # 保证每个学科至少一题：用超额学科的题换入缺失学科的题
    for subject in {p.subject for p in problems}:
        if any(p.subject == subject for p in picked):
            continue
        pool = [p for p in remaining if p.subject == subject]
        if not pool:
            continue
        counts = {}
        for p in picked:
            counts[p.subject] = counts.get(p.subject, 0) + 1
        dominant = max(counts, key=counts.get)
        victim = next(p for p in reversed(picked) if p.subject == dominant)
        picked.remove(victim)
        weights = [max(p.weight, 1) for p in pool]
        picked.append(random.choices(pool, weights=weights, k=1)[0])

    random.shuffle(picked)
    return picked


# ---------------------------------------------------------------------------
# 判题：把 "166 J" / "-2π" / "pi^2/4" / "-14/15" / "2×10^5" 都规约成数值再比较
# ---------------------------------------------------------------------------

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_NAMES = {'pi': math.pi, 'e': math.e}
_ALLOWED_FUNCS = {
    'sqrt': math.sqrt, 'ln': math.log, 'log': math.log10,
    'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
    'exp': math.exp, 'abs': abs,
}

_FULLWIDTH = str.maketrans('０１２３４５６７８９．－＋（）／＊，', '0123456789.-+()/*,')
_SUPERSCRIPTS = {'²': '**2', '³': '**3'}


def _safe_eval(expr):
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            return a ** b
        if isinstance(node, ast.Name) and node.id in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _ALLOWED_FUNCS and len(node.args) == 1
                and not node.keywords):
            return _ALLOWED_FUNCS[node.func.id](ev(node.args[0]))
        raise ValueError('unsupported expression')

    return ev(ast.parse(expr, mode='eval'))


def _normalize(text):
    s = str(text).strip().translate(_FULLWIDTH)
    for k, v in _SUPERSCRIPTS.items():
        s = s.replace(k, v)
    s = s.replace('π', 'pi').replace('Π', 'pi')
    s = s.replace('×', '*').replace('·', '*').replace('÷', '/').replace('−', '-')
    s = re.sub(r'√\s*\(', 'sqrt(', s)
    s = re.sub(r'√\s*(\d+(?:\.\d+)?|pi)', r'sqrt(\1)', s)
    s = s.replace('^', '**')
    s = re.sub(r'\s+', '', s)
    # 隐式乘法：2pi -> 2*pi, 3sqrt(2) -> 3*sqrt(2), 2(3+1) -> 2*(3+1)
    return re.sub(r'(\d)(pi\b|sqrt|\()', r'\1*\2', s)


def parse_number(text):
    """尽力把用户输入解析成数值；解析不了返回 None。"""
    s = _normalize(text)
    if not s:
        return None
    try:
        return _safe_eval(s)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
        pass
    # 兜底：忽略单位等尾巴，抽出第一个数字（如 "166J"、"2e5N/C"）
    m = re.search(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def check_answer(problem, user_text):
    """返回 True/False；题目没有标准答案时返回 None。"""
    if not problem.answer:
        return None
    expected = parse_number(problem.answer)
    given = parse_number(user_text)
    if expected is not None and given is not None:
        tol = max(problem.tolerance, 0.0)
        return abs(given - expected) <= max(1e-9, tol * abs(expected))
    # 文本答案：忽略大小写与空白直接比对
    return _normalize(user_text).casefold() == _normalize(problem.answer).casefold()
