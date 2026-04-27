import math
from datetime import datetime
from typing import Any
from typing import Optional
from typing import Union

import pandas
import pandas as pd
from tdxhub.protocol.exceptions import ValidationException
from tdxhub.protocol.exhq import TdxExHq_API
from tdxhub.protocol.hq import TdxHq_API
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import retry_if_result
from tenacity import stop_after_attempt
from tenacity import wait_random
from tqdm import tqdm

from tdxhub import config
from tdxhub.consts import MARKET_SH
from tdxhub.consts import MARKET_SZ
from tdxhub.consts import return_last_value
from tdxhub.exceptions import MootdxValidationException
from tdxhub.logger import logger
from tdxhub.server import check_server
from tdxhub.utils import get_frequency
from tdxhub.utils import get_stock_market
from tdxhub.utils import get_stock_markets
from tdxhub.utils import to_data


ServerAddress = tuple[str, int]
SymbolInput = Union[str, list[str]]
MarketSymbol = tuple[int, str]


class Quotes(object):
    @staticmethod
    def factory(market: str = 'std', **kwargs: Any) -> 'BaseQuotes':
        """
        股票市场 工厂方法

        :param market:  std 股票市场, ext 扩展市场， 默认股票市场
        :param kwargs:  可变参数
        :return: object
        """

        if market == 'ext':
            return ExtQuotes(**kwargs)

        return StdQuotes(**kwargs)


def valid_server(server: Any) -> Optional[ServerAddress]:
    import ipaddress

    if isinstance(server, str) and ':' in server:
        parts = server.strip().split(':')
        if len(parts) == 2:
            try:
                ipaddress.ip_address(parts[0])
                return parts[0], int(parts[1])
            except Exception:
                pass

    if isinstance(server, (tuple, list)):
        try:
            address, port = server
            ipaddress.ip_address(str(address))
            return str(address), int(port)
        except Exception:
            raise ValueError('Server 格式错误. 例如: server = ("127.0.0.1", 7709) 或 "127.0.0.1:7709"')

    return None


