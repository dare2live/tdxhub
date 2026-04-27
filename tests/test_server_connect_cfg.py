import asyncio
import copy
import importlib
import json

from click.testing import CliRunner

server_module = importlib.import_module('tdxhub.server')
cli_module = importlib.import_module('tdxhub.__main__')


CONNECT_CFG_SAMPLE = """[USER]
UserName=

[HQHOST]
HostNum=2
PrimaryHost=1
HostName01=上海双线主站Z1
IPAddress01=1.1.1.1
Port01=7709
Weight01=60
Areas01=1
HostName02=深圳双线主站Z1
IPAddress02=2.2.2.2
Port02=80
Weight02=50
Areas02=4

[DSHOST]
HostNum=2
PrimaryHost=1
HostName01=扩展市场主站1
IPAddress01=3.3.3.3
Port01=7727
HostName02=扩展市场主站1重复
IPAddress02=3.3.3.3
Port02=7727
"""


def test_parse_connect_cfg_extracts_hq_and_ex_hosts(tmp_path):
    connect_cfg = tmp_path / 'connect.cfg'
    connect_cfg.write_bytes(CONNECT_CFG_SAMPLE.encode('gbk'))

    parsed = server_module.parse_connect_cfg(connect_cfg)

    assert parsed['HQ'] == [
        ('上海双线主站Z1', '1.1.1.1', 7709),
        ('深圳双线主站Z1', '2.2.2.2', 80),
    ]
    assert parsed['EX'] == [
        ('扩展市场主站1', '3.3.3.3', 7727),
    ]


def test_configure_hosts_from_connect_cfg_updates_runtime_and_persists(tmp_path):
    connect_cfg = tmp_path / 'connect.cfg'
    config_path = tmp_path / 'config.json'
    connect_cfg.write_bytes(CONNECT_CFG_SAMPLE.encode('gbk'))

    original_hosts = {key: [item.copy() for item in value] for key, value in server_module.hosts.items()}
    original_results = copy.deepcopy(server_module.results)

    try:
        imported = server_module.configure_hosts_from_connect_cfg(connect_cfg, config_path=config_path)

        assert imported['HQ'][0] == ('上海双线主站Z1', '1.1.1.1', 7709)
        assert server_module.hosts['HQ'][0]['addr'] == '1.1.1.1'
        assert server_module.hosts['EX'][0]['port'] == 7727

        config_data = json.loads(config_path.read_text(encoding='utf-8'))
        assert config_data['SERVER']['HQ'][0] == ['上海双线主站Z1', '1.1.1.1', 7709]
        assert config_data['SERVER']['EX'][0] == ['扩展市场主站1', '3.3.3.3', 7727]
    finally:
        server_module.hosts.clear()
        server_module.hosts.update(original_hosts)
        server_module.results.clear()
        server_module.results.update(original_results)


def test_verify_uses_asyncio_open_connection(monkeypatch):
    calls = {}

    class DummyWriter:
        def close(self):
            calls['closed'] = True

        async def wait_closed(self):
            calls['wait_closed'] = True

    async def fake_open_connection(addr, port):
        calls['addr'] = addr
        calls['port'] = port
        return object(), DummyWriter()

    monkeypatch.setattr(server_module.asyncio, 'open_connection', fake_open_connection)

    proxy = {'addr': '1.1.1.1', 'port': 7709, 'time': 0, 'site': '测试线路'}
    result = asyncio.run(server_module.verify(proxy))

    assert result['time'] is not None
    assert calls['addr'] == '1.1.1.1'
    assert calls['port'] == 7709
    assert calls['closed'] is True
    assert calls['wait_closed'] is True


def test_bestip_cli_imports_connect_cfg_before_ranking(monkeypatch, tmp_path):
    connect_cfg = tmp_path / 'connect.cfg'
    connect_cfg.write_bytes(CONNECT_CFG_SAMPLE.encode('gbk'))
    calls = {}
    messages = []

    def fake_configure_hosts_from_connect_cfg(path):
        calls['connect_cfg'] = path
        return {
            'HQ': [('上海双线主站Z1', '1.1.1.1', 7709)],
            'EX': [('扩展市场主站1', '3.3.3.3', 7727)],
        }

    def fake_bestip(limit, console, sync):
        calls['bestip'] = (limit, console, sync)

    monkeypatch.setattr(server_module, 'configure_hosts_from_connect_cfg', fake_configure_hosts_from_connect_cfg)
    monkeypatch.setattr(server_module, 'bestip', fake_bestip)
    monkeypatch.setattr(cli_module, 'get_config_path', lambda _: '/tmp/config.json')
    monkeypatch.setattr(cli_module.logger, 'info', messages.append)

    result = CliRunner().invoke(cli_module.entry, ['bestip', '-c', str(connect_cfg), '-l', '10'])

    assert result.exit_code == 0, result.output
    assert calls['connect_cfg'] == str(connect_cfg)
    assert calls['bestip'] == (10, True, False)
    assert any('导入服务器列表 HQ:1, EX:1' in message for message in messages)
    assert any('已经将最优服务器IP写入配置文件 /tmp/config.json' in message for message in messages)


def test_bestip_cli_without_connect_cfg_skips_import(monkeypatch):
    calls = {'imported': False}

    def fake_configure_hosts_from_connect_cfg(_):
        calls['imported'] = True
        return {}

    def fake_bestip(limit, console, sync):
        calls['bestip'] = (limit, console, sync)

    monkeypatch.setattr(server_module, 'configure_hosts_from_connect_cfg', fake_configure_hosts_from_connect_cfg)
    monkeypatch.setattr(server_module, 'bestip', fake_bestip)
    monkeypatch.setattr(cli_module, 'get_config_path', lambda _: '/tmp/config.json')
    monkeypatch.setattr(cli_module.logger, 'info', lambda *_: None)

    result = CliRunner().invoke(cli_module.entry, ['bestip'])

    assert result.exit_code == 0, result.output
    assert calls['imported'] is False
    assert calls['bestip'] == (5, True, False)