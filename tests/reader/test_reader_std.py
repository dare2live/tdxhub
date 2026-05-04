import pytest

from tdxhub.reader import Reader
from tests.conftest import is_empty


@pytest.fixture()
def reader():
    return Reader.factory(market='std', tdxdir='tests/fixtures')


@pytest.mark.parametrize(
    'symbol,adjust,empty', [
        ('127021', '', False),
        ('000000', '', True),
        ('sh881478', '', False),
        ('881478', '', False),
    ])
def test_daily(reader, symbol, adjust, empty):
    result = reader.daily(symbol=symbol, adjust=adjust)
    assert is_empty(result) is empty


@pytest.mark.parametrize(
    'symbol,adjust', [
        ('688001', 'qfq'),
        ('000001', 'qfq'),
        ('127021', 'qfq'),
    ])
def test_daily_qfq_is_disabled_in_records_mode(reader, symbol, adjust):
    with pytest.raises(NotImplementedError):
        reader.daily(symbol=symbol, adjust=adjust)


@pytest.mark.parametrize(
    'symbol,adjust', [
        ('688001', '02'),
        ('000001', 'hfq'),
        ('127021', 'hfq'),
    ])
def test_daily_hfq_is_disabled_in_records_mode(reader, symbol, adjust):
    with pytest.raises(NotImplementedError):
        reader.daily(symbol=symbol, adjust=adjust)


@pytest.mark.parametrize('symbol', ['688001', '688001.5', '688001.loc1'])
def test_minute(reader, symbol):
    for suffix in ('1', '5'):
        result = reader.minute(symbol=symbol, suffix=suffix)
        assert is_empty(result) is False
