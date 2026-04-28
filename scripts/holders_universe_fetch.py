"""Concurrent full-universe holder fetch into a local DuckDB snapshot.

Each worker thread holds its own :class:`tdxhub.holders.HolderFetcher`,
which means each worker latches onto its own (different) TDX HQ server,
giving us linear speed-up while keeping per-server load low. Failed
servers cool down for 10 min and are auto-retried; the candidate pool is
re-synced from ``HQ_HOSTS`` every 30 min.

Output: a DuckDB file with these tables:

- ``raw_text``: stock_code, fetched_at, raw_len, raw_hash, raw_text, server
- ``holders``: per-holder per-period structured rows
- ``periods``: per-period header metadata
- ``controlling``: section-1 controlling shareholder + actual controller
- ``plans``: section-2 increase/decrease plans
- ``trades``: section-3 individual trades
- ``stats``: per-stock fetch outcome (ok / err / elapsed / counts)

Usage::

    python scripts/holders_universe_fetch.py [--workers 4]
        [--out /tmp/tdxhub_universe.duckdb]
        [--source-db /Users/dp/Documents/M/stock/chunky-monkey-v2/data/smartmoney.duckdb]
        [--limit N]   # cap stocks for a partial run
        [--symbols 600519,000001,...]  # explicit list overrides the universe
        [--resume]    # skip stocks already present in the output DB
        [--flush-every 50]
"""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import duckdb
import pandas as pd

sys.path.insert(0, "/Users/dp/Documents/M/stock/tdxhub")
from tdxhub.holders import HolderFetcher, parse_research, _hash  # noqa: E402


@dataclass
class StockOutcome:
    stock_code: str
    ok: bool
    elapsed_s: float
    raw_len: int = 0
    raw_hash: Optional[str] = None
    server: Optional[str] = None
    n_periods_free: int = 0
    n_periods_all: int = 0
    n_holders: int = 0
    n_exit_rows: int = 0
    n_secondary: int = 0
    n_plans: int = 0
    n_trades: int = 0
    has_controlling: bool = False
    err: Optional[str] = None


@dataclass
class Bundle:
    """Per-stock output bundle accumulated for batch DB write."""

    raw_text: list[dict] = field(default_factory=list)
    holders: list[pd.DataFrame] = field(default_factory=list)
    periods: list[pd.DataFrame] = field(default_factory=list)
    plans: list[pd.DataFrame] = field(default_factory=list)
    trades: list[pd.DataFrame] = field(default_factory=list)
    controlling: list[dict] = field(default_factory=list)
    stats: list[dict] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.raw_text or self.holders or self.periods or
            self.plans or self.trades or self.controlling or self.stats
        )


