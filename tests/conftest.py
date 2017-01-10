import pytest
import zoterosync


class ZoteroLocal(object):
    pass


@pytest.fixture
def zoterolocal():
    return zoterosync.ZoteroLibrary(ZoteroLocal())


@pytest.fixture
def zoteroremote():
    return zoterosync.ZoteroLibrary.factory(475425, "")

@pytest.fixture
def zotero_write_remote():
    return zoterosync.ZoteroLibrary.factory(3661336, "NnfdXD5dmXkCJcGUBDgJTEV9")
