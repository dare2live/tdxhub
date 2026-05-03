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
    parse_common_major_holder_stocks_format_b,
    parse_controlling_shareholder,
    parse_controlling_shareholder_format_b,
    parse_fund_holdings_format_b,
    parse_holder_count_history_format_b,
    parse_holders,
    parse_research,
    parse_shareholder_plans,
    parse_shareholder_plans_format_b,
    parse_shareholder_trades,
    parse_shareholder_trades_format_b,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "holders"
FIXTURE_DIR_B = Path(__file__).parent / "fixtures" / "holders_b"

FORMAT_B_FUND_HOLDING_TEXT = """股东研究☆ ◇600519 贵州茅台 更新日期：2026-04-28◇ 通达信沪深京F10
【7.基金持股】截止日期：2025-12-31
┌────────────────────┬──────┬───────┬───────┐
│基金名称                                │持股数(股)│占流通A股比(%)│持股市值(元)│
├────────────────────┼──────┼───────┼───────┤
│中国工商银行股份有限公司－华泰柏瑞沪深300│456.64万  │0.36          │66.22亿     │
│交易型开放式指数证券投资基金            │          │              │            │
│国泰基金管理有限公司                    │12.34万   │0.01          │1.79亿      │
└────────────────────┴──────┴───────┴───────┘
"""

FORMAT_B_FUND_HOLDING_HEADER_UNIT_TEXT = """股东研究☆ ◇688809 晶华微 更新日期：2026-04-28◇ 通达信沪深京F10
【7.基金持股】截止日期：2025-12-31
┌────────────────────┬──────┬───────┬───────┐
│基金名称                                │持股数(万股)│占流通A股比(%)│持股市值(万元)│
├────────────────────┼──────┼───────┼───────┤
│华夏中证1000交易型开放式指数证券投资基金│0.97        │0.02          │30.99        │
│国泰基金管理有限公司                    │456.64万    │0.36          │66.22亿      │
└────────────────────┴──────┴───────┴───────┘
1、本公司力求但不保证提供的任何信息的真实性、准确性、完整性及原创性等。
投资者使用前请自行予以核实，不作为投资决策的依据。投资有风险。
"""

FORMAT_B_FUND_HOLDING_FOOTER_ONLY_TEXT = """股东研究☆ ◇688809 晶华微 更新日期：2026-04-28◇ 通达信沪深京F10
【7.基金持股】截止日期：2025-12-31
基金名称                            持股数(万股) 占流通A股比(%) 持股市值(万元)
────────────────────────────────────────────────────────
1、本公司力求但不保证提供的任何信 息的真实性、准确 性、完整性及原创 性等，投资者使
用前请自行予以核实，如有错漏请以 中国证监会指定上市 公司信息披露媒 体为准，本公司
不对因上述信息全部或部分内容而引 致的盈亏承担任何责 任。
"""


def _load(label_code: str) -> tuple[str, str]:
    matches = [p for p in FIXTURE_DIR.iterdir() if p.name.endswith(f"_{label_code}.txt")]
    assert len(matches) == 1, f"expected exactly one fixture for {label_code}, got {matches}"
    text = matches[0].read_text(encoding="utf-8")
    return text, label_code


def _load_b(label_code: str) -> tuple[str, str]:
    matches = [p for p in FIXTURE_DIR_B.iterdir() if p.name.endswith(f"_{label_code}.txt")]
    assert len(matches) == 1, f"expected exactly one Format B fixture for {label_code}, got {matches}"
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


def test_format_b_controlling_shareholder_keeps_control_chain():
    text, code = _load_b("600519")
    rec = parse_controlling_shareholder_format_b(text, symbol=code)
    assert rec["primary_shareholder_name"] == "中国贵州茅台酒厂（集团）有限责任公司"
    assert rec["primary_shareholder_ratio"] == pytest.approx(54.40)
    assert rec["actual_controller_name"] == "贵州省人民政府国有资产监督管理委员会"
    assert rec["actual_controller_ratio"] == pytest.approx(48.96)
    assert "→90%中国贵州茅台酒厂" in rec["control_chain_text"]


def test_controlling_shareholder_auto_dispatches_format_b():
    text, code = _load_b("300750")
    rec = parse_controlling_shareholder(text, symbol=code)
    assert rec["primary_shareholder_name"] == "厦门瑞庭投资有限公司"
    assert "曾毓群→55%厦门瑞庭" in rec["control_chain_text"]


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


