"""森空岛 API 交互模块

参考 FrostN0v0/nonebot-plugin-skland 实现
包含登录认证和游戏数据查询两大部分
"""

import hmac
import json
import hashlib
from typing import Literal, Optional
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass

import httpx
from nonebot import logger


# ==================== API 常量 ====================

SKLAND_BASE_URL = "https://zonai.skland.com/api/v1"
SKLAND_APP_CODE = "4ca99fa6b56cc2ba"
WEB_APP_CODE = "be36d44aa36bfb5b"


# ==================== 异常定义 ====================


class SklandException(Exception):
    """森空岛 API 异常基类"""
    pass


class RequestException(SklandException):
    """请求异常"""
    pass


class LoginException(SklandException):
    """登录异常"""
    pass


class UnauthorizedException(SklandException):
    """认证过期异常"""
    pass


# ==================== 数据类 ====================


@dataclass
class CRED:
    """森空岛认证凭据"""
    cred: str
    token: str
    userId: Optional[str] = None


# ==================== 登录 API ====================


class SklandLoginAPI:
    """森空岛登录认证 API"""

    _headers = {
        "User-Agent": "Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0",
        "Accept-Encoding": "gzip",
        "Connection": "close",
    }

    @classmethod
    async def get_grant_code(cls, token: str, grant_type: int) -> str:
        """
        获取认证代码或 token

        Args:
            token: 用户 token
            grant_type: 0 返回森空岛认证代码, 1 返回官网通行证 token
        """
        async with httpx.AsyncClient() as client:
            code = SKLAND_APP_CODE if grant_type == 0 else WEB_APP_CODE
            response = await client.post(
                "https://as.hypergryph.com/user/oauth2/v2/grant",
                json={"appCode": code, "token": token, "type": grant_type},
                headers={**cls._headers},
            )
            data = response.json()
            if status := data.get("status"):
                if status != 0:
                    raise RequestException(f"获取认证代码失败：{data.get('msg')}")
            return data["data"]["code"] if grant_type == 0 else data["data"]["token"]

    @classmethod
    async def get_cred(cls, grant_code: str) -> CRED:
        """通过认证代码获取 cred 凭据"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code",
                json={"code": grant_code, "kind": 1},
                headers={**cls._headers},
            )
            data = response.json()
            if status := data.get("status"):
                if status != 0:
                    raise RequestException(f"获取 cred 失败：{data.get('message')}")
            return CRED(**data["data"])

    @classmethod
    async def refresh_token(cls, cred: str) -> str:
        """刷新 cred_token"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://zonai.skland.com/api/v1/auth/refresh",
                    headers={**cls._headers, "cred": cred},
                )
                response.raise_for_status()
                data = response.json()
                if status := data.get("status"):
                    if status != 0:
                        raise RequestException(f"刷新 token 失败：{data.get('message')}")
                return data["data"]["token"]
            except httpx.HTTPError as e:
                raise RequestException(f"刷新 token 失败：{e}")

    @classmethod
    async def get_scan(cls) -> str:
        """获取扫码登录的 scan_id"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://as.hypergryph.com/general/v1/gen_scan/login",
                json={"appCode": SKLAND_APP_CODE},
            )
            data = response.json()
            if status := data.get("status"):
                if status != 0:
                    raise RequestException(f"获取二维码失败：{data.get('msg')}")
            return data["data"]["scanId"]

    @classmethod
    async def get_scan_status(cls, scan_id: str) -> str:
        """查询扫码状态，未完成时抛出 RequestException"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://as.hypergryph.com/general/v1/scan_status",
                params={"scanId": scan_id},
            )
            data = response.json()
            if status := data.get("status"):
                if status != 0:
                    raise RequestException(f"获取扫码状态失败：{data.get('msg')}")
            return data["data"]["scanCode"]

    @classmethod
    async def get_token_by_scan_code(cls, scan_code: str) -> str:
        """通过扫码结果获取 token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://as.hypergryph.com/user/auth/v1/token_by_scan_code",
                json={"scanCode": scan_code},
            )
            data = response.json()
            if status := data.get("status"):
                if status != 0:
                    raise RequestException(f"获取 token 失败：{data.get('msg')}")
            return data["data"]["token"]


# ==================== 森空岛数据 API ====================


class SklandAPI:
    """森空岛游戏数据 API"""

    _headers = {
        "User-Agent": "Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0",
        "Accept-Encoding": "gzip",
        "Connection": "close",
    }

    _header_for_sign = {"platform": "", "timestamp": "", "dId": "", "vName": ""}

    @classmethod
    def get_sign_header(
        cls,
        cred: CRED,
        url: str,
        method: Literal["get", "post"],
        query_body: dict | None = None,
    ) -> dict:
        """
        生成带 HMAC 签名的请求头

        签名算法: HMAC-SHA256 → MD5
        secret = "{path}{query_params}{timestamp}{header_ca_str}"
        """
        timestamp = int(datetime.now().timestamp()) - 1
        header_ca = {**cls._header_for_sign, "timestamp": str(timestamp)}
        parsed_url = urlparse(url)

        if method == "post":
            query_params = json.dumps(query_body) if query_body is not None else ""
        else:
            query_params = parsed_url.query

        header_ca_str = json.dumps(
            {**cls._header_for_sign, "timestamp": str(timestamp)},
            separators=(",", ":"),
        )

        secret = f"{parsed_url.path}{query_params}{timestamp}{header_ca_str}"
        hex_secret = hmac.new(
            cred.token.encode("utf-8"),
            secret.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signature = hashlib.md5(hex_secret.encode("utf-8")).hexdigest()

        return {"cred": cred.cred, **cls._headers, "sign": signature, **header_ca}

    @classmethod
    def _check_response(cls, data: dict, action: str):
        """统一检查 API 响应状态码"""
        if status := data.get("code"):
            if status == 10000:
                raise UnauthorizedException(f"{action}：{data.get('message')}")
            elif status == 10002:
                raise LoginException(f"{action}：{data.get('message')}")
            if status != 0:
                raise RequestException(f"{action}：{data.get('message')}")

    @classmethod
    async def get_binding(cls, cred: CRED) -> list[dict]:
        """获取绑定的角色列表"""
        binding_url = f"{SKLAND_BASE_URL}/game/player/binding"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    binding_url,
                    headers=cls.get_sign_header(cred, binding_url, method="get"),
                )
                data = response.json()
                cls._check_response(data, "获取绑定角色失败")
                return data["data"]["list"]
            except httpx.HTTPError as e:
                raise RequestException(f"获取绑定角色失败: {e}")

    @classmethod
    async def get_user_id(cls, cred: CRED) -> str:
        """获取森空岛用户 ID"""
        uid_url = f"{SKLAND_BASE_URL}/user/teenager"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    uid_url,
                    headers=cls.get_sign_header(cred, uid_url, method="get"),
                )
                data = response.json()
                cls._check_response(data, "获取用户 ID 失败")
                return data["data"]["teenager"]["userId"]
            except httpx.HTTPError as e:
                raise RequestException(f"获取用户 ID 失败: {e}")

    @classmethod
    async def ark_sign(cls, cred: CRED, uid: str, channel_master_id: str) -> dict:
        """
        明日方舟签到

        Returns:
            签到结果, 包含 awards 列表
        """
        body = {"uid": uid, "gameId": channel_master_id}
        json_body = json.dumps(body, ensure_ascii=False, separators=(", ", ": "), allow_nan=False)
        sign_url = f"{SKLAND_BASE_URL}/game/attendance"
        headers = cls.get_sign_header(cred, sign_url, method="post", query_body=body)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    sign_url,
                    headers={**headers, "Content-Type": "application/json"},
                    content=json_body,
                )
                data = response.json()
                logger.debug(f"签到回复：{data}")
                cls._check_response(data, f"角色 {uid} 签到失败")
                return data.get("data", {})
            except httpx.HTTPError as e:
                raise RequestException(f"角色 {uid} 签到失败: {e}")

    @classmethod
    async def get_player_info(cls, cred: CRED, uid: str) -> dict:
        """获取明日方舟角色详细信息"""
        game_info_url = f"{SKLAND_BASE_URL}/game/player/info?uid={uid}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    game_info_url,
                    headers=cls.get_sign_header(cred, game_info_url, method="get"),
                )
                data = response.json()
                cls._check_response(data, "获取角色信息失败")
                return data.get("data", {})
            except httpx.HTTPError as e:
                raise RequestException(f"获取角色信息失败: {e}")
