# -*- coding: utf-8 -*-
"""把题目渲染成 PNG 卡片：markdown + KaTeX（行内 $..$ 与块级 $$..$$）+ 本地图片。

用 Playwright 驱动无头 Chromium 截图，完整支持中文与 LaTeX 混排。
"""
import base64
import html
import mimetypes
import os
import re

_KATEX_VERSION = '0.16.21'

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@{katex}/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@{katex}/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@{katex}/dist/contrib/auto-render.min.js"></script>
<style>
  body {{ margin: 0; background: #ffffff; }}
  #card {{
    width: 860px; box-sizing: border-box; padding: 34px 40px 26px;
    background: #ffffff; color: #1a1a1a;
    font-family: "Noto Serif CJK SC", "Noto Serif SC", "Source Han Serif SC",
                 "Microsoft YaHei", "PingFang SC", serif;
    font-size: 22px; line-height: 1.75;
  }}
  .head {{
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: 16px; color: #667; border-bottom: 2px solid #e8e8ee;
    padding-bottom: 10px; margin-bottom: 20px;
  }}
  .head .subject {{ font-weight: 700; color: #334; }}
  h1, h2, h3 {{ font-size: 24px; margin: 0 0 14px; }}
  p {{ margin: 0 0 12px; }}
  img {{ max-width: 100%; display: block; margin: 14px auto; }}
  .img-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 14px 0; }}
  .img-grid img {{ margin: 0; width: 100%; }}
  .katex-display {{ margin: 16px 0; }}
  .foot {{
    margin-top: 20px; padding-top: 8px; border-top: 1px dashed #ddd;
    font-size: 14px; color: #99a;
  }}
</style>
</head>
<body>
<div id="card">
  <div class="head"><span class="subject">{subject}</span><span>{topic}</span></div>
  {body}
  <div class="foot">🆔 {pid} · 回复消息提交答案</div>
</div>
<script>
window.__done = false;
document.addEventListener('DOMContentLoaded', async () => {{
  try {{
    if (window.renderMathInElement) {{
      renderMathInElement(document.getElementById('card'), {{
        delimiters: [
          {{left: '$$', right: '$$', display: true}},
          {{left: '$', right: '$', display: false}}
        ],
        throwOnError: false
      }});
    }}
    await document.fonts.ready;
    // 公式太长会撑出卡片右边界，截图时直接被裁掉；量出溢出比例后缩小字号让它老实待在卡片里
    document.querySelectorAll('.katex-display').forEach(el => {{
      const available = el.clientWidth;
      if (available <= 0 || el.scrollWidth <= available) return;
      const scale = Math.max(0.5, (available / el.scrollWidth) * 0.98);
      const baseSize = parseFloat(getComputedStyle(el).fontSize);
      el.style.fontSize = (baseSize * scale) + 'px';
    }});
    await Promise.all(Array.from(document.images).map(img =>
      img.complete ? null : new Promise(res => {{ img.onload = res; img.onerror = res; }})));
  }} catch (e) {{}}
  window.__done = true;
}});
</script>
</body>
</html>"""

_MATH_TOKEN = '⁉KATEX{}⁉'  # 不会出现在正文里的占位符


def _extract_math(text):
    """先把公式抠出来，防止 markdown 转换把 LaTeX 里的符号弄坏。"""
    segments = []

    def stash(match):
        segments.append(match.group(0))
        return _MATH_TOKEN.format(len(segments) - 1)

    text = re.sub(r'\$\$.*?\$\$', stash, text, flags=re.DOTALL)
    text = re.sub(r'\$[^$\n]+\$', stash, text)
    return text, segments


def markdown_to_html(body, base_dir):
    text, math_segments = _extract_math(body)
    text = html.escape(text, quote=False)

    def img_tag(match):
        src = match.group(2)
        if not src.startswith(('http://', 'https://')):
            # set_content 的页面是 about:blank 源，加载不了 file://，
            # 所以本地图片一律内联成 data URI
            path = os.path.normpath(os.path.join(base_dir, src))
            if not os.path.exists(path):
                print(f'⚠️ 找不到题图 {path}')
                return ''
            mime = mimetypes.guess_type(path)[0] or 'image/png'
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('ascii')
            src = f'data:{mime};base64,{data}'
        return '<img alt="{}" src="{}">'.format(html.escape(match.group(1)), src)

    text = re.sub(r'!\[(.*?)\]\((.*?)\)', img_tag, text)
    text = re.sub(r'^(#{1,3})\s*(.+)$',
                  lambda m: '<h{0}>{1}</h{0}>'.format(len(m.group(1)), m.group(2)),
                  text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    blocks = []
    for para in re.split(r'\n\s*\n', text):
        para = para.strip()
        if not para:
            continue
        imgs = re.findall(r'<img [^>]*>', para)
        if imgs and not re.sub(r'<img [^>]*>|\s', '', para):
            # 整段都是图片：多张（如选择题的四个选项图）排成两列网格
            if len(imgs) >= 2:
                blocks.append('<div class="img-grid">{}</div>'.format(''.join(imgs)))
            else:
                blocks.append(para)
        elif para.startswith('<h'):
            blocks.append(para)
        else:
            blocks.append('<p>{}</p>'.format(para.replace('\n', '<br>')))
    result = '\n'.join(blocks)

    for i, seg in enumerate(math_segments):
        result = result.replace(_MATH_TOKEN.format(i), html.escape(seg, quote=False))
    return result


def build_page(problem):
    return _PAGE_TEMPLATE.format(
        katex=_KATEX_VERSION,
        subject=html.escape(problem.subject),
        topic=html.escape(problem.topic),
        pid=html.escape(problem.id),
        body=markdown_to_html(problem.body, os.path.dirname(problem.path)),
    )


def render_problems(problems, out_dir):
    """渲染一批题目，返回 {problem_id: png_path}。共用一个浏览器实例。"""
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 940, 'height': 600},
                                device_scale_factor=2)
        for problem in problems:
            page.set_content(build_page(problem), wait_until='load')
            page.wait_for_function('window.__done === true', timeout=30000)
            if not page.evaluate('!!window.renderMathInElement'):
                print(f'⚠️ KaTeX 未能加载，{problem.id} 将以纯文本渲染')
            path = os.path.join(out_dir, problem.id + '.png')
            page.locator('#card').screenshot(path=path)
            results[problem.id] = path
        browser.close()
    return results
