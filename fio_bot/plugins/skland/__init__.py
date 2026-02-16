"""
森空岛插件 - 通过森空岛查询明日方舟游戏数据

功能:
  - 森空岛绑定 <token/cred>: 绑定账号（私聊）
  - 扫码绑定: 二维码扫码绑定
  - 明日方舟签到: 为绑定角色签到
  - 角色列表: 查看绑定的角色
  - 角色更新: 刷新角色绑定信息
"""

import asyncio
import base64
from io import BytesIO
from datetime import datetime, timedelta

from nonebot import on_command, logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import (
    Message,
    MessageSegment,
    Bot,
    MessageEvent,
    PrivateMessageEvent,
)
from nonebot.params import CommandArg

from .config import Config
from .api import (
    CRED,
    SklandAPI,
    SklandLoginAPI,
    SklandException,
    RequestException,
    LoginException,
    UnauthorizedException,
)
from . import storage


__plugin_meta__ = PluginMetadata(
    name="森空岛",
    description="通过森空岛查询明日方舟游戏数据，支持绑定、签到等功能",
    usage=(
        "森空岛绑定 <token/cred> - 绑定森空岛账号（私聊）\n"
        "扫码绑定 - 扫码绑定森空岛账号\n"
        "明日方舟签到 - 为绑定的角色签到\n"
        "角色列表 - 查看绑定的角色\n"
        "角色更新 - 更新角色绑定信息"
    ),
    config=Config,
)


# ==================== 辅助函数 ====================


async def refresh_cred_if_needed(user_data: dict) -> CRED | None:
    """
    尝试刷新过期凭据

    1. 先尝试 refresh_token 刷新 cred_token
    2. 失败则尝试用 access_token 重新走完整流程
    """
    try:
        new_token = await SklandLoginAPI.refresh_token(user_data["cred"])
        user_data["cred_token"] = new_token
        return CRED(cred=user_data["cred"], token=new_token)
    except SklandException:
        pass

    # 用 access_token 完全刷新
    if user_data.get("access_token"):
        try:
            grant_code = await SklandLoginAPI.get_grant_code(user_data["access_token"], 0)
            new_cred = await SklandLoginAPI.get_cred(grant_code)
            user_data["cred"] = new_cred.cred
            user_data["cred_token"] = new_cred.token
            user_data["user_id"] = new_cred.userId
            return new_cred
        except SklandException:
            pass

    return None


async def fetch_and_save_characters(user_id: str, user_data: dict, cred: CRED) -> list[dict]:
    """获取并保存角色绑定信息"""
    binding_list = await SklandAPI.get_binding(cred)
    characters = []
    for app in binding_list:
        app_code = app.get("appCode", "")
        for binding in app.get("bindingList", []):
            for role in binding.get("roles", []):
                characters.append({
                    "uid": role.get("roleId", ""),
                    "nickname": role.get("nickname", ""),
                    "app_code": app_code,
                    "channel_master_id": str(binding.get("channelMasterId", "")),
                    "is_default": role.get("isDefault", False),
                    "server_name": binding.get("channelName", ""),
                    "level": role.get("level", 0),
                })
    user_data["characters"] = characters
    storage.save_user(user_id, user_data)
    return characters


def format_ark_chars(ark_chars: list[dict]) -> str:
    """格式化明日方舟角色列表"""
    lines = []
    for c in ark_chars:
        server = "官服" if c["channel_master_id"] == "1" else "B服"
        lines.append(f"  {c['nickname']} | Lv.{c.get('level', '?')} | {server}")
    return "\n".join(lines)


# ==================== 命令定义 ====================

bind_cmd = on_command("森空岛绑定", priority=10, block=True)
qrcode_cmd = on_command("扫码绑定", priority=10, block=True)
sign_cmd = on_command("明日方舟签到", aliases={"方舟签到"}, priority=10, block=True)
char_list_cmd = on_command("角色列表", priority=10, block=True)
char_update_cmd = on_command("角色更新", priority=10, block=True)


# ==================== 绑定 ====================


