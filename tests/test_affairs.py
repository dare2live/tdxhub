import glob
import struct
import unittest
from pathlib import Path

import pytest

from tdxhub.affair import Affair
from tdxhub.financial.financial import Financial
from tdxhub.financial.financial import FinancialReader
from tdxhub.financial.financial import _field_index_for_column
from tdxhub.financial.financial import _normalize_selected_columns
from tdxhub.logger import logger


def _write_gpcw_dat(path: Path, *, report_date: int = 20260331, field_count: int = 4):
    header_format = '<1hI1H3L'
    stock_item_format = '<6s1c1L'
    header_size = struct.calcsize(header_format)
    stock_item_size = struct.calcsize(stock_item_format)
    data_offset = header_size + stock_item_size
    with path.open('wb') as fp:
        fp.write(struct.pack(header_format, 1, report_date, 1, 0, field_count * 4, 0))
        fp.write(struct.pack(stock_item_format, b'000001', b'\x00', data_offset))
        fp.write(struct.pack(f'<{field_count}f', *[float(i) for i in range(1, field_count + 1)]))


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


def test_to_records_keeps_only_requested_gpcw_columns():
    data = [('000001', 20260331, 1.23, 4.56)]

    records = Financial.to_records(data, columns=['report_date', '基本每股收益', '每股净资产'])

    assert list(records[0].keys()) == ['code', 'report_date', '基本每股收益', '每股净资产']
    assert records[0]['code'] == '000001'
    assert records[0]['基本每股收益'] == pytest.approx(1.23)
    assert records[0]['每股净资产'] == pytest.approx(4.56)


def test_to_records_can_drop_report_date_from_projection():
    data = [('000001', 20260331, 1.23, 4.56)]

    records = Financial.to_records(data, columns=['基本每股收益', '每股净资产'])

    assert list(records[0].keys()) == ['code', '基本每股收益', '每股净资产']
    assert records[0]['基本每股收益'] == pytest.approx(1.23)


def test_to_records_extends_unknown_tail_gpcw_columns_as_raw_names():
    data = [('000001', 20260331, *range(1, 585))]

    records = Financial.to_records(data)

    assert list(records[0].keys())[-4:] == ['col581', 'col582', 'col583', 'col584']
    assert records[0]['col581'] == pytest.approx(581)
    assert records[0]['col584'] == pytest.approx(584)


def test_raw_gpcw_columns_can_be_projected_beyond_known_mapping():
    data = [('000001', 20260331, 581.0)]

    records = Financial.to_records(data, columns=['col581'])

    assert list(records[0].keys()) == ['code', 'col581']
    assert records[0]['col581'] == pytest.approx(581.0)
    assert _normalize_selected_columns(['code', 'col581']) == ('col581',)
    assert _field_index_for_column('col581') == 580


def test_to_df_compatibility_name_returns_records():
    data = [('000001', 20260331, 1.23)]

    assert Financial.to_df(data, columns=['基本每股收益']) == [
        {'code': '000001', '基本每股收益': pytest.approx(1.23)}
    ]


def test_financial_reader_to_data_returns_records(tmp_path):
    dat_path = tmp_path / 'gpcw20260331.dat'
    _write_gpcw_dat(dat_path, field_count=2)

    records = FinancialReader.to_data(dat_path, columns=['report_date', '基本每股收益'])

    assert records == [
        {'code': '000001', 'report_date': 20260331, '基本每股收益': pytest.approx(1.0)}
    ]


def test_parse_rejects_raw_projection_outside_report_width(tmp_path):
    dat_path = tmp_path / 'gpcw20260331.dat'
    _write_gpcw_dat(dat_path, field_count=2)

    with dat_path.open('rb') as fp, pytest.raises(ValueError, match='report_fields_count=2'):
        Financial().parse(fp, columns=['col3'])


def test_inspect_reports_dynamic_gpcw_schema(tmp_path):
    dat_path = tmp_path / 'gpcw20260331.dat'
    _write_gpcw_dat(dat_path, field_count=584)

    with dat_path.open('rb') as fp:
        info = Financial().inspect(fp, sample_size=1)

    assert info['report_date'] == 20260331
    assert info['stock_count'] == 1
    assert info['report_fields_count'] == 584
    assert info['raw_tail_columns'] == ['col581', 'col582', 'col583', 'col584']
    assert info['raw_tail_count'] == 4
    assert info['sample'] == [{'code': '000001', 'non_zero_fields': 584, 'zero_fields': 0}]


if __name__ == '__main__':
    unittest.main()
