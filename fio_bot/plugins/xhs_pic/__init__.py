import re
import json
import httpx
from typing import List, Optional, Dict, Any
from nonebot import on_regex, logger, get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, MessageEvent
from nonebot.typing import T_State
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="小红书去水印",
    description="解析小红书分享链接，发送无水印原图",
    usage="直接发送包含小红书链接的消息即可触发。请在配置文件中设置 xhs_cookie 以获取更稳定的体验。",
    config=Config,
)

plugin_config = get_plugin_config(Config)

# 匹配小红书的短链 (xhslink.com) 或 长链 (xiaohongshu.com)
# 支持 /discovery/item/ 和 /explore/
# 允许匹配后面的参数
# 修复短链正则，支持 /o/ 等路径
xhs = on_regex(
    r"(http://xhslink\.com/[A-Za-z0-9/]+)|(https?://(www\.)?xiaohongshu\.com/(discovery/item|explore)/[a-fA-F0-9]+(\?[\w=&-]+)?)",
    priority=11,
    block=True
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.xiaohongshu.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

async def get_url_from_msg(text: str) -> Optional[str]:
    """从消息中提取第一条符合的 URL"""
    # 修复短链正则，支持 /o/ 等路径
    short_pattern = r"http://xhslink\.com/[A-Za-z0-9/]+"
    # 允许匹配后面的参数
    long_pattern = r"https?://(www\.)?xiaohongshu\.com/(discovery/item|explore)/[a-fA-F0-9]+(\?[\w=&-]+)?"
    
    match = re.search(short_pattern, text)
    if match:
        return match.group(0)
    
    match = re.search(long_pattern, text)
    if match:
        return match.group(0)
    return None

async def get_final_url(url: str) -> str:
    """获取重定向后的最终 URL"""
    if "xhslink.com" in url:
        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=False, timeout=10) as client:
                resp = await client.get(url)
                if resp.status_code in [301, 302, 307, 308]:
                    return resp.headers.get("Location", url)
                # 如果没有重定向，可能是直接返回了 HTML，里面包含跳转逻辑，或者就是最终页面
                # 但 xhslink 通常是 302
                return str(resp.url)
        except Exception as e:
            logger.warning(f"获取短链重定向失败: {e}")
            return url
    return url

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

def extract_initial_state(html: str) -> Optional[Dict[str, Any]]:
    """从 HTML 中提取 window.__INITIAL_STATE__"""
    # 1. 尝试正则提取
    pattern = r"window\.__INITIAL_STATE__\s*=\s*({.*?});"
    match = re.search(pattern, html, re.DOTALL)
    if match:
        json_str = match.group(1)
        try:
            # 处理 undefined
            json_str = json_str.replace("undefined", "null")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"正则提取 JSON 解析失败: {e}")

    # 2. 尝试手动提取（应对正则失败的情况）
    try:
        start_marker = "window.__INITIAL_STATE__"
        start_index = html.find(start_marker)
        if start_index != -1:
            # 找到第一个 {
            json_start = html.find("{", start_index)
            if json_start != -1:
                brace_count = 0
                json_end = -1
                for i in range(json_start, len(html)):
                    char = html[i]
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end != -1:
                    json_str = html[json_start:json_end]
                    try:
                        json_str = json_str.replace("undefined", "null")
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"手动提取 JSON 解析失败: {e}")
    except Exception as e:
        logger.error(f"手动提取异常: {e}")

    return None

