import re
import json
import httpx
import io
import subprocess
import traceback
from typing import Optional, Dict, Any
from nonebot import on_regex, on_command, logger, get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, MessageEvent
from nonebot.typing import T_State
from nonebot.params import CommandArg
from nonebot.exception import FinishedException
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="B站视频下载",
    description="解析B站视频链接或BV号，下载并发送视频，支持音频提取功能",
    usage="直接发送包含B站链接或BV号的消息即可触发视频下载。使用 /audio <B站链接或BV号> 命令可提取并发送音频下载链接。",
    config=Config,
)

plugin_config = get_plugin_config(Config)

# 匹配B站链接或BV号
bili = on_regex(
    r"(https?://(www\.)?bilibili\.com/(video|BV)[a-zA-Z0-9]+)|(BV[a-zA-Z0-9]+)",
    priority=11,
    block=True
)

# 音频命令
bili_audio = on_command(
    "audio",
    priority=10,
    block=True
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

async def get_bvid_from_input(text: str) -> Optional[str]:
    """从输入中提取BV号"""
    # 匹配BV号
    bv_pattern = r"BV[a-zA-Z0-9]+"
    match = re.search(bv_pattern, text)
    if match:
        return match.group(0)
    return None

async def get_video_info(bvid: str) -> Optional[Dict[str, Any]]:
    """获取视频信息"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data.get("data")
                else:
                    logger.error(f"获取视频信息失败: {data.get('message')}")
            else:
                logger.error(f"获取视频信息失败，状态码: {resp.status_code}")
    except Exception as e:
        logger.error(f"获取视频信息异常: {e}")
    return None

async def get_video_url(bvid: str, cid: int, quality: int = 2) -> Optional[str]:
    """获取视频下载链接"""
    url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn={quality}"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    durl = data.get("data", {}).get("durl", [])
                    if durl:
                        return durl[0].get("url")
                else:
                    logger.error(f"获取视频链接失败: {data.get('message')}")
            else:
                logger.error(f"获取视频链接失败，状态码: {resp.status_code}")
    except Exception as e:
        logger.error(f"获取视频链接异常: {e}")
    return None

async def download_video(url: str) -> Optional[bytes]:
    """下载视频"""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.content
            else:
                logger.error(f"下载视频失败，状态码: {resp.status_code}")
    except Exception as e:
        logger.error(f"下载视频异常: {e}")
    return None

async def extract_audio(video_data: bytes, output_format: str = "mp3") -> Optional[bytes]:
    """从视频中提取音频"""
    try:
        # 将视频数据写入临时文件
        with open("temp_video.mp4", "wb") as f:
            f.write(video_data)
        
        # 使用ffmpeg提取音频
        output_file = f"temp_audio.{output_format}"
        cmd = [
            "ffmpeg",
            "-i", "temp_video.mp4",
            "-vn",  # 禁用视频
            "-acodec", "libmp3lame" if output_format == "mp3" else "aac",
            "-ab", "128k",  # 音频比特率
            "-f", output_format,
            "-y",  # 覆盖输出文件
            output_file
        ]
        
        # 执行ffmpeg命令
        subprocess.run(cmd, check=True, capture_output=True)
        
        # 读取提取的音频数据
        with open(output_file, "rb") as f:
            audio_data = f.read()
        
        # 清理临时文件
        import os
        os.remove("temp_video.mp4")
        os.remove(output_file)
        
        return audio_data
    except Exception as e:
        logger.error(f"提取音频异常: {e}")
        # 清理临时文件
        try:
            import os
            if os.path.exists("temp_video.mp4"):
                os.remove("temp_video.mp4")
            if os.path.exists(f"temp_audio.{output_format}"):
                os.remove(f"temp_audio.{output_format}")
        except:
            pass
        return None

async def upload_file(file_data: bytes, filename: str) -> Optional[str]:
    """上传文件到临时存储服务并返回下载链接"""
    try:
        # 使用catbox.moe作为临时存储服务
        url = "https://catbox.moe/user/api.php"
        data = {
            "reqtype": "fileupload",
            "userhash": "",  # 无需登录
        }
        files = {
            "fileToUpload": (filename, file_data, "audio/mpeg")
        }
        
        # 添加headers
        upload_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://catbox.moe/",
        }
        
        async with httpx.AsyncClient(headers=upload_headers, timeout=30, trust_env=True) as client:
            resp = await client.post(url, data=data, files=files)
            if resp.status_code == 200:
                return resp.text.strip()
            else:
                logger.error(f"上传文件失败，状态码: {resp.status_code}, 响应: {resp.text}")
    except Exception as e:
        logger.error(f"上传文件异常: {traceback.format_exc()}")
    return None

@bili.handle()
async def handle_bili(bot: Bot, event: MessageEvent, state: T_State):
    msg_text = event.get_plaintext()
    bvid = await get_bvid_from_input(msg_text)
    
    if not bvid:
        await bili.finish("没有找到有效的B站BV号喵~")

    try:
        # 1. 获取视频信息
        video_info = await get_video_info(bvid)
        if not video_info:
            await bili.finish("获取视频信息失败惹喵~")

        # 2. 检查视频时长
        duration = video_info.get("duration", 0)
        if duration > plugin_config.bili_video_max_duration:
            await bili.finish(f"视频时长太长啦（{duration}秒），超过最大限制（{plugin_config.bili_video_max_duration}秒）喵~")

        # 3. 获取视频信息
        title = video_info.get("title", "无标题")
        cid = video_info.get("cid")
        if not cid:
            await bili.finish("获取视频CID失败惹喵~")

        # 4. 获取视频下载链接
        video_url = await get_video_url(bvid, cid, plugin_config.bili_video_quality)
        if not video_url:
            await bili.finish("获取视频下载链接失败惹喵~")

        # 5. 下载视频
        video_data = await download_video(video_url)
        if not video_data:
            await bili.finish("下载视频失败惹喵~")

        # 6. 发送视频
        await bili.send(Message(MessageSegment.text(f"视频下载好啦喵~") + MessageSegment.video(video_data)))

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"B站视频处理异常: {e}")
        await bili.finish(f"处理视频失败惹喵~ {e}")

@bili_audio.handle()
async def handle_bili_audio(bot: Bot, event: MessageEvent, state: T_State, arg: Message = CommandArg()):
    msg_text = arg.extract_plain_text()
    bvid = await get_bvid_from_input(msg_text)
    
    if not bvid:
        await bili_audio.finish("没有找到有效的B站BV号喵~")

    try:
        # 1. 获取视频信息
        video_info = await get_video_info(bvid)
        if not video_info:
            await bili_audio.finish("获取视频信息失败惹喵~")

        # 2. 检查音频时长
        duration = video_info.get("duration", 0)
        if duration > plugin_config.bili_audio_max_duration:
            await bili_audio.finish(f"音频时长太长啦（{duration}秒），超过最大限制（{plugin_config.bili_audio_max_duration}秒）喵~")

        # 3. 获取视频信息
        title = video_info.get("title", "无标题")
        cid = video_info.get("cid")
        if not cid:
            await bili_audio.finish("获取视频CID失败惹喵~")

        # 4. 获取视频下载链接
        video_url = await get_video_url(bvid, cid, plugin_config.bili_video_quality)
        if not video_url:
            await bili_audio.finish("获取视频下载链接失败惹喵~")

        # 5. 下载视频
        video_data = await download_video(video_url)
        if not video_data:
            await bili_audio.finish("下载视频失败惹喵~")

        # 6. 提取音频
        audio_data = await extract_audio(video_data, plugin_config.bili_audio_format)
        if not audio_data:
            await bili_audio.finish("提取音频失败惹喵~")

        # 7. 上传音频文件并获取下载链接
        filename = f"{title}.{plugin_config.bili_audio_format}"
        download_url = await upload_file(audio_data, filename)
        if not download_url:
            await bili_audio.finish("上传音频文件失败惹喵~")

        # 8. 发送下载链接
        await bili_audio.send(Message(MessageSegment.text(f"音频提取好啦喵~ {download_url}")))

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"B站音频处理异常: {e}")
        await bili_audio.finish(f"处理音频失败惹喵~ {e}")
