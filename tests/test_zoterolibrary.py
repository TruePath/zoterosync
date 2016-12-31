import pytest
import zoterosync
import datetime

@pytest.fixture
def zoterolocal():
	return zoterosync.ZoteroLibrary(3661336, "")

@pytest.fixture
def zdocsimp(zoterolocal):
	return zoterosync.ZoteroDocument(zoterolocal, docsimp)

@pytest.fixture
def zdocone(zoterolocal):
	return zoterosync.ZoteroDocument(zoterolocal, docone)

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

docone = { 'data': {
				'proceedingsTitle': 'Proceedings on Supercomputing',
        'collections': ['2QWF3CPM'],
        'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/DBQFTAHP'
                      , 'http://zotero.org/users/3661336/items/C6IAXB94'
                      , 'http://zotero.org/users/3661336/items/VEIX2QFM'
                      , 'http://zotero.org/users/3661336/items/DQMM2KFD'
                      , 'http://zotero.org/users/3661336/items/HS74N2BJ'
                      ]},
        'key': '52JRNN9E',
        'tags': [{'tag': 'parallel'}],
        'itemType': 'conferencePaper',
        'title': 'Global optimization techniques for automatic parallelization of hybrid applications',
        'version': 1,
        'date': '2001',
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
	zdoc = zoterosync.ZoteroDocument(zoterolocal, docsimp)
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

def test_create_docone(zdocone):
	pass