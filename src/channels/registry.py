# -*- coding: utf-8 -*-
"""
渠道注册表

根据配置自动发现、初始化可用渠道。
NotificationService 只需调用 registry.send_all(content)。
"""

import logging
from typing import List, Dict

from src.channels.base import BaseChannel
from src.channels.implementations import (
    WeChatChannel, FeishuChannel, TelegramChannel, EmailChannel,
    PushoverChannel, PushPlusChannel, ServerChan3Channel,
    CustomWebhookChannel, DiscordChannel, AstrBotChannel,
)

logger = logging.getLogger(__name__)


class ChannelRegistry:
    """渠道注册表 - 自动发现并管理所有通知渠道"""

    def __init__(self, config=None):
        from src.config import get_config
        cfg = config or get_config()
        self._channels: List[BaseChannel] = []
        self._init_channels(cfg)

    def _init_channels(self, cfg):
        """根据配置初始化所有渠道"""
        candidates = [
            WeChatChannel(
                webhook_url=cfg.wechat_webhook_url,
                msg_type=getattr(cfg, 'wechat_msg_type', 'markdown'),
                max_bytes_override=getattr(cfg, 'wechat_max_bytes', None),
            ),
            FeishuChannel(
                webhook_url=getattr(cfg, 'feishu_webhook_url', None),
                max_bytes_override=getattr(cfg, 'feishu_max_bytes', None),
            ),
            TelegramChannel(
                bot_token=getattr(cfg, 'telegram_bot_token', None),
                chat_id=getattr(cfg, 'telegram_chat_id', None),
                message_thread_id=getattr(cfg, 'telegram_message_thread_id', None),
            ),
            EmailChannel(
                sender=cfg.email_sender,
                password=cfg.email_password,
                receivers=cfg.email_receivers or ([cfg.email_sender] if cfg.email_sender else []),
                sender_name=getattr(cfg, 'email_sender_name', 'Stock分析助手'),
            ),
            PushoverChannel(
                user_key=getattr(cfg, 'pushover_user_key', None),
                api_token=getattr(cfg, 'pushover_api_token', None),
            ),
            PushPlusChannel(
                token=getattr(cfg, 'pushplus_token', None),
            ),
            ServerChan3Channel(
                sendkey=getattr(cfg, 'serverchan3_sendkey', None),
            ),
            CustomWebhookChannel(
                urls=getattr(cfg, 'custom_webhook_urls', []) or [],
                bearer_token=getattr(cfg, 'custom_webhook_bearer_token', None),
            ),
            DiscordChannel(
                webhook_url=getattr(cfg, 'discord_webhook_url', None),
                bot_token=getattr(cfg, 'discord_bot_token', None),
                channel_id=getattr(cfg, 'discord_main_channel_id', None),
            ),
            AstrBotChannel(
                url=getattr(cfg, 'astrbot_url', None),
                token=getattr(cfg, 'astrbot_token', None),
            ),
        ]

        for ch in candidates:
            if ch.is_configured():
                self._channels.append(ch)

        if self._channels:
            names = [ch.name for ch in self._channels]
            logger.info(f"已配置 {len(names)} 个通知渠道: {', '.join(names)}")
        else:
            logger.warning("未配置任何通知渠道")

    @property
    def available(self) -> List[BaseChannel]:
        return self._channels

    @property
    def channel_names(self) -> List[str]:
        return [ch.name for ch in self._channels]

    def send_all(self, content: str) -> bool:
        """向所有渠道发送，返回是否至少一个成功"""
        if not self._channels:
            return False

        success = 0
        fail = 0
        for ch in self._channels:
            if ch.send(content):
                success += 1
            else:
                fail += 1

        logger.info(f"通知发送完成: 成功 {success}, 失败 {fail}")
        return success > 0
