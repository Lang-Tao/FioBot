from pydantic import BaseModel


class Config(BaseModel):
    """明日方舟公招识别插件配置"""
    # 游戏数据源 URL（使用 jsdelivr CDN 加速，国内可直达）
    mrfz_character_table_url: str = (
        "https://cdn.jsdelivr.net/gh/Kengxxiao/ArknightsGameData@master/zh_CN/gamedata/excel/character_table.json"
    )
    mrfz_gacha_table_url: str = (
        "https://cdn.jsdelivr.net/gh/Kengxxiao/ArknightsGameData@master/zh_CN/gamedata/excel/gacha_table.json"
    )

    # 百度 OCR 配置（用于公招截图识别）
    # 通过 .env 文件注入，不要在代码中硬编码
    baidu_ocr_api_key: str = ""
    baidu_ocr_secret_key: str = ""
