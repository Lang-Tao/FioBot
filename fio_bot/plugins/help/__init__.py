from nonebot import get_plugin_config, on_command, logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import MessageSegment

from .config import Config
from .render import render_help_image

__plugin_meta__ = PluginMetadata(
    name="help",
    description="command list of fiobot",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

help = on_command("fiop", aliases={"fio帮助"}, priority=2, block=True)


@help.handle()
async def handle_function():
    try:
        img_bytes = await render_help_image()
        await help.finish(MessageSegment.image(img_bytes))
    except Exception as e:
        logger.error(f"渲染帮助图片失败: {e}")
        await help.finish("帮助图片生成失败，请稍后再试")