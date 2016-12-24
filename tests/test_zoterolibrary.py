import pytest
import zoterosync
import datetime

@pytest.fixture
def zoterolocal():
	return zoterosync.ZoteroLibrary(3661336, "")

@pytest.fixture
def zdocsimp(zoterolocal):
	return zoterosync.ZoteroDocument(zoterolocal, docsimp)


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
        'proceedingsTitle': 'Proceedings of the 15th international conference on Supercomputing'
            ,
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
        'version': 4024,
        'creators': [{'creatorType': 'author', 'firstName': 'Dhruva R.'
                     , 'lastName': 'Chakrabarti'},
                     {'creatorType': 'author', 'firstName': 'Prithviraj'
                     , 'lastName': 'Banerjee'}],
        'dateModified': '2016-12-24T02:55:29Z',
        'date': '2001',
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

def test_modifydoc_simp(zdocsimp):
	zdoc = zdocsimp
	zdoc.title = "new title"
	zdoc.date_added = datetime.datetime(2016, 12, 24, 2, 55, 29, tzinfo=datetime.timezone.utc)
	with pytest.raises(InvalidProperty):
		zdoc.type = "BSTYPE"
	zdoc.set_property('itemType', "bookSection")
	zdoc.set_property('date', "2001")