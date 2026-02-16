"""
明日方舟公招识别插件

功能:
  - 公招 <标签1> <标签2> ... : 根据标签计算最优公招组合
  - 公招更新 : 更新游戏数据
"""

import re

from nonebot import on_command, logger, get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.params import CommandArg

from .config import Config
from .game_data import (
    download_game_data,
    is_data_ready,
    build_recruit_data,
)
from .recruit import (
    normalize_tags,
    find_recruit_combinations,
    format_results,
)


__plugin_meta__ = PluginMetadata(
    name="明日方舟公招识别",
    description="根据公招标签计算最优干员组合",
    usage=(
        "公招 <标签1> <标签2> ... - 识别公招标签组合\n"
        "  标签用空格或逗号分隔，支持缩写（如：高资、近卫、远程）\n"
        "  示例：公招 高资 近卫 输出\n"
        "公招更新 - 更新游戏数据"
    ),
    config=Config,
)

plugin_config = get_plugin_config(Config)

# 缓存解析后的数据，避免每次都重新读取文件
_cached_operators: list[dict] | None = None
_cached_valid_tags: list[str] | None = None


def _load_cache():
    """加载/刷新缓存"""
    global _cached_operators, _cached_valid_tags
    if is_data_ready():
        _cached_operators, _cached_valid_tags = build_recruit_data()
        logger.info(f"公招数据加载完成：{len(_cached_operators)} 个可招募干员，{len(_cached_valid_tags)} 个标签")
    else:
        _cached_operators = None
        _cached_valid_tags = None


# ==================== 命令定义 ====================

recruit_cmd = on_command("公招", aliases={"公开招募", "gk","gz"}, priority=10, block=True)
update_cmd = on_command("公招更新", priority=10, block=True)


# ==================== 公招识别 ====================


@recruit_cmd.handle()
async def handle_recruit(event: MessageEvent, args: Message = CommandArg()):
    text = args.extract_plain_text().strip()

    if not text:
        await recruit_cmd.finish(
            "请输入公招标签喵~\n"
            "用法：公招 <标签1> <标签2> ...\n"
            "示例：公招 高资 近卫 输出\n"
            "支持缩写：高资/资深/近卫/狙击/近战/远程/回费 等"
        )

    # 数据未就绪时自动下载
    if _cached_operators is None or _cached_valid_tags is None:
        if not is_data_ready():
            await recruit_cmd.send("首次使用，正在下载游戏数据，请稍候喵...")
            try:
                await download_game_data(
                    plugin_config.mrfz_character_table_url,
                    plugin_config.mrfz_gacha_table_url,
                )
            except Exception as e:
                logger.error(f"下载游戏数据失败: {e}")
                await recruit_cmd.finish(f"下载游戏数据失败喵：{e}")
        _load_cache()

    if _cached_operators is None or _cached_valid_tags is None:
        await recruit_cmd.finish("游戏数据加载失败喵，请尝试「公招更新」")

    # 解析用户输入的标签
    raw_tags = re.split(r"[,，\s]+", text)
    raw_tags = [t.strip() for t in raw_tags if t.strip()]

    if not raw_tags:
        await recruit_cmd.finish("没有识别到标签喵~")

    if len(raw_tags) > 5:
        await recruit_cmd.finish("公招最多只能选 5 个标签喵~")

    # 标准化标签
    tags = normalize_tags(raw_tags, _cached_valid_tags)

    if not tags:
        await recruit_cmd.finish(
            f"未识别到有效标签喵~\n"
            f"你输入的：{' '.join(raw_tags)}\n"
            f"请检查标签是否正确"
        )

    # 反馈识别到的标签
    tag_echo = "、".join(tags)

    # 计算组合
    results = find_recruit_combinations(tags, _cached_operators)

    # 格式化输出
    output = format_results(results)

    await recruit_cmd.finish(f"📋 识别标签：{tag_echo}\n\n{output}")


# ==================== 数据更新 ====================


@update_cmd.handle()
async def handle_update(event: MessageEvent):
    await update_cmd.send("正在更新游戏数据喵...")
    try:
        await download_game_data(
            plugin_config.mrfz_character_table_url,
            plugin_config.mrfz_gacha_table_url,
            force=True,
        )
        _load_cache()

        if _cached_operators is not None:
            await update_cmd.finish(
                f"游戏数据更新成功喵！\n"
                f"可招募干员：{len(_cached_operators)} 个\n"
                f"标签数：{len(_cached_valid_tags or [])} 个"
            )
        else:
            await update_cmd.finish("数据下载成功但解析失败喵，请检查日志")

    except Exception as e:
        logger.error(f"更新游戏数据失败: {e}")
        await update_cmd.finish(f"更新失败喵：{e}")
