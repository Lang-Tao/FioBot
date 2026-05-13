"""复读插件

当群聊里出现“多个不同的人连续发送相同消息（复读）”时，Bot 也复读一次。

判定规则（可配置）：
- 在同一群内
- 在时间窗口内连续出现相同消息
- 参与复读的不同用户数达到阈值
- 且本轮尚未触发过

默认配置偏保守：至少 3 条消息、3 个不同用户。

另有一个可选的“首字母联想复读”（拼音首字母相同但内容不同也可能触发），默认关闭。
如需开启，请在配置中设置 `repeater_initialism_enabled=true`。
"""

from __future__ import annotations

import asyncio
import random
import re
import time
from dataclasses import dataclass, field

from nonebot import get_plugin_config
from nonebot import logger
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


try:
    from pypinyin import Style
    from pypinyin import lazy_pinyin

    _PYPINYIN_AVAILABLE = True
except Exception:
    _PYPINYIN_AVAILABLE = False
    Style = None  # type: ignore[assignment]
    lazy_pinyin = None  # type: ignore[assignment]


@dataclass
class _RepeatStreak:
    key: str = ""
    last_ts: float = 0.0
    count: int = 0
    user_ids: set[int] = field(default_factory=set)
    triggered: bool = False
    last_trigger_ts: float = 0.0


@dataclass
class _InitialismStreak:
    key: str = ""
    last_ts: float = 0.0
    count: int = 0
    user_ids: set[int] = field(default_factory=set)
    # 用于判断“内容不同时”
    contents: set[str] = field(default_factory=set)
    triggered: bool = False
    last_trigger_ts: float = 0.0


_group_state: dict[int, _RepeatStreak] = {}
_group_initialism_state: dict[int, _InitialismStreak] = {}
_group_locks: dict[int, asyncio.Lock] = {}


def _get_lock(group_id: int) -> asyncio.Lock:
    lock = _group_locks.get(group_id)
    if lock is None:
        lock = asyncio.Lock()
        _group_locks[group_id] = lock
    return lock


def _message_key(event: GroupMessageEvent) -> str:
    # 对“文字类消息”（纯 text / markdown）用 plaintext 作为 key：
    # 这样能兼容某些客户端的富文本样式（显示一样，但 raw_message 不同）。
    # 对包含图片/表情/at 等非文字段的消息，仍用 raw_message 保持严格匹配。
    try:
        text_like_types = {"text", "markdown"}
        if all(seg.type in text_like_types for seg in event.message):
            pt = event.get_plaintext().strip()
            if pt:
                return pt
    except Exception:
        pass

    raw = getattr(event, "raw_message", None)
    if raw is not None:
        return str(raw).strip()
    return str(event.message).strip()


_ALNUM_RE = re.compile(r"[a-zA-Z0-9]+")


def _initialism(text: str) -> str:
    """把文本转成拼音首字母串。

    - 中文：用 pypinyin 的 FIRST_LETTER
    - 英文/数字：保留（转小写）
    - 其他符号：跳过
    """
    text = (text or "").strip()
    if not text:
        return ""

    if not _PYPINYIN_AVAILABLE:
        return ""

    letters: list[str] = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            # 中文字符
            py = lazy_pinyin(ch, style=Style.FIRST_LETTER, strict=False)
            if py and py[0]:
                letters.append(str(py[0]).lower())
        elif ch.isascii() and ch.isalnum():
            letters.append(ch.lower())
        else:
            continue
    return "".join(letters)


_PHRASE_BANK: dict[str, list[str]] = {
    # 示例：说的道理 / 十点多了 -> sddl
    "sddl": ["是对的了", "说得对了"],
}


_LETTER_WORDS: dict[str, list[str]] = {
    "a": ["啊", "爱"],
    "b": ["不", "把", "吧"],
    "c": ["才", "从", "错"],
    "d": ["的", "对", "都", "大"],
    "e": ["额", "嗯"],
    "f": ["反", "非", "发"],
    "g": ["个", "更", "给"],
    "h": ["好", "还", "会"],
    "i": ["哎"],
    "j": ["就", "见", "将"],
    "k": ["看", "可", "快"],
    "l": ["了", "来", "里"],
    "m": ["么", "没", "慢"],
    "n": ["你", "那", "呢"],
    "o": ["哦"],
    "p": ["怕", "跑", "凭"],
    "q": ["去", "却", "起"],
    "r": ["人", "让", "如"],
    "s": ["是", "说", "上"],
    "t": ["他", "太", "同"],
    "u": ["呃"],
    "v": ["哇"],
    "w": ["我", "为", "问"],
    "x": ["行", "先", "想"],
    "y": ["有", "要", "也"],
    "z": ["再", "走", "做"],
    "0": ["0"],
    "1": ["1"],
    "2": ["2"],
    "3": ["3"],
    "4": ["4"],
    "5": ["5"],
    "6": ["6"],
    "7": ["7"],
    "8": ["8"],
    "9": ["9"],
}


