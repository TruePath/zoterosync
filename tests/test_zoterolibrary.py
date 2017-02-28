import pytest
import zoterosync
import datetime
import copy


@pytest.fixture
def zdocsimp(zoterolocal):
    return zoterosync.library.ZoteroDocument(zoterolocal, docsimp)


@pytest.fixture
def zdocsimp_keyonly(zoterolocal):
    return zoterosync.library.ZoteroDocument(zoterolocal, '52JRNN9E')


@pytest.fixture
def zdoc_collections(zoterolocal):
    doc_col = copy.deepcopy(docsimp)
    doc_col['data']['collections'] = ['2QWF3CPM', '3QWF3CPM']
    return zoterosync.library.ZoteroDocument(zoterolocal, doc_col)


@pytest.fixture
def zdoc_refresh_collections(zoterolocal, zdocsimp_keyonly):
    doc_col = copy.deepcopy(docsimp)
    doc_col['data']['collections'] = ['2QWF3CPM', '3QWF3CPM']
    zdocsimp_keyonly.refresh(doc_col)
    return zdocsimp_keyonly


@pytest.fixture
def zdoc_tags(zoterolocal):
    doc_tags = copy.deepcopy(docsimp)
    doc_tags['data']['tags'] = [{'tag': 'parallel'}, {'tag': 'test'}]
    return zoterosync.library.ZoteroDocument(zoterolocal, doc_tags)


@pytest.fixture
def zdoc_refresh_tags(zoterolocal, zdocsimp_keyonly):
    doc_tags = copy.deepcopy(docsimp)
    doc_tags['data']['tags'] = [{'tag': 'parallel'}, {'tag': 'test'}]
    zdocsimp_keyonly.refresh(doc_tags)
    return zdocsimp_keyonly


@pytest.fixture
def zdoc_relations(zoterolocal):
    doc_rels = copy.deepcopy(docsimp)
    doc_rels['data']['relations'] = {'dc:replaces': ['url1', 'url2'],
                                     'dc:bs': ['test1', 'test2']}
    return zoterosync.library.ZoteroDocument(zoterolocal, doc_rels)


@pytest.fixture
def zdoc_refresh_relations(zoterolocal, zdocsimp_keyonly):
    doc_rels = copy.deepcopy(docsimp)
    doc_rels['data']['relations'] = {'dc:replaces': ['url1', 'url2'],
                                     'dc:bs': ['test1', 'test2']}
    zdocsimp_keyonly.refresh(doc_rels)
    return zdocsimp_keyonly


docsimp = {'data': {
    'proceedingsTitle': 'Proceedings on Supercomputing',
    'key': '52JRNN9E',
    'itemType': 'conferencePaper',
    'title': 'Global optimization techniques for automatic parallelization of hybrid applications',
    'version': 1,
    'creators': [{'creatorType': 'author', 'firstName': 'Dhruva R.', 'lastName': 'Chakrabarti'},
                 {'creatorType': 'author', 'firstName': 'Prithviraj', 'lastName': 'Banerjee'}],
    'dateModified': '2016-12-24T02:55:29Z',
    'dateAdded': '2013-12-25T01:42:47Z',
}
}

imported_file_simp = {
    'data': {
        'contentType': 'application/pdf',
        'dateModified': '2016-12-24T02:53:19Z',
        'key': 'I9873X5Z',
        'filename': 'On Understanding Types, Data Abstraction, and Polymorphism -- Cardelli & Wegner (1985).pdf',
        'itemType': 'attachment',
        'title': 'Global optimization techniques for automatic parallelization of hybrid applications',
        'version': 1,
        'dateAdded': '2016-12-19T11:31:29Z',
        'linkMode': 'imported_file',
        'tags': [],
        'parentItem': '52JRNN9E',
        'md5': '1d0ffe22bc467a7ed478de8c1656a6e9',
    },
}


linked_file_simp = {
    'data': {
        'contentType': 'application/pdf',
        'dateModified': '2016-12-24T02:53:19Z',
        'key': 'I9873X5Z',
        'filename': 'On Understanding Types, Data Abstraction, and Polymorphism -- Cardelli & Wegner (1985).pdf',
        'itemType': 'attachment',
        'path': '/Users/T/L/test.pdf',
        'title': 'Global optimization techniques for automatic parallelization of hybrid applications',
        'version': 1,
        'dateAdded': '2016-12-19T11:31:29Z',
        'linkMode': 'linked_file',
        'tags': [],
        'parentItem': '52JRNN9E',
        'md5': '1d0ffe22bc467a7ed478de8c1656a6e9',
    },
}

