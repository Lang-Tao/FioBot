"""
森空岛插件本地测试脚本
- 生成二维码供扫描
- 获取角色绑定信息
- 尝试签到
"""

import hmac
import json
import hashlib
import asyncio
import time
from typing import Literal, Optional
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass

import httpx

# ==================== API 常量 ====================

SKLAND_BASE_URL = "https://zonai.skland.com/api/v1"
SKLAND_APP_CODE = "4ca99fa6b56cc2ba"

# 服务器时间偏移（秒），正值表示服务器比本地快
SERVER_TIME_OFFSET = 0


# ==================== 数据类 ====================

@dataclass
class CRED:
    cred: str
    token: str
    userId: Optional[str] = None


# ==================== 公共 headers ====================

COMMON_HEADERS = {
    "User-Agent": "Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0",
    "Accept-Encoding": "gzip",
    "Connection": "close",
}

HEADER_FOR_SIGN = {"platform": "", "timestamp": "", "dId": "", "vName": ""}


# ==================== 签名 ====================

def get_sign_header(cred: CRED, url: str, method: Literal["get", "post"], query_body: dict | None = None) -> dict:
    timestamp = int(time.time()) + SERVER_TIME_OFFSET - 1
    parsed_url = urlparse(url)
    if method == "post":
        query_params = json.dumps(query_body) if query_body is not None else ""
    else:
        query_params = parsed_url.query
    header_ca_str = json.dumps(
        {**HEADER_FOR_SIGN, "timestamp": str(timestamp)},
        separators=(",", ":"),
    )
    secret = f"{parsed_url.path}{query_params}{timestamp}{header_ca_str}"
    hex_secret = hmac.new(
        cred.token.encode("utf-8"),
        secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    signature = hashlib.md5(hex_secret.encode("utf-8")).hexdigest()
    return {
        "cred": cred.cred,
        **COMMON_HEADERS,
        "sign": signature,
        **HEADER_FOR_SIGN,
        "timestamp": str(timestamp),
    }


def check_response(data: dict, action: str):
    if status := data.get("code"):
        if status == 10000:
            raise Exception(f"[Unauthorized] {action}：{data.get('message')}")
        elif status == 10002:
            raise Exception(f"[Login] {action}：{data.get('message')}")
        if status != 0:
            raise Exception(f"[Request] {action}：{data.get('message')}")


# ==================== 主测试流程 ====================

async def main():
    try:
        import qrcode as qr_lib
    except ImportError:
        print("需要安装 qrcode 库: pip install qrcode[pil]")
        return

    print("=" * 50)
    print("  森空岛扫码绑定 → 获取角色 → 签到 测试")
    print("=" * 50)

    # 同步服务器时间
    global SERVER_TIME_OFFSET
    async with httpx.AsyncClient() as client:
        before = int(time.time())
        resp = await client.get("https://zonai.skland.com/api/v1/auth/refresh")
        server_ts = int(resp.json().get("timestamp", before))
        after = int(time.time())
        local_ts = (before + after) // 2
        SERVER_TIME_OFFSET = server_ts - local_ts
        print(f"\n  本地时间戳: {local_ts}")
        print(f"  服务器时间戳: {server_ts}")
        print(f"  时间偏移: {SERVER_TIME_OFFSET} 秒")

    async with httpx.AsyncClient() as client:
        # ========== 1. 获取 scan_id ==========
        print("\n[1/6] 获取扫码 scanId...")
        resp = await client.post(
            "https://as.hypergryph.com/general/v1/gen_scan/login",
            json={"appCode": SKLAND_APP_CODE},
        )
        scan_data = resp.json()
        if scan_data.get("status", 0) != 0:
            print(f"  ❌ 获取 scanId 失败: {scan_data}")
            return
        scan_id = scan_data["data"]["scanId"]
        print(f"  ✅ scanId: {scan_id}")

        # ========== 2. 生成二维码 ==========
        print("\n[2/6] 生成二维码...")
        scan_url = f"hypergryph://scan_login?scanId={scan_id}"
        qr = qr_lib.QRCode(version=1, box_size=1, border=1)
        qr.add_data(scan_url)
        qr.make(fit=True)

        # 在终端打印二维码
        print("\n请使用【森空岛APP】扫描下方二维码（有效期约2分钟）：\n")
        qr.print_ascii(invert=True)
        print()

        # ========== 3. 轮询扫码状态 ==========
        print("[3/6] 等待扫码...", end="", flush=True)
        scan_code = None
        for i in range(60):  # 最多等 120 秒
            await asyncio.sleep(2)
            print(".", end="", flush=True)
            try:
                status_resp = await client.get(
                    "https://as.hypergryph.com/general/v1/scan_status",
                    params={"scanId": scan_id},
                )
                status_data = status_resp.json()
                if status_data.get("status", 0) == 0 and status_data.get("data", {}).get("scanCode"):
                    scan_code = status_data["data"]["scanCode"]
                    break
            except Exception:
                pass

        if not scan_code:
            print("\n  ❌ 扫码超时！")
            return
        print(f"\n  ✅ 扫码成功！scanCode: {scan_code[:10]}...")

        # ========== 4. 获取 token → cred ==========
        print("\n[4/6] 获取 token 和 cred...")

        # scanCode → token
        token_resp = await client.post(
            "https://as.hypergryph.com/user/auth/v1/token_by_scan_code",
            json={"scanCode": scan_code},
        )
        token_data = token_resp.json()
        if token_data.get("status", 0) != 0:
            print(f"  ❌ 获取 token 失败: {token_data}")
            return
        access_token = token_data["data"]["token"]
        print(f"  ✅ access_token: {access_token[:10]}...")

        # token → grant_code
        grant_resp = await client.post(
            "https://as.hypergryph.com/user/oauth2/v2/grant",
            json={"appCode": SKLAND_APP_CODE, "token": access_token, "type": 0},
            headers=COMMON_HEADERS,
        )
        grant_data = grant_resp.json()
        if grant_data.get("status", 0) != 0:
            print(f"  ❌ 获取 grant_code 失败: {grant_data}")
            return
        grant_code = grant_data["data"]["code"]
        print(f"  ✅ grant_code: {grant_code[:10]}...")

        # grant_code → cred
        cred_resp = await client.post(
            "https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code",
            json={"code": grant_code, "kind": 1},
            headers=COMMON_HEADERS,
        )
        cred_data = cred_resp.json()
        print(f"  [DEBUG] cred 原始响应: {json.dumps(cred_data, ensure_ascii=False, indent=2)}")
        if cred_data.get("status", 0) != 0:
            print(f"  ❌ 获取 cred 失败: {cred_data}")
            return
        cred = CRED(**cred_data["data"])
        print(f"  ✅ cred: {cred.cred[:10]}...")
        print(f"  ✅ cred_token: {cred.token[:10]}...")
        print(f"  ✅ userId: {cred.userId}")

    # ========== 5. 获取绑定角色 ==========
    print("\n[5/6] 获取绑定角色...")
    async with httpx.AsyncClient() as client:
        binding_url = f"{SKLAND_BASE_URL}/game/player/binding"
        headers = get_sign_header(cred, binding_url, method="get")
        resp = await client.get(binding_url, headers=headers)
        binding_data = resp.json()
        print(f"  [DEBUG] 绑定角色原始响应:")
        print(f"  {json.dumps(binding_data, ensure_ascii=False, indent=2)}")

        check_response(binding_data, "获取绑定角色")
        binding_list = binding_data["data"]["list"]

        # 解析角色（使用修复后的逻辑）
        characters = []
        for app in binding_list:
            app_code = app.get("appCode", "")
            for binding in app.get("bindingList", []):
                roles = binding.get("roles", [])
                if roles:
                    for role in roles:
                        characters.append({
                            "uid": role.get("roleId", ""),
                            "nickname": role.get("nickname", ""),
                            "app_code": app_code,
                            "channel_master_id": str(role.get("serverId", binding.get("channelMasterId", ""))),
                            "is_default": len(roles) == 1 or role.get("isDefault", False),
                            "server_name": role.get("serverName", binding.get("channelName", "")),
                            "level": role.get("level", 0),
                        })
                else:
                    # roles 为空时回退
                    characters.append({
                        "uid": binding.get("uid", ""),
                        "nickname": binding.get("nickName", ""),
                        "app_code": app_code,
                        "channel_master_id": str(binding.get("channelMasterId", "")),
                        "is_default": len(app.get("bindingList", [])) == 1 or binding.get("isDefault", False),
                        "server_name": binding.get("channelName", ""),
                        "level": 0,
                    })

        print(f"\n  总共获取到 {len(characters)} 个角色:")
        ark_chars = []
        for c in characters:
            game_name = "明日方舟" if c["app_code"] == "arknights" else c["app_code"]
            server = ""
            if c["app_code"] == "arknights":
                server = " | 官服" if c["channel_master_id"] == "1" else " | B服"
                ark_chars.append(c)
            default_mark = " ⭐" if c.get("is_default") else ""
            print(f"    [{game_name}] {c['nickname']} | UID: {c['uid']} | Lv.{c.get('level', '?')}{server} | channelMasterId: {c['channel_master_id']}{default_mark}")

        if not ark_chars:
            print("\n  ⚠️ 没有找到明日方舟角色！")
            print("  这就是之前无法签到的原因。")
            print("  请检查上面的原始响应数据结构。")
            return

    # ========== 6. 尝试签到 ==========
    print(f"\n[6/6] 尝试为 {len(ark_chars)} 个明日方舟角色签到...")
    async with httpx.AsyncClient() as client:
        for char in ark_chars:
            uid = char["uid"]
            channel_master_id = char["channel_master_id"]
            nickname = char["nickname"]

            body = {"uid": uid, "gameId": channel_master_id}
            json_body = json.dumps(body, ensure_ascii=False, separators=(", ", ": "), allow_nan=False)
            sign_url = f"{SKLAND_BASE_URL}/game/attendance"
            headers = get_sign_header(cred, sign_url, method="post", query_body=body)

            resp = await client.post(
                sign_url,
                headers={**headers, "Content-Type": "application/json"},
                content=json_body,
            )
            sign_data = resp.json()
            print(f"\n  [{nickname}] 签到响应:")
            print(f"  {json.dumps(sign_data, ensure_ascii=False, indent=2)}")

            code = sign_data.get("code", 0)
            if code == 0:
                awards = sign_data.get("data", {}).get("awards", [])
                if awards:
                    award_text = ", ".join(
                        f"{a.get('resource', {}).get('name', '未知')} x{a.get('count', 0)}"
                        for a in awards
                    )
                    print(f"  ✅ {nickname}：签到成功！获得：{award_text}")
                else:
                    print(f"  ✅ {nickname}：签到成功！")
            else:
                msg = sign_data.get("message", "未知错误")
                if "请勿重复签到" in msg:
                    print(f"  ℹ️ {nickname}：今日已签到")
                else:
                    print(f"  ❌ {nickname}：签到失败 - {msg}")

    print("\n" + "=" * 50)
    print("  测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