def _generate_phrase_from_initialism(key: str) -> str:
    key = (key or "").strip().lower()
    if not key:
        return ""

    rng = random.Random(key)
    parts: list[str] = []
    for letter in key:
        choices = _LETTER_WORDS.get(letter)
        if not choices:
            return ""
        parts.append(rng.choice(choices))
    return "".join(parts)


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

    # 用纯文本做“首字母联想”的内容判定，避免 CQ 码影响
    plain = event.get_plaintext().strip()

    group_id = int(event.group_id)
    now = time.monotonic()

    to_send: Message | None = None
    to_send_text: str | None = None

    async with _get_lock(group_id):
        streak = _group_state.get(group_id)
        if streak is None:
            streak = _RepeatStreak()
            _group_state[group_id] = streak

        initialism_streak = _group_initialism_state.get(group_id)
        if initialism_streak is None:
            initialism_streak = _InitialismStreak()
            _group_initialism_state[group_id] = initialism_streak

        window = float(getattr(config, "repeater_window_seconds", 180.0))
        min_messages = int(getattr(config, "repeater_min_messages", 3))
        min_users = int(getattr(config, "repeater_min_users", 3))
        cooldown = float(getattr(config, "repeater_cooldown_seconds", 10.0))
        debug = bool(getattr(config, "repeater_debug", False))

        initialism_enabled = bool(getattr(config, "repeater_initialism_enabled", False))
        initialism_min_messages = int(getattr(config, "repeater_initialism_min_messages", 2))
        initialism_min_users = int(getattr(config, "repeater_initialism_min_users", 2))
        initialism_min_len = int(getattr(config, "repeater_initialism_min_len", 2))
        initialism_max_len = int(getattr(config, "repeater_initialism_max_len", 12))

        expired = (now - streak.last_ts) > window if streak.last_ts else False
        is_new_round = streak.key != key or expired
        if is_new_round:
            if debug and streak.key:
                logger.info(
                    "repeater reset | group=%s | prev_key=%r | new_key=%r | expired=%s | dt=%.2fs",
                    group_id,
                    streak.key,
                    key,
                    expired,
                    (now - streak.last_ts) if streak.last_ts else 0.0,
                )
            streak.key = key
            streak.last_ts = now
            streak.count = 1
            streak.user_ids = {int(event.user_id)}
            streak.triggered = False
        else:
            streak.last_ts = now
            streak.count += 1
            streak.user_ids.add(int(event.user_id))

        if debug:
            logger.info(
                "repeater tick | group=%s | key=%r | count=%s | users=%s/%s",
                group_id,
                key,
                streak.count,
                len(streak.user_ids),
                min_users,
            )

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
            if debug:
                logger.info(
                    "repeater trigger | group=%s | key=%r | count=%s | users=%s",
                    group_id,
                    key,
                    streak.count,
                    len(streak.user_ids),
                )

        # ==================== 首字母联想复读 ====================
        # 仅在“不是完全相同内容复读”的分支上补充触发；完全相同由上面处理
        if (
            initialism_enabled
            and to_send is None
            and plain
            and _PYPINYIN_AVAILABLE
        ):
            ikey = _initialism(plain)
            if initialism_min_len <= len(ikey) <= initialism_max_len:
                is_new_i_round = (
                    initialism_streak.key != ikey or (now - initialism_streak.last_ts) > window
                )
                if is_new_i_round:
                    initialism_streak.key = ikey
                    initialism_streak.last_ts = now
                    initialism_streak.count = 1
                    initialism_streak.user_ids = {int(event.user_id)}
                    initialism_streak.contents = {plain}
                    initialism_streak.triggered = False
                else:
                    initialism_streak.last_ts = now
                    initialism_streak.count += 1
                    initialism_streak.user_ids.add(int(event.user_id))
                    initialism_streak.contents.add(plain)

                # “内容不同时”要求：至少出现过 2 个不同内容
                has_distinct_contents = len(initialism_streak.contents) >= 2
                should_i_trigger = (
                    (not initialism_streak.triggered)
                    and has_distinct_contents
                    and initialism_streak.count >= initialism_min_messages
                    and len(initialism_streak.user_ids) >= initialism_min_users
                    and (now - initialism_streak.last_trigger_ts) >= cooldown
                )

                if should_i_trigger:
                    initialism_streak.triggered = True
                    initialism_streak.last_trigger_ts = now

                    candidates = _PHRASE_BANK.get(ikey, [])
                    picked = ""
                    for c in candidates:
                        if c and c not in initialism_streak.contents:
                            picked = c
                            break
                    if not picked:
                        picked = _generate_phrase_from_initialism(ikey)

                    if picked and picked not in initialism_streak.contents:
                        to_send_text = picked
            elif ikey and _PYPINYIN_AVAILABLE:
                # 过短/过长不参与统计，避免误触；无需动作
                pass
        elif initialism_enabled and not _PYPINYIN_AVAILABLE:
            # 只打一次日志，避免刷屏
            if getattr(handle_repeater, "_warned_no_pypinyin", False) is False:
                setattr(handle_repeater, "_warned_no_pypinyin", True)
                logger.warning("repeater: 未安装 pypinyin，已自动禁用首字母联想复读")

    if to_send is not None:
        await repeater.send(to_send)
    elif to_send_text is not None:
        await repeater.send(to_send_text)