coll_simp = {
    "data": {
        "key": "2QWF3CPM",
        "version": 3915,
        "name": "Computer Science",
        "parentCollection": False,
        "relations": {}
    }
}


def test_createdoc_simp(zoterolocal, zdocsimp):
    # zdoc = zoterosync.library.ZoteroDocument(zoterolocal, docsimp)
    zdoc = zdocsimp
    lib = zoterolocal
    assert zdoc.key == '52JRNN9E'
    assert zdoc.parent is None
    assert zdoc.title == 'Global optimization techniques for automatic parallelization of hybrid applications'
    assert zdoc.type == "conferencePaper"
    assert zdoc.version == 1
    assert zdoc.date_modified == datetime.datetime(
        2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
    assert zdoc.dirty is False
    assert zdoc.date_added == datetime.datetime(
        2013, 12, 25, 1, 42, 47, tzinfo=datetime.timezone.utc)
    assert zdoc['parent'] is None
    assert zdoc['title'] == zdoc.title
    assert zdoc.date_modified == zdoc["dateModified"]
    assert zdoc.date_added == zdoc["dateAdded"]
    assert 'parent' not in zdoc
    assert 'key' not in zdoc
    assert 'version' not in zdoc
    assert 'title' in zdoc
    assert "dateModified" not in zdoc
    assert "dateAdded" in zdoc
    assert "creators" in zdoc
    assert "children" in zdoc
    assert zdoc.creators == zdoc["creators"]
    assert len(zdoc.creators) == 2
    assert zdoc.creators[0].firstname == 'Dhruva R.'
    assert zdoc.creators[0].lastname == 'Chakrabarti'
    assert zdoc.creators[0].type == 'author'
    assert zdoc.creators[1].firstname == 'Prithviraj'
    assert zdoc.creators[1].lastname == 'Banerjee'
    assert zdoc.creators[1].type == 'author'
    assert zdoc in lib._documents
    assert lib.get_obj_by_key(zdoc.key) == zdoc


def test_refreshcreatedoc_simp(zoterolocal):
    zdoc = zoterosync.library.ZoteroDocument(zoterolocal, '52JRNN9E')
    lib = zoterolocal
    assert zdoc in lib._documents
    assert lib.get_obj_by_key(zdoc.key) == zdoc
    zdoc.refresh(docsimp)
    assert zdoc.key == '52JRNN9E'
    assert zdoc.parent is None
    assert zdoc.title == 'Global optimization techniques for automatic parallelization of hybrid applications'
    assert zdoc.type == "conferencePaper"
    assert zdoc.version == 1
    assert zdoc.date_modified == datetime.datetime(
        2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
    assert zdoc.dirty is False
    assert zdoc.date_added == datetime.datetime(
        2013, 12, 25, 1, 42, 47, tzinfo=datetime.timezone.utc)
    assert len(zdoc._changed_from) == 0
    assert zdoc['parent'] is None
    assert zdoc['title'] == zdoc.title
    assert zdoc.date_modified == zdoc["dateModified"]
    assert zdoc.date_added == zdoc["dateAdded"]
    assert 'parent' not in zdoc
    assert 'key' not in zdoc
    assert 'version' not in zdoc
    assert 'title' in zdoc
    assert "dateModified" not in zdoc
    assert "dateAdded" in zdoc
    assert "creators" in zdoc
    assert zdoc.creators == zdoc["creators"]
    assert len(zdoc.creators) == 2
    assert zdoc.creators[0].firstname == 'Dhruva R.'
    assert zdoc.creators[0].lastname == 'Chakrabarti'
    assert zdoc.creators[0].type == 'author'
    assert zdoc.creators[1].firstname == 'Prithviraj'
    assert zdoc.creators[1].lastname == 'Banerjee'
    assert zdoc.creators[1].type == 'author'
    assert zdoc in lib._documents
    assert lib.get_obj_by_key(zdoc.key) == zdoc


def test_modifydoc_simp(zdocsimp):
    zdoc = zdocsimp
    zdoc.title = "new title"
    zdoc.date_added = datetime.datetime(
        2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
    with pytest.raises(zoterosync.library.InvalidProperty):
        zdoc.type = "BSTYPE"
    zdoc.type = "bookSection"
    zdoc["date"] = "2001"
    assert zdoc.parent is None
    assert zdoc.title == "new title"
    assert zdoc.version == 1
    assert zdoc.date == "2001"
    assert zdoc.type == "bookSection"
    # assert zdoc.date_added == datetime.datetime(
    #     2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
    assert zdoc._data["dateAdded"] == '2013-12-25T01:42:47Z' # should remain unmodified '2016-12-24T02:55:29Z'
    assert zdoc.dirty is True
    assert zdoc.date_modified > datetime.datetime(
        2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
    assert zdoc._changed_from[
        "title"] == 'Global optimization techniques for automatic parallelization of hybrid applications'
    assert "dateAdded" not in zdoc._changed_from
    assert "dateModified" not in zdoc._changed_from
    assert zdoc._changed_from["date"] is None
    assert zdoc._changed_from['itemType'] == "conferencePaper"
    assert zdoc['parent'] is None
    assert zdoc['title'] == zdoc.title
    assert zdoc.date_modified == zdoc["dateModified"]
    assert zdoc.date_added == zdoc["dateAdded"]
    assert 'parent' not in zdoc
    assert 'key' not in zdoc
    assert 'version' not in zdoc
    assert 'title' in zdoc
    assert "date" in zdoc
    assert "dateModified" not in zdoc
    assert "dateAdded" in zdoc
    modified_data = {'version': zdoc['version'], 
                     'key': zdoc['key'],
                     'title': "new title",
                     'itemType': "bookSection",
                     "date": "2001"}
    assert zdoc.modified_data == modified_data


def test_register_new_collection(zoterolocal):
    lib = zoterolocal
    cthree = zoterosync.library.ZoteroCollection(lib, '4QWF3CPM')
    assert lib.get_obj_by_key(cthree.key) == cthree
    assert cthree in lib._collections


def test_create_collections(zoterolocal, zdoc_collections):
    zdoc = zdoc_collections
    lib = zoterolocal
    assert 'collections' in zdoc
    cols = zdoc["collections"].copy()
    assert len(cols) == 2
    cone = cols.pop()
    ctwo = cols.pop()
    assert isinstance(cone, zoterosync.library.ZoteroCollection)
    assert isinstance(ctwo, zoterosync.library.ZoteroCollection)
    assert cone.key in ['2QWF3CPM', '3QWF3CPM']
    assert ctwo.key in ['2QWF3CPM', '3QWF3CPM']
    assert cone.key != ctwo.key
    assert cone in lib._collections
    assert ctwo in lib._collections
    assert zdoc in cone.members
    assert zdoc in ctwo.members


def test_refresh_create_collections(zoterolocal, zdoc_refresh_collections):
    zdoc = zdoc_refresh_collections
    lib = zoterolocal
    assert 'collections' in zdoc
    cols = zdoc["collections"].copy()
    assert len(cols) == 2
    cone = cols.pop()
    ctwo = cols.pop()
    assert isinstance(cone, zoterosync.library.ZoteroCollection)
    assert isinstance(ctwo, zoterosync.library.ZoteroCollection)
    assert cone.key in ['2QWF3CPM', '3QWF3CPM']
    assert ctwo.key in ['2QWF3CPM', '3QWF3CPM']
    assert cone.key != ctwo.key
    assert cone in lib._collections
    assert ctwo in lib._collections
    assert zdoc in cone.members
    assert zdoc in ctwo.members


def test_modify_collections(zoterolocal, zdoc_collections):
    zdoc = zdoc_collections
    cols = zdoc["collections"].copy()
    cone = cols.pop()
    ctwo = cols.pop()
    cthree = zoterosync.library.ZoteroCollection(zoterolocal, '4QWF3CPM')
    zdoc["collections"] = {cone, cthree}
    assert zdoc["collections"] == {cone, cthree}
    assert zdoc in cone.members
    assert zdoc not in ctwo.members
    assert zdoc in cthree.members
    assert zdoc.dirty is True
    assert len(zdoc._changed_from["collections"]) == 2
    assert '2QWF3CPM' in zdoc._changed_from["collections"]
    assert '3QWF3CPM' in zdoc._changed_from["collections"]


def test_del_collections(zoterolocal, zdoc_collections):
    zdoc = zdoc_collections
    cols = zdoc["collections"].copy()
    cone = cols.pop()
    ctwo = cols.pop()
    del zdoc["collections"]
    assert zdoc["collections"] == set()
    assert zdoc not in cone.members
    assert zdoc not in ctwo.members
    assert zdoc.dirty is True
    assert len(zdoc._changed_from["collections"]) == 2
    assert '2QWF3CPM' in zdoc._changed_from["collections"]
    assert '3QWF3CPM' in zdoc._changed_from["collections"]


def test_create_tags(zoterolocal, zdoc_tags):
    zdoc = zdoc_tags
    lib = zoterolocal
    assert 'tags' in zdoc
    assert zdoc["tags"] == {'parallel', 'test'}
    assert 'parallel' in lib._tags
    assert 'test' in lib._tags
    assert zdoc in lib._tags['parallel']
    assert zdoc in lib._tags['test']


def test_refresh_create_tags(zoterolocal, zdoc_refresh_tags):
    zdoc = zdoc_refresh_tags
    lib = zoterolocal
    assert 'tags' in zdoc
    assert zdoc["tags"] == {'parallel', 'test'}
    assert 'parallel' in lib._tags
    assert 'test' in lib._tags
    assert zdoc in lib._tags['parallel']
    assert zdoc in lib._tags['test']


def test_modify_tags(zoterolocal, zdoc_tags):
    zdoc = zdoc_tags
    lib = zoterolocal
    zdoc["tags"] = {'newtest', 'parallel'}
    assert zdoc["tags"] == {'newtest', 'parallel'}
    assert 'parallel' in lib._tags
    assert 'test' not in lib._tags
    assert 'newtest' in lib._tags
    assert zdoc in lib._tags['parallel']
    assert zdoc in lib._tags['newtest']
    assert zdoc.dirty is True
    assert len(zdoc._changed_from["tags"]) == 2
    tone = zdoc._changed_from["tags"][0]["tag"]
    ttwo = zdoc._changed_from["tags"][1]["tag"]
    assert ((tone == "test" and ttwo == 'parallel') or (
        ttwo == "test" and tone == 'parallel'))


def test_del_tags(zoterolocal, zdoc_tags):
    zdoc = zdoc_tags
    lib = zoterolocal
    del zdoc["tags"]
    assert zdoc["tags"] == set()
    assert 'parallel' not in lib._tags
    assert 'test' not in lib._tags
    assert zdoc.dirty is True
    assert len(zdoc._changed_from["tags"]) == 2
    tone = zdoc._changed_from["tags"][0]["tag"]
    ttwo = zdoc._changed_from["tags"][1]["tag"]
    assert ((tone == "test" and ttwo == 'parallel') or (
        ttwo == "test" and tone == 'parallel'))


def test_create_relations(zoterolocal, zdoc_relations):
    zdoc = zdoc_relations
    assert 'relations' in zdoc
    assert zdoc["relations"] == {
        'dc:replaces': ['url1', 'url2'], 'dc:bs': ['test1', 'test2']}


def test_refresh_create_relations(zoterolocal, zdoc_refresh_relations):
    zdoc = zdoc_refresh_relations
    assert 'relations' in zdoc
    assert zdoc["relations"] == {
        'dc:replaces': ['url1', 'url2'], 'dc:bs': ['test1', 'test2']}


def test_modify_relations(zoterolocal, zdoc_relations):
    zdoc = zdoc_relations
    zdoc["relations"] = {
        'dc:fred': ['url1', 'url2'], 'dc:bs': ['test1', 'test2']}
    assert zdoc["relations"] == {
        'dc:fred': ['url1', 'url2'], 'dc:bs': ['test1', 'test2']}
    assert zdoc.dirty is True
    assert zdoc._changed_from["relations"] == {
        'dc:replaces': ['url1', 'url2'], 'dc:bs': ['test1', 'test2']}


def test_del_relations(zoterolocal, zdoc_relations):
    zdoc = zdoc_relations
    del zdoc["relations"]
    assert zdoc["relations"] == dict()
    assert zdoc.dirty is True
    assert zdoc._changed_from["relations"] == {
        'dc:replaces': ['url1', 'url2'], 'dc:bs': ['test1', 'test2']}


def test_factory_document(zoterolocal):
    zobj = zoterosync.library.ZoteroObject.factory(zoterolocal, docsimp)
    assert isinstance(zobj, zoterosync.library.ZoteroDocument)


def test_factory_document_from_document(zoterolocal):
    zobj = zoterosync.library.ZoteroDocument.factory(zoterolocal, docsimp)
    assert isinstance(zobj, zoterosync.library.ZoteroDocument)


def test_factory_document_from_item(zoterolocal):
    zobj = zoterosync.library.ZoteroItem.factory(zoterolocal, docsimp)
    assert isinstance(zobj, zoterosync.library.ZoteroDocument)


def test_factory_linked(zoterolocal):
    zobj = zoterosync.library.ZoteroObject.factory(
        zoterolocal, linked_file_simp)
    assert isinstance(zobj, zoterosync.library.ZoteroLinkedFile)


def test_factory_imported(zoterolocal):
    zobj = zoterosync.library.ZoteroObject.factory(
        zoterolocal, imported_file_simp)
    assert isinstance(zobj, zoterosync.library.ZoteroImportedFile)


def test_factory_linked_from_attachment(zoterolocal):
    zobj = zoterosync.library.ZoteroAttachment.factory(
        zoterolocal, linked_file_simp)
    assert isinstance(zobj, zoterosync.library.ZoteroLinkedFile)


def test_factory_imported_from_attachment(zoterolocal):
    zobj = zoterosync.library.ZoteroAttachment.factory(
        zoterolocal, imported_file_simp)
    assert isinstance(zobj, zoterosync.library.ZoteroImportedFile)


def test_factory_collection(zoterolocal):
    zobj = zoterosync.library.ZoteroObject.factory(zoterolocal, coll_simp)
    assert isinstance(zobj, zoterosync.library.ZoteroCollection)


def test_factory_collection_from_collection(zoterolocal):
    zobj = zoterosync.library.ZoteroCollection.factory(zoterolocal, coll_simp)
    assert isinstance(zobj, zoterosync.library.ZoteroCollection)


def test_fifty_keys_from_set(zoterolocal):
    lib = zoterolocal
    set_thirty = set()
    set_fifty = set()
    set_sixty = set()
    for i in range(30):
        set_thirty.add(str(i))
    for i in range(50):
        set_fifty.add(str(i))
    for i in range(60):
        set_sixty.add(str(i))
    key_thirty = lib._fifty_keys_from_set(set_thirty)
    assert len(key_thirty.split(',')) == 30
    key_fifty = lib._fifty_keys_from_set(set_fifty)
    assert len(key_fifty.split(',')) == 50
    key_sixty = lib._fifty_keys_from_set(set_sixty)
    assert len(key_sixty.split(',')) == 50
    assert key_thirty[-1] != ","
    assert key_fifty[-1] != ","
    assert key_sixty[-1] != ","


def test_mock_small(zoteromock_small):
    lib = zoteromock_small
    lib._queue_pull()
    assert len(lib._itemkeys_for_refresh) == 5
    assert len(lib._collkeys_for_refresh) == 20
    lib._process_pull()
    assert len(lib._itemkeys_for_refresh) == 0
    assert len(lib._collkeys_for_refresh) == 0
    assert lib.num_items == 5
    assert lib.num_collections == 20
    assert int(lib._server.request.headers.get(
        'last-modified-version', 0)) == 4030
    assert lib._version == 4030


def test_mock_delete(mock_small, zoteromock_small):
    lib = zoteromock_small
    lib.pull()
    mock_small.version = 5050
    lib._queue_pull()  # deletes after 4030 are pulled now
    assert len(lib._itemkeys_for_refresh) == 0
    assert len(lib._collkeys_for_refresh) == 0
    assert lib.num_items == 3
    assert lib.num_collections == 20
    lib._process_pull()
    assert lib._version == 5050
    mock_small.version = 6050
    lib.pull()
    assert lib.num_items == 3
    assert lib.num_collections == 19
    assert len(lib.get_obj_by_key('C776Z4WN').collections) == 0
    assert lib.get_obj_by_key('C776Z4WN').dirty is False


def test_mock_large(zoteromock):
    lib = zoteromock
