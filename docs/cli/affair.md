# 财务文件命令

`affair` 用于列出、下载和解析 gpcw 财务文件。当前 fork 的项目接入里，这也是最重要的 CLI 之一。

```shell
python -m tdxhub affair --help
```

当前实际支持的参数如下：

```shell
Usage: python -m tdxhub affair [OPTIONS]

  财务文件下载&解析.

Options:
  -h, --help          Show this message and exit.
  -p, --parse TEXT    要解析文件名
  -f, --fetch TEXT    下载财务文件的文件名
  -a, --downall       下载全部文件
  -o, --output TEXT   输出文件, 支持 CSV, HDF5, Excel, JSON 等格式.
  -d, --downdir TEXT  下载文件目录
  -l, --listfile      显示全部文件
  -v, --verbose       详细模式
```

## 1. 列出全部财务文件

```shell
python -m tdxhub affair -l
```

注意：当前参数名是 `--listfile`，不是旧文档里写过的 `--files`。

## 2. 下载单个文件

```shell
python -m tdxhub affair -f gpcw20241231.zip -d output
```

如果不写 `.zip` 后缀，当前实现也会自动补齐。

## 3. 下载全部文件

推荐写法：

```shell
python -m tdxhub affair -a -d output
```

兼容写法里 `-f all` 仍然可用，但当前文档建议优先使用显式的 `-a/--downall`。

## 4. 解析单个文件

```shell
python -m tdxhub affair -p gpcw20241231.zip -d output
```

如果目标文件本地不存在，当前实现会先尝试下载，再解析。

## 5. 解析后直接导出

```shell
python -m tdxhub affair -p gpcw20241231.zip -d output -o gpcw20241231.csv
```

如果你需要按字段裁剪、批量入库或做项目级数据落地，更推荐直接使用 Python API：`Affair.files()`、`Affair.fetch()`、`Affair.parse(...)`。
