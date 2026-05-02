"""复读插件

当群聊里出现“多个不同的人连续发送相同消息（复读）”时，Bot 也复读一次。

判定规则（可配置）：
- 在同一群内
- 在时间窗口内连续出现相同消息
- 参与复读的不同用户数达到阈值
- 且本轮尚未触发过

默认配置偏保守：至少 3 条消息、3 个不同用户。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="repeater",
    description="检测多人复读时，Bot 跟随复读一次",
    usage="无需指令，群聊自动生效",
    config=Config,
)

config = get_plugin_config(Config)


@dataclass
class _RepeatStreak:
    key: str = ""
    last_ts: float = 0.0
    count: int = 0
    user_ids: set[int] = field(default_factory=set)
    triggered: bool = False
    last_trigger_ts: float = 0.0


_group_state: dict[int, _RepeatStreak] = {}
_group_locks: dict[int, asyncio.Lock] = {}


def _get_lock(group_id: int) -> asyncio.Lock:
    lock = _group_locks.get(group_id)
    if lock is None:
        lock = asyncio.Lock()
        _group_locks[group_id] = lock
    return lock


def _message_key(event: GroupMessageEvent) -> str:
    # raw_message 在 OneBot V11 中包含 CQ 码；能覆盖图片/表情等复读
    raw = getattr(event, "raw_message", None)
    if raw is not None:
        return raw.strip()
    return str(event.message).strip()


repeater = on_message(priority=1, block=False)


@repeater.handle()
async def handle_repeater(bot: Bot, event: GroupMessageEvent):
    # 仅处理群消息
    if not isinstance(event, GroupMessageEvent):
        return

    # 忽略 Bot 自己发的，避免循环复读
    if str(event.user_id) in {str(event.self_id), str(bot.self_id)}:
        return

    # 简单规避把指令当作复读对象（以 / 或 ／ 开头）
    if event.get_plaintext().lstrip().startswith(("/", "／")):
        return

    key = _message_key(event)
    if not key:
        return

    group_id = int(event.group_id)
    now = time.monotonic()

    to_send: Message | None = None

    async with _get_lock(group_id):
        streak = _group_state.get(group_id)
        if streak is None:
            streak = _RepeatStreak()
            _group_state[group_id] = streak

        window = float(getattr(config, "repeater_window_seconds", 15.0))
        min_messages = int(getattr(config, "repeater_min_messages", 3))
        min_users = int(getattr(config, "repeater_min_users", 3))
        cooldown = float(getattr(config, "repeater_cooldown_seconds", 10.0))

        is_new_round = streak.key != key or (now - streak.last_ts) > window
        if is_new_round:
            streak.key = key
            streak.last_ts = now
            streak.count = 1
            streak.user_ids = {int(event.user_id)}
            streak.triggered = False
        else:
            streak.last_ts = now
            streak.count += 1
            streak.user_ids.add(int(event.user_id))

        should_trigger = (
            (not streak.triggered)
            and streak.count >= min_messages
            and len(streak.user_ids) >= min_users
            and (now - streak.last_trigger_ts) >= cooldown
        )

        if should_trigger:
            streak.triggered = True
            streak.last_trigger_ts = now
            to_send = event.message

    if to_send is not None:
        await repeater.send(to_send)
