from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="help",
    description="command list of fiobot",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

from nonebot import on_command

help = on_command("help", aliases={"帮助"}, priority=10, block=True)

@help.handle()
async def handle_function():
    HELP_TEXT = (
    "指令列表：\n"
    "skland：角色信息卡片\n"
    "角色更新：更新森空岛绑定的角色信息\n"
    "扫码绑定：获取二维码，用于扫码绑定森空岛账号\n"
    "明日方舟签到：为当前用户绑定的所有角色签到\n"
    "xx肉鸽：肉鸽战绩查询\n"
    "战绩详情 <战绩ID>：根据 ID 查询最近战绩详情 (可加 -f 查询收藏)\n"
    "skland gacha：查询明日方舟抽卡记录 \n"
    "skland import <url>：导入明日方舟抽卡记录，支持导入小黑盒记录的抽卡记录\n"
    # "skland bind <token>：绑定森空岛账号的 Token/Cred\n"
    # "skland bind -u <token>：更新已绑定的 Token 或 Cred\n"
    # "skland qrcode：获取二维码，用于扫码绑定森空岛账号\n"
    # "skland arksign -u <uid>：指定 UID 的角色进行签到\n"
    # "skland arksign status：查询个人自动签到服务的状态\n"
)
    await help.finish(HELP_TEXT)