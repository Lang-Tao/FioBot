"""公招标签组合计算模块

核心算法：给定用户选择的标签，计算所有有价值的标签组合及匹配干员
"""

import itertools
import re
from typing import Optional


# ==================== 标签别名/缩写 ====================

TAG_ALIASES = {
    # 资质类
    "高资": "高级资深干员", "高姿": "高级资深干员", "高级": "高级资深干员", "高级资深": "高级资深干员",
    "资深": "资深干员", "资干": "资深干员",
    "机械": "支援机械", "支机": "支援机械",
    # 位置类
    "近战": "近战位", "远程": "远程位",
    # 职业类（缩写 → 全称）
    "近卫": "近卫干员", "狙击": "狙击干员", "重装": "重装干员",
    "医疗": "医疗干员", "辅助": "辅助干员", "术师": "术师干员",
    "术士": "术师干员",  # 常见错字
    "特种": "特种干员", "先锋": "先锋干员",
    # 能力类
    "回费": "费用回复", "费回": "费用回复", "恢复": "费用回复",
    "快活": "快速复活", "复活": "快速复活", "快速": "快速复活",
    # 完整标签的自身映射（用户直接输入完整标签）
    "高级资深干员": "高级资深干员",
    "资深干员": "资深干员",
    "支援机械": "支援机械",
    "近战位": "近战位", "远程位": "远程位",
    "近卫干员": "近卫干员", "狙击干员": "狙击干员", "重装干员": "重装干员",
    "医疗干员": "医疗干员", "辅助干员": "辅助干员", "术师干员": "术师干员",
    "特种干员": "特种干员", "先锋干员": "先锋干员",
    "控场": "控场", "爆发": "爆发", "治疗": "治疗", "支援": "支援",
    "费用回复": "费用回复", "输出": "输出", "生存": "生存",
    "群攻": "群攻", "防护": "防护", "减速": "减速", "削弱": "削弱",
    "快速复活": "快速复活", "位移": "位移", "召唤": "召唤", "元素": "元素",
    "新手": "新手",
}


def smart_split_tags(text: str, valid_tags: list[str]) -> list[str]:
    """
    智能分词：支持用户输入无空格的标签连写（如"高资近卫输出"）

    1. 先按分隔符拆分
    2. 对无法直接识别的长段，尝试从已知别名/标签中贪婪匹配拆分
    """
    # 先按常规分隔符拆
    parts = re.split(r"[,，\s]+", text.strip())
    parts = [p.strip() for p in parts if p.strip()]

    # 构建所有可识别的关键词（别名 + 完整标签），按长度从长到短排序
    all_keywords = sorted(
        set(list(TAG_ALIASES.keys()) + list(valid_tags)),
        key=len,
        reverse=True,
    )

    result = []
    for part in parts:
        # 如果这个片段能直接被识别（在别名或合法标签中），直接保留
        if part in TAG_ALIASES or part in valid_tags:
            result.append(part)
            continue

        # 尝试贪婪拆分
        remaining = part
        found_any = False
        while remaining:
            matched = False
            for kw in all_keywords:
                if remaining.startswith(kw):
                    result.append(kw)
                    remaining = remaining[len(kw):]
                    matched = True
                    found_any = True
                    break
            if not matched:
                # 跳过一个字符继续尝试
                remaining = remaining[1:]

        # 如果完全没匹配到，保留原始片段让 normalize_tags 处理
        if not found_any:
            result.append(part)

    return result


def normalize_tags(raw_tags: list[str], valid_tags: list[str]) -> list[str]:
    """
    将用户输入的标签标准化为合法游戏标签

    Args:
        raw_tags: 用户输入的原始标签列表
        valid_tags: 游戏中所有合法标签

    Returns:
        标准化后的标签列表（去重）
    """
    result = []
    valid_set = set(valid_tags)

    for raw in raw_tags:
        raw = raw.strip()
        if not raw:
            continue

        # 优先完全匹配合法标签
        if raw in valid_set:
            if raw not in result:
                result.append(raw)
            continue

        # 别名映射
        mapped = TAG_ALIASES.get(raw)
        if mapped and mapped in valid_set:
            if mapped not in result:
                result.append(mapped)
            continue

        # 模糊匹配：用户输入是某个合法标签的子串
        for vt in valid_tags:
            if raw in vt:
                if vt not in result:
                    result.append(vt)
                break

    return result


# ==================== 星级显示 ====================

RARITY_STARS = {0: "★", 1: "★★", 2: "★★★", 3: "★★★★", 4: "★★★★★", 5: "★★★★★★"}


