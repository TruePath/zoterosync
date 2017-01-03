import pytest
import zoterosync


class ZoteroLocal(object):
    pass


@pytest.fixture
def zoterolocal():
    return zoterosync.ZoteroLibrary(ZoteroLocal())


@pytest.fixture
def zoteroremote():
    return zoterosync.ZoteroLibrary(3661336, "NnfdXD5dmXkCJcGUBDgJTEV9")
