from nonebot import get_plugin_config, on_command
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pydantic import BaseModel
import random
import re
import asyncio

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="rollanything",
    description="帮选择困难症做决定的随机插件",
    usage="指令: roll <选项1> <选项2> ... (用空格或逗号分隔)",
    config=Config,
)

config = get_plugin_config(Config)

roll = on_command("roll", aliases={"fioll"}, priority=10, block=True)

@roll.handle()
async def handle_function(args: Message = CommandArg()):
    text = args.extract_plain_text().strip()

    if not text:
        await roll.finish("没有识别到选项喵")


    options = re.split(r'[,，\s]+', text)
    
    options = [opt for opt in options if opt]

    if len(options) <= 1:
        await roll.finish("没有识别到选项喵")

    hidden = random.randint(0,100)
    if hidden < 3:
        await roll.finish("自...自己的事自己决定喵！")

    await roll.send("命运的齿轮开始转动...")

    await asyncio.sleep(3)

    chosen_one = random.choice(options)

    if chosen_one[-1] in {"喵"}:
        chosen_one = chosen_one[:-1]

    await roll.finish(f"{chosen_one}喵！")