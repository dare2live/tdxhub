from tdxhub.tools.tdx2csv import txt2csv


# @pytest.mark.asyncio
# async def test_covert():
#     await covert(src="tests/fixtures/export/SH#601005.txt", dst="tests/fixtures/export/SH#601005.csv")


def test_success(tmp_path):
    outfile = tmp_path / 'SH#601003.csv'
    result = txt2csv(infile='tests/fixtures/export/SH#601003.txt', outfile=str(outfile))
    assert result
    assert result[0]['date'] == '2007/02/28'
    assert result[0]['close'] == 2.12
    assert outfile.exists()


def test_exception():
    assert txt2csv(infile='setup.cfg') == []
    assert txt2csv(infile='/tmp/1.txt') == []
