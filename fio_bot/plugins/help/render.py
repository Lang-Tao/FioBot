"""帮助菜单图片渲染模块

使用 nonebot-plugin-htmlkit 渲染帮助菜单图片
本地预览：python fio_bot/plugins/help/render.py
"""

from __future__ import annotations


# ==================== 帮助数据 ====================

HELP_SECTIONS = [
    {
        "title": "森空岛",
        "icon": "🌲",
        "key": "skland",
        "commands": [
            ("森空岛绑定 &lt;token&gt;", "绑定账号（私聊）"),
            ("扫码绑定", "扫码绑定账号"),
            ("明日方舟签到", "为绑定角色签到"),
            ("角色列表", "查看绑定角色"),
            ("角色更新", "刷新绑定信息"),
        ],
    },
    {
        "title": "公招识别",
        "icon": "🎯",
        "key": "mrfz",
        "commands": [
            ("公招 &lt;标签...&gt;", "计算最优组合"),
            ("公招 + 图片", "OCR 识别截图"),
        ],
    },
    {
        "title": "随机功能",
        "icon": "🎲",
        "key": "random",
        "commands": [
            ("fioll &lt;选项1&gt; &lt;选项2&gt; ...", "小fio帮你选一个"),
        ],
    },
    {
        "title": "BiliBili",
        "icon": "📺",
        "key": "bili",
        "commands": [
            ("发送B站链接或BV号", "提取三分钟以内的视频"),
            ("audio &lt;链接&gt;", "提取视频中的音频"),
        ],
    },
    {
        "title": "小红书",
        "icon": "📕",
        "key": "xhs",
        "commands": [
            ("发送小红书链接", "发送无水印原图"),
        ],
    },
]

# 双列分配：左列（森空岛 + B站），右列（公招 + 随机 + 小红书）
LEFT_COL = [HELP_SECTIONS[0], HELP_SECTIONS[3]]
RIGHT_COL = [HELP_SECTIONS[1], HELP_SECTIONS[2], HELP_SECTIONS[4]]

# 分区配色（暖玫瑰木色调）
SECTION_COLORS: dict[str, dict[str, str]] = {
    "skland":  {"accent": "#7d6b5d", "light": "#f0e8e0", "grad_from": "#f0e8e0", "grad_to": "#e8ddd2"},
    "mrfz":    {"accent": "#8b6565", "light": "#f2e6e4", "grad_from": "#f2e6e4", "grad_to": "#e8d8d5"},
    "random":  {"accent": "#b07860", "light": "#f5ece5", "grad_from": "#f5ece5", "grad_to": "#ecddd2"},
    "bili":    {"accent": "#7c6268", "light": "#f0e5e8", "grad_from": "#f0e5e8", "grad_to": "#e5d8dc"},
    "xhs":     {"accent": "#a06058", "light": "#f5e5e2", "grad_from": "#f5e5e2", "grad_to": "#ecd8d4"},
}


# ==================== CSS ====================

_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  width: 640px;
  background: #f0e5dc;
  font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;
  padding: 0;
}

/* ---- 顶部横幅 ---- */
.header {
  background: #dcc0b5;
  padding: 36px 24px 28px;
  text-align: center;
  border-radius: 0 0 28px 28px;
}
.header h1 {
  font-size: 26px;
  font-weight: 700;
  color: #6e4040;
  letter-spacing: 2px;
}
.header .sub {
  font-size: 13px;
  color: #9e8585;
  margin-top: 6px;
  letter-spacing: 1px;
}
.header .flower { font-size: 16px; }

/* ---- 内容区（双列） ---- */
.content-table {
  width: 100%;
  padding: 22px 24px 16px;
}
.content-table td {
  width: 50%;
  vertical-align: top;
}
.content-table td.left-col {
  padding-right: 7px;
}
.content-table td.right-col {
  padding-left: 7px;
}

/* ---- 卡片 ---- */
.card {
  background: #fffcf8;
  border-radius: 14px;
  padding: 18px 16px 14px;
  border: 1px solid #ddd0c8;
  margin-bottom: 14px;
}

/* 分类标题 badge */
.badge {
  display: inline-block;
  padding: 5px 14px 5px 10px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}
.badge .icon { font-size: 15px; }

/* 指令条目 */
.cmd-item {
  padding: 6px 0;
  border-top: 1px dashed #e0d5d0;
}
.cmd-item:first-child {
  border-top: none;
}
.cmd-dot {
  font-size: 8px;
  margin-right: 6px;
}
.cmd-name {
  font-size: 13px;
  font-weight: 600;
}
.cmd-desc {
  font-size: 11px;
  color: #a09088;
  margin-top: 2px;
  padding-left: 15px;
}

/* ---- 底部 ---- */
.footer {
  text-align: center;
  padding: 6px 0 24px;
  font-size: 11px;
  color: #baa8a0;
  letter-spacing: 2px;
}
"""


# ==================== HTML 构建 ====================


def _build_card_html(section: dict) -> str:
    """构建单个分类卡片的 HTML"""
    key = section["key"]
    style = SECTION_COLORS.get(key, SECTION_COLORS["skland"])
    accent = style["accent"]
    light = style["light"]
    icon = section.get("icon", "")

    parts: list[str] = []
    parts.append('<div class="card">')

    # badge
    parts.append(
        f'<div class="badge" style="background:{light};color:{accent};">'
        f'<span class="icon">{icon}</span> {section["title"]}'
        f'</div>'
    )

    # commands
    for cmd_name, cmd_desc in section["commands"]:
        parts.append(
            f'<div class="cmd-item">'
            f'  <span class="cmd-dot" style="color:{accent};">●</span>'
            f'  <span class="cmd-name" style="color:{accent};">{cmd_name}</span>'
            f'  <div class="cmd-desc">{cmd_desc}</div>'
            f'</div>'
        )

    parts.append('</div>')
    return "\n".join(parts)


def _build_html() -> str:
    """构建完整帮助菜单 HTML"""
    parts: list[str] = []
    parts.append(f'<html><head><meta charset="utf-8"><style>{_CSS}</style></head><body>')

    # 头部
    parts.append(
        '<div class="header">'
        '  <h1><span class="flower">✿</span> FioBOT 指令帮助 <span class="flower">✿</span></h1>'
        '  <div class="sub">fiop / fio帮助</div>'
        '</div>'
    )

    # 双列内容（用 table 布局，litehtml 兼容性最好）
    parts.append('<table class="content-table"><tr>')

    # 左列
    parts.append('<td class="left-col">')
    for sec in LEFT_COL:
        parts.append(_build_card_html(sec))
    parts.append('</td>')

    # 右列
    parts.append('<td class="right-col">')
    for sec in RIGHT_COL:
        parts.append(_build_card_html(sec))
    parts.append('</td>')

    parts.append('</tr></table>')

    # Footer
    parts.append(
        '<div class="footer">'
        '· fiobot ·'
        '</div>'
    )

    parts.append('</body></html>')
    return "\n".join(parts)


# ==================== 渲染入口 ====================


async def render_help_image() -> bytes:
    """渲染帮助菜单图片，返回 PNG bytes"""
    from nonebot import require

    require("nonebot_plugin_htmlkit")
    from nonebot_plugin_htmlkit import html_to_pic

    html = _build_html()
    return await html_to_pic(html=html, max_width=640)


# ==================== 本地预览 ====================


def _preview():
    """生成 HTML 并在浏览器中打开预览"""
    import tempfile
    import webbrowser

    html = _build_html()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        path = f.name

    webbrowser.open(path)
    print(f"已在浏览器中打开预览：{path}")


if __name__ == "__main__":
    _preview()
