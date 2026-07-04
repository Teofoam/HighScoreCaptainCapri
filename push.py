# -*- coding: utf-8 -*-
"""每日推题：按权重抽取 DAILY_COUNT 道题（默认 10，覆盖全部学科），
渲染成 LaTeX 图片卡片后逐条推送到 Telegram。

用法：
    python push.py            # 正式推送（需要 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID）
    python push.py --dry-run  # 只渲染不推送，PNG 输出到 out/ 目录
"""
import datetime
import os
import sys
import time

import problem_bank
import render
import tg

SUBJECT_EMOJI = {'高数': '📘', '大物': '⚛️'}


def caption_for(problem):
    emoji = SUBJECT_EMOJI.get(problem.subject, '📚')
    lines = [f'{emoji} {problem.subject} · {problem.topic}'.rstrip(' ·'),
             f'🆔 ID: {problem.id}',
             '💬 回复本条消息提交答案']
    return '\n'.join(lines)


def main():
    dry_run = '--dry-run' in sys.argv
    count = int(os.environ.get('DAILY_COUNT', '10'))

    bank = problem_bank.load_problems()
    if not bank:
        print('❌ problems/ 目录下没有题目')
        sys.exit(1)
    for p in bank:
        if not p.answer:
            print(f'⚠️ {p.id} 缺少 answer 字段，将无法判题')

    picked = problem_bank.select_daily(bank, count)
    if len(picked) < count:
        print(f'⚠️ 题库只有 {len(bank)} 道题，今天推送 {len(picked)} 道')

    out_dir = os.environ.get('RENDER_OUT', 'out')
    print(f'🎨 渲染 {len(picked)} 道题目…')
    images = render.render_problems(picked, out_dir)

    if dry_run:
        for pid, path in images.items():
            print(f'   {pid} -> {path}')
        print('✅ dry-run 完成，未推送')
        return

    bot = tg.Telegram(os.environ['TELEGRAM_BOT_TOKEN'],
                      os.environ['TELEGRAM_CHAT_ID'])

    by_subject = {}
    for p in picked:
        by_subject[p.subject] = by_subject.get(p.subject, 0) + 1
    summary = ' · '.join(f'{s} {n}' for s, n in sorted(by_subject.items()))
    today = datetime.date.today().isoformat()
    bot.send_message(f'🌟 每日一练 · {today}\n'
                     f'今天共 {len(picked)} 道题：{summary}\n'
                     f'直接“回复”某道题的消息即可提交答案，'
                     f'也可以用 /answer <题目ID> <答案>')

    failures = []
    for problem in picked:
        try:
            bot.send_photo(images[problem.id], caption_for(problem))
            print(f'✅ 已推送 {problem.id}')
        except Exception as exc:  # noqa: BLE001 - 单题失败不阻塞其余题目
            failures.append(problem.id)
            print(f'❌ 推送 {problem.id} 失败：{exc}')
        time.sleep(2)  # 控制发送频率，避免触发 Telegram 限流

    if failures:
        print(f'❌ 共 {len(failures)} 道题推送失败：{", ".join(failures)}')
        sys.exit(1)
    print(f'🎉 全部 {len(picked)} 道题推送完成')


if __name__ == '__main__':
    main()
