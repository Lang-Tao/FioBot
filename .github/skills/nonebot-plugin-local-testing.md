---
title: "NoneBot2 插件本地化测试"
description: "在不启动 NoneBot2 框架的情况下，通过 mock 机制本地测试插件的核心逻辑，特别是涉及外部 API 调用的功能。"
---

# NoneBot2 插件本地化测试技能

## 适用场景

当需要测试 NoneBot2 插件中**不依赖消息收发**的核心业务逻辑时（如 OCR 识别、数据解析、算法计算），无需启动完整的 NoneBot2 + OneBot 环境，直接用 `python test.py` 即可验证。

## 核心思路

NoneBot2 插件的 `__init__.py` 会在被 import 时执行 `from nonebot import on_command` 等框架级导入，导致脱离框架运行时 ImportError。解决方案是 **在 import 项目模块之前，先用 `types.ModuleType` mock 掉 nonebot 及其子模块**。

## 步骤

### 1. 确保敏感配置通过 `.env` 管理

```dotenv
# .env（已在 .gitignore 中排除）
BAIDU_OCR_API_KEY=your_api_key
BAIDU_OCR_SECRET_KEY=your_secret_key
```

使用 `python-dotenv` 在测试脚本中加载：

```python
from dotenv import load_dotenv
load_dotenv()
```

### 2. Mock NoneBot2 框架模块

在 import 任何项目代码 **之前**，注入 mock 模块：

```python
import sys
import types
import logging

# 用标准 logging 替代 nonebot.logger
logging.basicConfig(level=logging.DEBUG)
_logger = logging.getLogger("test")

# mock nonebot 主模块
mock_nonebot = types.ModuleType("nonebot")
mock_nonebot.logger = _logger
mock_nonebot.get_plugin_config = lambda x: x()
sys.modules["nonebot"] = mock_nonebot

# mock nonebot 子模块（按需添加）
for name in [
    "nonebot.plugin", "nonebot.params",
    "nonebot.adapters", "nonebot.adapters.onebot",
    "nonebot.adapters.onebot.v11",
]:
    sys.modules[name] = types.ModuleType(name)

# 补齐子模块中被 import 的属性
sys.modules["nonebot"].on_command = lambda *a, **kw: type(
    "FakeMatcher", (), {"handle": lambda self: lambda f: f}
)()
sys.modules["nonebot.plugin"].PluginMetadata = type(
    "PluginMetadata", (), {"__init__": lambda self, **kw: None}
)
sys.modules["nonebot.params"].CommandArg = lambda: None
sys.modules["nonebot.adapters.onebot.v11"].Message = object
sys.modules["nonebot.adapters.onebot.v11"].MessageSegment = object
sys.modules["nonebot.adapters.onebot.v11"].MessageEvent = object
```

> **关键**：mock 代码必须在 `from fio_bot.plugins.xxx import yyy` 之前执行，否则 Python 解析 `__init__.py` 时会触发真实导入。

### 3. 导入并调用业务逻辑

mock 完成后，正常 import 插件中拆分出的纯逻辑模块：

```python
from fio_bot.plugins.mrfz.ocr import ocr_image
from fio_bot.plugins.mrfz.game_data import build_recruit_data, is_data_ready
from fio_bot.plugins.mrfz.recruit import extract_tags_from_ocr, find_recruit_combinations, format_results
```

### 4. 用 asyncio.run 驱动异步函数

NoneBot2 插件中的函数通常是 `async` 的，在测试脚本中用 `asyncio.run()` 驱动：

```python
import asyncio

async def main():
    image_data = Path("testpic.png").read_bytes()
    ocr_lines = await ocr_image(image_data, api_key, secret_key)
    tags = extract_tags_from_ocr(ocr_lines, valid_tags)
    results = find_recruit_combinations(tags, operators)
    print(format_results(results))

if __name__ == "__main__":
    asyncio.run(main())
```

### 5. 运行

```bash
python test.py
```

## 需要额外 mock 的常见场景

| 插件用到的功能                      | Mock 方式                                   |
| ----------------------------------- | ------------------------------------------- |
| `nonebot.on_command`                | 返回 FakeMatcher（带空 `.handle()` 装饰器） |
| `nonebot.get_plugin_config(Config)` | `lambda x: x()` 创建默认 Config 实例        |
| `nonebot.logger`                    | 标准库 `logging.getLogger()`                |
| `PluginMetadata`                    | 空类 `type("PluginMetadata", (), {...})`    |
| `MessageEvent` / `Message`          | `object` 占位                               |
| 数据库/Redis 连接                   | 用 SQLite 内存数据库或 `fakeredis` 替代     |

## 设计建议

为了让插件更容易测试，建议在编写插件时：

1. **分离核心逻辑与框架胶水代码**：将算法、数据处理放在独立 `.py` 文件中（如 `recruit.py`、`ocr.py`），`__init__.py` 只负责命令注册和消息流转。
2. **外部 API 配置不硬编码**：通过 `.env` + Pydantic Config 注入，方便本地测试和 CI/CD。
3. **异步函数保持纯粹**：避免在业务函数中直接调用 `matcher.send()`，而是返回结果让 handler 发送。
