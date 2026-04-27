# 在线行情命令

`quotes` 用于直接从行情服务器读取在线数据。当前实现走的是 `Quotes.factory(...).bars(...)` 这一层，因此 CLI 适合快速探测、导出单只标的的基础 K 线，不适合作为复杂批量同步任务的主入口。

可以在仓库根目录直接运行：

```shell
python -m tdxhub quotes --help
```

安装后也可以使用：

```shell
tdxhub quotes --help
```

当前实际支持的参数如下：

```shell
Usage: python -m tdxhub quotes [OPTIONS]

  读取股票在线行情数据.

Options:
  -h, --help         Show this message and exit.
  -o, --output TEXT  输出文件, 支持CSV, HDF5, Excel等格式.
  -s, --symbol TEXT  股票代码.
  -a, --action TEXT  操作类型 (daily: 日线, minute: 一分钟线, fzline: 五分钟线).
  -m, --market TEXT  证券市场, 默认 std (std: 标准股票市场, ext: 扩展市场).
```

## 推荐 action

- `daily`: 日线
- `minute`: 一分钟线
- `fzline`: 五分钟线

说明：当前源码里 `action` 的默认值仍写成 `bars`，但最终会回退到日线逻辑。文档里建议直接显式写 `daily` / `minute` / `fzline`，不要依赖这个兼容分支。

## 示例

读取日线并直接打印：

```shell
python -m tdxhub quotes -s 600036 -a daily
```

读取一分钟线并写入文件：

```shell
python -m tdxhub quotes -s 600036 -a minute -o minute.csv
```

如果你需要批量获取多只股票实时快照，优先使用 Python API 里的 `Quotes.quotes()`，而不是依赖这条 CLI。
