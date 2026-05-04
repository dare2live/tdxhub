import csv
import datetime
import logging
import re
from io import StringIO
from pathlib import Path

import httpx
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_fixed

from tdxhub import get_config_path
from tdxhub.cache import file_cache
from tdxhub.consts import return_last_value
from tdxhub.exceptions import TdxhubModuleNotFoundError
from tdxhub.logger import logger

JS_DECODE = (Path(__file__).parent / 'holiday.js').read_text(encoding='utf-8')


def holidays() -> list[dict]:
    try:
        from py_mini_racer import MiniRacer
    except (ImportError, ModuleNotFoundError):
        logging.warning('!!! 缺少依赖, 请安装 tdxhub[racer] 或 mini-racer（导入模块名仍为 py_mini_racer）')
        raise TdxhubModuleNotFoundError('!!! 缺少依赖, 请安装 tdxhub[racer] 或 mini-racer（导入模块名仍为 py_mini_racer）')

    cache_file = get_config_path('caches/holidays.plk')

    @file_cache(filepath=cache_file, refresh_time=3600 * 24)
    @retry(wait=wait_fixed(2), retry_error_callback=return_last_value, stop=stop_after_attempt(5))
    def _holidays() -> list[dict]:

        logger.debug('调用远程接口')
        client = httpx.Client(verify=False)

        url = 'https://finance.sina.com.cn/realstock/company/klc_td_sh.txt'
        res = client.get(url)

        js_code = MiniRacer()
        js_code.eval(JS_DECODE)

        # 执行js解密代码
        dict_list = js_code.call('d', res.text.split('=')[1].split(';')[0].replace('"', ''))

        temp_list = [_parse_holiday_date(item) for item in dict_list]
        temp_list.append(datetime.date(1992, 5, 4))  # 是交易日但是交易日历缺失该日期
        temp_list.sort()

        return [{'date': item, 'year': item.year} for item in temp_list]

    result = _holidays()

    if not result:
        Path(cache_file).unlink(missing_ok=True)
        return []

    return result


def holiday2(date: str = None) -> list[dict]:
    """交易日历-历史数据
    :return: 交易日历
    :rtype: records
    """

    rows = holidays()

    if date:
        try:
            date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            date = datetime.datetime.now().date()

        return [row for row in rows if row.get('date') == date]

    return rows


def holiday(date=None, format_=None, country=None, result=False):
    format_ = format_ if format_ else '%Y-%m-%d'
    country = country if country else '中国'

    try:
        if date:
            date = datetime.datetime.strptime(date, format_).date()
        else:
            date = datetime.datetime.now().date()
    except ValueError:
        logger.error('日期或者日期格式错误!')
        return None

    rows = _holiday()

    if country not in {row['国家'] for row in rows}:
        logger.error(f'没有该国家`{country}`的交易日数据')
        return None

    rows = [row for row in rows if row['国家'] == country and row['date'] == date]

    if result:
        return rows

    logger.debug(date.weekday())

    return bool(rows) or date.weekday() >= 5


@file_cache(filepath=get_config_path('caches/holiday.plk'), refresh_time=3600 * 24)
def _holiday():
    logger.debug('调用远程接口')
    res = httpx.get('https://www.tdx.com.cn/url/holiday/')

    res.encoding = 'gbk'
    ret = re.findall(r'<textarea id="data" style="display:none;">([\s\w\W]+)</textarea>', res.text, re.M)[0].strip()

    reader = csv.reader(StringIO(ret), delimiter='|')
    rows = []
    for row in reader:
        if len(row) < 4:
            continue
        date_text, festival, country, exchange = row[:4]
        try:
            date_value = datetime.datetime.strptime(str(date_text), '%Y%m%d').date()
        except ValueError:
            continue
        rows.append({'日期': date_text, '节日': festival, '国家': country, '交易所': exchange, 'date': date_value})

    if not rows:
        Path(get_config_path('caches/holiday.plk')).unlink(missing_ok=True)
        return []

    return rows


def holiday_(date=None, format_=None, country=None):
    return holiday(date=date, format_=format_, country=country, result=True)


def _parse_holiday_date(value):
    if isinstance(value, dict):
        value = value.get('date') or value.get('日期')
    if hasattr(value, 'date') and not isinstance(value, datetime.date):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value)
    for fmt in ('%Y-%m-%d', '%Y%m%d'):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'unsupported holiday date: {value!r}')
