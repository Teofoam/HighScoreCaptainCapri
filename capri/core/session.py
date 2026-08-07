# -*- coding: utf-8 -*-
"""会话态编解码。

整个方案不用数据库：推题进程把 "生成器id#种子" 写进 Telegram 消息的 caption，
判题进程读回来重跑一遍生成器，就能得到逐比特相同的题目和答案。
消息线程本身就是存储。

老格式 "ID: limits-01" 仍然认得 —— 手录的 problems/*.md 那条通道要继续能判题。
"""
import re

__all__ = ['encode', 'decode', 'split_ref', 'REF_RE']

# 新格式 gid#seed（seed 是十六进制），老格式就是个纯 id
REF_RE = re.compile(r'ID[:：]\s*([A-Za-z0-9_-]+)(?:#([0-9a-fA-F]{1,16}))?')
_RAW_RE = re.compile(r'^([A-Za-z0-9_-]+)(?:#([0-9a-fA-F]{1,16}))?$')


def encode(gid, seed):
    return f'{gid}#{seed:08x}'


def decode(text):
    """从消息文本里抠出 (gid, seed)。seed 为 None 表示是老的静态题。

    认不出返回 None。
    """
    if not text:
        return None
    m = REF_RE.search(str(text))
    if not m:
        return None
    return (m.group(1), int(m.group(2), 16) if m.group(2) else None)


def split_ref(raw):
    """解析用户在 /answer 里手打的 id，如 sop-simplify#00000007 或 limits-01。"""
    m = _RAW_RE.match(str(raw).strip())
    if not m:
        return None
    return (m.group(1), int(m.group(2), 16) if m.group(2) else None)
