"""公招结果图片渲染模块

使用 Pillow 将公招组合计算结果绘制为图片
"""

import io
from PIL import Image, ImageDraw, ImageFont
from .recruit import rarity_display


# ==================== 颜色配置 ====================

# 背景与边框
BG_COLOR = (30, 30, 35)          # 深灰背景
CARD_BG = (45, 45, 52)           # 卡片背景
BORDER_COLOR = (70, 70, 80)      # 卡片边框

# 文字颜色
TEXT_WHITE = (240, 240, 240)
TEXT_GRAY = (170, 170, 180)
TEXT_TITLE = (255, 200, 80)      # 标题金色

# 稀有度颜色（0-based）
RARITY_COLORS = {
    0: (150, 150, 150),   # 1★ 灰色
    1: (200, 200, 200),   # 2★ 白色
    2: (100, 180, 255),   # 3★ 蓝色
    3: (200, 150, 255),   # 4★ 紫色
    4: (255, 200, 60),    # 5★ 金色
    5: (255, 120, 50),    # 6★ 橙色
}

# 保底星级高亮色
MIN_STAR_COLORS = {
    1: (150, 150, 150),
    4: (200, 150, 255),
    5: (255, 200, 60),
    6: (255, 120, 50),
}

# ==================== 字体 ====================

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取字体（带缓存），优先使用微软雅黑"""
    if size not in _font_cache:
        for name in ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc"]:
            try:
                _font_cache[size] = ImageFont.truetype(name, size)
                break
            except (OSError, IOError):
                continue
        else:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


# ==================== 渲染 ====================

# 布局常量
PADDING = 30
CARD_PADDING = 16
CARD_GAP = 12
IMG_WIDTH = 520


def render_recruit_result(tags: list[str], results: list[dict]) -> bytes:
    """
    将公招结果渲染为图片

    Args:
        tags: 用户识别到的标签列表
        results: find_recruit_combinations 的返回值

    Returns:
        PNG 图片的 bytes
    """
    font_title = _get_font(22)
    font_tag = _get_font(18)
    font_body = _get_font(16)
    font_small = _get_font(14)

    # ===== 预计算总高度 =====
    y = PADDING

    # 标题行
    y += 28 + 10

    # 识别标签行
    y += 22 + 16

    if not results:
        y += 40  # 空结果提示
    else:
        for r in results:
            # 每个组合卡片：标签头 + 干员列表
            card_h = CARD_PADDING  # 上内边距
            card_h += 24 + 8      # 标签行 + 间距
            card_h += len(r["operators"]) * 22  # 每个干员一行
            card_h += CARD_PADDING  # 下内边距
            y += card_h + CARD_GAP

    y += 18 + PADDING  # 底部签名 + 留白

    # ===== 创建画布 =====
    img = Image.new("RGB", (IMG_WIDTH, y), BG_COLOR)
    draw = ImageDraw.Draw(img)

    cy = PADDING

    # ===== 绘制标题 =====
    draw.text((PADDING, cy), "🔍 明日方舟公招分析", fill=TEXT_TITLE, font=font_title)
    cy += 28 + 10

    # ===== 绘制识别标签 =====
    tag_text = "识别标签：" + "、".join(tags)
    draw.text((PADDING, cy), tag_text, fill=TEXT_GRAY, font=font_tag)
    cy += 22 + 16

    # ===== 空结果 =====
    if not results:
        draw.text(
            (PADDING, cy),
            "没有找到有价值的标签组合喵~",
            fill=TEXT_GRAY,
            font=font_body,
        )
        return _to_bytes(img)

    # ===== 绘制每个组合卡片 =====
    content_width = IMG_WIDTH - PADDING * 2

    for r in results:
        min_star = r["min_rarity"] + 1
        tag_str = " + ".join(r["tags"])

        # 卡片高度
        card_h = CARD_PADDING + 24 + 8 + len(r["operators"]) * 22 + CARD_PADDING

        # 卡片背景 + 左侧色条
        card_rect = (PADDING, cy, PADDING + content_width, cy + card_h)
        draw.rounded_rectangle(card_rect, radius=8, fill=CARD_BG, outline=BORDER_COLOR)

        # 左侧色条
        bar_color = MIN_STAR_COLORS.get(min_star, (100, 180, 255))
        draw.rectangle(
            (PADDING, cy + 4, PADDING + 4, cy + card_h - 4),
            fill=bar_color,
        )

        # 标签组合标题
        ix = PADDING + CARD_PADDING
        iy = cy + CARD_PADDING

        # 保底星级标记
        star_label = f"保底{min_star}★"
        star_color = MIN_STAR_COLORS.get(min_star, TEXT_WHITE)

        # 先绘制星级标签（右侧）
        star_bbox = draw.textbbox((0, 0), star_label, font=font_small)
        star_w = star_bbox[2] - star_bbox[0]
        star_x = PADDING + content_width - CARD_PADDING - star_w
        draw.text((star_x, iy + 2), star_label, fill=star_color, font=font_small)

        # 标签组合名（左侧）
        draw.text((ix, iy), f"【{tag_str}】", fill=TEXT_WHITE, font=font_tag)
        iy += 24 + 8

        # 干员列表
        for op in r["operators"]:
            rarity = op["rarity"]
            color = RARITY_COLORS.get(rarity, TEXT_WHITE)
            star_text = rarity_display(rarity)
            name = op["name"]

            draw.text((ix, iy), f"{star_text}", fill=color, font=font_body)
            # 星级文字后再绘制干员名
            star_text_w = draw.textbbox((0, 0), f"{star_text} ", font=font_body)[2]
            draw.text((ix + star_text_w, iy), name, fill=color, font=font_body)
            iy += 22

        cy += card_h + CARD_GAP

    # ===== 底部签名 =====
    footer = "Generated by fiobot"
    footer_bbox = draw.textbbox((0, 0), footer, font=font_small)
    footer_w = footer_bbox[2] - footer_bbox[0]
    draw.text(
        ((IMG_WIDTH - footer_w) // 2, cy),
        footer,
        fill=(100, 100, 110),
        font=font_small,
    )

    return _to_bytes(img)


def _to_bytes(img: Image.Image) -> bytes:
    """将 PIL Image 转换为 PNG bytes"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
