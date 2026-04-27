# tdxhub Capability Map

**版本**: 0.12.0
**生成**: 2026-04-27 (Phase A-D 完成, mootdx → tdxhub 自主化后)

tdxhub 现已包装 **29 个数据接口** (来自 vendored `tdxhub/protocol/`, 即原 tdxpy/pytdx 协议层).

机器可读: [capability-manifest.json](capability-manifest.json) — 推荐让数据源 registry / 调用方代码读这份, 不要硬编码方法名.

---

## 一图看全 (按数据类别)

| 类别 | 方法数 | 主要接口 |
|---|---:|---|
| 历史数据 | 8 | `bars` / `index_bars` / `minutes` / `transactions` / `xdxr` / `k` / `ExtQuotes.bars` 等 |
| 实时数据 | 6 | `quotes` / `minute` / `transaction` / 扩展市场实时 |
| 基础信息 | 6 | `stocks` / `stock_count` / `block` / F10 等 |
| 基本面 | 3 | `finance` / `Affair.files` / `Affair.fetch` |
| 财务数据 | 3 | `Affair.parse` (gpcw 二进制 585 字段) |
| 离线数据 | 3 | `Reader.daily` / `Reader.minute` / `Reader.fzline` (.day/.lc1/.lc5) |

---

## 标准行情 `StdQuotes` (16 接口)

```python
from tdxhub.quotes import Quotes
cli = Quotes.factory(market="std")
```

| 方法 | 描述 | 底层 (tdxpy) | 限制 | 项目用了? |
|---|---|---|---|:---:|
| `quotes(symbol)` | 实时五档盘口 | `get_security_quotes` | 单次 ≤80 只 | ⬜ |
| `bars(symbol, frequency, offset)` | K线 (12 周期) | `get_security_bars` | 单次 ≤800 根 | ✅ |
| `index_bars(symbol, frequency, offset)` | 指数 K 线 | `get_index_bars` | 单次 ≤800 根 | ✅ |
| `stocks(market)` | 全市场代码 | `get_security_list` | 自动翻页 | ✅ |
| `stock_count(market)` | 市场证券数 | `get_security_count` | — | ✅ |
| `minute(symbol)` | 当日分时 | `get_minute_time_data` | 仅当日 | ⬜ |
| `minutes(symbol, date)` | 历史分时 | `get_history_minute_time_data` | 每次一天 | ⬜ |
| `transaction(symbol)` | 当日分笔 | `get_transaction_data` | offset 2000 | ⬜ |
| `transactions(symbol, date)` | 历史分笔 | `get_history_transaction_data` | 2000 条/次 | ⬜ |
| `xdxr(symbol)` | 除权除息 | `get_xdxr_info` | — | ✅ |
| `finance(symbol)` | 财务摘要 | `get_finance_info` | 单只 | ✅ |
| `k(symbol, begin, end)` | 日期范围 K 线 | `bars` 组合 | 跨日历分页 | ✅ |
| `block(group, custom)` | 板块/概念 | `get_and_parse_block_info` | block_*.dat 4 种 | ✅ |
| `F10C(symbol)` | F10 资料目录 | `get_company_info_category` | — | ⬜ |
| `F10(symbol, name)` | F10 详情 | `get_company_info_content` | 按标题查 | ⬜ |

**项目使用率: 8/15 = 53%**. 还有 7 个 (实时五档/分时/分笔/F10) 接但没用上.

---

## 扩展行情 `ExtQuotes` (8 接口)

期货 / 外汇 / 黄金 / 港股市场.

```python
ecli = Quotes.factory(market="ext")
```

| 方法 | 描述 | 底层 (tdxpy) | 项目用了? |
|---|---|---|:---:|
| `markets()` | 市场列表 | `TdxExHq_API.get_markets` | ⬜ |
| `instrument_info(...)` | 合约信息 | `get_instrument_info` | ⬜ |
| `instrument_count()` | 合约计数 | `get_instrument_count` | ⬜ |
| `instrument_quote(...)` | 实时报价 | `get_instrument_quote` | ⬜ |
| `bars(symbol, ...)` | K 线 | `get_instrument_bars` | ⬜ |
| `minute(...)` / `minutes(...)` | 分时 | 略 | ⬜ |
| `transaction(...)` / `transactions(...)` | 分笔 | 略 | ⬜ |

**项目使用率: 0/8 = 0%**. 当前业务以股票为主, 未触及.

---

## 财务文件 `Affair` (3 接口)

```python
from tdxhub.affair import Affair
```

| 方法 | 描述 | 底层 | 项目用了? |
|---|---|---|:---:|
| `Affair.files()` | gpcw 文件列表 (含 hash) | `get_report_file_by_size` + 直连 120.76.152.87 | ✅ (sync_financial) |
| `Affair.fetch(...)` | 下载 gpcw 文件 | 二进制 HTTP | ✅ |
| `Affair.parse(...)` | **解析 gpcw 二进制 (585 字段)** | 自实现 | ✅ |

