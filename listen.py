# -*- coding: utf-8 -*-
"""答题机器人：长轮询 getUpdates，判定用户提交的答案对不对。

两种提交方式：
  1. 直接“回复”某道题的消息，内容就是答案（推荐）
  2. 发送命令 /answer <题目ID> <答案>

由 GitHub Actions 周期性拉起，跑 LISTEN_SECONDS 秒后自然退出；
未处理的消息 Telegram 会保留 24 小时，下次运行会补处理。
"""
import os
import re
import time

import problem_bank
import tg

ID_TAG_RE = re.compile(r'ID[:：]\s*([A-Za-z0-9_-]+)')

HELP_TEXT = (
    '📖 用法：\n'
    '· 直接“回复”某道题的消息，写上你的答案，我来判对错\n'
    '· 或发送 /answer <题目ID> <答案>，例如 /answer thermodynamics-01 166\n'
    '· 答案支持分数、pi、科学计数法等写法，如 -14/15、-2*pi、2e5、166 J'
)


def judge_reply(problem, verdict):
    if verdict is None:
        return f'🤔 题目 {problem.id} 暂时没有录入标准答案，无法判题'
    if verdict:
        return f'✅ 回答正确！{problem.id} 的答案是 {problem.answer}'
    return f'❌ 再想想哦～（题目 {problem.id}）'


def handle_message(bot, bank, msg):
    if str(msg.get('chat', {}).get('id')) != bot.chat_id:
        return
    text = (msg.get('text') or '').strip()
    if not text:
        return
    msg_id = msg['message_id']

    command = text.split()[0].split('@')[0].lower()
    if command in ('/start', '/help'):
        bot.send_message(HELP_TEXT, reply_to=msg_id)
        return

    if command == '/answer':
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            bot.send_message('用法：/answer <题目ID> <答案>', reply_to=msg_id)
            return
        pid, user_answer = parts[1], parts[2]
        problem = problem_bank.get_problem(bank, pid)
        if problem is None:
            bot.send_message(f'😵 找不到题目 {pid}，请核对 ID', reply_to=msg_id)
            return
        bot.send_message(judge_reply(problem, problem_bank.check_answer(problem, user_answer)),
                         reply_to=msg_id)
        return

    replied = msg.get('reply_to_message')
    if replied:
        source = (replied.get('caption') or replied.get('text') or '')
        m = ID_TAG_RE.search(source)
        if not m:
            bot.send_message('请回复具体某道题的消息来提交答案，或用 /answer <题目ID> <答案>',
                             reply_to=msg_id)
            return
        problem = problem_bank.get_problem(bank, m.group(1))
        if problem is None:
            bot.send_message(f'😵 题库里已经找不到题目 {m.group(1)} 了', reply_to=msg_id)
            return
        bot.send_message(judge_reply(problem, problem_bank.check_answer(problem, text)),
                         reply_to=msg_id)
        return

    # 普通消息：提示用法（这是个单一用途的推题频道，不会误伤闲聊场景）
    bot.send_message(HELP_TEXT, reply_to=msg_id)


def main():
    bot = tg.Telegram(os.environ['TELEGRAM_BOT_TOKEN'],
                      os.environ['TELEGRAM_CHAT_ID'])
    bank = problem_bank.load_problems()
    listen_seconds = int(os.environ.get('LISTEN_SECONDS', '3300'))
    deadline = time.monotonic() + listen_seconds
    offset = None
    print(f'👂 开始监听答案，共 {listen_seconds} 秒，题库 {len(bank)} 道题')

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        poll = max(1, min(50, int(remaining)))
        try:
            updates = bot.get_updates(offset=offset, timeout=poll)
        except Exception as exc:  # noqa: BLE001 - 网络抖动等，稍后重试
            print(f'⚠️ getUpdates 出错：{exc}')
            time.sleep(5)
            continue
        if updates is None:  # 409：有别的实例在轮询（新旧 Action 交接）
            print('⚠️ 检测到并发轮询（409），等待接管…')
            time.sleep(10)
            continue
        for update in updates:
            offset = update['update_id'] + 1
            msg = update.get('message')
            if not msg:
                continue
            try:
                handle_message(bot, bank, msg)
            except Exception as exc:  # noqa: BLE001 - 单条消息失败不影响其他
                print(f'⚠️ 处理消息失败：{exc}')

    # 确认最后一批 update，避免下次重复处理
    if offset is not None:
        try:
            bot.get_updates(offset=offset, timeout=0)
        except Exception:  # noqa: BLE001
            pass
    print('👋 本轮监听结束')


if __name__ == '__main__':
    main()
