# -*- coding: utf-8 -*-
"""每日推题：从两条通道取题，渲染成 LaTeX 图片卡片后逐条推送到 Telegram。

两条通道并行，不是二选一：
  · 生成器（capri/）—— 参数随机，题量无上限，标准答案是算出来的
  · problems/*.md  —— 手录，用来放生成器写不出来的题（看图判断那类）

用法：
    python push.py            # 正式推送（需要 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID）
    python push.py --dry-run  # 只渲染不推送，PNG 输出到 out/

环境变量：
    DAILY_COUNT       今天总共推几道，默认 10
    GENERATED_COUNT   其中几道来自生成器，默认 6；静态题不够时会自动多生成补齐
"""
import datetime
import os
import random
import sys
import time

import problem_bank
import render
import tg
from capri import generators  # noqa: F401  导入即注册全部生成器
from capri.core import registry

SUBJECT_EMOJI = {'高数': '📘', '大物': '⚛️', '模电': '🔌', '数电': '🔢'}


def caption_for(item):
    subject, topic, ident, _, _ = render.view(item)
    emoji = SUBJECT_EMOJI.get(subject, '📚')
    lines = [f'{emoji} {subject} · {topic}'.rstrip(' ·'),
             f'🆔 ID: {ident}',
             '💬 回复本条消息提交答案']
    blanks = getattr(item, 'blanks', ())
    if len(blanks) > 1:
        lines.insert(2, '✍️ 本题 {} 空，用 ; 分隔：{}'.format(
            len(blanks), ' ; '.join(b.prompt for b in blanks)))
    return '\n'.join(lines)


def collect(count, generated_count):
    """凑齐今天要推的题。返回列表，已打乱顺序。"""
    generated_count = max(0, min(generated_count, count))
    items = registry.draw_daily(generated_count) if generated_count else []

    bank = problem_bank.load_problems()
    for p in bank:
        if not p.answer:
            print(f'⚠️ {p.id} 缺少 answer 字段，将无法判题')

    want_static = count - len(items)
    if want_static > 0:
        items += problem_bank.select_daily(bank, want_static)

    # 静态题库不够（或已全部 disabled）就多生成几道补齐
    shortfall = count - len(items)
    if shortfall > 0:
        items += registry.draw_daily(shortfall)

    random.shuffle(items)
    return items


def main():
    dry_run = '--dry-run' in sys.argv
    count = int(os.environ.get('DAILY_COUNT', '10'))
    generated_count = int(os.environ.get('GENERATED_COUNT', '6'))

    picked = collect(count, generated_count)
    if not picked:
        print('❌ 一道题也没凑出来：problems/ 是空的，生成器也没注册上')
        sys.exit(1)
    if len(picked) < count:
        print(f'⚠️ 只凑出 {len(picked)} 道，少于设定的 {count} 道')

    out_dir = os.environ.get('RENDER_OUT', 'out')
    print(f'🎨 渲染 {len(picked)} 道题目…')
    images = render.render_problems(picked, out_dir)

    if dry_run:
        for ident, path in images.items():
            print(f'   {ident} -> {path}')
        print('✅ dry-run 完成，未推送')
        return

    bot = tg.Telegram(os.environ['TELEGRAM_BOT_TOKEN'],
                      os.environ['TELEGRAM_CHAT_ID'])

    by_subject = {}
    for item in picked:
        subject = render.view(item)[0]
        by_subject[subject] = by_subject.get(subject, 0) + 1
    summary = ' · '.join(f'{s} {n}' for s, n in sorted(by_subject.items()))
    today = datetime.date.today().isoformat()
    bot.send_message(f'🌟 每日一练 · {today}\n'
                     f'今天共 {len(picked)} 道题：{summary}\n'
                     f'直接“回复”某道题的消息即可提交答案，'
                     f'也可以用 /answer <题目ID> <答案>')

    failures = []
    for item in picked:
        ident = render.view(item)[2]
        try:
            bot.send_photo(images[ident], caption_for(item))
            print(f'✅ 已推送 {ident}')
        except Exception as exc:  # noqa: BLE001 - 单题失败不阻塞其余题目
            failures.append(ident)
            print(f'❌ 推送 {ident} 失败：{exc}')
        time.sleep(2)  # 控制发送频率，避免触发 Telegram 限流

    if failures:
        print(f'❌ 共 {len(failures)} 道题推送失败：{", ".join(failures)}')
        sys.exit(1)
    print(f'🎉 全部 {len(picked)} 道题推送完成')


if __name__ == '__main__':
    main()
