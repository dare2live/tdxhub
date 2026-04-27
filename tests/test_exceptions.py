from tdxhub.exceptions import FileNeedRefresh
from tdxhub.exceptions import MootdxDependencyException
from tdxhub.exceptions import MootdxException
from tdxhub.exceptions import TdxhubModuleNotFoundError
from tdxhub.exceptions import MootdxValidationException


def test_exception_hierarchy_and_metadata():
    err = MootdxException('boom', provider='hq', response={'ok': False}, data={'code': '000001'})

    assert str(err) == 'boom'
    assert err.provider == 'hq'
    assert err.response == {'ok': False}
    assert err.data == {'code': '000001'}
    assert repr(err) == '<MootdxException: boom>'


def test_validation_exception_inherits_base_and_value_error():
    err = MootdxValidationException('市场代码错误')

    assert isinstance(err, MootdxException)
    assert isinstance(err, ValueError)
    assert str(err) == '市场代码错误'


def test_dependency_exception_hierarchy():
    err = TdxhubModuleNotFoundError('missing mini-racer')

    assert isinstance(err, MootdxDependencyException)
    assert isinstance(err, ModuleNotFoundError)
    assert isinstance(err, MootdxException)
    assert str(err) == 'missing mini-racer'


def test_file_need_refresh_still_behaves_like_file_not_found():
    err = FileNeedRefresh('cache expired')

    assert isinstance(err, FileNotFoundError)
    assert isinstance(err, MootdxException)
    assert str(err) == 'cache expired'