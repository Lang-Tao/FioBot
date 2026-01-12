import re
import json
import httpx
from typing import List, Optional
from nonebot import on_regex, logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, MessageEvent
from nonebot.typing import T_State

__plugin_meta__ = PluginMetadata(
    name="小红书去水印",
    description="解析小红书分享链接，发送无水印原图",
    usage="直接发送包含小红书链接的消息即可触发",
)

# 匹配小红书的短链 (xhslink.com) 或 长链 (xiaohongshu.com)
# 优先级设为 11，防止拦截其他重要指令
xhs = on_regex(
    r"(http://xhslink\.com/[A-Za-z0-9]+)|(https?://(www\.)?xiaohongshu\.com/discovery/item/[a-fA-F0-9]+)",
    priority=11,
    block=True
)

# 模拟手机浏览器的 Header，这是成功的关键
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.xiaohongshu.com/",
}

async def get_url_from_msg(text: str) -> Optional[str]:
    """从消息中提取第一条符合的 URL"""
    # 匹配短链
    short_pattern = r"http://xhslink\.com/[A-Za-z0-9]+"
    # 匹配长链
    long_pattern = r"https?://(www\.)?xiaohongshu\.com/discovery/item/[a-fA-F0-9]+"
    
    match = re.search(short_pattern, text)
    if match:
        return match.group(0)
    
    match = re.search(long_pattern, text)
    if match:
        return match.group(0)
    return None

async def download_image(url: str) -> Optional[bytes]:
    """下载图片并返回二进制数据"""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.content
    except Exception as e:
        logger.warning(f"图片下载失败 {url}: {e}")
    return None

@xhs.handle()
async def handle_xhs(bot: Bot, event: MessageEvent, state: T_State):
    msg_text = event.get_plaintext()
    url = await get_url_from_msg(msg_text)
    
    if not url:
        return

    # 发送提示，防止解析时间过长用户以为没反应
    await xhs.send("正在解析小红书笔记，请稍候喵...")

    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
            # 1. 访问链接 (如果是短链会自动跳转)
            resp = await client.get(url)
            html = resp.text
            
            # 2. 从 HTML 中提取 JSON 数据
            # 小红书的数据通常藏在 window.__INITIAL_STATE__ 中
            pattern = r"window\.__INITIAL_STATE__\s*=\s*({.*?});"
            match = re.search(pattern, html, re.DOTALL)
            
            if not match:
                # 尝试另一种匹配模式 (有时候是 __INITIAL_SSR_STATE__)
                pattern = r"window\.__INITIAL_SSR_STATE__\s*=\s*({.*?});"
                match = re.search(pattern, html, re.DOTALL)

            if not match:
                await xhs.finish("解析失败：无法找到笔记数据，可能是由于小红书的风控策略，请稍后再试喵。")

            # 3. 解析 JSON
            json_str = match.group(1)
            # 有时候 json 里的 undefined 需要替换为 null 才能解析
            json_str = json_str.replace("undefined", "null")
            data = json.loads(json_str)

            # 4. 提取图片列表
            # 数据结构路径通常比较深，需要尝试获取
            note_data = data.get("note", {}).get("note", {})
            
            # 如果没找到，尝试从 noteDetailMap 获取
            if not note_data:
                # 尝试通过当前 URL 的 ID 查找
                # 这里做简化处理，直接找第一个存在的 note
                detail_map = data.get("note", {}).get("noteDetailMap", {})
                if detail_map:
                    note_data = list(detail_map.values())[0]

            if not note_data:
                 await xhs.finish("解析失败：数据结构不匹配喵。")

            title = note_data.get("title", "无标题")
            desc = note_data.get("desc", "")
            image_list = note_data.get("imageList", [])
            type_ = note_data.get("type", "normal") # normal 是图文，video 是视频

            if type_ == "video":
                await xhs.finish("检测到这是一条视频笔记，目前仅支持下载图片喵")

            if not image_list:
                await xhs.finish("未检测到图片列表喵。")

            # 5. 构建消息
            # 先发标题
            msg_chain = [MessageSegment.text(f"【{title}】\n")]
            
            # 下载并添加图片
            # 小红书 JSON 里的 urlDefault 通常就是无水印的
            success_count = 0
            for img_info in image_list:
                # 优先获取 urlDefault，其次是 urlOriginal (如果有)
                # 小红书目前的 urlDefault 往往是无水印的高清图
                # info_list 里的 image_scene 也可以用
                img_url = img_info.get("urlDefault", "")
                if not img_url:
                    img_url = img_info.get("infoList", [{}])[1].get("url", "")

                if img_url:
                    # 替换域名 (有时候 http 需要换成 https)
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    
                    # 下载图片数据 (解决 Docker 路径问题)
                    img_bytes = await download_image(img_url)
                    if img_bytes:
                        msg_chain.append(MessageSegment.image(img_bytes))
                        success_count += 1
            
            if success_count == 0:
                await xhs.finish("图片下载失败，可能链接已失效喵。")

            # 6. 发送最终消息
            # 如果图片太多，可能会导致消息过长，建议分段发送或合并转发
            # 这里为了简单，直接发送
            if len(msg_chain) > 1:
                await xhs.send(Message(msg_chain))
            else:
                await xhs.finish("没有找到可下载的图片喵。")

    except httpx.RequestError as e:
        logger.error(f"网络请求错误: {e}")
        await xhs.finish("连接小红书服务器失败，请检查网络。")
    except Exception as e:
        logger.error(f"解析异常: {e}")
        await xhs.finish(f"解析过程中发生未知错误: {e}")