class BaseQuotes(object):
    client: Any = None
    bestip: Optional[ServerAddress] = None
    server: Optional[ServerAddress] = None

    verbose = False
    timeout = 15

    def __init__(
        self,
        server: Any = None,
        bestip: bool = False,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        config.setup()

        self.server = valid_server(server)
        bestip and check_server(sync=True)

        self.timeout = timeout or 15

        self.verbose = kwargs.get('verbose', False)

    def __del__(self) -> None:
        self.close()

    def reconnect(self) -> None:
        target_server = self.bestip or self.server

        if self.closed and target_server:
            self.client.connect(*target_server)

    def close(self) -> None:
        hasattr(self.client, 'close') and self.client.close()

    @property
    def closed(self) -> bool:
        transport = getattr(self.client, 'client', None)

        if not hasattr(transport, '_closed') or getattr(transport, '_closed', True):
            return True

        return False

    def pool(self) -> None:
        ...


instance: Optional[BaseQuotes] = None


def check_empty(value: Any) -> bool:
    """
    重试判断函数

    :param value: 要判断的值
    :return:
    """
    _empty = value.all().empty if isinstance(value, pd.DataFrame) else not value

    # 判断状态空，则重连接
    if instance and _empty:
        logger.warning('返回数据空, 重新连接服务器...')
        # instance.client.connect(*instance.server)

    return _empty


class StdQuotes(BaseQuotes):
    """
    股票市场实时行情"""

    def __init__(
        self,
        server: Any = None,
        bestip: bool = False,
        timeout: int = 15,
        heartbeat: bool = False,
        auto_retry: bool = True,
        raise_exception: bool = False,
        **kwargs: Any,
    ) -> None:
        """构造函数

        :param bestip:  最佳 IP
        :param timeout: 超时时间
        :param kwargs:  可变参数
        """

        super().__init__(bestip=bestip, timeout=timeout, server=server, **kwargs)

        if self.server:
            config.set('BESTIP', {'HQ': self.server})

        bestip_val = config.get('BESTIP').get('HQ') if config.get('BESTIP') else None
        if bestip_val and isinstance(bestip_val, (tuple, list)) and len(bestip_val) == 2:
            self.server = tuple(bestip_val)
        else:
            hq_list = config.get('SERVER', {}).get('HQ', [])
            self.server = tuple(hq_list[0][1:]) if hq_list else ('110.41.147.114', 7709)

        self.bestip = self.server
        ip, port = self.server

        self.client = TdxHq_API(heartbeat=heartbeat, auto_retry=auto_retry, raise_exception=raise_exception)
        self.client.connect(ip, int(port), time_out=timeout)

        global instance
        instance = self

    def traffic(self) -> Any:
        return self.client.get_traffic_stats()

    def quotes(self, symbol: Optional[SymbolInput] = None, **kwargs: Any) -> pd.DataFrame:
        """
        获取实时日行情数据

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        if not symbol:
            return to_data(None)

        if isinstance(symbol, str):
            symbol = [symbol]

        try:
            symbol = get_stock_markets(symbol)
            result = self.client.get_security_quotes(symbol)
        except ValidationException:
            return to_data(None)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def bars(
        self,
        symbol: str = '000001',
        frequency: Union[int, str] = 9,
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        获取实时日K线数据

        :param symbol: 股票代码
        :param frequency: 数据频次
        :param start: 开始位置
        :param offset: 每次获取条数
        :return: pd.dataFrame or None
        """
        frequency = get_frequency(frequency)
        market = get_stock_market(symbol)

        offset = (offset, 800)[offset > 800]
        result = self.client.get_security_bars(int(frequency), int(market), str(symbol), int(start), int(offset))

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def stock_count(self, market: int = MARKET_SH) -> int:
        """
        获取市场股票数量

        :param market: 股票市场代码 sh 上海， sz 深圳
        :return: pd.dataFrame or None
        """
        if market not in [0, 1, 2]:
            raise MootdxValidationException('市场代码错误')

        result = self.client.get_security_count(market=market)

        return result

    def stocks(self, market: int = MARKET_SH) -> Optional[pd.DataFrame]:
        """
        获取股票列表

        :param market: 股票市场
        :return:
        """

        if market not in [0, 1]:
            raise MootdxValidationException('市场代码错误, 目前只支持沪深市场')

        counts = self.stock_count(market=market)
        stocks = None

        if counts > 0:
            for start in tqdm(range(0, counts, 1000), ascii=True):
                result = self.client.get_security_list(market=market, start=start)
                stocks = pandas.concat([stocks, to_data(result)], ignore_index=True) if start > 1 else to_data(result)

        return stocks

    def stock_all(self) -> Optional[pd.DataFrame]:
        stocks = None

        for m in [0, 1]:
            stocks = pandas.concat([stocks, self.stocks(m)], ignore_index=True)

        return stocks

    def index_bars(
        self,
        symbol: str = '000001',
        frequency: Union[int, str] = 9,
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        获取指数k线

        :param symbol: 股票代码
        :param frequency: 数据频次
        :param start: 开始位置
        :param offset: 获取数量
        :return:
        """

        frequency = get_frequency(frequency)
        offset = (offset, 800)[offset > 800]

        market = (MARKET_SZ, MARKET_SH)[symbol[:2] in ['00', '88', '99']]
        result = self.client.get_index_bars(int(frequency), int(market), str(symbol), int(start), int(offset))

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def minute(self, symbol: Optional[str] = None, **kwargs: Any) -> pd.DataFrame:
        """
        获取实时分时数据

        :param symbol: 股票代码
        :return: pd.DataFrame
        """

        today = datetime.now().strftime('%Y%m%d')
        return self.minutes(symbol=symbol, date=today, **kwargs)

    def minutes(self, symbol: Optional[str] = None, date: str = '20191023', **kwargs: Any) -> pd.DataFrame:
        """
        分时历史数据

        :param symbol:  股票代码
        :param date:    查询日期
        :return: pd.dataFrame or None
        """

        market = get_stock_market(symbol)

        if market not in [0, 1]:
            raise MootdxValidationException('市场代码错误, 目前只支持沪深市场')

        result = self.client.get_history_minute_time_data(market=market, code=symbol, date=date)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def transaction(self, symbol: str = '', start: int = 0, offset: int = 800, **kwargs: Any) -> pd.DataFrame:
        """
        查询分笔成交

        :param symbol:  股票代码
        :param start:   起始位置
        :param offset:  结束位置
        :return: pd.dataFrame or None
        """

        market = get_stock_market(symbol)

        result = self.client.get_transaction_data(int(market), symbol, start, offset)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def transactions(
        self,
        symbol: str = '',
        start: int = 0,
        offset: int = 800,
        date: str = '20170209',
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        查询历史分笔成交

        :param symbol:  股票代码
        :param start:   起始位置
        :param offset:  获取数量
        :param date:    查询日期
        :return: pd.dataFrame or None
        """

        market = get_stock_market(symbol, string=False)

        if market not in [0, 1]:
            raise MootdxValidationException('市场代码错误, 目前只支持沪深市场')

        result = self.client.get_history_transaction_data(market, symbol, start, offset, int(date))
        return to_data(result, symbol=symbol, client=self, **kwargs)

    def F10C(self, symbol: str = '') -> Any:  # noqa: N802
        """
        查询公司信息目录

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        market = int(get_stock_market(symbol))

        if market not in [0, 1]:
            raise MootdxValidationException('市场代码错误, 目前只支持沪深市场')

        result = self.client.get_company_info_category(market, symbol)

        return result

    def F10(self, symbol: str = '', name: str = '') -> Any:  # noqa: N802
        """
        读取公司信息详情

        :param name: 公司 F10 标题
        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        result: dict[str, Any] = {}
        market = int(get_stock_market(symbol, string=False))

        if market not in [0, 1]:
            raise MootdxValidationException('市场代码错误, 目前只支持沪深市场')

        category = self.client.get_company_info_category(market, symbol)

        if not category:
            return None

        if name:
            for x in category:
                if x['name'] == name:
                    return self.client.get_company_info_content(
                        market=market,
                        code=symbol,
                        filename=x['filename'],
                        start=x['start'],
                        length=x['length'],
                    )

        for x in category:
            result[x['name']] = self.client.get_company_info_content(
                market=market, code=symbol, filename=x['filename'], start=x['start'], length=x['length']
            )

        return result

    def xdxr(self, symbol: str = '', **kwargs: Any) -> pd.DataFrame:
        """
        读取除权除息信息

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        market = get_stock_market(symbol)
        result = self.client.get_xdxr_info(int(market), symbol)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def finance(self, symbol: str = '000001', **kwargs: Any) -> pd.DataFrame:
        """
        读取财务信息

        :param symbol: 股票代码
        :return:
        """

        market = get_stock_market(symbol)
        result = self.client.get_finance_info(market=market, code=symbol)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def k(
        self,
        symbol: str = '',
        begin: Optional[str] = None,
        end: Optional[str] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        读取k线信息

        :param symbol:  股票代码
        :param begin:   开始日期
        :param end:     截止日期
        :return: pd.dataFrame or None
        """

        result = self.get_k_data(symbol, begin, end)
        return to_data(result, symbol=symbol, **kwargs)

    def ohlc(self, **kwargs: Any) -> pd.DataFrame:
        return self.k(**kwargs)

    def get_k_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        # 开始时间离现在有几天
        first = (pd.to_datetime(end_date) - pd.to_datetime(datetime.now().date())).days
        first = (abs(first), 0)[first >= 0]

        # 结束时间离现在有几天
        last = (pd.to_datetime(start_date) - pd.to_datetime(datetime.now().date())).days
        last = (abs(last), 0)[last >= 0]

        # 去除节假日
        first -= int(first / 2.8)  # 非交易日大概是全年的1/3
        last -= int(last / 3.5)  # 非交易日大概是全年的1/3

        temp = []
        market = get_stock_market(code)

        for i in range(math.ceil((last - first) / 800)):
            data = self.client.get_security_bars(9, market, code, (first + i * 800), 800)
            temp.append(self.client.to_df(data))

        data = pd.concat(temp)
        data = data.assign(date=data['datetime'].apply(lambda x: str(x)[0:10])).assign(code=str(code))
        data = data.set_index('date', drop=False, inplace=False)
        data = data.drop(['year', 'month', 'day', 'hour', 'minute', 'datetime'], axis=1)
        data = data.loc[(data.date >= start_date) & (data.date < end_date)]
        data = data.sort_index()

        return data

    def index(
        self,
        symbol: str = '000001',
        frequency: Union[int, str] = 9,
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        获取指数k线

        K线种类:
        - 0 5分钟K线
        - 1 15分钟K线
        - 2 30分钟K线
        - 3 1小时K线
        - 4 日K线
        - 5 周K线
        - 6 月K线
        - 7 1分钟
        - 8 1分钟K线
        - 9 日K线
        - 10 季K线
        - 11 年K线

        :param symbol:      股票代码
        :param frequency:   数据频次
        :param market:      证券市场
        :param start:       开始位置
        :param offset:      每次获取条数
        :return: pd.dataFrame or None
        """
        frequency = get_frequency(frequency)

        offset = (offset, 800)[offset > 800]
        market = (MARKET_SZ, MARKET_SH)[symbol[:2] in ['00', '88', '99']]
        result = self.client.get_index_bars(int(frequency), int(market), str(symbol), int(start), int(offset))

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def block(self, tofile: str = 'block.dat', **kwargs: Any) -> pd.DataFrame:
        """
        获取证券板块信息

        :param tofile: 保存文件
        :return: pd.dataFrame or None
        """

        result = self.client.get_and_parse_block_info(tofile)
        return to_data(result, **kwargs)


class ExtQuotes(BaseQuotes):
    """扩展市场实时行情"""

    # server = ("112.74.214.43", 7727)

    def __init__(self, server: Any = None, bestip: bool = False, timeout: int = 15, **kwargs: Any) -> None:
        """
        构造函数

        :param bestip:  最优服务器IP
        :param timeout: 超时时间
        :param kwargs:  可变参数
        """
        super().__init__(bestip=bestip, timeout=timeout, server=server, **kwargs)

        if self.server:
            config.set('BESTIP', {'EX': self.server})

        logger.warning('目前扩展市场行情接口已经失效, 后期有望修复.')

        bestip_val = config.get('BESTIP').get('EX') if config.get('BESTIP') else None
        if bestip_val and isinstance(bestip_val, (tuple, list)) and len(bestip_val) == 2:
            self.server = tuple(bestip_val)
        else:
            ex_list = config.get('SERVER', {}).get('EX', [])
            self.server = tuple(ex_list[0][1:]) if ex_list else ('47.112.95.207', 7720)

        self.bestip = self.server

        for x in ['verbose', 'server', 'quiet']:
            kwargs.pop(x, None)

        try:
            self.client = TdxExHq_API(raise_exception=False, auto_retry=True, **kwargs)
            self.client.connect(*self.server)
        except Exception:  # noqa
            logger.error('服务器连接超时.')

        global instance
        instance = self

    @staticmethod
    def validate(market: Optional[Union[int, str]], symbol: str) -> MarketSymbol:
        """
        验证股票市场

        :param market: 股票市场
        :param symbol: 股票代码
        :return: tuple
        """

        if not market:
            if len(symbol.split('#')) > 1:
                market = symbol.split('#')[0]
                symbol = symbol.split('#')[1]

        if not market:
            raise ValueError('市场参数错误, 市场参数不能为空.')

        return int(market), symbol

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def markets(self, **kwargs: Any) -> pd.DataFrame:
        """
        获取实时市场列表

        :return: pd.dataFrame or None
        """

        result = self.client.get_markets()
        return to_data(result, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def instrument(self, start: int = 0, offset: int = 800, **kwargs: Any) -> pd.DataFrame:
        """
        查询代码列表

        :param start:   开始位置
        :param offset:  获取数量
        :return:
        """

        result = self.client.get_instrument_info(start=start, count=offset)
        return to_data(result, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def instrument_count(self) -> int:
        """
        市场商品数量

        :return:
        """

        result = self.client.get_instrument_count()

        return result

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def instruments(self, **kwargs: Any) -> pd.DataFrame:
        """
        查询所有代码列表

        :return:
        """

        result: list[Any] = []

        count = self.client.get_instrument_count()
        pages = math.ceil(count / 100)

        for page in tqdm(range(0, pages), ascii=True):
            result += self.client.get_instrument_info(page * 100, 100)

        return to_data(result, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def quote(
        self,
        market: Optional[Union[int, str]] = '',
        symbol: str = '',
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        查询五档行情

        :param market: 市场ID
        :param symbol: 证券代码
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_instrument_quote(market, symbol)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def minute(
        self,
        market: Optional[Union[int, str]] = '',
        symbol: str = '',
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        查询分时行情

        :param market: 市场ID
        :param symbol: 证券代码
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_minute_time_data(market, symbol)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def minutes(
        self,
        market: Optional[Union[int, str]] = None,
        symbol: str = '',
        date: str = '',
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        查询历史分时行情

        :param market:  市场ID
        :param symbol:  证券代码
        :param date:    查询日期
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_history_minute_time_data(market, symbol, date)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def bars(
        self,
        frequency: Union[int, str] = '',
        market: Optional[Union[int, str]] = '',
        symbol: str = '',
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        查询k线数据

        :param frequency: 数据频次, K线周期
        :param market: 市场ID
        :param symbol: 证券代码
        :param start:  起始位置
        :param offset: 获取数量
        :return:
        """

        frequency = get_frequency(frequency)
        market, symbol = self.validate(market, symbol)
        result = self.client.get_instrument_bars(
            category=frequency, market=market, code=symbol, start=start, count=offset
        )

        return to_data(result, symbol=symbol, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def transaction(
        self,
        market: Optional[Union[int, str]] = None,
        symbol: str = '',
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        查询分笔成交

        :param market: 市场ID
        :param symbol: 证券代码
        :param start:  开始位置
        :param offset: 获取数量
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_transaction_data(market=market, code=symbol, start=start, count=offset)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def transactions(
        self,
        market: Optional[Union[int, str]] = None,
        symbol: str = '',
        date: str = '',
        start: int = 0,
        offset: int = 800,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        查询历史分笔成交

        :param market:  市场ID
        :param symbol:  证券代码
        :param date:    查询日期
        :param start:   开始位置
        :param offset:  获取数量
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_history_transaction_data(
            market=market, code=symbol, date=int(date), start=start, count=offset
        )

        return to_data(result, symbol=symbol, client=self, **kwargs)
