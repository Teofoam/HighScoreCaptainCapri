# -*- coding: utf-8 -*-
"""答题机器人：长轮询 getUpdates，判定用户提交的答案对不对。

两种提交方式：
  1. 直接“回复”某道题的消息，内容就是答案（推荐）
  2. 发送命令 /answer <题目ID> <答案>

题目有两个来源，判题时按消息里的 ID 自动分流：
  · gid#seed 形式 → 用 capri 的生成器按种子重建原题（不需要数据库）
  · 纯 id 形式    → 老的 problems/*.md 静态题库

由 GitHub Actions 周期性拉起，跑 LISTEN_SECONDS 秒后自然退出；
未处理的消息 Telegram 会保留 24 小时，下次运行会补处理。
"""
import os
import time

import problem_bank
import tg
from capri import generators  # noqa: F401  导入即注册全部生成器
from capri.core import grading, registry, session

HELP_TEXT = (
    '📖 用法：\n'
    '· 直接“回复”某道题的消息，写上你的答案，我来判对错\n'
    '· 或发送 /answer <题目ID> <答案>，例如 /answer sop-simplify#00000007 AB+C\n'
    '· 多空的题用 ; 分隔，按题面给的顺序一次答完\n'
    '· 数值支持分数、pi、科学计数法和单位词头，如 -14/15、2*pi、2e5、2.2k、10μA\n'
    "· 逻辑表达式的非号 '、~、!、/ 和上划线都认，并置即与（AB 就是 A·B）"
)


def resolve(bank, ref):
    """(gid, seed) → 题目对象。生成题现算，静态题查库。找不到返回 None。"""
    if ref is None:
        return None
    gid, seed = ref
    if seed is not None:
        return registry.build(gid, seed)
    return problem_bank.get_problem(bank, gid)


def _judge_task(task, user_text):
    results = grading.grade_task(task, user_text)
    if not results:
        return ('✍️ 本题有 {} 个空，请用 ; 分隔一次答完：\n{}'.format(
            len(task.blanks), ' ; '.join(b.prompt for b in task.blanks)))

    all_ok = all(v.ok for _, v in results)
    if len(results) == 1:
        blank, verdict = results[0]
        if verdict.ok:
            answer = getattr(blank.grader, 'answer_text', None)
            return f'✅ 回答正确！' + (f'（标准答案 {answer}）' if answer else '')
        return f'❌ {verdict.detail or "再想想哦～"}'

    lines = ['🎉 全对！' if all_ok else '❌ 还有没对的：']
    for blank, verdict in results:
        mark = '✅' if verdict.ok else '❌'
        line = f'{mark} {blank.prompt}'
        if verdict.detail:
            line += f' —— {verdict.detail}'
        lines.append(line)
    return '\n'.join(lines)


def judge_reply(item, user_text):
    """统一入口：Task 走多空判定，Problem 走老的 check_answer。"""
    if hasattr(item, 'blanks'):
        return _judge_task(item, user_text)
    verdict = problem_bank.check_answer(item, user_text)
    if verdict is None:
        return f'🤔 题目 {item.id} 暂时没有录入标准答案，无法判题'
    if verdict:
        return f'✅ 回答正确！{item.id} 的答案是 {item.answer}'
    return f'❌ 再想想哦～（题目 {item.id}）'


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
        item = resolve(bank, session.split_ref(pid))
        if item is None:
            bot.send_message(f'😵 找不到题目 {pid}，请核对 ID', reply_to=msg_id)
            return
        bot.send_message(judge_reply(item, user_answer), reply_to=msg_id)
        return

    replied = msg.get('reply_to_message')
    if replied:
        source = (replied.get('caption') or replied.get('text') or '')
        ref = session.decode(source)
        if ref is None:
            bot.send_message('请回复具体某道题的消息来提交答案，或用 /answer <题目ID> <答案>',
                             reply_to=msg_id)
            return
        item = resolve(bank, ref)
        if item is None:
            bot.send_message(f'😵 已经找不到题目 {ref[0]} 了', reply_to=msg_id)
            return
        bot.send_message(judge_reply(item, text), reply_to=msg_id)
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
    print(f'👂 开始监听答案，共 {listen_seconds} 秒，'
          f'静态题库 {len(bank)} 道 + 生成器 {len(registry.all_generators())} 个')

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
