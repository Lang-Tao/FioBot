from pydantic import BaseModel


class Config(BaseModel):
    """复读插件配置"""

    # 连续相同消息达到多少条后触发（包含不同用户的发送）
    repeater_min_messages: int = 3

    # 至少需要多少个不同用户参与复读
    repeater_min_users: int = 3

    # 复读统计的时间窗口（秒）；超过该间隔视为新一轮
    repeater_window_seconds: float = 15.0

    # 每个群的触发冷却（秒）；防止短时间内频繁复读
    repeater_cooldown_seconds: float = 10.0
