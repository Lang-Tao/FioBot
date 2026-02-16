"""游戏数据管理模块

负责下载、缓存和解析明日方舟游戏数据
包括角色表和卡池表
"""

import json
import re
from pathlib import Path
from typing import Optional

import httpx
from nonebot import logger


DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "mrfz"
CHAR_TABLE_FILE = DATA_DIR / "character_table.json"
GACHA_TABLE_FILE = DATA_DIR / "gacha_table.json"

# ==================== 职业映射 ====================

PROFESSION_MAP = {
    "PIONEER": "先锋干员",
    "WARRIOR": "近卫干员",
    "SNIPER": "狙击干员",
    "TANK": "重装干员",
    "MEDIC": "医疗干员",
    "SUPPORT": "辅助干员",
    "CASTER": "术师干员",
    "SPECIAL": "特种干员",
}

# 稀有度映射：支持新版 TIER_X 字符串和旧版数字格式
RARITY_MAP = {
    "TIER_1": 0, "TIER_2": 1, "TIER_3": 2,
    "TIER_4": 3, "TIER_5": 4, "TIER_6": 5,
}


def parse_rarity(raw_rarity) -> int:
    """将 rarity 字段统一转换为 0-based 数字 (0=1★, 5=6★)"""
    if isinstance(raw_rarity, int):
        return raw_rarity
    if isinstance(raw_rarity, str):
        if raw_rarity in RARITY_MAP:
            return RARITY_MAP[raw_rarity]
        # 尝试直接转数字
        try:
            return int(raw_rarity)
        except ValueError:
            pass
    return -1

# ==================== 数据下载与缓存 ====================


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


async def download_game_data(char_url: str, gacha_url: str, force: bool = False):
    """
    下载游戏数据并缓存到本地

    Args:
        char_url: character_table.json 下载地址
        gacha_url: gacha_table.json 下载地址
        force: 是否强制重新下载
    """
    _ensure_dir()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=60, headers=headers, follow_redirects=True) as client:
        if force or not CHAR_TABLE_FILE.exists():
            logger.info("正在下载 character_table.json ...")
            resp = await client.get(char_url)
            resp.raise_for_status()
            CHAR_TABLE_FILE.write_bytes(resp.content)
            logger.info(f"character_table.json 下载完成 ({len(resp.content)} bytes)")

        if force or not GACHA_TABLE_FILE.exists():
            logger.info("正在下载 gacha_table.json ...")
            resp = await client.get(gacha_url)
            resp.raise_for_status()
            GACHA_TABLE_FILE.write_bytes(resp.content)
            logger.info(f"gacha_table.json 下载完成 ({len(resp.content)} bytes)")


def is_data_ready() -> bool:
    """检查游戏数据是否已就绪"""
    return CHAR_TABLE_FILE.exists() and GACHA_TABLE_FILE.exists()


# ==================== 数据解析 ====================


def load_character_table() -> dict:
    """加载角色表"""
    with open(CHAR_TABLE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_gacha_table() -> dict:
    """加载卡池表"""
    with open(GACHA_TABLE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_all_recruit_tags(gacha_table: dict) -> list[str]:
    """从卡池表获取所有合法公招标签名"""
    return [tag["tagName"] for tag in gacha_table.get("gachaTags", [])]


def parse_recruit_pool(gacha_table: dict) -> set[str]:
    """
    从 recruitDetail 解析当前公招可用干员名单

    recruitDetail 格式举例:
      ★\\n干员1/干员2\\n\\n★★\\n干员3/干员4
    """
    recruit_detail = gacha_table.get("recruitDetail", "")
    # 去掉星号和空行，提取干员名
    names = set()
    for line in recruit_detail.replace("\\n", "\n").split("\n"):
        line = line.strip()
        if not line or line.startswith("★") or line.startswith("<"):
            continue
        # 去除 html 标签
        line = re.sub(r"<[^>]+>", "", line)
        line = line.replace("/", " ").replace("／", " ")
        for name in line.split():
            name = name.strip()
            if name and name != "-":
                names.add(name)
    return names


def build_recruit_data(
    char_url: str = "", gacha_url: str = ""
) -> tuple[list[dict], list[str]]:
    """
    构建公招数据：为每个可招募干员生成完整标签集

    Returns:
        (operators, valid_tags)
        operators: [{name, rarity, tags: set[str]}, ...]
        valid_tags: 合法标签列表
    """
    char_table = load_character_table()
    gacha_table = load_gacha_table()

    valid_tags = get_all_recruit_tags(gacha_table)
    recruit_pool = parse_recruit_pool(gacha_table)

    operators = []
    for char_id, char_data in char_table.items():
        if not isinstance(char_data, dict):
            continue

        name = char_data.get("name", "")
        if not name or name not in recruit_pool:
            continue

        rarity = parse_rarity(char_data.get("rarity", 0))  # 0-based: 0=1★, 5=6★
        if rarity < 0:
            continue
        profession = char_data.get("profession", "")
        position = char_data.get("position", "")
        tag_list = char_data.get("tagList") or []

        # 构建完整标签集
        tags = set(tag_list)

        # 职业标签
        prof_name = PROFESSION_MAP.get(profession)
        if prof_name:
            tags.add(prof_name)

        # 位置标签
        if position == "MELEE":
            tags.add("近战位")
        elif position == "RANGED":
            tags.add("远程位")

        # 稀有度标签
        if rarity == 0:
            tags.add("支援机械")
        elif rarity == 4:
            tags.add("资深干员")
        elif rarity == 5:
            tags.add("高级资深干员")

        operators.append({
            "name": name,
            "rarity": rarity,  # 0-based
            "tags": tags,
        })

    return operators, valid_tags
