import pytest

from antenna.lib.storage import Storage


class TestStorage:
    def test_get_set(self):
        s = Storage()

        s.test1 = 'foo'
        assert s['test1'] == 'foo'

        s['test2'] = 'foo'
        assert s.test2 == 'foo'

    def test_delete(self):
        s = Storage()
        s.test1 = 'foo'
        del s.test1

    def test_exceptions(self):
        s = Storage()

        # Attribute access raises an AttributeError
        with pytest.raises(AttributeError):
            s.test1

        # Key access raises a KeyError
        with pytest.raises(KeyError):
            s['test1']

    def test_initialized(self):
        s = Storage({'test1': 'foo'})
        assert s.test1 == 'foo'
        assert s['test1'] == 'foo'

    def test_storage_len(self):
        s = Storage()
        assert len(s) == 0

        s.test1 = 'foo'
        assert len(s) == 1
