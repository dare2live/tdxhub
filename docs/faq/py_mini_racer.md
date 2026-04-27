# FAQ: py_mini_racer / mini-racer

## 当前 fork 还依赖 `py_mini_racer` 吗？

依赖的是 `mini-racer` 这个安装包，但运行时导入模块名仍然是 `py_mini_racer`。

这也是很多旧问题的来源：

- 包管理层看到的是 `mini-racer`
- Python 代码里导入的还是 `py_mini_racer`

当前 fork 已经把安装依赖切到 `mini-racer`，这样在 macOS Apple Silicon 等环境里更容易安装，也更符合当前维护状态；但导入名并没有一起改掉。

## 我什么时候才需要这个依赖？

只有在使用公式解析、脚本执行或相关扩展工具链时，才需要额外关注这个依赖。纯行情、离线 reader、Affair 财务文件解析这几类常见能力，并不会因为这个 FAQ 页面单独多出额外步骤。

## 安装建议

- 优先按项目安装页执行当前 fork 的安装方式。
- 如果你的环境里仍然报 `py_mini_racer` 相关错误，通常说明你参考了旧版本文档、旧缓存环境，或者混用了上游说明。
- 在当前 fork 语境下，应优先安装 `tdxhub[racer]` 或底层包 `mini-racer`；运行时报错里如果出现 `py_mini_racer`，那通常只是导入模块名，而不代表你应该去安装旧包名。

## 排查顺序

1. 确认当前仓库是 `tdxhub`，不是上游历史镜像。
2. 确认你安装的是当前 fork，而不是旧 wheel 或旧缓存。
3. 确认缺的是 `tdxhub[racer]` / `mini-racer`，而不是被导入名 `py_mini_racer` 误导。
4. 重新核对安装页里的依赖说明，不要继续照搬历史 FAQ。

如果你只是使用 `Quotes`、`Affair`、`Reader` 这些主能力，优先先验证主流程是否可用，再决定是否需要额外安装公式相关依赖。