def make_universe(
    source_db: str,
    *,
    limit: int = 0,
    explicit_symbols: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    """Return list of ``(stock_code, stock_name, market)`` for the fetch run.

    Excludes 北交所 (per user direction it is filtered on the frontend).
    """

    if explicit_symbols:
        return [(s, "", "") for s in explicit_symbols]
    con = duckdb.connect(source_db, read_only=True)
    rows = con.execute(
        """
        select stock_code, coalesce(stock_name,''), coalesce(market,'')
        from dim_active_a_stock
        where market in ('SH','SZ')
          and stock_code not like '83%'
          and stock_code not like '87%'
          and stock_code not like '88%'
          and stock_code not like '92%'
        order by stock_code
        """
    ).fetchall()
    con.close()
    if limit:
        rows = rows[:limit]
    return [(r[0], r[1], r[2]) for r in rows]


def init_output_db(path: str) -> None:
    con = duckdb.connect(path)
    con.execute(
        """
        create table if not exists raw_text(
            stock_code varchar,
            stock_name varchar,
            market varchar,
            fetched_at varchar,
            raw_len integer,
            raw_hash varchar,
            server varchar,
            raw_text varchar
        )
        """
    )
    con.execute(
        """create table if not exists holders as
           select * from (select null::varchar as stock_code) where false"""
    )
    con.execute(
        """create table if not exists periods as
           select * from (select null::varchar as stock_code) where false"""
    )
    con.execute(
        """create table if not exists plans as
           select * from (select null::varchar as stock_code) where false"""
    )
    con.execute(
        """create table if not exists trades as
           select * from (select null::varchar as stock_code) where false"""
    )
    con.execute(
        """create table if not exists controlling as
           select * from (select null::varchar as stock_code) where false"""
    )
    con.execute(
        """
        create table if not exists stats(
            stock_code varchar,
            ok boolean,
            elapsed_s double,
            raw_len integer,
            raw_hash varchar,
            server varchar,
            n_periods_free integer,
            n_periods_all integer,
            n_holders integer,
            n_exit_rows integer,
            n_secondary integer,
            n_plans integer,
            n_trades integer,
            has_controlling boolean,
            err varchar
        )
        """
    )
    con.close()


def already_done(path: str) -> set[str]:
    con = duckdb.connect(path, read_only=True)
    try:
        rows = con.execute(
            "select stock_code from stats where ok=true and raw_len>0"
        ).fetchall()
    except Exception:
        rows = []
    con.close()
    return {r[0] for r in rows}


def flush_bundle(path: str, bundle: Bundle, lock: threading.Lock) -> None:
    if bundle.is_empty():
        return
    with lock:
        con = duckdb.connect(path)
        if bundle.raw_text:
            con.register("rt_in", pd.DataFrame(bundle.raw_text))
            con.execute("insert into raw_text select * from rt_in")
            con.unregister("rt_in")
        if bundle.holders:
            df = pd.concat(bundle.holders, ignore_index=True)
            if not df.empty:
                con.register("h_in", df)
                _replace_or_insert(con, "holders", "h_in")
                con.unregister("h_in")
        if bundle.periods:
            df = pd.concat(bundle.periods, ignore_index=True)
            if not df.empty:
                con.register("p_in", df)
                _replace_or_insert(con, "periods", "p_in")
                con.unregister("p_in")
        if bundle.plans:
            df = pd.concat(bundle.plans, ignore_index=True)
            if not df.empty:
                con.register("pl_in", df)
                _replace_or_insert(con, "plans", "pl_in")
                con.unregister("pl_in")
        if bundle.trades:
            df = pd.concat(bundle.trades, ignore_index=True)
            if not df.empty:
                con.register("tr_in", df)
                _replace_or_insert(con, "trades", "tr_in")
                con.unregister("tr_in")
        if bundle.controlling:
            df = pd.DataFrame(bundle.controlling)
            con.register("ctrl_in", df)
            _replace_or_insert(con, "controlling", "ctrl_in")
            con.unregister("ctrl_in")
        if bundle.stats:
            con.register("st_in", pd.DataFrame(bundle.stats))
            con.execute("insert into stats select * from st_in")
            con.unregister("st_in")
        con.close()


def _replace_or_insert(con, target: str, source: str) -> None:
    """Insert into a typed-from-empty table; if columns differ, recreate."""

    try:
        con.execute(f"insert into {target} select * from {source}")
    except Exception:
        # First-time insert: target was created from a phantom row that
        # only carries the stock_code column. Re-materialise with the
        # source's full schema.
        con.execute(f"drop table {target}")
        con.execute(f"create table {target} as select * from {source}")


def worker(
    name: str,
    job_q: queue.Queue,
    out_lock: threading.Lock,
    bundle: Bundle,
    flush_path: str,
    flush_every: int,
    progress_cb,
) -> None:
    fetcher = HolderFetcher(timeout=15, max_attempts_per_call=6)
    local_count = 0
    while True:
        item = job_q.get()
        if item is None:
            break
        idx, total, code, stock_name, _market = item
        t0 = time.time()
        outcome = StockOutcome(stock_code=code, ok=False, elapsed_s=0.0)
        try:
            text = fetcher.fetch_text(code)
            if not text:
                outcome.elapsed_s = time.time() - t0
                outcome.err = "no_f10"
                with out_lock:
                    bundle.stats.append(outcome.__dict__.copy())
                progress_cb(idx, total, code, outcome, name, fetcher)
                local_count += 1
                if local_count % flush_every == 0:
                    flush_bundle(flush_path, bundle, out_lock)
                    _reset_bundle(bundle)
                job_q.task_done()
                continue
            res = parse_research(text, symbol=code, stock_name=stock_name)
            elapsed = time.time() - t0
            holders = res["holders"]
            periods = res["periods"]
            ctrl = res["controlling"]
            plans = res["plans"]
            trades = res["trades"]
            outcome.ok = True
            outcome.elapsed_s = elapsed
            outcome.raw_len = len(text)
            outcome.raw_hash = _hash(text)
            outcome.server = str(fetcher.stats().get("active_server"))
            outcome.n_periods_free = int((periods["holder_set"] == "free").sum())
            outcome.n_periods_all = int((periods["holder_set"] == "all").sum())
            outcome.n_holders = len(holders)
            outcome.n_exit_rows = int(holders["is_exit_row"].sum())
            outcome.n_secondary = int(holders["is_secondary_class"].sum())
            outcome.n_plans = len(plans)
            outcome.n_trades = len(trades)
            outcome.has_controlling = ctrl is not None
            with out_lock:
                bundle.raw_text.append(
                    {
                        "stock_code": code,
                        "stock_name": stock_name,
                        "market": res["page"]["market"],
                        "fetched_at": res["page"]["fetched_at"],
                        "raw_len": len(text),
                        "raw_hash": outcome.raw_hash,
                        "server": outcome.server,
                        "raw_text": text,
                    }
                )
                bundle.holders.append(holders)
                bundle.periods.append(periods)
                bundle.plans.append(plans)
                bundle.trades.append(trades)
                if ctrl is not None:
                    bundle.controlling.append(ctrl)
                bundle.stats.append(outcome.__dict__.copy())
            progress_cb(idx, total, code, outcome, name, fetcher)
            local_count += 1
            if local_count % flush_every == 0:
                flush_bundle(flush_path, bundle, out_lock)
                _reset_bundle(bundle)
        except Exception as e:
            outcome.elapsed_s = time.time() - t0
            outcome.err = f"{type(e).__name__}: {e}"
            outcome.server = str(fetcher.stats().get("active_server"))
            with out_lock:
                bundle.stats.append(outcome.__dict__.copy())
            progress_cb(idx, total, code, outcome, name, fetcher)
        job_q.task_done()
    fetcher.close()


def _reset_bundle(bundle: Bundle) -> None:
    bundle.raw_text.clear()
    bundle.holders.clear()
    bundle.periods.clear()
    bundle.plans.clear()
    bundle.trades.clear()
    bundle.controlling.clear()
    bundle.stats.clear()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default="/tmp/tdxhub_universe.duckdb")
    p.add_argument(
        "--source-db",
        default="/Users/dp/Documents/M/stock/chunky-monkey-v2/data/smartmoney.duckdb",
    )
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--symbols", default="")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--flush-every", type=int, default=50)
    args = p.parse_args()

    explicit = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    universe = make_universe(args.source_db, limit=args.limit, explicit_symbols=explicit)
    print(f"universe: {len(universe)} stocks")

    init_output_db(args.out)
    skip = already_done(args.out) if args.resume else set()
    if skip:
        universe = [u for u in universe if u[0] not in skip]
        print(f"resume: skipping {len(skip)} already-done stocks; {len(universe)} to fetch")

    if not universe:
        print("nothing to do")
        return 0

    job_q: queue.Queue = queue.Queue()
    for i, (code, name, market) in enumerate(universe, 1):
        job_q.put((i, len(universe), code, name, market))
    for _ in range(args.workers):
        job_q.put(None)

    bundle = Bundle()
    out_lock = threading.Lock()
    progress = {"done": 0, "ok": 0, "err": 0, "started_at": time.time()}
    progress_lock = threading.Lock()

    def progress_cb(idx, total, code, outcome, worker_name, fetcher):
        with progress_lock:
            progress["done"] += 1
            if outcome.ok:
                progress["ok"] += 1
            else:
                progress["err"] += 1
            elapsed = time.time() - progress["started_at"]
            rate = progress["done"] / max(elapsed, 0.001)
            eta = (total - progress["done"]) / max(rate, 0.001)
            status = "ok" if outcome.ok else f"err={outcome.err[:30] if outcome.err else '-'}"
            if progress["done"] % 10 == 0 or not outcome.ok:
                print(
                    f"  [{progress['done']:4d}/{total}] {code} ({worker_name}) {status} "
                    f"{outcome.elapsed_s:.1f}s  rate={rate:.2f}/s  eta={eta/60:.1f}min  "
                    f"server={fetcher.stats().get('active_server')} "
                    f"susp={fetcher.stats().get('suspended_count')}",
                    flush=True,
                )

    workers = []
    for i in range(args.workers):
        t = threading.Thread(
            target=worker,
            args=(f"w{i+1}", job_q, out_lock, bundle, args.out, args.flush_every, progress_cb),
            name=f"holder-worker-{i+1}",
        )
        t.start()
        workers.append(t)
    for t in workers:
        t.join()
    flush_bundle(args.out, bundle, out_lock)

    elapsed = time.time() - progress["started_at"]
    print()
    print("=" * 64)
    print(f"universe fetch complete: {progress['done']} stocks in {elapsed/60:.1f} min")
    print(f"  ok={progress['ok']} err={progress['err']}")
    print(f"  output: {args.out}")
    return 0 if progress["err"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
