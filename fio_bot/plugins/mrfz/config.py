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