@bind_cmd.handle()
async def handle_bind(event: MessageEvent, args: Message = CommandArg()):
    # 仅允许私聊，防止 token 泄露
    if not isinstance(event, PrivateMessageEvent):
        await bind_cmd.finish("请私聊我进行绑定操作喵~（token 是敏感信息）")

    token_or_cred = args.extract_plain_text().strip()
    if not token_or_cred:
        await bind_cmd.finish(
            "请输入 token 或 cred 喵~\n"
            "用法：森空岛绑定 <token/cred>\n"
            "token(24位): 森空岛APP - 设置 - 数据管理 - 使用凭证抓取\n"
            "cred(32位): 森空岛网页端 Cookie 中的 cred 字段"
        )

    user_id = str(event.user_id)
    existing = storage.get_user(user_id)

    try:
        if len(token_or_cred) == 24:
            # Token 绑定
            grant_code = await SklandLoginAPI.get_grant_code(token_or_cred, 0)
            cred = await SklandLoginAPI.get_cred(grant_code)
            user_data = {
                "access_token": token_or_cred,
                "cred": cred.cred,
                "cred_token": cred.token,
                "user_id": cred.userId,
                "characters": [],
            }
        elif len(token_or_cred) == 32:
            # Cred 绑定
            cred_token = await SklandLoginAPI.refresh_token(token_or_cred)
            cred = CRED(cred=token_or_cred, token=cred_token)
            sk_user_id = await SklandAPI.get_user_id(cred)
            user_data = {
                "access_token": None,
                "cred": token_or_cred,
                "cred_token": cred_token,
                "user_id": sk_user_id,
                "characters": [],
            }
        else:
            await bind_cmd.finish("格式不正确喵~\ntoken 应为 24 位，cred 应为 32 位")
            return

        # 获取并保存角色信息
        cred_obj = CRED(cred=user_data["cred"], token=user_data["cred_token"])
        characters = await fetch_and_save_characters(user_id, user_data, cred_obj)

        ark_chars = [c for c in characters if c["app_code"] == "arknights"]
        msg = "账号更新成功喵！" if existing else "绑定成功喵！"

        if ark_chars:
            msg += f"\n发现 {len(ark_chars)} 个明日方舟角色：\n{format_ark_chars(ark_chars)}"

        await bind_cmd.finish(msg)

    except SklandException as e:
        await bind_cmd.finish(f"绑定失败喵：{e}")


# ==================== 扫码绑定 ====================


@qrcode_cmd.handle()
async def handle_qrcode(bot: Bot, event: MessageEvent):
    try:
        import qrcode as qr_lib
    except ImportError:
        await qrcode_cmd.finish("扫码功能需要安装 qrcode 库喵~\n请运行: pip install qrcode[pil]")
        return

    user_id = str(event.user_id)

    try:
        scan_id = await SklandLoginAPI.get_scan()
        scan_url = f"hypergryph://scan_login?scanId={scan_id}"

        # 生成二维码图片
        qr = qr_lib.make(scan_url)
        buf = BytesIO()
        qr.save(buf, "PNG")
        qr_bytes = buf.getvalue()
        qr_b64 = base64.b64encode(qr_bytes).decode()

        await qrcode_cmd.send(
            Message(
                MessageSegment.text("请使用森空岛APP扫描下方二维码绑定账号喵~\n有效时间两分钟，请勿扫描他人二维码！\n")
                + MessageSegment.image(f"base64://{qr_b64}")
            )
        )

        # 轮询扫码状态 (最长 100 秒)
        scan_code = None
        end_time = datetime.now() + timedelta(seconds=100)

        while datetime.now() < end_time:
            try:
                scan_code = await SklandLoginAPI.get_scan_status(scan_id)
                break
            except RequestException:
                pass
            await asyncio.sleep(2)

        if not scan_code:
            await qrcode_cmd.finish("扫码超时了喵，请重新发起扫码绑定~")
            return

        # 扫码成功，完成绑定流程
        token = await SklandLoginAPI.get_token_by_scan_code(scan_code)
        grant_code = await SklandLoginAPI.get_grant_code(token, 0)
        cred = await SklandLoginAPI.get_cred(grant_code)

        user_data = {
            "access_token": token,
            "cred": cred.cred,
            "cred_token": cred.token,
            "user_id": cred.userId,
            "characters": [],
        }

        cred_obj = CRED(cred=cred.cred, token=cred.token)
        characters = await fetch_and_save_characters(user_id, user_data, cred_obj)

        ark_chars = [c for c in characters if c["app_code"] == "arknights"]
        msg = "扫码绑定成功喵！"
        if ark_chars:
            msg += f"\n发现 {len(ark_chars)} 个明日方舟角色：\n{format_ark_chars(ark_chars)}"

        await qrcode_cmd.finish(msg)

    except SklandException as e:
        await qrcode_cmd.finish(f"扫码绑定失败喵：{e}")


# ==================== 签到 ====================


