"""Dedup + re-parse the raw F10 corpus from a universe-fetch DuckDB.

The earlier writer thread flush had a race between (locked) ``flush_bundle``
and (unlocked) ``_reset_bundle`` — duplicate inserts ensued. Rather than
chase the race, we treat ``raw_text`` as ground truth (the parser is pure)
and re-build the structured tables from it. This is also what we want to
do every time we add a new field or fix a parser bug.

Output: overwrites ``holders``, ``periods``, ``controlling``, ``plans``,
``trades``, and ``stats`` tables in place. ``raw_text`` is left untouched
but each stock is reduced to its latest snapshot.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/Users/dp/Documents/M/stock/tdxhub")
from tdxhub.holders import parse_research  # noqa: E402
from _holder_records_duckdb import create_table_from_records  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="/tmp/tdxhub_universe.duckdb")
    args = p.parse_args()

    con = duckdb.connect(args.db)

    print("step 1: dedupe raw_text to latest per stock")
    con.execute(
        """
        create or replace temp table raw_dedup as
        select * exclude(rn) from (
            select *,
                   row_number() over (partition by stock_code order by fetched_at desc) rn
            from raw_text
        ) where rn = 1
        """
    )
    n = con.execute("select count(*) from raw_dedup").fetchone()[0]
    print(f"  unique stocks in raw_text: {n}")
    con.execute("drop table if exists raw_text_old")
    con.execute("alter table raw_text rename to raw_text_old")
    con.execute("create table raw_text as select * from raw_dedup")
    n_dedup = con.execute("select count(*) from raw_text").fetchone()[0]
    print(f"  raw_text after dedupe: {n_dedup} rows")

    print("step 2: re-parse all stocks")
    con.execute("drop table if exists holders")
    con.execute("drop table if exists periods")
    con.execute("drop table if exists plans")
    con.execute("drop table if exists trades")
    con.execute("drop table if exists controlling")
    con.execute("drop table if exists stats")

    rows = con.execute(
        "select stock_code, stock_name, market, fetched_at, raw_len, raw_hash, server, raw_text from raw_text"
    ).fetchall()
    holders_acc: list[list[dict[str, Any]]] = []
    periods_acc: list[list[dict[str, Any]]] = []
    plans_acc: list[list[dict[str, Any]]] = []
    trades_acc: list[list[dict[str, Any]]] = []
    controlling_acc: list[dict] = []
    stats_acc: list[dict] = []

    BATCH = 500
    t0 = time.time()
    for i, (code, name, market, fetched_at, raw_len, raw_hash, server, text) in enumerate(rows, 1):
        try:
            res = parse_research(text or "", symbol=code, stock_name=name)
            holders = res["holders"]
            periods = res["periods"]
            ctrl = res["controlling"]
            plans = res["plans"]
            trades = res["trades"]
            n_periods_free = sum(1 for row in periods if row["holder_set"] == "free")
            n_periods_all = sum(1 for row in periods if row["holder_set"] == "all")
            n_exit_rows = sum(1 for row in holders if row["is_exit_row"])
            n_secondary = sum(1 for row in holders if row["is_secondary_class"])
            stats_acc.append(
                {
                    "stock_code": code,
                    "stock_name": name,
                    "market": market,
                    "ok": True,
                    "raw_len": raw_len,
                    "raw_hash": raw_hash,
                    "server": server,
                    "fetched_at": str(fetched_at),
                    "n_periods_free": n_periods_free,
                    "n_periods_all": n_periods_all,
                    "n_holders": len(holders),
                    "n_exit_rows": n_exit_rows,
                    "n_secondary": n_secondary,
                    "n_plans": len(plans),
                    "n_trades": len(trades),
                    "has_controlling": ctrl is not None,
                    "err": None,
                }
            )
            if holders:
                holders_acc.append(holders)
            if periods:
                periods_acc.append(periods)
            if plans:
                plans_acc.append(plans)
            if trades:
                trades_acc.append(trades)
            if ctrl is not None:
                controlling_acc.append(ctrl)
        except Exception as e:
            stats_acc.append(
                {
                    "stock_code": code,
                    "stock_name": name,
                    "market": market,
                    "ok": False,
                    "raw_len": raw_len,
                    "raw_hash": raw_hash,
                    "server": server,
                    "fetched_at": str(fetched_at),
                    "n_periods_free": 0,
                    "n_periods_all": 0,
                    "n_holders": 0,
                    "n_exit_rows": 0,
                    "n_secondary": 0,
                    "n_plans": 0,
                    "n_trades": 0,
                    "has_controlling": False,
                    "err": f"{type(e).__name__}: {e}",
                }
            )
        if i % BATCH == 0:
            elapsed = time.time() - t0
            print(f"  parsed {i}/{n_dedup}  ({i / elapsed:.0f}/s)")

    print(f"step 3: write back tables")
    if holders_acc:
        rows = [row for records in holders_acc for row in records]
        create_table_from_records(con, "holders", "h_in", rows)
        print(f"  holders: {len(rows)} rows")
    if periods_acc:
        rows = [row for records in periods_acc for row in records]
        create_table_from_records(con, "periods", "p_in", rows)
        print(f"  periods: {len(rows)} rows")
    if plans_acc:
        rows = [row for records in plans_acc for row in records]
        create_table_from_records(con, "plans", "pl_in", rows)
        print(f"  plans: {len(rows)} rows")
    if trades_acc:
        rows = [row for records in trades_acc for row in records]
        create_table_from_records(con, "trades", "tr_in", rows)
        print(f"  trades: {len(rows)} rows")
    if controlling_acc:
        create_table_from_records(con, "controlling", "ctrl_in", controlling_acc)
        print(f"  controlling: {len(controlling_acc)} rows")
    if stats_acc:
        create_table_from_records(con, "stats", "st_in", stats_acc)
        print(f"  stats: {len(stats_acc)} rows")

    con.execute("drop table if exists raw_text_old")
    con.close()
    print(f"\nconsolidate done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
