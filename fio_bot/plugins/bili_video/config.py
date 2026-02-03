from pydantic import BaseModel
from typing import Optional

class Config(BaseModel):
    # B站视频插件配置
    bili_video_enabled: bool = True
    # 最大下载视频长度（秒）
    bili_video_max_duration: int = 600
    # 下载视频的默认清晰度（1: 480p, 2: 720p, 3: 1080p）
    bili_video_quality: int = 2
    # B站Cookie（可选，用于获取会员视频）
    bili_cookie: Optional[str] = None
    # 音频功能配置
    bili_audio_enabled: bool = True
    # 最大下载音频长度（秒）
    bili_audio_max_duration: int = 600
    # 音频输出格式
    bili_audio_format: str = "mp3"
