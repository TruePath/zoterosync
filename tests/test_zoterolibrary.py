import pytest
import zoterosync
import datetime
import copy

@pytest.fixture
def zoterolocal():
	return zoterosync.ZoteroLibrary(3661336, "")

@pytest.fixture
def zdocsimp(zoterolocal):
	return zoterosync.ZoteroDocument(zoterolocal, docsimp)

@pytest.fixture
def zdocsimp_keyonly(zoterolocal):
	return zoterosync.ZoteroDocument(zoterolocal, '52JRNN9E')

@pytest.fixture
def zdoc_collections(zoterolocal):
	doc_col = copy.deepcopy(docsimp)
	doc_col['data']['collections'] = ['2QWF3CPM', '3QWF3CPM']
	return zoterosync.ZoteroDocument(zoterolocal, doc_col)

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
	return zoterosync.ZoteroDocument(zoterolocal, doc_tags)

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
	return zoterosync.ZoteroDocument(zoterolocal, doc_rels)

@pytest.fixture
def zdoc_refresh_relations(zoterolocal, zdocsimp_keyonly):
	doc_rels = copy.deepcopy(docsimp)
	doc_rels['data']['relations'] = {'dc:replaces': ['url1', 'url2'],
                           'dc:bs': ['test1', 'test2']}
	zdocsimp_keyonly.refresh(doc_rels)
	return zdocsimp_keyonly

docsimp = { 'data': {
        'proceedingsTitle': 'Proceedings on Supercomputing',
        'key': '52JRNN9E',
        'itemType': 'conferencePaper',
        'title': 'Global optimization techniques for automatic parallelization of hybrid applications',
        'version': 1,
        'creators': [{'creatorType': 'author', 'firstName': 'Dhruva R.'
                     , 'lastName': 'Chakrabarti'},
                     {'creatorType': 'author', 'firstName': 'Prithviraj'
                     , 'lastName': 'Banerjee'}],
        'dateModified': '2016-12-24T02:55:29Z',
        'dateAdded': '2013-12-25T01:42:47Z',
        }
      }


def test_createdoc_simp(zdocsimp):
	# zdoc = zoterosync.ZoteroDocument(zoterolocal, docsimp)
	zdoc = zdocsimp
	assert zdoc.key == '52JRNN9E'
	assert zdoc.parent is None
	assert zdoc.title == 'Global optimization techniques for automatic parallelization of hybrid applications'
	assert zdoc.type == "conferencePaper"
	assert zdoc.version == 1
	assert zdoc.date_modified == datetime.datetime(2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
	assert zdoc.dirty is False
	assert zdoc.date_added == datetime.datetime(2013, 12, 25, 1, 42, 47, tzinfo=datetime.timezone.utc)
	assert zdoc['parent'] is None
	assert zdoc['title'] == zdoc.title
	assert zdoc.date_modified == zdoc["dateModified"]
	assert zdoc.date_added == zdoc["dateAdded"]
	assert 'parent' not in zdoc
	assert 'key' not in zdoc
	assert 'version' not in zdoc
	assert 'title' in zdoc
	assert "dateModified" in zdoc
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

def test_refreshcreatedoc_simp(zoterolocal):
	zdoc = zoterosync.ZoteroDocument(zoterolocal, '52JRNN9E')
	zdoc.refresh(docsimp)
	assert zdoc.key == '52JRNN9E'
	assert zdoc.parent is None
	assert zdoc.title == 'Global optimization techniques for automatic parallelization of hybrid applications'
	assert zdoc.type == "conferencePaper"
	assert zdoc.version == 1
	assert zdoc.date_modified == datetime.datetime(2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
	assert zdoc.dirty is False
	assert zdoc.date_added == datetime.datetime(2013, 12, 25, 1, 42, 47, tzinfo=datetime.timezone.utc)
	assert len(zdoc._changed_from) == 0
	assert zdoc['parent'] is None
	assert zdoc['title'] == zdoc.title
	assert zdoc.date_modified == zdoc["dateModified"]
	assert zdoc.date_added == zdoc["dateAdded"]
	assert 'parent' not in zdoc
	assert 'key' not in zdoc
	assert 'version' not in zdoc
	assert 'title' in zdoc
	assert "dateModified" in zdoc
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

def test_modifydoc_simp(zdocsimp):
	zdoc = zdocsimp
	zdoc.title = "new title"
	zdoc.date_added = datetime.datetime(2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
	with pytest.raises(zoterosync.InvalidProperty):
		zdoc.type = "BSTYPE"
	zdoc.type = "bookSection"
	zdoc["date"] = "2001"
	assert zdoc.parent is None
	assert zdoc.title == "new title"
	assert zdoc.version == 1
	assert zdoc.date == "2001"
	assert zdoc.type == "bookSection"
	assert zdoc.date_added == datetime.datetime(2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
	assert zdoc._data["dateAdded"] == '2016-12-24T02:55:29Z'
	assert zdoc.dirty is True
	assert zdoc.date_modified > datetime.datetime(2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
	assert zdoc._changed_from["title"] == 'Global optimization techniques for automatic parallelization of hybrid applications'
	assert zdoc._changed_from["dateAdded"] == '2013-12-25T01:42:47Z'
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
	assert "dateModified" in zdoc
	assert "dateAdded" in zdoc

def test_create_collections(zoterolocal, zdoc_collections):
	zdoc = zdoc_collections
	lib = zoterolocal
	assert 'collections' in zdoc
	cols = zdoc["collections"].copy()
	assert len(cols) == 2
	cone = cols.pop()
	ctwo = cols.pop()
	assert isinstance(cone, zoterosync.ZoteroCollection)
	assert isinstance(ctwo, zoterosync.ZoteroCollection)
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
	assert isinstance(cone, zoterosync.ZoteroCollection)
	assert isinstance(ctwo, zoterosync.ZoteroCollection)
	assert cone.key in ['2QWF3CPM', '3QWF3CPM']
	assert ctwo.key in ['2QWF3CPM', '3QWF3CPM']
	assert cone.key != ctwo.key
	assert cone in lib._collections
	assert ctwo in lib._collections
	assert zdoc in cone.members
	assert zdoc in ctwo.members

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

def test_create_relations(zoterolocal, zdoc_relations):
	zdoc = zdoc_relations
	lib = zoterolocal
	assert 'relations' in zdoc
	assert zdoc["relations"] == {'dc:replaces': ['url1', 'url2'],
                           'dc:bs': ['test1', 'test2']}

def test_refresh_create_relations(zoterolocal, zdoc_refresh_relations):
	zdoc = zdoc_refresh_relations
	lib = zoterolocal
	assert 'relations' in zdoc
	assert zdoc["relations"] == {'dc:replaces': ['url1', 'url2'],
                           'dc:bs': ['test1', 'test2']}