def rarity_display(rarity: int) -> str:
    """将 0-based 稀有度转换为星级显示"""
    return RARITY_STARS.get(rarity, f"{rarity + 1}★")


# ==================== 核心算法 ====================


def find_recruit_combinations(
    user_tags: list[str],
    operators: list[dict],
    max_combo_size: int = 3,
) -> list[dict]:
    """
    计算所有有价值的标签组合及匹配干员

    Args:
        user_tags: 用户选择的标签（已标准化）
        operators: 干员数据 [{name, rarity, tags}, ...]
        max_combo_size: 最大组合标签数（公招最多选 3 个标签）

    Returns:
        结果列表，按最低保底星级从高到低排序
        [{"tags": [...], "operators": [{name, rarity}, ...], "min_rarity": int}, ...]
    """
    results = []

    # 生成 1~max_combo_size 的所有标签组合
    for size in range(1, min(max_combo_size, len(user_tags)) + 1):
        for combo in itertools.combinations(user_tags, size):
            combo_set = set(combo)
            matched = []

            for op in operators:
                # 干员的标签集必须包含组合中的所有标签
                if not combo_set.issubset(op["tags"]):
                    continue

                # 6★ 保护：除非组合中有"高级资深干员"，否则跳过 6★
                if op["rarity"] == 5 and "高级资深干员" not in combo_set:
                    continue

                matched.append({"name": op["name"], "rarity": op["rarity"]})

            if not matched:
                continue

            # 计算这个组合的最低保底稀有度
            min_rarity = min(m["rarity"] for m in matched)
            max_rarity = max(m["rarity"] for m in matched)

            # 只保留高价值组合：保底 4★+ 或必出 1★（支援机械），跳过 2★ 和 3★
            if min_rarity in (1, 2):
                continue

            # 1★ 组合仅在"必出"时保留（所有匹配干员都是 1★）
            if min_rarity == 0:
                if max_rarity > 0:
                    continue
                matched = [m for m in matched if m["rarity"] == 0]

            # 按稀有度从高到低排序匹配干员
            matched.sort(key=lambda x: (-x["rarity"], x["name"]))

            results.append({
                "tags": list(combo),
                "operators": matched,
                "min_rarity": min_rarity,
            })

    # 按最低保底星级从高到低排序，相同则按标签数从少到多
    results.sort(key=lambda x: (-x["min_rarity"], len(x["tags"])))

    return results


def extract_tags_from_ocr(ocr_lines: list[str], valid_tags: list[str]) -> list[str]:
    """
    从 OCR 识别结果中提取公招标签

    公招截图中的标签通常是标准的游戏标签名，直接做完全匹配即可。
    也会尝试从长文本中提取已知标签子串。

    Args:
        ocr_lines: OCR 识别出的文字行列表
        valid_tags: 所有合法的公招标签

    Returns:
        提取到的标签列表（去重）
    """
    found_tags: list[str] = []
    valid_set = set(valid_tags)

    for line in ocr_lines:
        line = line.strip()
        if not line:
            continue

        # 1. 完全匹配
        if line in valid_set:
            if line not in found_tags:
                found_tags.append(line)
            continue

        # 2. 别名匹配（OCR 可能识别出别名/错字）
        mapped = TAG_ALIASES.get(line)
        if mapped and mapped in valid_set:
            if mapped not in found_tags:
                found_tags.append(mapped)
            continue

        # 3. 子串匹配：在 OCR 识别的长文本中搜索已知标签
        for tag in valid_tags:
            if tag in line and tag not in found_tags:
                found_tags.append(tag)

    return found_tags


def format_results(results: list[dict]) -> str:
    """
    将计算结果格式化为文本

    Args:
        results: find_recruit_combinations 的返回值

    Returns:
        格式化的文本消息
    """
    if not results:
        return "没有找到有价值的标签组合喵~\n（只显示保底 4★ 及以上和 1★ 的组合）"

    lines = []
    for i, r in enumerate(results):
        tag_str = " + ".join(r["tags"])
        min_star = r["min_rarity"] + 1  # 转为 1-based

        # 标记高价值组合
        if min_star >= 5:
            prefix = "🌟"
        elif min_star >= 4:
            prefix = "⭐"
        elif min_star == 1:
            prefix = "🤖"
        else:
            prefix = "▪️"

        lines.append(f"{prefix}【{tag_str}】(保底 {min_star}★)")

        for op in r["operators"]:
            star = rarity_display(op["rarity"])
            lines.append(f"  {star} {op['name']}")

        if i < len(results) - 1:
            lines.append("")

    return "\n".join(lines)
