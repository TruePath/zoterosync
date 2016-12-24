import pytest
import zoterosync


@pytest.fixture
def zoteroremote():
    return zoterosync.ZoteroLibrary(3661336, "NnfdXD5dmXkCJcGUBDgJTEV9")
