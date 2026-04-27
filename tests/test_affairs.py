import glob
import unittest
from pathlib import Path

import pytest

from tdxhub.affair import Affair
from tdxhub.financial.financial import Financial
from tdxhub.logger import logger


@pytest.mark.skip(reason='暂时不做重复测试')
class TestAffair(unittest.TestCase):
    files = []

    downdir = 'tests/fixtures/tmp'

    def setup_class(self) -> None:
        logger.info('获取文件列表')
        self.files = [x['filename'] for x in Affair.files()]
        # Path(self.downdir).is_file() or Path(self.downdir).mkdir()

    def teardown_class(self):
        [Path(x).unlink() for x in glob.glob(f'{self.downdir}/*.*')]
        Path(self.downdir).rmdir()

    def test_parse_err(self):
        data = Affair.parse(downdir=self.downdir)
        self.assertIsNone(data, data)

    def test_parse_one(self):
        data = Affair.parse(downdir=self.downdir, filename=self.files[1])
        self.assertIsNotNone(data, data)

    def test_parse_export(self):
        csv_file = Path(self.downdir, self.files[1] + '.csv')
        Affair.parse(downdir=self.downdir, filename=self.files[1]).to_csv(csv_file)
        self.assertTrue(csv_file.exists())

    def test_fetch_one(self):
        Affair.fetch(downdir=self.downdir, filename=self.files[-1])
        self.assertTrue(Path(self.downdir, self.files[-1]).exists())


def test_to_df_keeps_only_requested_gpcw_columns():
    data = [('000001', 20260331, 1.23, 4.56)]

    df = Financial.to_df(data, columns=['report_date', '基本每股收益', '每股净资产'])

    assert list(df.columns) == ['report_date', '基本每股收益', '每股净资产']
    assert df.loc['000001', '基本每股收益'] == pytest.approx(1.23)
    assert df.loc['000001', '每股净资产'] == pytest.approx(4.56)


def test_to_df_can_drop_report_date_from_projection():
    data = [('000001', 20260331, 1.23, 4.56)]

    df = Financial.to_df(data, columns=['基本每股收益', '每股净资产'])

    assert list(df.columns) == ['基本每股收益', '每股净资产']
    assert df.loc['000001', '基本每股收益'] == pytest.approx(1.23)


if __name__ == '__main__':
    unittest.main()
