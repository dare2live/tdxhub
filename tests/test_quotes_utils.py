import pandas as pd
import pytest

from tdxhub.quotes import BaseQuotes
from tdxhub.quotes import check_empty
from tdxhub.quotes import ExtQuotes
from tdxhub.quotes import StdQuotes
from tdxhub.quotes import valid_server


class _DummyTransport:
    def __init__(self, closed=True):
        self._closed = closed


class _DummyClient:
    def __init__(self, closed=True):
        self.client = _DummyTransport(closed=closed)
        self.connected_to = None

    def connect(self, *server):
        self.connected_to = server


def test_valid_server_accepts_host_port_string():
    assert valid_server('127.0.0.1:7709') == ('127.0.0.1', 7709)


def test_valid_server_accepts_tuple_input():
    assert valid_server(('1.2.3.4', '7709')) == ('1.2.3.4', 7709)


def test_valid_server_rejects_malformed_iterable():
    with pytest.raises(ValueError):
        valid_server(('bad-ip', 7709))


def test_check_empty_handles_none_and_dataframe():
    test_df_empty = pd.DataFrame([])

    assert check_empty(None) is True
    assert check_empty(test_df_empty) is True


def test_base_quotes_reconnect_uses_server_when_bestip_missing():
    client = _DummyClient(closed=True)
    quote = BaseQuotes.__new__(BaseQuotes)
    quote.client = client
    quote.server = ('127.0.0.1', 7709)
    quote.bestip = None

    quote.reconnect()

    assert client.connected_to == ('127.0.0.1', 7709)


def test_base_quotes_closed_is_true_without_nested_transport():
    quote = BaseQuotes.__new__(BaseQuotes)
    quote.client = object()

    assert quote.closed is True


def test_ext_quotes_validate_accepts_market_prefix_in_symbol():
    assert ExtQuotes.validate(None, '42#IMCI') == (42, 'IMCI')


def test_ext_quotes_validate_rejects_missing_market():
    with pytest.raises(ValueError):
        ExtQuotes.validate(None, 'IMCI')


def test_std_quotes_records_wrappers_return_plain_records(monkeypatch):
    quote = StdQuotes.__new__(StdQuotes)
    frame = pd.DataFrame(
        [{"open": 1.0, "close": float("nan")}],
        index=pd.to_datetime(["2026-05-04"]),
    )
    monkeypatch.setattr(
        StdQuotes,
        "bars",
        lambda self, **kwargs: frame,
    )

    records = quote.bars_records(symbol="000001")

    assert records == [{"open": 1.0, "close": None, "datetime": "2026-05-04T00:00:00"}]


def test_std_quotes_records_wrappers_keep_existing_datetime(monkeypatch):
    quote = StdQuotes.__new__(StdQuotes)
    frame = pd.DataFrame([{"datetime": "2026-05-04", "open": 1.0}])
    monkeypatch.setattr(
        StdQuotes,
        "index_bars",
        lambda self, **kwargs: frame,
    )

    records = quote.index_bars_records(symbol="000001")

    assert records == [{"datetime": "2026-05-04", "open": 1.0}]
