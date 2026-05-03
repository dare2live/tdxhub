import glob
import unittest
from pathlib import Path

import pytest

from tdxhub.affair import Affair
from tdxhub.financial import financial
from tdxhub.logger import logger


@pytest.mark.skip(reason='暂时不做重复测试')
class TestAffair(unittest.TestCase):
    files = []

    downdir = 'tests/fixtures/tmp'

    def setup_class(self) -> None:
        logger.debug('setup_class: 获取文件列表')
        self.files = [x['filename'] for x in Affair.files() if x['filesize'] > 165]
        Path(self.downdir).is_file() or Path(self.downdir).mkdir()

    def teardown_class(self):
        logger.debug('teardown_class: 删除测试数据')
        [Path(x).unlink() for x in glob.glob(f'{self.downdir}/*.*')]
        Path(self.downdir).rmdir()

    def test_parse_err(self):
        data = Affair.parse(downdir=self.downdir)
        self.assertIsNone(data, data)

    def test_parse_one(self):
        Affair.parse(filename='gpcw20220331.zip', downdir='output')
        data = Affair.parse(downdir=self.downdir, filename=self.files[1])
        self.assertIsNotNone(data, data)

    def test_parse_export(self):
        csv_file = Path(self.downdir, self.files[1] + '.csv')
        Affair.parse(downdir=self.downdir, filename=self.files[1]).to_csv(csv_file)
        self.assertTrue(csv_file.exists())

    def test_fetch_one(self):
        Affair.fetch(downdir=self.downdir, filename=self.files[-1])
        self.assertTrue(Path(self.downdir, self.files[-1]).exists())


if __name__ == '__main__':
    unittest.main()


def test_financial_list_content_closes_api_when_connect_returns_bool(monkeypatch, tmp_path):
    closed = {"value": False}

    class FakeApi:
        need_setup = True

        def __init__(self, **_kwargs):
            pass

        def connect(self, *_args):
            return True

        def get_report_file_by_size(self, filename, **_kwargs):
            assert filename == "tdxfin/gpcw.txt"
            return b"gpcw20260331.zip,abc,120000\n"

        def close(self):
            closed["value"] = True

    monkeypatch.setattr(financial, "TdxHq_API", FakeApi)
    crawler = financial.FinancialList()
    crawler.bestip = ("1.1.1.1", 7727)
    output = tmp_path / "gpcw.txt"

    handle = crawler.content(downdir=str(output))

    handle.close()
    assert output.read_bytes() == b"gpcw20260331.zip,abc,120000\n"
    assert closed["value"] is True


def test_financial_content_raises_clear_error_when_connect_fails(monkeypatch, tmp_path):
    class FakeApi:
        need_setup = True

        def connect(self, *_args):
            return False

        def close(self):
            raise AssertionError("close should not be called after failed connect")

    monkeypatch.setattr(financial, "TdxHq_API", FakeApi)
    crawler = financial.Financial()
    crawler.bestip = ("1.1.1.1", 7727)

    with pytest.raises(ConnectionError, match="connect to TDX financial server failed"):
        crawler.content(downdir=str(tmp_path), filename="gpcw20260331.zip")
