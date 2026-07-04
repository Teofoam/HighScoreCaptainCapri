# -*- coding: utf-8 -*-
"""Telegram Bot API 的小封装：自动处理 429 限流与临时性错误重试。"""
import time

import requests


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token, chat_id):
        self.base = f'https://api.telegram.org/bot{token}'
        self.chat_id = str(chat_id)

    def _request(self, method, *, data=None, files=None, timeout=65, retries=4):
        url = f'{self.base}/{method}'
        last = None
        for attempt in range(retries):
            try:
                resp = requests.post(url, data=data, files=files, timeout=timeout)
            except requests.RequestException as exc:
                last = exc
                time.sleep(3 * (attempt + 1))
                continue
            if resp.status_code == 429:
                retry_after = resp.json().get('parameters', {}).get('retry_after', 5)
                time.sleep(retry_after + 1)
                continue
            if resp.status_code >= 500:
                time.sleep(3 * (attempt + 1))
                continue
            body = resp.json()
            if not body.get('ok'):
                raise TelegramError(f'{method} failed: {resp.text}')
            return body['result']
        raise TelegramError(f'{method} failed after {retries} retries: {last}')

    def send_message(self, text, reply_to=None):
        data = {'chat_id': self.chat_id, 'text': text}
        if reply_to:
            data['reply_to_message_id'] = reply_to
            data['allow_sending_without_reply'] = True
        return self._request('sendMessage', data=data)

    def send_photo(self, photo_path, caption, reply_to=None):
        data = {'chat_id': self.chat_id, 'caption': caption[:1024]}
        if reply_to:
            data['reply_to_message_id'] = reply_to
            data['allow_sending_without_reply'] = True
        with open(photo_path, 'rb') as f:
            return self._request('sendPhoto', data=data, files={'photo': f})

    def get_updates(self, offset=None, timeout=50):
        """长轮询取消息。同一时刻只能有一个消费者，409 表示有别的实例在跑。"""
        data = {'timeout': timeout, 'allowed_updates': '["message"]'}
        if offset is not None:
            data['offset'] = offset
        url = f'{self.base}/getUpdates'
        resp = requests.post(url, data=data, timeout=timeout + 15)
        if resp.status_code == 409:
            return None  # 让调用方稍等重试
        body = resp.json()
        if not body.get('ok'):
            raise TelegramError(f'getUpdates failed: {resp.text}')
        return body['result']
