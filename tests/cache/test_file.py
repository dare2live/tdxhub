import datetime
import unittest
from pathlib import Path
from unittest import mock

import freezegun

from tdxhub.cache import file_cache

NUM_SAMPLES = 10
DUMMY_TIME = datetime.datetime(2012, 1, 1, tzinfo=datetime.timezone.utc)

number_of_times_called = 0


def sample_function() -> list[dict]:
    return [
        {'int': i, 'str': str(i), 'num': float(i)}
        for i in range(NUM_SAMPLES)
    ]


class TestCacheFile(unittest.TestCase):
    def setUp(self) -> None:
        self.filepath = 'sample.pkl'
        Path(self.filepath).unlink(missing_ok=True)

    @mock.patch('pickle.dump')
    def test_caches_if_not_exists(self, mock_file: mock.MagicMock) -> None:
        wrapped_func = file_cache(self.filepath)(sample_function)

        actual = wrapped_func()
        expected = sample_function()

        assert actual == expected
        mock_file.assert_called_once()

    @freezegun.freeze_time(DUMMY_TIME)
    @mock.patch('os.path.getmtime', return_value=DUMMY_TIME.timestamp())
    @mock.patch('pickle.dump')
    def test_does_not_cache_if_not_expired(self, mock_file: mock.MagicMock, mock_getmtime: mock.MagicMock) -> None:
        refresh_time = 100

        expected = sample_function()
        Path(self.filepath).write_bytes(b"cached")
        with mock.patch('pickle.load', return_value=expected):
            wrapped_func = file_cache(self.filepath, refresh_time=refresh_time)(sample_function)

            actual = wrapped_func()

        assert actual == expected
        mock_file.assert_not_called()

    @freezegun.freeze_time(DUMMY_TIME, as_kwarg='frozen_time')
    @mock.patch('os.path.getmtime', return_value=DUMMY_TIME.timestamp())
    @mock.patch('pickle.dump')
    def test_caches_if_expired(self, mock_file: mock.MagicMock, mock_getmtime: mock.MagicMock,
                               frozen_time=None) -> None:
        refresh_time = 100
        expiration_time = DUMMY_TIME + datetime.timedelta(seconds=refresh_time)

        expected = sample_function()

        frozen_time.move_to(expiration_time + datetime.timedelta(seconds=10))
        with mock.patch('pickle.load', return_value=expected):
            wrapped_func = file_cache(self.filepath, refresh_time=refresh_time)(sample_function)
            actual = wrapped_func()

        assert actual == expected
        mock_file.assert_called_once()