def test_format_b_shareholder_trades_parse_period_price_and_method():
    text, code = _load_b("600519")
    df = parse_shareholder_trades_format_b(text, symbol=code)
    assert len(df) == 3
    first = df.iloc[0]
    assert first["change_period_text"] == "2025.10.21-2025.12.26"
    assert first["change_start_date"] == "2025-10-21"
    assert first["change_end_date"] == "2025-12-26"
    assert first["change_date"] == "2025-12-26"
    assert first["holder_name"] == "中国贵州茅台酒厂（集团）有限责任公司"
    assert first["shares_change"] == 1_274_200
    assert first["average_price"] == pytest.approx(1443.14)
    assert first["shares_after"] == 681_282_900
    assert first["change_method"] == "二级市场买卖"


def test_format_b_shareholder_trades_join_wrapped_names_and_signed_decrease():
    text, code = _load_b("300750")
    df = parse_shareholder_trades_format_b(text, symbol=code)
    assert len(df) > 40
    first = df.iloc[0]
    assert first["holder_name"] == "宁波联合创新新能源投资管理合伙企业（有限合伙）"
    assert first["shares_change"] == -58_000_000
    assert first["change_method"] == "询价转让"
    assert (df[df["holder_name"].str.contains("Mirae Asset", regex=False)]["holder_name"]
            .iloc[0].endswith("Co.Ltd"))


def test_format_b_holder_count_history_parses_latest_row():
    text, code = _load_b("600519")
    df = parse_holder_count_history_format_b(text, symbol=code)
    assert len(df) >= 60
    row = df.iloc[0]
    assert row["report_date"] == "2026-03-31"
    assert row["holder_count"] == 243_159
    assert row["holder_count_change"] == -12_733
    assert row["holder_count_change_pct"] == pytest.approx(-4.98)
    assert row["avg_float_shares"] == 5_150
    assert row["avg_float_shares_change_pct"] == pytest.approx(5.24)
    assert row["close_price"] == pytest.approx(1450.00)


def test_date_sanity_sets_future_artifacts_to_none():
    text = """股东研究☆ ◇600519 贵州茅台 更新日期：2026-04-28◇ 通达信沪深京F10
【5.股东人数变化】
┌─────┬──────┬──────┬──────┬───────┬───────┬────┐
│截止日期  │股东人数(户)│变动户数(户)│ 变动比率(%)│人均流通股(股)│ 较上期变化(%)│股价(元)│
├─────┼──────┼──────┼──────┼───────┼───────┼────┤
│2232-02-26│        1000│          10│        1.00│       1000.00│          1.00│   10.00│
└─────┴──────┴──────┴──────┴───────┴───────┴────┘
"""
    df = parse_holder_count_history_format_b(text, symbol="600519")
    assert len(df) == 1
    assert df.iloc[0]["report_date"] is None
    assert df.iloc[0]["report_date_text"] == "2232-02-26"


def test_format_b_shareholder_plans_parse_wrapped_rows_and_amount_bounds():
    text, code = _load_b("600519")
    df = parse_shareholder_plans_format_b(text, symbol=code)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["announce_date"] == "2025-12-30"
    assert row["first_announce_date"] == "2025-08-30"
    assert row["subject"] == "中国贵州茅台酒厂（集团）有限责任公司"
    assert row["direction"] == "增持计划"
    assert row["progress"] == "完成"
    assert row["start_date"] == "2025-09-01"
    assert row["end_date"] == "2026-02-28"
    assert row["target_amount_min"] == 3_000_000_000
    assert row["target_amount_max"] == 3_300_000_000
    assert "集中竞价" in row["trade_method"]


def test_format_b_shareholder_plans_filters_empty_shell_rows():
    text, code = _load_b("300750")
    df = parse_shareholder_plans(text, symbol=code)
    assert len(df) == 2
    assert df.iloc[0]["subject"] == "宁波联合创新新能源投资管理合伙企业（有限合伙）"
    assert df.iloc[0]["target_shares"] == 58_000_000
    assert df.iloc[0]["target_ratio"] == pytest.approx(1.27)
    assert df.iloc[1]["subject"] == "黄世霖"
    assert (df[["subject", "direction", "progress"]].fillna("").agg("".join, axis=1) != "").all()


def test_format_b_common_major_holder_stocks_parse_real_fixture():
    text, code = _load_b("601398")
    df = parse_common_major_holder_stocks_format_b(text, symbol=code)
    assert len(df) == 31
    first = df.iloc[0]
    assert first["report_date"] == "2025-12-31"
    assert first["report_date_text"] == "2025-12-31"
    assert first["major_holder_name"] == "中央汇金投资有限责任公司"
    assert first["peer_stock_code"] == "601988"
    assert first["peer_stock_name"] == "中国银行"
    assert first["shares"] == 188_792_000_000
    assert first["hold_ratio"] == pytest.approx(58.59)
    assert first["change_shares"] == 0
    assert first["net_profit_parent"] == 243_021_000_000
    changed = df[df["peer_stock_code"] == "600028"].iloc[0]
    assert changed["major_holder_name"] == "香港中央结算(代理人)有限公司"
    assert changed["change_text"] == "-1.63亿"
    assert changed["change_shares"] == -163_000_000


