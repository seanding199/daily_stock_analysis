# -*- coding: utf-8 -*-
"""
所有通知渠道实现

每个渠道只需实现 is_configured() 和 _do_send()。
公共逻辑（分段、HTTP、错误处理）由 BaseChannel 提供。
"""

import hashlib
import hmac
import logging
import re
import smtplib
import time
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Dict, Any, Optional, List

import requests

from src.channels.base import BaseChannel

logger = logging.getLogger(__name__)

# SMTP 服务器自动识别配置
SMTP_CONFIGS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},
}


class WeChatChannel(BaseChannel):
    """企业微信 Webhook"""

    name = "企业微信"
    max_bytes = 4000
    chunk_delay = 2.5

    def __init__(self, webhook_url: str = None, msg_type: str = 'markdown',
                 max_bytes_override: int = None):
        self._url = webhook_url
        self._msg_type = msg_type
        if max_bytes_override:
            self.max_bytes = max_bytes_override
        if msg_type == 'text':
            self.max_bytes = min(self.max_bytes, 2048)

    def is_configured(self) -> bool:
        return bool(self._url)

    def _do_send(self, content: str) -> bool:
        payload = {
            "msgtype": self._msg_type,
            self._msg_type: {"content": self.truncate_to_bytes(content, self.max_bytes)}
        }
        resp = self._post_json(self._url, payload)
        return self._check_response(resp, self.name)


class FeishuChannel(BaseChannel):
    """飞书 Webhook"""

    name = "飞书"
    max_bytes = 20000
    chunk_delay = 1.0

    def __init__(self, webhook_url: str = None, max_bytes_override: int = None):
        self._url = webhook_url
        if max_bytes_override:
            self.max_bytes = max_bytes_override

    def is_configured(self) -> bool:
        return bool(self._url)

    def _do_send(self, content: str) -> bool:
        try:
            from src.formatters import format_feishu_markdown
            formatted = format_feishu_markdown(content)
        except Exception:
            formatted = content

        # 尝试富文本卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": formatted}}],
                "header": {"title": {"content": "A股分析报告", "tag": "plain_text"}}
            }
        }
        resp = self._post_json(self._url, payload)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code', data.get('StatusCode', -1)) == 0:
                return True
            # 卡片失败，回退纯文本
            logger.debug(f"[飞书] 卡片发送失败，回退文本模式")

        payload = {"msg_type": "text", "content": {"text": content}}
        resp = self._post_json(self._url, payload)
        return self._check_response(resp, self.name, ok_key='code')


class TelegramChannel(BaseChannel):
    """Telegram Bot"""

    name = "Telegram"
    max_bytes = 4096  # Telegram 按字符计
    chunk_delay = 0.5

    def __init__(self, bot_token: str = None, chat_id: str = None,
                 message_thread_id: str = None):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._thread_id = message_thread_id

    def is_configured(self) -> bool:
        return bool(self._bot_token and self._chat_id)

    def _do_send(self, content: str) -> bool:
        # 转换 Markdown 为 Telegram 格式
        text = self._convert_markdown(content)
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text[:4096],
            "parse_mode": "Markdown",
        }
        if self._thread_id:
            payload["message_thread_id"] = int(self._thread_id)

        resp = self._post_json(url, payload, timeout=30)
        if resp.status_code == 200 and resp.json().get('ok'):
            return True

        # Markdown 失败则回退纯文本
        payload["text"] = self.markdown_to_plain(content)[:4096]
        payload.pop("parse_mode", None)
        resp = self._post_json(url, payload, timeout=30)
        return resp.status_code == 200 and resp.json().get('ok', False)

    @staticmethod
    def _convert_markdown(text: str) -> str:
        """转换为 Telegram Markdown"""
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = text.replace('---', '────────')
        return text


class EmailChannel(BaseChannel):
    """邮件 SMTP"""

    name = "邮件"
    max_bytes = 999999  # 邮件无长度限制

    def __init__(self, sender: str = None, password: str = None,
                 receivers: List[str] = None, sender_name: str = 'Stock分析助手'):
        self._sender = sender
        self._password = password
        self._receivers = receivers or ([sender] if sender else [])
        self._sender_name = sender_name

    def is_configured(self) -> bool:
        return bool(self._sender and self._password)

    def _do_send(self, content: str) -> bool:
        smtp_cfg = self._detect_smtp()
        if not smtp_cfg:
            logger.error(f"[邮件] 无法识别 SMTP 配置: {self._sender}")
            return False

        # 构建邮件
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header('A股分析日报', 'utf-8')
        msg['From'] = formataddr((self._sender_name, self._sender))
        msg['To'] = ', '.join(self._receivers)
        msg.attach(MIMEText(content, 'plain', 'utf-8'))
        msg.attach(MIMEText(self.markdown_to_html(content), 'html', 'utf-8'))

        try:
            if smtp_cfg['ssl']:
                server = smtplib.SMTP_SSL(smtp_cfg['server'], smtp_cfg['port'], timeout=30)
            else:
                server = smtplib.SMTP(smtp_cfg['server'], smtp_cfg['port'], timeout=30)
                server.starttls()
            server.login(self._sender, self._password)
            server.sendmail(self._sender, self._receivers, msg.as_string())
            server.quit()
            logger.info(f"[邮件] 发送成功 -> {self._receivers}")
            return True
        except Exception as e:
            logger.error(f"[邮件] 发送失败: {e}")
            return False

    def _detect_smtp(self) -> Optional[Dict]:
        if not self._sender:
            return None
        domain = self._sender.split('@')[-1].lower()
        return SMTP_CONFIGS.get(domain)


