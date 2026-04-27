# 快速上手

这份快速上手以当前 fork 的真实状态为准：仓库名是 `tdxhub`，导入路径已重命名为 `tdxhub`。

## 选择较优服务器

```shell
tdxhub bestip -l 5
```

## 在线行情读取

```python
from tdxhub.quotes import Quotes

client = Quotes.factory(market='std', multithread=True, heartbeat=True, bestip=True, timeout=15)

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

如果你本机已经安装通达信客户端，也可以先导入它的服务器列表再测速：

```shell
tdxhub bestip -c /path/to/connect.cfg -l 10
```

## 扩展市场

```python
from tdxhub.quotes import Quotes

ext_client = Quotes.factory(market='ext')

ext_client.quote(symbol='42#IMCI')
ext_client.bars(market=31, symbol='00020', frequency=9)
```

## 财务文件读取

```python
from tdxhub.affair import Affair

files = Affair.files()
filename = files[0]['filename']

Affair.fetch(downdir='tmp', filename=filename)

# 可直接解析全量字段，也可以只取需要的列
df = Affair.parse(downdir='tmp', filename=filename, columns=('code', 'report_date'))
```

## 离线数据读取

```python
from tdxhub.reader import Reader

reader = Reader.factory(market='std', tdxdir='C:/new_tdx')

daily = reader.daily(symbol='600036')
minute = reader.minute(symbol='600036')
fzline = reader.fzline(symbol='600036')
```

## 下一步

- 行情接口说明见 `api/quote1.md` 与 `api/quote2.md`
- 财务文件说明见 `api/affair.md`
- 如果你要在项目里统一接入，建议把第三方导入再封装一层，而不是在业务代码里到处直接 `import tdxhub`
