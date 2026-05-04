from datetime import datetime

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


def test_check_empty_handles_none_and_records():
    assert check_empty(None) is True
    assert check_empty([]) is True
    assert check_empty([{"code": "000001"}]) is False


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
    records = [{"datetime": datetime(2026, 5, 4), "open": 1.0, "close": float("nan")}]
    monkeypatch.setattr(
        StdQuotes,
        "bars",
        lambda self, **kwargs: records,
    )

    result = quote.bars_records(symbol="000001")

    assert result == [{"datetime": "2026-05-04T00:00:00", "open": 1.0, "close": None}]


def test_std_quotes_records_wrappers_keep_existing_datetime(monkeypatch):
    quote = StdQuotes.__new__(StdQuotes)
    records = [{"datetime": "2026-05-04", "open": 1.0}]
    monkeypatch.setattr(
        StdQuotes,
        "index_bars",
        lambda self, **kwargs: records,
    )

    result = quote.index_bars_records(symbol="000001")

    assert result == [{"datetime": "2026-05-04", "open": 1.0}]