@sign_cmd.handle()
async def handle_sign(event: MessageEvent):
    user_id = str(event.user_id)
    user_data = storage.get_user(user_id)

    if not user_data:
        await sign_cmd.finish("你还没有绑定森空岛账号喵~\n请先使用「森空岛绑定」或「扫码绑定」")

    characters = user_data.get("characters", [])
    ark_chars = [c for c in characters if c["app_code"] == "arknights"]

    if not ark_chars:
        await sign_cmd.finish("没有找到绑定的明日方舟角色喵~")

    cred = CRED(cred=user_data["cred"], token=user_data["cred_token"])

    results = []
    for char in ark_chars:
        try:
            sign_data = await SklandAPI.ark_sign(cred, char["uid"], char["channel_master_id"])
            awards = sign_data.get("awards", [])
            if awards:
                award_text = ", ".join(
                    f"{a.get('resource', {}).get('name', '未知')} x{a.get('count', 0)}"
                    for a in awards
                )
                results.append(f"✅ {char['nickname']}：签到成功！\n   获得：{award_text}")
            else:
                results.append(f"✅ {char['nickname']}：签到成功！")
        except UnauthorizedException:
            # 凭据过期，尝试刷新
            new_cred = await refresh_cred_if_needed(user_data)
            if new_cred:
                storage.save_user(user_id, user_data)
                cred = new_cred
                try:
                    sign_data = await SklandAPI.ark_sign(cred, char["uid"], char["channel_master_id"])
                    awards = sign_data.get("awards", [])
                    if awards:
                        award_text = ", ".join(
                            f"{a.get('resource', {}).get('name', '未知')} x{a.get('count', 0)}"
                            for a in awards
                        )
                        results.append(f"✅ {char['nickname']}：签到成功！\n   获得：{award_text}")
                    else:
                        results.append(f"✅ {char['nickname']}：签到成功！")
                except SklandException as e:
                    results.append(f"❌ {char['nickname']}：{e}")
            else:
                results.append(f"❌ {char['nickname']}：凭据已过期，请重新绑定")
        except SklandException as e:
            results.append(f"❌ {char['nickname']}：{e}")

    await sign_cmd.finish("\n".join(results))


# ==================== 角色列表 ====================


@char_list_cmd.handle()
async def handle_char_list(event: MessageEvent):
    user_id = str(event.user_id)
    user_data = storage.get_user(user_id)

    if not user_data:
        await char_list_cmd.finish("你还没有绑定森空岛账号喵~")

    characters = user_data.get("characters", [])
    if not characters:
        await char_list_cmd.finish("没有找到绑定的角色喵，试试「角色更新」~")

    ark_chars = [c for c in characters if c["app_code"] == "arknights"]
    other_chars = [c for c in characters if c["app_code"] != "arknights"]

    lines = ["📋 绑定角色列表："]

    if ark_chars:
        lines.append("\n🎮 明日方舟：")
        for c in ark_chars:
            server = "官服" if c["channel_master_id"] == "1" else "B服"
            default_mark = " ⭐" if c.get("is_default") else ""
            lines.append(f"  {c['nickname']} | Lv.{c.get('level', '?')} | {server}{default_mark}")

    if other_chars:
        lines.append("\n🎮 其他游戏：")
        for c in other_chars:
            lines.append(f"  {c['nickname']} ({c['app_code']})")

    await char_list_cmd.finish("\n".join(lines))


# ==================== 角色更新 ====================


@char_update_cmd.handle()
async def handle_char_update(event: MessageEvent):
    user_id = str(event.user_id)
    user_data = storage.get_user(user_id)

    if not user_data:
        await char_update_cmd.finish("你还没有绑定森空岛账号喵~")

    cred = CRED(cred=user_data["cred"], token=user_data["cred_token"])

    try:
        characters = await fetch_and_save_characters(user_id, user_data, cred)
        ark_chars = [c for c in characters if c["app_code"] == "arknights"]
        msg = f"角色信息更新成功喵！共 {len(characters)} 个角色"
        if ark_chars:
            msg += f"，其中明日方舟 {len(ark_chars)} 个"
        await char_update_cmd.finish(msg)
    except UnauthorizedException:
        new_cred = await refresh_cred_if_needed(user_data)
        if new_cred:
            storage.save_user(user_id, user_data)
            try:
                characters = await fetch_and_save_characters(user_id, user_data, new_cred)
                ark_chars = [c for c in characters if c["app_code"] == "arknights"]
                msg = f"角色信息更新成功喵！共 {len(characters)} 个角色"
                if ark_chars:
                    msg += f"，其中明日方舟 {len(ark_chars)} 个"
                await char_update_cmd.finish(msg)
            except SklandException as e:
                await char_update_cmd.finish(f"更新失败喵：{e}")
        else:
            await char_update_cmd.finish("凭据已过期，请重新绑定喵~")
    except SklandException as e:
        await char_update_cmd.finish(f"更新失败喵：{e}")
