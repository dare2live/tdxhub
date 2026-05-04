"""End-to-end verification: fetch + parse F10 「股东研究」 for a representative
basket of A-share stocks across markets, save the result to DuckDB, and
print a summary suitable for shipping decisions.

Usage::

    python scripts/holders_e2e_verify.py [--symbols 600519,000001,...]

Default: a curated 40-stock basket covering sh/sz main, chinext, star, and
A/H dual-listed names.

Output: ``/tmp/tdxhub_holders_e2e.duckdb`` with three tables (holders,
periods, controlling, plans, trades, raw_text) and a stats report on stdout.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/Users/dp/Documents/M/stock/tdxhub")
from tdxhub.holders import HolderFetcher, parse_research  # noqa: E402
from _holder_records_duckdb import create_table_from_records  # noqa: E402


DEFAULT_BASKET = [
    # 上交所主板（含蓝筹龙头）
    "600519",  # 茅台
    "600028",  # 中石化（A/H）
    "600036",  # 招商银行（A/H）
    "600276",  # 恒瑞医药
    "600585",  # 海螺水泥（A/H）
    "601318",  # 中国平安（A/H）
    "601398",  # 工商银行（A/H）
    "601628",  # 中国人寿（A/H）
    "601888",  # 中国中免（A/H）
    "601012",  # 隆基绿能
    # 上交所科创板
    "688318",  # 财富趋势
    "688041",  # 海光信息
    "688981",  # 中芯国际（A/H 已退H不持续讨论）
    "688256",  # 寒武纪
    # 深交所主板
    "000001",  # 平安银行
    "000063",  # 中兴通讯（A/H）
    "000333",  # 美的集团
    "000651",  # 格力电器
    "000725",  # 京东方A
    "000858",  # 五粮液
    # 深交所中小板（已并入主板）
    "002415",  # 海康威视
    "002475",  # 立讯精密
    "002594",  # 比亚迪（A/H）
    "002714",  # 牧原股份
    # 深交所创业板
    "300015",  # 爱尔眼科
    "300059",  # 东方财富
    "300122",  # 智飞生物
    "300750",  # 宁德时代
    "300760",  # 迈瑞医疗
    "301308",  # 江波龙（新上市）
    # A/H 双重上市补充
    "600030",  # 中信证券
    "600031",  # 三一重工（A/H）
    "601628",  # 中国人寿 （重复，但 OK）
    "601988",  # 中国银行（A/H）
    "601988",
    # 沪市消费类
    "603288",  # 海天味业
    "603259",  # 药明康德（A/H）
    "603501",  # 韦尔股份
    "601899",  # 紫金矿业（A/H）
]


@dataclass
class StockResult:
    code: str
    ok: bool
    raw_len: int
    elapsed_s: float
    err: str | None
    n_periods_free: int
    n_periods_all: int
    n_holders: int
    n_exit_rows: int
    n_secondary_class: int
    n_plans: int
    n_trades: int
    has_controlling: bool
    a_h_split_count: int
    server_used: str | None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="", help="comma-separated override")
    parser.add_argument("--db", default="/tmp/tdxhub_holders_e2e.duckdb")
    parser.add_argument("--limit", type=int, default=0, help="stop after N stocks")
    args = parser.parse_args()

    if args.symbols:
        basket = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        basket = list(dict.fromkeys(DEFAULT_BASKET))  # dedupe preserving order
    if args.limit:
        basket = basket[: args.limit]

    print(f"basket size: {len(basket)} stocks")
    print(f"output DB:   {args.db}")
    print()

    con = duckdb.connect(args.db)
    con.execute("drop table if exists holders")
    con.execute("drop table if exists periods")
    con.execute("drop table if exists controlling")
    con.execute("drop table if exists plans")
    con.execute("drop table if exists trades")
    con.execute("drop table if exists raw_text")
    con.execute("drop table if exists stats")

    fetcher = HolderFetcher(timeout=15, max_attempts_per_call=6, prescreen_limit=8)
    results: list[StockResult] = []
    all_holders: list[list[dict[str, Any]]] = []
    all_periods: list[list[dict[str, Any]]] = []
    all_controlling: list[dict] = []
    all_plans: list[list[dict[str, Any]]] = []
    all_trades: list[list[dict[str, Any]]] = []
    raw_texts: list[dict] = []

    for i, code in enumerate(basket, 1):
        t0 = time.time()
        try:
            text = fetcher.fetch_text(code)
            if not text:
                elapsed = time.time() - t0
                results.append(
                    StockResult(
                        code=code, ok=False, raw_len=0, elapsed_s=elapsed,
                        err="no F10 page", n_periods_free=0, n_periods_all=0,
                        n_holders=0, n_exit_rows=0, n_secondary_class=0,
                        n_plans=0, n_trades=0, has_controlling=False,
                        a_h_split_count=0, server_used=str(fetcher.stats().get("active_server")),
                    )
                )
                print(f"  [{i:2d}/{len(basket)}] {code}: skip (no F10) {elapsed:.1f}s")
                continue
            res = parse_research(text, symbol=code)
            elapsed = time.time() - t0
            holders = res["holders"]
            periods = res["periods"]
            ctrl = res["controlling"]
            plans = res["plans"]
            trades = res["trades"]
            ah_split = len({
                row["holder_name"]
                for row in holders
                if not row["is_exit_row"] and row["is_secondary_class"]
            })
            n_periods_free = sum(1 for row in periods if row["holder_set"] == "free")
            n_periods_all = sum(1 for row in periods if row["holder_set"] == "all")
            n_exit_rows = sum(1 for row in holders if row["is_exit_row"])
            n_secondary = sum(1 for row in holders if row["is_secondary_class"])
            results.append(
                StockResult(
                    code=code,
                    ok=True,
                    raw_len=len(text),
                    elapsed_s=elapsed,
                    err=None,
                    n_periods_free=n_periods_free,
                    n_periods_all=n_periods_all,
                    n_holders=len(holders),
                    n_exit_rows=n_exit_rows,
                    n_secondary_class=n_secondary,
                    n_plans=len(plans),
                    n_trades=len(trades),
                    has_controlling=ctrl is not None,
                    a_h_split_count=int(ah_split),
                    server_used=str(fetcher.stats().get("active_server")),
                )
            )
            all_holders.append(holders)
            all_periods.append(periods)
            if ctrl is not None:
                all_controlling.append(ctrl)
            all_plans.append(plans)
            all_trades.append(trades)
            raw_texts.append(
                {"stock_code": code, "raw_text": text, "raw_len": len(text)}
            )
            print(
                f"  [{i:2d}/{len(basket)}] {code}: ok  "
                f"len={len(text):5d}  periods={n_periods_free}f/"
                f"{n_periods_all}a  "
                f"rows={len(holders):3d}  exits={n_exit_rows:2d}  "
                f"secondary={n_secondary:2d}  "
                f"plans={len(plans)}  trades={len(trades)}  "
                f"{elapsed:.1f}s"
            )
        except Exception as e:
            elapsed = time.time() - t0
            results.append(
                StockResult(
                    code=code, ok=False, raw_len=0, elapsed_s=elapsed,
                    err=f"{type(e).__name__}: {e}", n_periods_free=0,
                    n_periods_all=0, n_holders=0, n_exit_rows=0,
                    n_secondary_class=0, n_plans=0, n_trades=0,
                    has_controlling=False, a_h_split_count=0,
                    server_used=str(fetcher.stats().get("active_server")),
                )
            )
            print(f"  [{i:2d}/{len(basket)}] {code}: ERROR {type(e).__name__}: {e}  {elapsed:.1f}s")
            traceback.print_exc(limit=1)

    fetcher.close()

    # Persist
    if all_holders:
        create_table_from_records(con, "holders", "h_in", [row for rows in all_holders for row in rows])
    if all_periods:
        create_table_from_records(con, "periods", "p_in", [row for rows in all_periods for row in rows])
    if all_plans:
        create_table_from_records(con, "plans", "pl_in", [row for rows in all_plans for row in rows])
    if all_trades:
        create_table_from_records(con, "trades", "tr_in", [row for rows in all_trades for row in rows])
    if all_controlling:
        create_table_from_records(con, "controlling", "ctrl_in", all_controlling)
    if raw_texts:
        create_table_from_records(con, "raw_text", "raw_in", raw_texts)
    create_table_from_records(con, "stats", "stats_in", [r.__dict__ for r in results])
    con.close()

    # Report
    print()
    print("=" * 68)
    print(f"E2E verification — {len(results)} stocks")
    print("=" * 68)
    n_ok = sum(1 for r in results if r.ok)
    n_fail = len(results) - n_ok
    total_time = sum(r.elapsed_s for r in results)
    print(f"  success / total              : {n_ok} / {len(results)}")
    print(f"  total elapsed                : {total_time:.1f}s")
    print(f"  avg elapsed per stock        : {total_time / max(len(results),1):.2f}s")
    print(f"  total holder rows captured   : {sum(r.n_holders for r in results)}")
    print(f"  total exit rows captured     : {sum(r.n_exit_rows for r in results)}")
    print(f"  total A/H secondary rows     : {sum(r.n_secondary_class for r in results)}")
    print(f"  stocks with A/H split        : {sum(1 for r in results if r.a_h_split_count>0)}")
    print(f"  stocks with controlling info : {sum(1 for r in results if r.has_controlling)}")
    print(f"  total plans captured         : {sum(r.n_plans for r in results)}")
    print(f"  total trades captured        : {sum(r.n_trades for r in results)}")
    print(f"  fetcher final stats          : {fetcher.stats()}")
    if n_fail:
        print()
        print("  failures:")
        for r in results:
            if not r.ok:
                print(f"    {r.code}: {r.err}")
    print()
    print(f"output DB: {args.db}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
