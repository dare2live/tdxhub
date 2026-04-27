# 项目概述

tdxhub 是当前维护中的通达信数据接入层仓库，基于上游 mootdx 持续演进，面向沪深 A 股、ETF、指数以及部分扩展市场的数据抓取、解析与落地。

- 仓库地址: [https://github.com/dare2live/tdxhub](https://github.com/dare2live/tdxhub)
- 上游来源: [https://github.com/mootdx/mootdx](https://github.com/mootdx/mootdx)
- Python 包名: `tdxhub`
- 当前版本: `0.12.0`
- Python 版本: `3.9+`

## 当前定位

- 统一通达信行情、财务文件和离线数据读取能力
- 为实际项目提供稳定、可维护的接入层，而不是仅保留上游镜像
- 保持历史导入路径兼容，避免下游项目大面积改造

注意：仓库名是 `tdxhub`，但为了兼容既有代码，导入路径和命令行入口已重命名为 `tdxhub`。

```python
from tdxhub.quotes import Quotes
from tdxhub.affair import Affair
```

## 当前能力范围

- 标准市场行情：`quotes`、`bars`、`index_bars`、`k`、`minute`、`transaction`
- 基础数据与资料：`stocks`、`stock_count`、`finance`、`xdxr`、`block`、`F10`
- 财务文件能力：`Affair.files()`、`Affair.fetch()`、`Affair.parse()`
- 本地离线读取：`Reader.factory(...).daily()`、`minute()`、`fzline()`

## 运行环境

- 操作系统：`Windows / macOS / Linux`
- Python：`3.9+`
- 依赖基础：`tdxpy`、`httpx`、`tenacity`

## 安装入口

当前更推荐直接从 GitHub 安装本 fork，而不是参考上游历史说明：

```shell
pip install -U "git+https://github.com/dare2live/tdxhub.git"
```

如果你需要命令行工具，请安装 `cli` extra；如果你需要 holiday / JS 扩展运行时，请安装 `racer` extra。

如果你只是想先看典型调用方式，继续阅读 [快速上手](quick.md)。
