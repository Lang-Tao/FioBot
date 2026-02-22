"""
明日方舟公招识别插件

功能:
  - 公招 <标签1> <标签2> ... : 根据标签计算最优公招组合
  - 公招 + 图片 : OCR 识别公招截图标签并计算组合
  - 公招更新 : 更新游戏数据
"""

import re

from nonebot import on_command, logger, get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message, MessageSegment, MessageEvent
from nonebot.params import CommandArg
from nonebot.exception import MatcherException

from .config import Config
from .game_data import (
    download_game_data,
    is_data_ready,
    build_recruit_data,
)
from .recruit import (
    normalize_tags,
    smart_split_tags,
    find_recruit_combinations,
    format_results,
    extract_tags_from_ocr,
)
from .ocr import ocr_image, download_image
from .render import render_recruit_result


__plugin_meta__ = PluginMetadata(
    name="明日方舟公招识别",
    description="根据公招标签计算最优干员组合，支持截图 OCR 识别",
    usage=(
        "公招 <标签1> <标签2> ... - 识别公招标签组合\n"
        "  标签用空格或逗号分隔，支持缩写（如：高资、近卫、远程）\n"
        "  示例：公招 高资 近卫 输出\n"
        "公招 + 图片 - 发送公招截图自动 OCR 识别标签\n"
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

recruit_cmd = on_command("/公招", aliases={"/公开招募", "/gk", "/gz"}, priority=10, block=True)
update_cmd = on_command("/公招更新", priority=10, block=True)


# ==================== 辅助函数 ====================


def _extract_image_url(msg: Message) -> str | None:
    """从消息中提取图片 URL"""
    for seg in msg:
        if seg.type == "image":
            url = seg.data.get("url") or seg.data.get("file")
            if url:
                return url
    return None


async def _ensure_data() -> str | None:
    """
    确保公招数据已就绪，返回 None 表示成功，否则返回错误提示

    会在需要时自动下载数据并刷新缓存
    """
    global _cached_operators, _cached_valid_tags

    if _cached_operators is not None and _cached_valid_tags is not None:
        return None

    if not is_data_ready():
        return "need_download"

    _load_cache()
    if _cached_operators is None or _cached_valid_tags is None:
        return "游戏数据加载失败喵，请尝试「公招更新」"

    return None


async def _do_recruit(tags: list[str]) -> MessageSegment | str:
    """执行公招计算，有结果返回图片，无结果返回文字"""
    results = find_recruit_combinations(tags, _cached_operators)  # type: ignore
    if not results:
        return "没有找到有价值的标签组合喵~\n（只显示保底 4★ 及以上和必出 1★ 的组合）"
    img_bytes = render_recruit_result(tags, results)
    return MessageSegment.image(img_bytes)


# ==================== 公招识别 ====================


@recruit_cmd.handle()
async def handle_recruit(event: MessageEvent, args: Message = CommandArg()):
    text = args.extract_plain_text().strip()
    image_url = _extract_image_url(event.message)

    # 既没有文字也没有图片
    if not text and not image_url:
        await recruit_cmd.finish(
            "请输入公招标签或发送公招截图喵~\n"
            "用法：公招 <标签1> <标签2> ...\n"
            "示例：公招 高资 近卫 输出\n"
            "支持截图：发送「公招」并附上公招截图\n"
            "支持缩写：高资/资深/近卫/狙击/近战/远程/回费 等"
        )

    # 数据未就绪时自动下载
    data_status = await _ensure_data()
    if data_status == "need_download":
        await recruit_cmd.send("首次使用，正在下载游戏数据，请稍候喵...")
        try:
            await download_game_data(
                plugin_config.mrfz_character_table_url,
                plugin_config.mrfz_gacha_table_url,
            )
        except MatcherException:
            raise
        except Exception as e:
            logger.error(f"下载游戏数据失败: {e}")
            await recruit_cmd.finish(f"下载游戏数据失败喵：{e}")
        _load_cache()
        data_status = await _ensure_data()

    if data_status:
        await recruit_cmd.finish(data_status)

    # ===== 图片 OCR 模式 =====
    if image_url:
        # 检查 OCR 配置
        if not plugin_config.baidu_ocr_api_key or not plugin_config.baidu_ocr_secret_key:
            await recruit_cmd.finish(
                "未配置百度 OCR 喵~\n"
                "请在 .env 中配置 BAIDU_OCR_API_KEY 和 BAIDU_OCR_SECRET_KEY"
            )

        await recruit_cmd.send("正在识别公招截图喵...")

        try:
            # 下载图片
            img_data = await download_image(image_url)
        except MatcherException:
            raise
        except Exception as e:
            logger.error(f"下载公招截图失败: {e}")
            await recruit_cmd.finish(f"下载图片失败喵：{e}")

        try:
            # OCR 识别
            ocr_lines = await ocr_image(
                img_data,
                plugin_config.baidu_ocr_api_key,
                plugin_config.baidu_ocr_secret_key,
            )
        except MatcherException:
            raise
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            await recruit_cmd.finish(f"OCR 识别失败喵：{e}")

        if not ocr_lines:
            await recruit_cmd.finish("截图中没有识别到文字喵~")

        logger.info(f"OCR 原始结果: {ocr_lines}")

        # 从 OCR 结果中提取标签
        tags = extract_tags_from_ocr(ocr_lines, _cached_valid_tags)  # type: ignore

        if not tags:
            ocr_text = " | ".join(ocr_lines)
            await recruit_cmd.finish(
                f"未从截图中识别到公招标签喵~\n"
                f"OCR 识别文字：{ocr_text}\n"
                f"请确保截图包含完整的公招标签区域"
            )

        if len(tags) > 5:
            tags = tags[:5]

        result = await _do_recruit(tags)
        await recruit_cmd.finish(Message(result))

    # ===== 文字标签模式 =====
    # 解析用户输入的标签（支持无空格连写）
    raw_tags = smart_split_tags(text, _cached_valid_tags)  # type: ignore

    if not raw_tags:
        await recruit_cmd.finish("没有识别到标签喵~")

    if len(raw_tags) > 5:
        await recruit_cmd.finish("公招最多只能选 5 个标签喵~")

    # 标准化标签
    tags = normalize_tags(raw_tags, _cached_valid_tags)  # type: ignore

    if not tags:
        await recruit_cmd.finish(
            f"未识别到有效标签喵~\n"
            f"你输入的：{' '.join(raw_tags)}\n"
            f"请检查标签是否正确"
        )

    result = await _do_recruit(tags)
    await recruit_cmd.finish(Message(result))


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
    except Exception as e:
        logger.error(f"更新游戏数据失败: {e}", exc_info=True)
        await update_cmd.finish(f"更新失败喵：{e}")

    _load_cache()

    if _cached_operators is not None:
        await update_cmd.finish(
            f"游戏数据更新成功喵！\n"
            f"可招募干员：{len(_cached_operators)} 个\n"
            f"标签数：{len(_cached_valid_tags or [])} 个"
        )
    else:
        await update_cmd.finish("数据下载成功但解析失败喵，请检查日志")
