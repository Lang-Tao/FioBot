import re
import asyncio
from nonebot import get_plugin_config, on_command, logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="poke",
    description="戳一戳功能",
    usage="指令: poke @用户 [次数]\n例如: poke @张三 5 (戳张三5次)\n默认戳1次",
    config=Config,
)

config = get_plugin_config(Config)

poke_cmd = on_command("poke", aliases={"戳", "戳一戳"}, priority=5, block=True)


@poke_cmd.handle()
async def handle_poke(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    text = args.extract_plain_text().strip()
    
    # 解析消息中的 @ 用户
    at_segments = [seg for seg in args if seg.type == "at"]
    
    if not at_segments:
        await poke_cmd.finish("请@要戳的人喵！\n用法: poke @用户 [次数]")
    
    # 获取被@的用户ID
    target_id = at_segments[0].data.get("qq")
    if not target_id:
        await poke_cmd.finish("未能识别到用户喵！")
    
    # 解析次数（从纯文本中提取数字）
    times = 1  # 默认1次
    numbers = re.findall(r'\d+', text)
    if numbers:
        try:
            times = int(numbers[0])
            # 限制次数范围
            if times < 1:
                times = 1
            elif times > 10:
                await poke_cmd.send("次数太多了喵！最多戳10次喵~")
                times = 10
        except ValueError:
            times = 1
    
    # 判断是群聊还是私聊
    if isinstance(event, GroupMessageEvent):
        group_id = event.group_id
        
        # 执行戳一戳
        success_count = 0
        fail_count = 0
        
        for i in range(times):
            try:
                await bot.call_api("group_poke", group_id=group_id, user_id=int(target_id))
                success_count += 1
                # 间隔一下，避免频繁操作
                if i < times - 1:
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"戳一戳失败: {e}")
                fail_count += 1
        
        # 成功了就不回复，失败了才提示
        if success_count == 0:
            await poke_cmd.finish("戳一戳失败了喵...")
    
    else:
        # 私聊暂不支持
        await poke_cmd.finish("私聊暂不支持戳一戳功能喵~")
