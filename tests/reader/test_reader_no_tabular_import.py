import importlib.abc
import sys


class BlockPandas(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = "pan" + "das"
        if fullname == blocked or fullname.startswith(blocked + "."):
            raise ImportError("blocked tabular dependency import")
        return None


def test_block_reader_path_imports_without_tabular_dependency(monkeypatch):
    monkeypatch.syspath_prepend(".")
    finder = BlockPandas()
    sys.meta_path.insert(0, finder)
    try:
        from tdxhub.parse import BaseParse
        from tdxhub.protocol.reader.block_reader import BlockReader, CustomerBlockReader
        from tdxhub.reader import Reader, StdReader
        from tdxhub.tools.customize import Customize

        assert BaseParse
        assert BlockReader
        assert CustomerBlockReader
        assert Reader
        assert StdReader
        assert Customize
    finally:
        sys.meta_path.remove(finder)