@xhs.handle()
async def handle_xhs(bot: Bot, event: MessageEvent, state: T_State):
    msg_text = event.get_plaintext()
    url = await get_url_from_msg(msg_text)
    
    if not url:
        return

    # 检查 Cookie 配置
    if not plugin_config.xhs_cookie:
        logger.warning("未配置 xhs_cookie，解析可能会失败。建议在配置文件中添加 xhs_cookie。")

    # 更新 Headers
    current_headers = HEADERS.copy()
    if plugin_config.xhs_cookie:
        current_headers["Cookie"] = plugin_config.xhs_cookie

    try:
        # 1. 获取最终 URL
        final_url = await get_final_url(url)
        logger.info(f"目标 URL: {final_url}")

        # 2. 请求页面
        async with httpx.AsyncClient(headers=current_headers, follow_redirects=True, timeout=20) as client:
            resp = await client.get(final_url)
            if resp.status_code != 200:
                logger.error(f"访问失败，状态码: {resp.status_code}")
                await xhs.finish("获取失败了喵")
            
            html = resp.text

        # 3. 提取数据
        data = extract_initial_state(html)
        if not data:
            # 尝试检查是否被反爬（例如验证码页面）
            if "验证码" in html or "captcha" in html:
                logger.error("解析失败：触发了小红书验证码，请更新 Cookie 或稍后再试。")
            else:
                logger.error("解析失败：无法提取笔记数据，可能是 Cookie 失效或接口变动。")
            await xhs.finish("获取失败了喵")

        # 4. 定位 Note 数据
        # 结构通常是 data['note']['note']
        note_data = data.get("note", {}).get("note", {})
        
        # 如果没找到，尝试从 noteDetailMap 获取 (key 是 noteId)
        if not note_data:
            detail_map = data.get("note", {}).get("noteDetailMap", {})
            if detail_map:
                # detail_map 的结构是 { noteId: { note: {...}, ... } }
                # 所以我们需要再取一层 note
                first_item = list(detail_map.values())[0]
                note_data = first_item.get("note", {})
        
        if not note_data:
            logger.error("解析失败：未找到笔记详情数据。")
            await xhs.finish("获取失败了喵")

        # 5. 解析内容
        type_ = note_data.get("type", "normal")
        
        # 仅保留媒体内容，移除标题、作者、描述等文本
        msg_chain = []

        if type_ == "video":
            # 视频处理
            video_info = note_data.get("video", {})
            media_info = video_info.get("media", {})
            stream = media_info.get("stream", {})
            # 通常 h264 兼容性好
            h264 = stream.get("h264", [])
            if h264:
                video_url = h264[0].get("masterUrl", "")
                if video_url:
                    # 发送视频封面
                    cover_url = note_data.get("imageList", [{}])[0].get("urlDefault", "")
                    if cover_url:
                         img_bytes = await download_image(cover_url)
                         if img_bytes:
                             msg_chain.append(MessageSegment.image(img_bytes))
                    
                    msg_chain.append(MessageSegment.text(f"\n视频链接：{video_url}"))
            else:
                logger.error("无法解析视频地址。")
                await xhs.finish("获取失败了喵")

        else:
            # 图片处理
            image_list = note_data.get("imageList", [])
            if not image_list:
                logger.error("未检测到图片列表。")
                await xhs.finish("获取失败了喵")

            success_count = 0
            for img_info in image_list:
                # 尝试获取无水印大图
                # 策略：优先找 infoList 中的高分辨率图，如果没有则用 urlDefault
                # infoList 通常包含: [{imageScene: 'CR_1080P', url: ...}, ...]
                
                target_url = ""
                info_list = img_info.get("infoList", [])
                
                # 尝试寻找 1080P 或 原图
                for info in info_list:
                    if info.get("imageScene") in ["CR_1080P", "WB_DET"]:
                        target_url = info.get("url", "")
                        break
                
                if not target_url:
                    target_url = img_info.get("urlDefault", "")

                if target_url:
                    # 处理协议头
                    if target_url.startswith("//"):
                        target_url = "https:" + target_url
                    
                    # 下载
                    img_bytes = await download_image(target_url)
                    if img_bytes:
                        msg_chain.append(MessageSegment.image(img_bytes))
                        success_count += 1
            
            if success_count == 0:
                logger.error("图片下载失败，可能链接已失效。")
                await xhs.finish("获取失败了喵")

        # 6. 发送
        if len(msg_chain) > 0:
            await xhs.send(Message(msg_chain))
        else:
            logger.error("内容解析为空。")
            await xhs.finish("获取失败了喵")

    except Exception as e:
        logger.error(f"小红书解析异常: {e}")
        await xhs.finish("获取失败了喵")
