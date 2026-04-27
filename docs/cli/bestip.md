# 线路测试命令

当前 fork 的 CLI 既可以在安装后使用 `mootdx bestip`，也可以在仓库根目录下直接运行：

```shell
python -m tdxhub bestip --help
```

当前实际支持的参数如下：

```shell
Usage: python -m tdxhub bestip [OPTIONS]

  测试行情服务器.

Options:
  -h, --help           Show this message and exit.
  -c, --connect-cfg TEXT
                       从通达信 connect.cfg 导入服务器列表后再测速.
  -l, --limit INTEGER  显示最快前几个，默认 5.
  -v, --verbose        详细模式
```

## 常用示例

显示最快 5 条线路并打印更详细日志：

```shell
python -m tdxhub bestip -l 5 -v
```

安装后也可以写成：

```shell
tdxhub bestip -l 5 -v
```

如果你本机已经有通达信客户端，也可以直接导入它的 `connect.cfg` 再测速：

```shell
python -m tdxhub bestip -c /path/to/connect.cfg -l 10
```

## 当前行为说明

- 这条命令会测试当前可用行情节点，并输出延迟排名。
- 传入 `-c/--connect-cfg` 时，会先从通达信客户端配置里导入 `HQHOST` / `DSHOST` 服务器列表，再继续测速，并把导入结果写回本地 `config.json`。
- 当前 fork 的 CLI 已不再提供旧文档里出现过的 `-w/--write`、`-t/--tofile` 选项。
- 不过命令执行完成后，当前实现仍会把最优线路写入本地配置文件，并在日志里打印配置路径。

如果你只想在项目内统一使用固定服务器，更推荐在业务代码里封装共享入口，而不是让业务层直接依赖 CLI 输出。
