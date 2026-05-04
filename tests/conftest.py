import pytest

from tdxhub.quotes import Quotes


def is_empty(obj):
    return not obj


@pytest.fixture()
def quotes():
    return Quotes.factory('std')

# @pytest.fixture()
# def reader():
#     return Reader.factory("std")
