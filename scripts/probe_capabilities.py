"""tdxhub capability live probe — 跑通每一个能联网拿数据的 API, 输出 JSON 报告.

用法:
    python scripts/probe_capabilities.py              # 全跑
    python scripts/probe_capabilities.py --quick      # 跳过慢的 (gpcw 下载等)
    python scripts/probe_capabilities.py --capability quotes  # 只跑指定的

输出:
    docs/capability-probe-<date>.json
    docs/capability-map.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tdxhub.quotes import Quotes
from tdxhub.affair import Affair


# 测试 symbol: 茅台 (沪) + 平安 (深) + 中证 1000 指数
TEST_SYMBOLS = {
    "stock_sh": "600519",
    "stock_sz": "000001",
    "stock_bj": "832000",
    "index": "000001",  # 上证指数
}


def _probe(name: str, fn, *, timeout: int = 30) -> dict:
    t0 = time.time()
    try:
        result = fn()
        elapsed = time.time() - t0
        ok, info = _summarize(result)
        return {
            "name": name,
            "status": "ok" if ok else "empty",
            "elapsed_s": round(elapsed, 2),
            "info": info,
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "fail",
            "elapsed_s": round(time.time() - t0, 2),
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }


def _summarize(result):
    """返回 (ok: bool, info: dict|str). 兼容 DataFrame / list / dict / scalar."""
    try:
        import pandas as pd
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return False, {"shape": [0, 0], "cols": list(result.columns)}
            sample = result.iloc[0].to_dict() if len(result) > 0 else {}
            # 简化采样: 只保留前 6 列, 避免 dump 太多
            sample_short = dict(list(sample.items())[:6])
            return True, {
                "shape": list(result.shape),
                "cols": list(result.columns)[:20],
                "sample_first_row": sample_short,
            }
    except Exception:
        pass
    if isinstance(result, list):
        return bool(result), {"count": len(result), "first": str(result[0])[:120] if result else None}
    if isinstance(result, dict):
        return bool(result), {"keys": list(result.keys())[:20]}
    return result is not None, {"value": str(result)[:200]}


def run_probes(args) -> dict:
    cli = Quotes.factory(market="std")

    probes = []

    # ===== 标准行情 =====
    probes.append(("quotes (实时五档)", lambda: cli.quotes(symbol=TEST_SYMBOLS["stock_sh"])))
    probes.append(("bars (K线 30 根日)",  lambda: cli.bars(symbol=TEST_SYMBOLS["stock_sh"], frequency=9, offset=30)))
    probes.append(("bars (K线 30 根 5 分)", lambda: cli.bars(symbol=TEST_SYMBOLS["stock_sh"], frequency=0, offset=30)))
    probes.append(("index_bars (上证指数 30 根日)", lambda: cli.index_bars(symbol=TEST_SYMBOLS["index"], frequency=9, offset=30)))
    probes.append(("stocks (深市)", lambda: cli.stocks(market=0)))
    probes.append(("stock_count (沪)", lambda: cli.stock_count(market=1)))
    probes.append(("minute (当日分时)", lambda: cli.minute(symbol=TEST_SYMBOLS["stock_sh"])))
    if not args.quick:
        probes.append(("minutes (历史分时)", lambda: cli.minutes(symbol=TEST_SYMBOLS["stock_sh"], date="20260415")))
        probes.append(("transaction (当日分笔)", lambda: cli.transaction(symbol=TEST_SYMBOLS["stock_sh"])))
        probes.append(("transactions (历史分笔)", lambda: cli.transactions(symbol=TEST_SYMBOLS["stock_sh"], date="20260415")))
    probes.append(("xdxr (除权除息)", lambda: cli.xdxr(symbol=TEST_SYMBOLS["stock_sh"])))
    probes.append(("finance (财务摘要)", lambda: cli.finance(symbol=TEST_SYMBOLS["stock_sh"])))
    probes.append(("F10C (公司资料目录)", lambda: cli.F10C(symbol=TEST_SYMBOLS["stock_sh"])))
    probes.append(("F10 (公司资料具体)", lambda: cli.F10(symbol=TEST_SYMBOLS["stock_sh"], name="公司概况")))
    probes.append(("block (板块概念)", lambda: cli.block(group=False, custom=False)))
    probes.append(("k (K 线日期范围)", lambda: cli.k(symbol=TEST_SYMBOLS["stock_sh"], begin="20260101", end="20260427")))

    # ===== Affair (财务文件) =====
    probes.append(("Affair.files (gpcw 列表)", lambda: Affair.files()))

    # ===== 扩展行情 (期货 / 外汇) =====
    if not args.quick:
        from tdxhub.quotes import ExtQuotes
        ecli = Quotes.factory(market="ext")
        probes.append(("ExtQuotes.markets", lambda: ecli.markets()))
        probes.append(("ExtQuotes.instrument_count", lambda: ecli.instrument_count()))

    # 过滤
    if args.capability:
        probes = [(n, f) for n, f in probes if args.capability.lower() in n.lower()]

    print(f"=== 跑 {len(probes)} 个 probe ===")
    results = []
    for name, fn in probes:
        print(f"  [{name}] ... ", end="", flush=True)
        r = _probe(name, fn)
        status_icon = "✓" if r["status"] == "ok" else ("○" if r["status"] == "empty" else "✗")
        print(f"{status_icon} {r['elapsed_s']}s")
        results.append(r)

    return {
        "probe_at": dt.datetime.now().isoformat(),
        "tdxhub_version": __import__("tdxhub").__version__,
        "test_symbols": TEST_SYMBOLS,
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "empty": sum(1 for r in results if r["status"] == "empty"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="跳过慢的 probe")
    parser.add_argument("--capability", help="只跑名字含此关键字的 probe")
    parser.add_argument("--out", default="docs/capability-probe.json")
    args = parser.parse_args()

    report = run_probes(args)

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"=== 汇总 ===")
    print(f"  ok={report['ok']} / empty={report['empty']} / fail={report['fail']} / total={report['total']}")
    print(f"  报告: {out_path}")


if __name__ == "__main__":
    main()
