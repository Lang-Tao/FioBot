from pydantic import BaseModel


class Config(BaseModel):
    """复读插件配置"""

    # 开启后会在日志中输出计数/重置原因，便于排查未触发问题
    repeater_debug: bool = False

    # 连续相同消息达到多少条后触发（包含不同用户的发送）
    repeater_min_messages: int = 3

    # 至少需要多少个不同用户参与复读
    repeater_min_users: int = 3

    # 复读统计的时间窗口（秒）；超过该间隔视为新一轮
    repeater_window_seconds: float = 180.0

    # 每个群的触发冷却（秒）；防止短时间内频繁复读
    repeater_cooldown_seconds: float = 10.0

    # ==================== 首字母联想复读 ====================

    # 是否启用“拼音首字母相同但内容不同”的联想复读
    repeater_initialism_enabled: bool = True

    # 首字母联想触发所需的消息条数
    repeater_initialism_min_messages: int = 2

    # 首字母联想触发所需的不同用户数
    repeater_initialism_min_users: int = 2

    # 首字母联想允许的首字母串长度范围（过短/过长都容易误触）
    repeater_initialism_min_len: int = 2
    repeater_initialism_max_len: int = 12
