# 本地数据读取命令

`reader` 用于读取通达信本地目录里的离线数据文件。和 `quotes` 不同，这条命令不走在线行情服务器，而是直接读本地 `vipdoc` 数据。

```shell
python -m tdxhub reader --help
```

当前实际支持的参数如下：

```shell
Usage: python -m tdxhub reader [OPTIONS]

  读取股票本地行情数据.

Options:
  -h, --help         Show this message and exit.
  -d, --tdxdir TEXT  通达信数据目录.
  -s, --symbol TEXT  股票代码.
  -a, --action TEXT  操作类型 (daily: 日线, minute: 一分钟线, fzline: 五分钟线).
  -m, --market TEXT  证券市场, 默认 std (std: 标准股票市场, ext: 扩展市场).
  -o, --output TEXT  输出文件, 支持 CSV, HDF5, Excel 等格式.
```

## 示例

读取日线并导出：

```shell
python -m tdxhub reader --tdxdir ../fixtures -s 600000 -a daily -o daily.csv
```

读取一分钟线：

```shell
python -m tdxhub reader --tdxdir ../fixtures -s 600000 -a minute -o minute.csv
```

读取五分钟线：

```shell
python -m tdxhub reader --tdxdir ../fixtures -s 600000 -a fzline -o fzline.csv
```

如果你的项目需要批量离线读取多个本地文件，更推荐直接调用 `Reader.factory(...)`，而不是循环 shell 调这条命令。
