# tdxhub

tdxhub 是一个基于 mootdx 的维护中 fork，定位是通达信数据接入层，面向沪深 A 股、ETF、指数以及部分扩展市场的数据抓取、解析与落地。

这个仓库当前用于实际项目接入，因此 README 以本 fork 的真实状态为准，不再沿用上游的官网、镜像和发布说明。

## 项目定位

- 仓库地址: <https://github.com/dare2live/tdxhub>
- 上游来源: <https://github.com/mootdx/mootdx>
- Python 包名: `tdxhub`
- 当前版本: `0.12.0`
- Python 版本: `3.9+`
- 开源协议: MIT

注意: 仓库名是 tdxhub，但为了兼容既有项目，导入路径和命令行入口仍然保留为 `tdxhub`。

```python
from tdxhub.quotes import Quotes
from tdxhub.affair import Affair
```

## 当前能力范围

### 1. 标准市场行情

- 实时行情快照: `quotes`
- K 线: `bars`、`index_bars`、`k`
- 证券清单与市场信息: `stocks`、`stock_count`
- 分时/分笔: `minute`、`minutes`、`transaction`、`transactions`
- 基本面与资料: `finance`、`xdxr`、`block`、`F10C`、`F10`

### 2. 扩展市场行情

- 市场列表: `markets`
- 合约列表: `instruments` / `instrument`
- 实时报价: `quote`
- K 线与分时: `bars`、`minute`、`minutes`
- 分笔成交: `transaction`、`transactions`

### 3. 财务文件能力

- `Affair.files()` 获取远程财务文件清单
- `Affair.fetch()` 下载单个或全部文件
- `Affair.parse()` 解析 gpcw 财务文件为 records (`list[dict]`)

### 4. 本地离线数据读取

- `Reader.factory(...).daily()`
- `Reader.factory(...).minute()`
- `Reader.factory(...).fzline()`

### 5. 能力目录

仓库内置了能力清单模块，便于直接查看当前封装了哪些通达信能力:

```python
from tdxhub.capabilities import CAPABILITIES, summary

summary()
print(CAPABILITIES['std_quotes'])
```

## 安装

这个 fork 当前推荐直接从 GitHub 安装，而不是依赖上游 README 里的旧链接。

### 直接安装

```bash
pip install -U "git+https://github.com/dare2live/tdxhub.git"
```

如果需要命令行工具：

```bash
pip install -U "tdxhub[cli] @ git+https://github.com/dare2live/tdxhub.git"
```

如果需要 holiday / JS 扩展运行时：

```bash
pip install -U "tdxhub[racer] @ git+https://github.com/dare2live/tdxhub.git"
```

如果两者都需要：

```bash
pip install -U "tdxhub[cli,racer] @ git+https://github.com/dare2live/tdxhub.git"
```

### 本地开发安装

```bash
git clone https://github.com/dare2live/tdxhub.git
cd tdxhub
pip install -e ".[cli,racer]"
```

### Poetry

```bash
poetry install --extras cli --extras racer
```

## 快速示例

### 在线行情

```python
from tdxhub.quotes import Quotes

client = Quotes.factory(market='std', multithread=True, heartbeat=True)

# 实时行情
client.quotes(symbol=['600036', '000001'])

# 日线
client.bars(symbol='600036', frequency=9, offset=800)

# 指数日线
client.index_bars(symbol='000001', frequency=9, offset=800)

# 财务摘要
client.finance(symbol='600036')

# 除权除息
client.xdxr(symbol='600036')

# 分笔 / Tick
client.transaction(symbol='600036', start=0, offset=10)
client.transactions(symbol='600036', date='20240201', start=0, offset=10)
```

### 扩展市场

```python
from tdxhub.quotes import Quotes

ext_client = Quotes.factory(market='ext')

# 五档行情
ext_client.quote(symbol='42#IMCI')

# 日线
ext_client.bars(market=31, symbol='00020', frequency=9)
```

### 财务文件

```python
from tdxhub.affair import Affair

files = Affair.files()
filename = files[0]['filename']

Affair.fetch(downdir='tmp', filename=filename)
df = Affair.parse(downdir='tmp', filename=filename)
```

### 离线数据读取

```python
from tdxhub.reader import Reader

reader = Reader.factory(market='std', tdxdir='C:/new_tdx')
daily = reader.daily(symbol='600036')
minute = reader.minute(symbol='600036')
fzline = reader.fzline(symbol='600036')
```

## 命令行

安装后可以直接使用 `tdxhub` 命令:

```bash
tdxhub --help
tdxhub bestip -l 5
tdxhub bestip -c /path/to/connect.cfg -l 10
tdxhub quotes -s 600036 -a daily
tdxhub affair -l
tdxhub affair -f gpcw20241231.zip -d output
```

如果你需要先选择较优行情节点，可以先运行 `tdxhub bestip`。

## 与上游的关系

- 本仓库基于 mootdx 演进，但不再照搬上游 README、官网和镜像链接。
- 仓库名改为 tdxhub，用于表达“通达信数据接入层”的定位。
- 包名保持 `tdxhub`，这是兼容性选择，不代表当前 GitHub 仓库仍是上游项目本身。
- 文档优先描述这个 fork 当前已经实现并正在维护的内容。

## 问题与贡献

- 问题反馈: <https://github.com/dare2live/tdxhub/issues>
- 代码仓库: <https://github.com/dare2live/tdxhub>
