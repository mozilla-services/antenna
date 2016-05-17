import os

import mock
import pytest

from antenna.configlib import (
    config,
    config_override,
    ConfigDictEnv,
    ConfigIniEnv,
    ConfigOSEnv,
    ConfigurationError,
    get_parser,
    parse_bool,
    ListOf,
)


def test_parse_bool_error():
    with pytest.raises(ValueError):
        parse_bool('')


@pytest.mark.parametrize('data', [
    't',
    'true',
    'True',
    'TRUE',
    'y',
    'yes',
    'YES',
    '1',
])
def test_parse_bool_true(data):
    assert parse_bool(data) == True


@pytest.mark.parametrize('data', [
    'f',
    'false',
    'False',
    'FALSE',
    'n',
    'no',
    'No',
    'NO',
    '0',
])
def test_parse_bool_false(data):
    assert parse_bool(data) == False


def test_get_parser():
    assert get_parser(bool) == parse_bool
    assert get_parser(str) == str
    foo = lambda val: val
    assert get_parser(foo) == foo


def test_ListOf():
    assert ListOf(str)('foo') == ['foo']
    assert ListOf(bool)('t,f') == [True, False]
    assert ListOf(int)('1,2,3') == [1, 2, 3]
    assert ListOf(int, delimiter=':')('1:2') == [1, 2]


def test_ConfigDictEnv():
    cde = ConfigDictEnv({'FOO': 'bar', 'NAMESPACE_FOO': 'baz'})
    assert cde.get('foo') == 'bar'
    assert cde.get('foo', namespace='namespace') == 'baz'


def test_ConfigOSEnv():
    with mock.patch('os.environ') as os_environ_mock:
        os_environ_mock.__contains__.return_value = True
        os_environ_mock.__getitem__.return_value = 'baz'
        cose = ConfigOSEnv()
        assert cose.get('foo') == 'baz'
        os_environ_mock.__getitem__.assert_called_with('FOO')


    with mock.patch('os.environ') as os_environ_mock:
        os_environ_mock.__contains__.return_value = True
        os_environ_mock.__getitem__.return_value = 'baz'
        cose = ConfigOSEnv()
        assert cose.get('foo', namespace='namespace') == 'baz'
        os_environ_mock.__getitem__.assert_called_with('NAMESPACE_FOO')


def test_ConfigIniEnv(datadir):
    ini_filename = os.path.join(datadir, 'config_test.ini')
    cie = ConfigIniEnv(ini_filename)
    assert cie.get('foo') == 'bar'
    assert cie.get('foo', namespace='namespacebaz') == 'bat'


def test_config():
    assert config('DOESNOTEXISTNOWAY') == None
    with pytest.raises(ConfigurationError):
        config('DOESNOTEXISTNOWAY', raise_error=True)
    assert config('DOESNOTEXISTNOWAY', default='ohreally') == 'ohreally'


def test_config_override():
    # Make sure the key doesn't exist
    assert config('DOESNOTEXISTNOWAY') == None

    # Try one override
    with config_override(DOESNOTEXISTNOWAY='bar'):
        assert config('DOESNOTEXISTNOWAY') == 'bar'

    # Try nested overrides--innermost one rules supreme!
    with config_override(DOESNOTEXISTNOWAY='bar'):
        with config_override(DOESNOTEXISTNOWAY='bat'):
            assert config('DOESNOTEXISTNOWAY') == 'bat'
