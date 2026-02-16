"""JSON 文件存储模块

为每个 QQ 用户保存森空岛凭据和角色绑定信息
数据保存在 data/skland/users.json
"""

import json
from pathlib import Path
from typing import Optional, Any

from nonebot import logger


DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "skland"
USERS_FILE = DATA_DIR / "users.json"


def _ensure_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_data() -> dict:
    """加载所有用户数据"""
    _ensure_dir()
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载用户数据失败: {e}")
    return {}


def _save_data(data: dict):
    """保存所有用户数据"""
    _ensure_dir()
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存用户数据失败: {e}")


def get_user(user_id: str) -> Optional[dict]:
    """
    获取用户数据

    Returns:
        用户数据字典, 不存在时返回 None
    """
    data = _load_data()
    return data.get(str(user_id))


def save_user(user_id: str, user_data: dict):
    """保存用户数据"""
    data = _load_data()
    data[str(user_id)] = user_data
    _save_data(data)


def delete_user(user_id: str):
    """删除用户数据"""
    data = _load_data()
    data.pop(str(user_id), None)
    _save_data(data)


def get_all_users() -> dict:
    """获取所有用户数据"""
    return _load_data()


def update_user_field(user_id: str, field: str, value: Any):
    """更新用户的某个字段"""
    data = _load_data()
    uid = str(user_id)
    if uid in data:
        data[uid][field] = value
        _save_data(data)
