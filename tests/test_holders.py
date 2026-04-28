"""Offline tests for tdxhub.holders parser.

These run against captured F10 「股东研究」 fixtures so they don't require
network access. The fixtures live in ``tests/fixtures/holders/`` and are
named ``<label>_<stock_code>.txt``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import pytest

from tdxhub.holders import (
    parse_controlling_shareholder,
    parse_holders,
    parse_research,
    parse_shareholder_plans,
    parse_shareholder_trades,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "holders"


def _load(label_code: str) -> tuple[str, str]:
    matches = [p for p in FIXTURE_DIR.iterdir() if p.name.endswith(f"_{label_code}.txt")]
    assert len(matches) == 1, f"expected exactly one fixture for {label_code}, got {matches}"
    text = matches[0].read_text(encoding="utf-8")
    return text, label_code


def _parse(label_code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    text, code = _load(label_code)
    return parse_holders(text, symbol=code)


def test_returns_empty_with_stable_columns_for_empty_input():
    holders, periods = parse_holders("", symbol="600519")
    assert list(holders.columns) == [
        "stock_code",
        "stock_name",
        "market",
        "report_date",
        "holder_set",
        "holder_rank",
        "row_seq",
        "holder_name",
        "share_class",
        "shares_text",
        "shares_approx",
        "shares_precision",
        "hold_ratio",
        "holder_type_or_nature",
        "change_status",
        "change_shares_text",
        "change_shares_approx",
        "is_exit_row",
        "is_secondary_class",
        "page_update_date",
        "source",
        "raw_hash",
        "fetched_at",
    ]
    assert holders.empty
    assert periods.empty


def test_moutai_period_count_and_split():
    holders, periods = _parse("600519")
    # 600519 fixture covers four quarters (2026Q1, 2025Q4, 2025Q3, 2025Q2)
    assert (periods["holder_set"] == "free").sum() == 4
    assert (periods["holder_set"] == "all").sum() == 4
    assert sorted(periods["report_date"].unique().tolist()) == [
        "2025-06-30",
        "2025-09-30",
        "2025-12-31",
        "2026-03-31",
    ]


def test_moutai_2026q1_top_holder_exact():
    holders, _ = _parse("600519")
    m = (
        (holders["report_date"] == "2026-03-31")
        & (holders["holder_set"] == "free")
        & (~holders["is_exit_row"])
        & (holders["holder_rank"] == 1)
    )
    row = holders[m].iloc[0]
    assert row["holder_name"] == "中国贵州茅台酒厂（集团）有限责任公司"
    assert row["share_class"] == "A"
    assert row["shares_text"] == "6.8128亿"
    assert row["shares_approx"] == 681_280_000
    assert row["shares_precision"] == "亿"
    assert row["hold_ratio"] == pytest.approx(54.40)
    assert row["change_status"] == "不变"
    assert row["change_shares_approx"] == 0
    assert row["holder_type_or_nature"] == "其他"


def test_moutai_2026q1_exit_rows_match_text():
    holders, _ = _parse("600519")
    m = (
        (holders["report_date"] == "2026-03-31")
        & (holders["holder_set"] == "free")
        & holders["is_exit_row"]
    )
    rows = holders[m]
    assert len(rows) == 2
    names = rows["holder_name"].tolist()
    assert names == [
        "中国建设银行股份有限公司－易方达沪深300交易型开放式指数发起式证券投资基金",
        "中国工商银行股份有限公司－华夏沪深300交易型开放式指数证券投资基金",
    ]
    assert (rows["change_status"] == "退出").all()
    assert (rows["share_class"] == "A").all()


def test_zte_a_h_split_secondary_class():
    holders, _ = _parse("000063")
    m = (
        (holders["report_date"] == "2026-03-31")
        & (holders["holder_set"] == "free")
        & (~holders["is_exit_row"])
    )
    rows = holders[m].sort_values("row_seq").reset_index(drop=True)
    # The first holder 中兴新通讯 has BOTH an A leg (rank 1, primary) and
    # an H leg (same rank, secondary). The secondary leg has empty change
    # so its status is 未知, not "退出".
    primary = rows[rows["holder_name"] == "中兴新通讯有限公司"]
    assert len(primary) == 2
    classes = primary["share_class"].tolist()
    assert "A" in classes and "H" in classes
    a_leg = primary[primary["share_class"] == "A"].iloc[0]
    h_leg = primary[primary["share_class"] == "H"].iloc[0]
    assert a_leg["is_secondary_class"] is False or a_leg["is_secondary_class"] == False  # noqa: E712
    assert bool(h_leg["is_secondary_class"]) is True
    assert a_leg["shares_approx"] == 958_940_000
    assert h_leg["shares_approx"] == 2_038_000
    assert h_leg["change_status"] == "未知"


def test_zte_h_only_holders_have_share_class_h():
    holders, _ = _parse("000063")
    m = (
        (holders["report_date"] == "2026-03-31")
        & (holders["holder_set"] == "free")
        & (~holders["is_exit_row"])
        & (~holders["is_secondary_class"])
        & (holders["holder_name"] == "香港中央结算代理人有限公司")
    )
    row = holders[m].iloc[0]
    assert row["share_class"] == "H"


def test_change_status_classification_examples():
    holders, _ = _parse("600519")
    m = (holders["report_date"] == "2026-03-31") & (holders["holder_set"] == "free")
    statuses = holders[m]["change_status"].tolist()
    # The 2026Q1 free holders snapshot for Moutai contains 不变, 增持, 减持,
    # 新进, 退出 (across main + exit rows).
    assert {"不变", "增持", "减持", "新进", "退出"}.issubset(set(statuses))


def test_period_stat_parsed_correctly_for_moutai():
    _, periods = _parse("600519")
    p = periods[
        (periods["report_date"] == "2026-03-31") & (periods["holder_set"] == "free")
    ].iloc[0]
    assert p["a_share_holder_count_text"] == "24.3159万"
    assert p["a_share_holder_count"] == 243_159
    assert p["cumulative_text"] == "8.5806亿"
    assert p["cumulative_shares"] == 858_060_000
    assert p["cumulative_ratio"] == pytest.approx(68.52)
    assert p["delta_vs_prev_text"] == "-1646.02万"
    assert p["delta_vs_prev_shares"] == -16_460_200


def test_no_duplicate_rank_within_primary_holders_per_period():
    """Within (period, holder_set, is_exit_row, primary), ranks 1..N are unique."""

    for fname in FIXTURE_DIR.iterdir():
        code = fname.stem.split("_")[-1]
        holders, _ = parse_holders(fname.read_text(encoding="utf-8"), symbol=code)
        if holders.empty:
            continue
        primary = holders[~holders["is_secondary_class"]]
        groups = primary.groupby(["report_date", "holder_set", "is_exit_row"])
        for key, sub in groups:
            ranks = sub["holder_rank"].tolist()
            assert len(ranks) == len(set(ranks)), f"duplicate ranks in {code} {key}: {ranks}"


def test_top10_count_within_normal_bounds():
    """For each (period, holder_set, primary, non-exit) bucket, expect 1..10 rows.

    Some quarters may show fewer than 10 holders (recently listed stocks).
    """

    for fname in FIXTURE_DIR.iterdir():
        code = fname.stem.split("_")[-1]
        holders, _ = parse_holders(fname.read_text(encoding="utf-8"), symbol=code)
        if holders.empty:
            continue
        primary_main = holders[
            (~holders["is_secondary_class"]) & (~holders["is_exit_row"])
        ]
        groups = primary_main.groupby(["report_date", "holder_set"])
        for key, sub in groups:
            n = len(sub)
            assert 1 <= n <= 10, f"{code} {key}: unexpected holder count {n}"


def test_market_inference_from_symbol():
    holders_sh, _ = _parse("600519")
    holders_sz, _ = _parse("000001")
    holders_star, _ = _parse("688318")
    assert (holders_sh["market"] == "SH").all()
    assert (holders_sz["market"] == "SZ").all()
    assert (holders_star["market"] == "SH").all()


def test_continuation_rows_join_long_names():
    """Long fund names that wrap should be joined into a single holder_name."""

    holders, _ = _parse("600519")
    m = (
        (holders["holder_name"]
         == "国丰兴华（北京）私募基金管理有限公司－鸿鹄志远（上海）私募投资基金有限公司")
    )
    assert m.sum() >= 1


def test_raw_hash_stable_for_same_text():
    text = (FIXTURE_DIR / "sh_main_moutai_600519.txt").read_text(encoding="utf-8")
    h1, p1 = parse_holders(text, symbol="600519")
    h2, p2 = parse_holders(text, symbol="600519")
    assert h1["raw_hash"].iloc[0] == h2["raw_hash"].iloc[0]


def test_exit_rows_present_for_dual_listed_citic():
    holders, _ = _parse("600030")
    exits_2026q1_free = holders[
        (holders["report_date"] == "2026-03-31")
        & (holders["holder_set"] == "free")
        & holders["is_exit_row"]
    ]
    assert len(exits_2026q1_free) == 2
    assert set(exits_2026q1_free["holder_name"].tolist()) == {
        "中国工商银行－上证50交易型开放式指数证券投资基金",
        "大成基金－农业银行－大成中证金融资动产管理计划".replace("动产", "资"),  # safety
    } or set(exits_2026q1_free["holder_name"].tolist()) == {
        "中国工商银行－上证50交易型开放式指数证券投资基金",
        "大成基金－农业银行－大成中证金融资产管理计划",
    }


# ---------------------------------------------------------------------------
# Section 1 — 控股股东与实际控制人
# ---------------------------------------------------------------------------


def _ctrl(label_code: str) -> dict:
    text, code = _load(label_code)
    rec = parse_controlling_shareholder(text, symbol=code)
    assert rec is not None, f"section 1 missing for {code}"
    return rec


def test_controlling_shareholder_moutai_keeps_inner_parens():
    """名字里带'(集团)'不应该被截断。"""

    rec = _ctrl("600519")
    assert rec["primary_shareholder_label"] == "控股股东"
    assert rec["primary_shareholder_name"] == "中国贵州茅台酒厂(集团)有限责任公司"
    assert rec["primary_shareholder_ratio"] == pytest.approx(54.40)
    assert rec["actual_controller_name"] == "贵州省国有资产监督管理委员会"
    assert rec["actual_controller_ratio"] == pytest.approx(54.40)


def test_controlling_shareholder_strips_lianxi_aux_paren():
    """中信(601398)：'(联席股东:中华人民共和国财政部)' 应作为 aux 被剥掉。"""

    rec = _ctrl("601398")
    assert rec["primary_shareholder_label"] == "第一大股东"
    assert rec["primary_shareholder_name"] == "中央汇金投资有限责任公司"
    assert rec["primary_shareholder_ratio"] == pytest.approx(34.79)


def test_controlling_shareholder_strips_lianxi_full_width_brackets():
    """财富趋势(688318)：'【联席股东：黄青为一致行动人】' 应作为 aux 被剥掉。"""

    rec = _ctrl("688318")
    assert rec["primary_shareholder_name"] == "黄山"
    assert rec["primary_shareholder_ratio"] == pytest.approx(68.23)


def test_controlling_shareholder_no_actual_controller_for_zte():
    rec = _ctrl("000063")
    assert rec["primary_shareholder_name"] == "中兴新通讯有限公司"
    assert rec["actual_controller_name"] is None
    assert rec["actual_controller_ratio"] is None


def test_controlling_shareholder_handles_outer_paren_actual_layout():
    """茅台 实际控制人：name(控股比例(上市公司):54.40%) — outer paren wraps ratio."""

    rec = _ctrl("600519")
    assert rec["actual_controller_name"] == "贵州省国有资产监督管理委员会"
    assert rec["actual_controller_ratio"] == pytest.approx(54.40)


def test_controlling_shareholder_full_width_parens_preserved():
    """平安(000001)：name 含全角'（集团）'；不应替换或截断。"""

    rec = _ctrl("000001")
    assert rec["primary_shareholder_name"] == "中国平安保险（集团）股份有限公司"


def test_controlling_shareholder_returns_none_when_section_absent():
    rec = parse_controlling_shareholder("", symbol="600519")
    assert rec is None


# ---------------------------------------------------------------------------
# Section 2 — 股东增减持计划
# ---------------------------------------------------------------------------


def test_shareholder_plans_empty_when_暂无数据():
    text, code = _load("000063")
    df = parse_shareholder_plans(text, symbol=code)
    assert df.empty


def test_shareholder_plans_moutai_single_plan():
    text, code = _load("600519")
    df = parse_shareholder_plans(text, symbol=code)
    assert len(df) == 1
    p = df.iloc[0]
    assert p["announce_date"] == "2025-08-30"
    assert p["direction"] == "增持计划"
    assert p["progress"] == "实施"
    assert p["start_date"] == "2025-09-01"
    assert p["end_date"] == "2025-12-26"
    assert p["target_shares_text"] == "-"
    assert p["target_shares"] is None
    assert p["target_ratio"] is None
    assert "长期价值" in p["reason"]
    assert "30亿元" in p["narrative"]


def test_shareholder_plans_jiangbolong_multi_plans():
    text, code = _load("301308")
    df = parse_shareholder_plans(text, symbol=code)
    assert len(df) == 5
    # The most recent plan
    p = df.iloc[0]
    assert p["announce_date"] == "2026-03-20"
    assert p["direction"] == "减持计划"
    assert p["target_shares"] == 2_422_986
    assert p["target_ratio"] == pytest.approx(0.5781, rel=1e-4)
    # All plans are 减持 in this fixture
    assert (df["direction"] == "减持计划").all()


# ---------------------------------------------------------------------------
# Section 3 — 股东持股变动
# ---------------------------------------------------------------------------


def test_shareholder_trades_empty_when_暂无数据():
    text, code = _load("600030")
    df = parse_shareholder_trades(text, symbol=code)
    assert df.empty


def test_shareholder_trades_moutai_two_trades():
    text, code = _load("600519")
    df = parse_shareholder_trades(text, symbol=code)
    assert len(df) == 2
    assert df["change_date"].tolist() == ["2025-12-26", "2025-09-01"]
    assert all(
        df["holder_name"] == "中国贵州茅台酒厂（集团）有限责任公司"
    ), "wrap continuation rows must be joined"
    assert df.iloc[0]["shares_before"] == 679_280_000
    assert df.iloc[0]["shares_after"] == 681_280_000
    assert df.iloc[0]["shares_change"] == 2_003_538
    assert df.iloc[0]["change_type"] == "二级市场买入"
    assert df.iloc[0]["ratio_after"] == pytest.approx(54.4038)


def test_shareholder_trades_jiangbolong_long_wrapped_names():
    text, code = _load("301308")
    df = parse_shareholder_trades(text, symbol=code)
    assert len(df) >= 17
    # Confirm wrap continuation across many rows produced a single record
    long_names = df[df["holder_name"].str.contains("龙熹一号")]
    assert len(long_names) >= 1
    first = long_names.iloc[0]["holder_name"]
    # Joined name should be much longer than any single visual row
    assert len(first) > 30


def test_shareholder_trades_signed_change_for_decrease():
    """卖出方向的 shares_change 必须是负数。"""

    text, code = _load("301308")
    df = parse_shareholder_trades(text, symbol=code)
    sells = df[df["change_type"] == "二级市场卖出"]
    assert len(sells) > 0
    assert (sells["shares_change"] < 0).all()


# ---------------------------------------------------------------------------
# parse_research combined view
# ---------------------------------------------------------------------------


def test_parse_research_returns_all_sections():
    text, code = _load("600519")
    res = parse_research(text, symbol=code)
    assert set(res.keys()) == {"page", "controlling", "plans", "trades", "holders", "periods"}
    assert res["page"]["stock_code"] == "600519"
    assert res["page"]["stock_name"] == "贵州茅台"
    assert res["controlling"]["primary_shareholder_name"] == "中国贵州茅台酒厂(集团)有限责任公司"
    assert len(res["plans"]) == 1
    assert len(res["trades"]) == 2
    assert (res["periods"]["holder_set"] == "free").sum() == 4