def test_format_b_common_major_holder_future_date_preserves_text():
    text = """股东研究☆ ◇601398 工商银行 更新日期：2026-04-28◇ 通达信沪深京F10
【6.同大股东个股】截止日期：2232-02-26
中央汇金投资有限责任公司（共1家）
排名   证券代码     证券简称   持股数(股)      占比(%)     增减情况 归母净利润(元) 扣非净利润(元)
─────────────────────────────────────────────────
1        601988     中国银行    1887.92亿        58.59         不变      2430.21亿      2429.12亿
"""
    df = parse_common_major_holder_stocks_format_b(text, symbol="601398")
    assert len(df) == 1
    assert df.iloc[0]["report_date"] is None
    assert df.iloc[0]["report_date_text"] == "2232-02-26"


def test_format_b_fund_holdings_parse_box_table_and_wrapped_name():
    df = parse_fund_holdings_format_b(FORMAT_B_FUND_HOLDING_TEXT, symbol="600519")
    assert len(df) == 2
    first = df.iloc[0]
    assert first["report_date"] == "2025-12-31"
    assert first["fund_name"] == "中国工商银行股份有限公司－华泰柏瑞沪深300交易型开放式指数证券投资基金"
    assert first["shares_text"] == "456.64万"
    assert first["shares"] == 4_566_400
    assert first["float_a_ratio"] == pytest.approx(0.36)
    assert first["market_value_text"] == "66.22亿"
    assert first["market_value"] == 6_622_000_000


def test_format_b_fund_holdings_header_units_and_footer_disclaimer():
    df = parse_fund_holdings_format_b(FORMAT_B_FUND_HOLDING_HEADER_UNIT_TEXT, symbol="688809")
    assert len(df) == 2
    first = df.iloc[0]
    second = df.iloc[1]
    assert first["fund_name"] == "华夏中证1000交易型开放式指数证券投资基金"
    assert first["shares_text"] == "0.97"
    assert first["shares"] == 9_700
    assert first["market_value_text"] == "30.99"
    assert first["market_value"] == 309_900
    assert second["shares_text"] == "456.64万"
    assert second["shares"] == 4_566_400
    assert second["market_value_text"] == "66.22亿"
    assert second["market_value"] == 6_622_000_000
    assert not df["fund_name"].str.contains("真实性|投资有风险", regex=True).any()


def test_format_b_fund_holdings_footer_only_is_not_record():
    df = parse_fund_holdings_format_b(FORMAT_B_FUND_HOLDING_FOOTER_ONLY_TEXT, symbol="688809")
    assert df.empty
    assert "fund_name" in df.columns


def test_format_b_extra_sections_empty_with_stable_columns():
    text, code = _load_b("600519")
    common = parse_common_major_holder_stocks_format_b(text, symbol=code)
    funds = parse_fund_holdings_format_b(text, symbol=code)
    assert common.empty
    assert funds.empty
    assert "major_holder_name" in common.columns
    assert "fund_name" in funds.columns


# ---------------------------------------------------------------------------
# parse_research combined view
# ---------------------------------------------------------------------------


def test_parse_research_returns_all_sections():
    text, code = _load("600519")
    res = parse_research(text, symbol=code)
    assert set(res.keys()) == {
        "page",
        "controlling",
        "plans",
        "trades",
        "trades_b",
        "holders",
        "periods",
        "holder_count_history",
        "common_major_holder_stocks",
        "fund_holdings",
    }
    assert res["page"]["stock_code"] == "600519"
    assert res["page"]["stock_name"] == "贵州茅台"
    assert res["controlling"]["primary_shareholder_name"] == "中国贵州茅台酒厂(集团)有限责任公司"
    assert len(res["plans"]) == 1
    assert len(res["trades"]) == 2
    assert (res["periods"]["holder_set"] == "free").sum() == 4
    assert res["trades_b"].empty
    assert res["holder_count_history"].empty


def test_parse_research_format_b_adds_rich_section_keys():
    text, code = _load_b("601398")
    res = parse_research(text, symbol=code)
    assert len(res["holder_count_history"]) > 0
    assert len(res["common_major_holder_stocks"]) == 31
    assert res["fund_holdings"].empty
