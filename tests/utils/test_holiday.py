import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import pytest

from tdxhub import get_config_path
from tests.conftest import is_empty

try:
    from py_mini_racer import MiniRacer

    MiniRacer()

    not_mini_racer = False
except Exception:
    not_mini_racer = True


def _holiday_rows():
    return [
        {'日期': '20220123', '节日': '周末', '国家': '中国', '交易所': 'SSE', 'date': datetime.date(2022, 1, 23)},
        {'日期': '20220123', '节日': '周末', '国家': '法国', '交易所': 'EURONEXT', 'date': datetime.date(2022, 1, 23)},
    ]


def _trade_rows():
    return [
        {'date': datetime.date(2022, 1, 26), 'year': 2022},
    ]


@pytest.mark.skipif(not_mini_racer, reason='py_mini_racer not installed')
class TestHoliday(TestCase):
    # 初始化工作
    # def setUp(self) -> None:
    #     Path(get_config_path('holiday.plk')).unlink(missing_ok=True)

    def test_holiday_exists(self):
        from tdxhub.utils.holiday import holiday
        with patch('tdxhub.utils.holiday._holiday', return_value=_holiday_rows()):
            result = holiday('2022-01-23')
        assert result, result

    def test_holiday_country(self):
        from tdxhub.utils.holiday import holiday
        with patch('tdxhub.utils.holiday._holiday', return_value=_holiday_rows()):
            assert holiday('2022-01-23', '%Y-%m-%d', '法国')
            assert not holiday('20220126')
            assert not holiday('2022-01-26', '%Y-%m-%d', country='巴西')

    def test_holiday_not(self):
        from tdxhub.utils.holiday import holiday
        with patch('tdxhub.utils.holiday._holiday', return_value=_holiday_rows()):
            result = holiday('2022-01-26')
        assert result is False, result

    def test_holiday_fmt(self):
        from tdxhub.utils.holiday import holiday
        with patch('tdxhub.utils.holiday._holiday', return_value=_holiday_rows()):
            assert holiday('2022-01-23', '%Y-%m-%d')
            assert holiday('20220123', '%Y%m%d')


@pytest.mark.skipif(not_mini_racer, reason='py_mini_racer not installed')
class TestHoliday2(TestCase):
    def setUp(self) -> None:
        Path(get_config_path('caches/holidays.plk')).write_text('')

    def test_holiday_not_exists(self):
        from tdxhub.utils.holiday import holiday2
        with patch('tdxhub.utils.holiday.holidays', return_value=_trade_rows()):
            assert is_empty(holiday2('2022-01-23'))

    def test_holiday_today(self):
        from tdxhub.utils.holiday import holiday2
        with patch('tdxhub.utils.holiday.holidays', return_value=_trade_rows()):
            assert not is_empty(holiday2())

    def test_holiday2not(self):
        from tdxhub.utils.holiday import holiday2
        with patch('tdxhub.utils.holiday.holidays', return_value=_trade_rows()):
            assert not is_empty(holiday2('2022-01-26'))


@pytest.mark.skipif(not_mini_racer, reason='py_mini_racer not installed')
def test_holidays(tmp_path):
    import tdxhub.utils.holiday as holiday_module

    class FakeMiniRacer:
        def eval(self, code):
            assert code

        def call(self, name, payload):
            assert name == 'd'
            assert payload == 'encoded'
            return ['2022-01-26']

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs == {'verify': False}

        def get(self, url):
            assert 'klc_td_sh' in url
            return type('Response', (), {'text': 'var hq_str=\"encoded\";'})()

    def cache_path(name):
        return str(tmp_path / name.replace('/', '_'))

    with (
        patch('py_mini_racer.MiniRacer', FakeMiniRacer),
        patch.object(holiday_module.httpx, 'Client', FakeClient),
        patch.object(holiday_module, 'get_config_path', cache_path),
    ):
        assert not is_empty(holiday_module.holidays())
