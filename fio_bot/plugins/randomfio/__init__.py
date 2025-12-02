import os
import random
import shutil
import uuid
from pathlib import Path

import httpx
from nonebot import get_plugin_config, logger, on_command, on_notice, on_message
from nonebot.plugin import PluginMetadata
from nonebot.matcher import Matcher
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    PokeNotifyEvent,
    MessageSegment,
)

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="randomfio",
    description="随机fio图与上传功能",
    usage="指令: /fio\n关键词: 聊天包含'fio'\n上传: /上传fio [回复图片]\n戳一戳: 戳Bot触发",
    config=Config,
)

config = get_plugin_config(Config)

RES_DIR = Path(__file__).parent / "resource"
RES_DIR.mkdir(parents=True, exist_ok=True) 

# 加载文件名列表
def reload_images():
    """重新加载图片列表"""
    valid_suffix = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    return [f.name for f in RES_DIR.iterdir() if f.is_file() and f.suffix.lower() in valid_suffix]

all_file_name = reload_images()

async def send_random_fio(matcher: Matcher):
    """通用的发送逻辑"""
    global all_file_name
    all_file_name = reload_images()

    if not all_file_name:
        # 为了防止关键词误触导致刷屏报错，如果是关键词触发且没图，可以选择不回复
        # 这里为了演示还是回复提示
        await matcher.finish("图库是空的！快去上传吧~")
    
    img_name = random.choice(all_file_name)
    img_path = RES_DIR / img_name
    
    try:
        # 二进制读取，兼容 Docker 环境
        with open(img_path, "rb") as f:
            img_bytes = f.read()
        
        await matcher.send(MessageSegment.image(img_bytes))
        
    except Exception as e:
        logger.error(f"发送图片失败: {e}")
        await matcher.send(f"干什么！")

# 1. 指令触发 (/fio)
# priority=5: 设置为较高优先级
randomfio = on_command('fio', aliases={'小fio'}, priority=5, block=True)

@randomfio.handle()
async def _(matcher: Matcher):
    await send_random_fio(matcher)


# 2. 关键词触发 (新增功能)
# 规则函数：判断消息纯文本中是否包含 "fio" (转为小写判断，即 Fio, FIO 都会触发)
async def check_fio_keyword(event: MessageEvent) -> bool:
    return "fio" in event.get_plaintext().lower()

# priority=10: 优先级比指令(5)低，防止和指令冲突。
# 这样只有当消息不是指令时，才会轮到这里检查是否有关键词。
fio_keyword = on_message(rule=Rule(check_fio_keyword), priority=10, block=True)

@fio_keyword.handle()
async def _(matcher: Matcher):
    if random.random() < 0.5:
        await send_random_fio(matcher)


# 3. 戳一戳触发 
def _poke_check(event: PokeNotifyEvent):
    return event.target_id == event.self_id

# priority=1: 戳一戳是独立事件，设为1响应最快
poke = on_notice(rule=_poke_check, priority=1)

@poke.handle()
async def handle_poke(matcher: Matcher):
    await send_random_fio(matcher)


# 4. 上传fio
# priority=5: 与普通指令一致
add_fio = on_command('上传fio', aliases={'上传小fio'}, priority=5, block=True)

adders = config.fio_adders if hasattr(config, "fio_adders") else []

@add_fio.handle()
async def save_img_handle(bot: Bot, event: MessageEvent, matcher: Matcher):
    user_id = event.user_id
    if adders and int(user_id) not in adders:
         await matcher.finish("你没有权限上传fio！")

    if not event.reply:
        await matcher.finish("请回复所需上传的图片消息来上传")

    reply_msg = event.reply.message
    img_seg = None
    for seg in reply_msg:
        if seg.type == "image":
            img_seg = seg
            break
            
    if not img_seg:
        await matcher.finish("未检测到图片，请回复图片消息")

    file_id = img_seg.data.get("file")
    url = img_seg.data.get("url")
    
    save_filename = f"{uuid.uuid4().hex}.jpg"
    save_path = RES_DIR / save_filename

    success = False
    
    # 优先尝试 URL 下载
    if url:
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"正在下载图片: {url}")
                r = await client.get(url, timeout=20)
                if r.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(r.content)
                    success = True
        except Exception as e:
            logger.error(f"URL下载失败: {e}")

    # 备选 API 下载
    if not success:
        try:
            resp = await bot.call_api('get_image', file=file_id)
            local_file_path = resp.get('file')
            if local_file_path and os.path.exists(local_file_path):
                shutil.copy(local_file_path, save_path)
                success = True
        except Exception as e:
            logger.warning(f"get_image API 失败: {e}")

    if success:
        await matcher.finish(f"有新的fio加入了哦！")
    else:
        await matcher.finish("图片保存失败，请检查日志。")