gpcw 字段含三大报表 + 机构持仓 + 盈利预测. 这是 tdxhub 最有价值的独家能力.

---

## 离线读取 `Reader` (3 接口)

读本地通达信安装目录的 `.day` `.lc1` `.lc5` 文件.

```python
from tdxhub.reader import Reader
r = Reader.factory(market="std", tdxdir="C:/通达信")
```

| 方法 | 文件 | 项目用了? |
|---|---|:---:|
| `Reader.daily(symbol)` | `.day` 日线 | ⬜ |
| `Reader.minute(symbol)` | `.lc1` 1 分线 | ⬜ |
| `Reader.fzline(symbol)` | 5 分线 | ⬜ |

适合用户本机有 TDX 客户端的场景, 项目走在线接口足够, **未用**.

---

## tdxhub 相对 mootdx 上游的改进

| 改进 | 文件 | 备注 |
|---|---|---|
| **vendored tdxpy** (Phase A) | `tdxhub/protocol/` | 解除 pip tdxpy 依赖, 自主化 |
| **包重命名** (Phase B) | 全仓 | mootdx → tdxhub, 配置目录 ~/.mootdx → ~/.tdxhub |
| **117 台服务器整合** | `consts.py` | 合并 tdxpy 104 + mootdx 38 → 去重 117 |
| **gpcw 按列解析** | `financial/financial.py` | 历史改进 |
| **Bug 修复 (Phase D)** | 见下 |

### Phase D 修的 bug

| 文件 | 类型 | 说明 |
|---|---|---|
| `protocol/reader/min_bar_reader.py:43` | P0 | `Exception(...,filename)` 字符串格式化错, 改 f-string |
| `protocol/reader/daily_bar_reader.py:80,106` | P0 | 同上 (2 处) |
| `tools/reversion.py:78` | P0 | bare `except:` 吞 KeyboardInterrupt, 改 specific |
| `tools/reversion.py:18,43,104,112` | P1 | `fillna(method=)` pandas 2.2+ 弃用 → `.ffill()/.bfill()` |
| `utils/adjust.py:99,125` | P1 | 同上 |
| `quotes.py:136` | P1 | `value.all().empty` 逻辑混乱 → `value.empty` |

---

## 项目用得到 vs 用不到

(以 chunky-monkey-v2 为消费方)

### ✅ 已用 (8 类)
- `bars` / `index_bars` / `k` — K 线
- `xdxr` — 除权除息
- `finance` — 财务摘要
- `Affair.files/fetch/parse` — gpcw 财务文件
- `block` — 板块
- `stocks` / `stock_count` — 代码列表

### ⬜ 已实现可用但项目没接 (7 类, 零工程量直接吃)
1. **`quotes`** 实时五档 — 工作台股票卡片实时刷新
2. **`minute`** 当日分时 — 个股详情页分时图
3. **`minutes(date)`** 历史分时 — 事件回测精确入场点
4. **`transaction`** 当日分笔 — 龙虎榜资金分析补充
5. **`transactions(date)`** 历史分笔 — 历史成交回测
6. **`F10C / F10`** F10 资料 — (跟妙想重叠, 优先妙想; 但 tdxhub F10 是 TDX 终端原版, 字段口径不同)
7. **`Reader.*`** 离线 .day 文件 — 不用 (在线够)

### ⏳ pytdx 原生支持 / tdxhub 待扩展 (远期需求, P6)
- 可转债 / 国债期货
- 基金场内 (LOF / ETF, ETF 工作台未来可能用)
- 期权链
- 期货主力连续合约 (主力切换逻辑)
- 高频委托队列
- 宏观经济数据

### ❌ tdxhub 没有, 必须走其他源
- 龙虎榜 → 东财 datacenter-web
- 资金流 → 东财 datacenter-web
- QFII 持仓 → 东财 datacenter-web
- 融资融券 → 东财 datacenter-web
- 机构调研 → 东财 datacenter-web
- 主营构成 / 估值分位 / 一致预期 → 妙想 F10 (`miaoxiang/`)

---

## 联网验证

```bash
# 全量探针 (~30 个 API, 每个一次真实调用, 跑 ~3-5 min)
python scripts/probe_capabilities.py

# 快速 (跳过慢的)
python scripts/probe_capabilities.py --quick

# 单类
python scripts/probe_capabilities.py --capability bars
```

输出: `docs/capability-probe.json` (每个 API 实际响应结构 + 耗时).

---

## 数据源 registry 集成 (chunky-monkey-v2)

参考 [chunky-monkey-v2/docs/architecture-redesign-2026-04.md](https://github.com/dare2live/chunky-monkey-v2/blob/main/docs/architecture-redesign-2026-04.md) §6.1 适配层.

每个 capability 在 chunky-monkey-v2 的 `data_sources/sources/tdxhub.py` 里都对应一个 `Capability(name, freshness, ...)`. registry 按优先级 `tdxhub > 妙想 > 东财 datacenter-web > akshare` 自动 failover.
