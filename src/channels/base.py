# -*- coding: utf-8 -*-
"""
通知渠道基类

提供公共功能：
1. 智能分段（按 Markdown 分隔符切分长消息）
2. HTTP POST 通用方法
3. 统一错误处理
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


class BaseChannel(ABC):
    """通知渠道抽象基类"""

    # 子类必须覆盖
    name: str = "未知渠道"
    max_bytes: int = 4096
    chunk_delay: float = 1.0  # 分段发送间隔（秒）

    @abstractmethod
    def is_configured(self) -> bool:
        """检查渠道是否已配置"""
        ...

    @abstractmethod
    def _do_send(self, content: str) -> bool:
        """
        实际发送逻辑（子类实现）

        content 已经过分段处理，保证不超过 max_bytes。
        """
        ...

    # ── 公共方法 ──────────────────────────────────────────

    def send(self, content: str) -> bool:
        """
        发送消息（自动处理分段）

        Args:
            content: Markdown 格式消息

        Returns:
            是否发送成功
        """
        if not self.is_configured():
            return False

        content_bytes = len(content.encode('utf-8'))
        if content_bytes <= self.max_bytes:
            return self._safe_send(content)

        # 需要分段
        chunks = self._smart_chunk(content, self.max_bytes)
        total = len(chunks)
        logger.info(f"[{self.name}] 消息过长({content_bytes}B)，分 {total} 段发送")

        all_ok = True
        for i, chunk in enumerate(chunks, 1):
            tagged = f"{chunk}\n\n📄 ({i}/{total})"
            if not self._safe_send(tagged):
                all_ok = False
            if i < total and self.chunk_delay > 0:
                time.sleep(self.chunk_delay)
        return all_ok

    def _safe_send(self, content: str) -> bool:
        """带异常捕获的发送"""
        try:
            return self._do_send(content)
        except Exception as e:
            logger.error(f"[{self.name}] 发送异常: {e}")
            return False

    # ── HTTP 工具 ─────────────────────────────────────────

    @staticmethod
    def _post_json(
        url: str,
        payload: dict,
        timeout: int = 10,
        headers: Optional[dict] = None,
    ) -> requests.Response:
        """通用 JSON POST"""
        return requests.post(url, json=payload, timeout=timeout, headers=headers)

    @staticmethod
    def _check_response(response: requests.Response, channel_name: str,
                        ok_key: str = 'errcode', ok_value=0) -> bool:
        """通用响应检查"""
        if response.status_code != 200:
            logger.error(f"[{channel_name}] HTTP {response.status_code}: {response.text[:200]}")
            return False
        try:
            data = response.json()
        except ValueError:
            # 某些服务返回非 JSON（如 204 No Content），视为成功
            return True
        # 灵活匹配：errcode==0 / code==0 / ok==true / StatusCode==0 等
        if ok_key in data:
            return data[ok_key] == ok_value
        return True

    # ── 分段工具 ─────────────────────────────────────────

    @staticmethod
    def _smart_chunk(text: str, max_bytes: int) -> List[str]:
        """
        智能分段：按 Markdown 结构切分

        优先级：
        1. --- 分隔线
        2. ### 三级标题
        3. ## 二级标题
        4. 空行
        5. 强制按行切分
        """
        if len(text.encode('utf-8')) <= max_bytes:
            return [text]

        separators = ['\n---\n', '\n### ', '\n## ', '\n\n']
        for sep in separators:
            parts = text.split(sep)
            if len(parts) <= 1:
                continue
            chunks = []
            current = parts[0]
            for part in parts[1:]:
                candidate = current + sep + part
                if len(candidate.encode('utf-8')) <= max_bytes:
                    current = candidate
                else:
                    if current.strip():
                        chunks.append(current.strip())
                    current = part
            if current.strip():
                chunks.append(current.strip())
            if chunks:
                return chunks

        # 回退：按行强制切分
        return BaseChannel._force_chunk_by_lines(text, max_bytes)

    @staticmethod
    def _force_chunk_by_lines(text: str, max_bytes: int) -> List[str]:
        """按行强制切分"""
        lines = text.split('\n')
        chunks = []
        current_lines: List[str] = []
        current_size = 0

        for line in lines:
            line_size = len(line.encode('utf-8')) + 1  # +1 for \n
            if current_size + line_size > max_bytes and current_lines:
                chunks.append('\n'.join(current_lines))
                current_lines = []
                current_size = 0
            current_lines.append(line)
            current_size += line_size

        if current_lines:
            chunks.append('\n'.join(current_lines))
        return chunks if chunks else [text[:max_bytes]]

    # ── 格式转换工具 ─────────────────────────────────────

    @staticmethod
    def markdown_to_plain(text: str) -> str:
        """Markdown 转纯文本"""
        import re
        text = re.sub(r'#{1,6}\s*', '', text)       # 去标题
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 去粗体
        text = re.sub(r'\*(.*?)\*', r'\1', text)       # 去斜体
        text = re.sub(r'`(.*?)`', r'\1', text)         # 去代码
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # 去链接
        text = re.sub(r'\|[-:\s|]+\|', '', text)       # 去表格分隔
        return text.strip()

    @staticmethod
    def markdown_to_html(text: str) -> str:
        """Markdown 转 HTML"""
        import markdown2
        html = markdown2.markdown(text, extras=['tables', 'fenced-code-blocks'])
        return f"""<html><body style="font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#333">
{html}
</body></html>"""

    @staticmethod
    def truncate_to_bytes(text: str, max_bytes: int) -> str:
        """按字节截断（不破坏 UTF-8）"""
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        truncated = encoded[:max_bytes]
        return truncated.decode('utf-8', errors='ignore').rstrip() + '\n...(已截断)'
