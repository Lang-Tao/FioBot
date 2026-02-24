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
  background: linear-gradient(168deg, #f5ebe1 0%, #f0e3d8 35%, #ede0d8 65%, #f2e8e2 100%);
  font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;
  padding: 0;
  position: relative;
  overflow: hidden;
}

/* ---- 顶部横幅 ---- */
.header {
  background: linear-gradient(135deg, #e8d0c2 0%, #dcc0b5 40%, #d8bbb2 100%);
  padding: 36px 24px 28px;
  text-align: center;
  border-radius: 0 0 28px 28px;
  position: relative;
}
.header::before {
  content: "";
  position: absolute;
  top: 12px; left: 28px; right: 28px; bottom: 12px;
  border: 2px dashed rgba(255,255,255,0.35);
  border-radius: 18px;
  pointer-events: none;
}
.header h1 {
  font-size: 26px;
  font-weight: 700;
  color: #6e4040;
  letter-spacing: 2px;
  text-shadow: 0 1px 0 rgba(255,240,230,0.5);
}
.header .sub {
  font-size: 13px;
  color: #9e8585;
  margin-top: 6px;
  letter-spacing: 1px;
}
.header .flower { font-size: 16px; vertical-align: middle; }

/* ---- 内容区 ---- */
.content {
  display: flex;
  gap: 14px;
  padding: 22px 24px 16px;
}
.column {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---- 卡片 ---- */
.card {
  background: rgba(255,252,248,0.78);
  border-radius: 16px;
  padding: 18px 16px 14px;
  box-shadow: 0 2px 10px rgba(120,90,80,0.07), 0 0.5px 2px rgba(80,50,40,0.04);
  border: 1px solid rgba(210,195,185,0.45);
}

/* 分类标题 badge */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px 5px 10px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}
.badge .icon { font-size: 15px; }

/* 指令列表 */
.cmd-list {
  list-style: none;
}
.cmd-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
}
.cmd-item + .cmd-item {
  border-top: 1px dashed rgba(180,160,150,0.30);
}
.cmd-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}
.cmd-body {
  flex: 1;
  min-width: 0;
}
.cmd-name {
  font-size: 13px;
  font-weight: 600;
  font-family: "Consolas", "Menlo", "Noto Sans SC", monospace;
  word-break: break-all;
}
.cmd-desc {
  font-size: 11px;
  color: #a09088;
  margin-top: 2px;
}

/* ---- 底部 ---- */
.footer {
  text-align: center;
  padding: 6px 0 24px;
  font-size: 11px;
  color: #baa8a0;
  letter-spacing: 2px;
}
.footer .dot {
  display: inline-block;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: #d8c8c0;
  vertical-align: middle;
  margin: 0 8px;
}
"""


# ==================== HTML 构建 ====================


def _build_card_html(section: dict) -> str:
    """构建单个分类卡片的 HTML"""
    key = section["key"]
    style = SECTION_COLORS.get(key, SECTION_COLORS["skland"])
    accent = style["accent"]
    light = style["light"]
    icon = section.get("icon", "•")

    parts: list[str] = []
    parts.append(f'<div class="card">')

    # badge
    parts.append(
        f'<div class="badge" style="background:{light};color:{accent};">'
        f'<span class="icon">{icon}</span> {section["title"]}'
        f'</div>'
    )

    # commands
    parts.append('<ul class="cmd-list">')
    for cmd_name, cmd_desc in section["commands"]:
        parts.append(
            f'<li class="cmd-item">'
            f'  <span class="cmd-dot" style="background:{accent};"></span>'
            f'  <div class="cmd-body">'
            f'    <div class="cmd-name" style="color:{accent};">{cmd_name}</div>'
            f'    <div class="cmd-desc">{cmd_desc}</div>'
            f'  </div>'
            f'</li>'
        )
    parts.append('</ul>')
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

    # 双列内容
    parts.append('<div class="content">')

    # 左列
    parts.append('<div class="column">')
    for sec in LEFT_COL:
        parts.append(_build_card_html(sec))
    parts.append('</div>')

    # 右列
    parts.append('<div class="column">')
    for sec in RIGHT_COL:
        parts.append(_build_card_html(sec))
    parts.append('</div>')

    parts.append('</div>')

    # Footer
    parts.append(
        '<div class="footer">'
        '<span class="dot"></span> fiobot <span class="dot"></span>'
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