class PushoverChannel(BaseChannel):
    """Pushover 推送"""

    name = "Pushover"
    max_bytes = 1024
    chunk_delay = 1.0

    def __init__(self, user_key: str = None, api_token: str = None):
        self._user_key = user_key
        self._api_token = api_token

    def is_configured(self) -> bool:
        return bool(self._user_key and self._api_token)

    def _do_send(self, content: str) -> bool:
        plain = self.markdown_to_plain(content)[:1024]
        payload = {
            "token": self._api_token,
            "user": self._user_key,
            "title": "A股分析报告",
            "message": plain,
        }
        resp = requests.post("https://api.pushover.net/1/messages.json",
                             data=payload, timeout=10)
        return resp.status_code == 200 and resp.json().get('status') == 1


class PushPlusChannel(BaseChannel):
    """PushPlus 推送"""

    name = "PushPlus"
    max_bytes = 10000

    def __init__(self, token: str = None):
        self._token = token

    def is_configured(self) -> bool:
        return bool(self._token)

    def _do_send(self, content: str) -> bool:
        payload = {
            "token": self._token,
            "title": "A股分析报告",
            "content": content,
            "template": "markdown",
        }
        resp = self._post_json("http://www.pushplus.plus/send", payload)
        return resp.status_code == 200 and resp.json().get('code') == 200


class ServerChan3Channel(BaseChannel):
    """Server酱3 推送"""

    name = "Server酱3"
    max_bytes = 20000

    def __init__(self, sendkey: str = None):
        self._sendkey = sendkey

    def is_configured(self) -> bool:
        return bool(self._sendkey)

    def _do_send(self, content: str) -> bool:
        # 根据 sendkey 格式构造 URL
        key = self._sendkey.strip()
        if key.startswith('sctp'):
            num = re.match(r'sctp(\d+)t', key)
            url = f"https://{num.group(1)}.push.ft07.com/send/{key}.send" if num else f"https://sc3.ft07.com/api/push/{key}"
        else:
            url = f"https://sc3.ft07.com/api/push/{key}"

        # 提取标题（第一行非空文本）
        title = "A股分析报告"
        for line in content.split('\n'):
            line = line.strip().lstrip('#').strip()
            if line:
                title = line[:32]
                break

        payload = {"title": title, "desp": content}
        resp = self._post_json(url, payload)
        return resp.status_code == 200


class CustomWebhookChannel(BaseChannel):
    """自定义 Webhook（自动识别钉钉/Discord/Slack/Bark等）"""

    name = "自定义Webhook"
    max_bytes = 4000
    chunk_delay = 1.0

    def __init__(self, urls: List[str] = None, bearer_token: str = None):
        self._urls = urls or []
        self._bearer_token = bearer_token

    def is_configured(self) -> bool:
        return bool(self._urls)

    def _do_send(self, content: str) -> bool:
        all_ok = True
        for url in self._urls:
            payload, headers = self._build_payload(url, content)
            try:
                resp = self._post_json(url, payload, headers=headers)
                if resp.status_code not in (200, 204):
                    logger.warning(f"[Webhook] {url[:50]}... -> HTTP {resp.status_code}")
                    all_ok = False
            except Exception as e:
                logger.error(f"[Webhook] {url[:50]}... 异常: {e}")
                all_ok = False
        return all_ok

    def _build_payload(self, url: str, content: str):
        """根据 URL 自动识别服务类型并构建 payload"""
        headers = {}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        if 'oapi.dingtalk.com' in url:
            return {"msgtype": "markdown", "markdown": {"title": "A股分析", "text": content}}, headers
        elif 'discord.com' in url:
            return {"content": self.markdown_to_plain(content)[:2000]}, headers
        elif 'hooks.slack.com' in url:
            return {"text": content}, headers
        elif 'api.day.app' in url or '/push' in url:
            title = content.split('\n')[0].strip('#').strip()[:50]
            return {"title": title, "body": self.markdown_to_plain(content)}, headers
        else:
            return {"content": content, "msg_type": "markdown"}, headers


class DiscordChannel(BaseChannel):
    """Discord Webhook / Bot"""

    name = "Discord"
    max_bytes = 2000

    def __init__(self, webhook_url: str = None, bot_token: str = None,
                 channel_id: str = None):
        self._webhook_url = webhook_url
        self._bot_token = bot_token
        self._channel_id = channel_id

    def is_configured(self) -> bool:
        return bool(self._webhook_url) or bool(self._bot_token and self._channel_id)

    def _do_send(self, content: str) -> bool:
        text = self.markdown_to_plain(content)[:2000]

        # 优先 Webhook
        if self._webhook_url:
            resp = self._post_json(self._webhook_url, {"content": text})
            if resp.status_code in (200, 204):
                return True

        # 回退 Bot API
        if self._bot_token and self._channel_id:
            url = f"https://discord.com/api/v10/channels/{self._channel_id}/messages"
            headers = {"Authorization": f"Bot {self._bot_token}"}
            resp = self._post_json(url, {"content": text}, headers=headers)
            return resp.status_code == 200

        return False


class AstrBotChannel(BaseChannel):
    """AstrBot 推送"""

    name = "AstrBot"
    max_bytes = 20000

    def __init__(self, url: str = None, token: str = None):
        self._url = url
        self._token = token

    def is_configured(self) -> bool:
        return bool(self._url and self._token)

    def _do_send(self, content: str) -> bool:
        html = self.markdown_to_html(content)
        timestamp = str(int(time.time()))
        signature = hmac.new(
            self._token.encode('utf-8'),
            timestamp.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-Signature": signature,
            "X-Timestamp": timestamp,
            "Content-Type": "application/json",
        }
        payload = {"message": html, "format": "html"}
        resp = self._post_json(self._url, payload, headers=headers)
        return resp.status_code == 200
