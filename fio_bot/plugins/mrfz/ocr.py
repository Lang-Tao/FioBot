"""百度 OCR 模块

调用百度云通用文字识别 API，从公招截图中提取标签文字
"""

import base64
import time
from typing import Optional

import httpx
from nonebot import logger


# ==================== Access Token 缓存 ====================

_access_token: Optional[str] = None
_token_expire_time: float = 0  # token 过期时间戳


async def _get_access_token(api_key: str, secret_key: str) -> str:
    """
    获取百度 OCR Access Token（带缓存）

    Token 有效期 30 天，缓存后避免重复请求
    """
    global _access_token, _token_expire_time

    # 如果 token 还在有效期内，直接返回
    if _access_token and time.time() < _token_expire_time:
        return _access_token

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "access_token" not in data:
        raise ValueError(f"获取百度 OCR Token 失败: {data}")

    _access_token = data["access_token"]
    # 提前 1 小时过期，避免边界问题
    _token_expire_time = time.time() + data.get("expires_in", 2592000) - 3600
    logger.info("百度 OCR Access Token 获取成功")

    return _access_token


# ==================== OCR 识别 ====================


async def ocr_image(
    image_data: bytes,
    api_key: str,
    secret_key: str,
) -> list[str]:
    """
    调用百度通用文字识别 API 识别图片文字

    Args:
        image_data: 图片二进制数据
        api_key: 百度 OCR API Key
        secret_key: 百度 OCR Secret Key

    Returns:
        识别到的文字行列表
    """
    token = await _get_access_token(api_key, secret_key)

    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
    params = {"access_token": token}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # 图片转 base64
    img_b64 = base64.b64encode(image_data).decode("utf-8")

    payload = {"image": img_b64}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, params=params, headers=headers, data=payload)
        resp.raise_for_status()
        data = resp.json()

    if "error_code" in data:
        raise ValueError(f"百度 OCR 识别失败: [{data['error_code']}] {data.get('error_msg', '')}")

    words_list = data.get("words_result", [])
    result = [item["words"] for item in words_list if "words" in item]

    logger.debug(f"百度 OCR 识别结果: {result}")
    return result


# ==================== 从图片 URL 下载图片 ====================


async def download_image(url: str) -> bytes:
    """
    下载图片

    Args:
        url: 图片 URL

    Returns:
        图片二进制数据
    """
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content
