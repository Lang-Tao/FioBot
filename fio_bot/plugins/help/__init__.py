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

help = on_command("fiop", aliases={"fio帮助"}, priority=10000, block=True)

@help.handle()
async def handle_function():
    HELP_TEXT = (
        "📋 指令列表：\n"
        "\n"
        "【🎮 森空岛】\n"
        "  森空岛绑定 <token/cred> - 绑定账号（私聊）\n"
        "  扫码绑定 - 二维码扫码绑定\n"
        "  明日方舟签到 / 方舟签到 - 为绑定角色签到\n"
        "  角色列表 - 查看绑定的角色\n"
        "  角色更新 - 刷新角色绑定信息\n"
        "\n"
        "【🎲 随机功能】\n"
        "  roll / fioll <选项1> <选项2> ... - 帮你做选择（空格或逗号分隔）\n"
        "\n"
        "【📺 B站视频】\n"
        "  发送B站链接或BV号 - 自动解析并发送三分钟以内的视频\n"
        "  audio <B站链接或BV号> - 提取并发送音频下载链接\n"
        "\n"
        "【📷 小红书】\n"
        "  发送小红书链接 - 自动解析并发送无水印原图\n"
        "\n"
        "【🏷️ 公招识别】\n"
        "  公招 <标签1> <标签2> ... - 计算最优公招组合\n"
        "  公招更新 - 更新游戏数据\n"
    )
    await help.finish(HELP_TEXT)