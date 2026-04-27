# 批量下载命令

`bundle` 用于按股票代码批量拉取在线行情，并把每个标的单独写入输出目录。

```shell
python -m tdxhub bundle --help
```

当前实际支持的参数如下：

```shell
Usage: python -m tdxhub bundle [OPTIONS]

  批量下载行情数据.

Options:
  -h, --help            Show this message and exit.
  -o, --output TEXT     转存文件目录.
  -s, --symbol TEXT     股票代码. 多个用,隔开
  -a, --action TEXT     操作类型 (daily: 日线, minute: 一分钟线, fzline: 五分钟线).
  -m, --market TEXT     证券市场, 默认 std (std: 标准股票市场, ext: 扩展市场).
  -e, --extension TEXT  转存文件的格式, 支持 CSV, HDF5, Excel, JSON 等格式.
```

## 示例

下载两只股票的日线到 `bundle/` 目录：

```shell
python -m tdxhub bundle -s 600036,000001 -a daily -o bundle
```

下载一分钟线并导出为 JSON：

```shell
python -m tdxhub bundle -s 600036,000001 -a minute -o bundle -e json
```

说明：当前实现按逗号拆分股票代码，并对每只股票单独调用 `bars()`；如果你需要更高吞吐的项目级批量同步，更推荐直接使用 Python API 或在业务层自行做并发/落库控制。
