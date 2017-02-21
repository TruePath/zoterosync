import pytest
import zoterosync
import itertools
import functools
from functools import reduce
from pyzotero import zotero_errors
import copy

def paged_iter(iterat, n):
    itr = iter(iterat)
    deq = None
    try:
        while(True):
            deq = collections.deque(maxlen=n)
            for q in range(n):
                deq.append(next(itr))
            yield (i for i in deq)
    except StopIteration:
        yield (i for i in deq)


class ZoteroLocal(object):
    pass


class GetImplementor(object):

    def __init__(self, mock):
        self._mock = mock

    def get(self, str, num):
        return self._mock.version


class Empty(object):
    pass


class MockPyzotero(object):

    def __init__(self, items, collections, version=None):
        self._items = items
        self._collections = collections
        self._item_deletions = dict()
        self._collection_deletions = dict()
        self.request = Empty()
        self.request.headers = GetImplementor(self)
        if (version is None):
            self.version = reduce(lambda x, dct: max(x, dct["data"]["version"]), itertools.chain(
                                  self._items, self._collections), 0)
        else:
            self.version = version

    def _delete_items(self, ikeys, atversion=0):
        if (isinstance(ikeys, str)):
            ikeys = [ikeys]
        for k in ikeys:
            vers = atversion
            if (k in self._item_deletions):
                vers = min(vers, self._item_deletions[k])
            self._item_deletions[k] = vers

    def _delete_collections(self, ikeys, atversion=0):
        if (isinstance(ikeys, str)):
            ikeys = [ikeys]
        for k in ikeys:
            vers = atversion
            if (k in self._collection_deletions):
                vers = min(vers, self._collection_deletions[k])
            self._collection_deletions[k] = vers

    def item_versions(self, since=-1, **kwargs):
        return {item["data"]["key"]: item["data"]["version"] for item in self._items if item["data"]["version"] > since}

    def collection_versions(self, since=-1, **kwargs):
        return {coll["data"]["key"]: coll["data"]["version"] for
                coll in self._collections if coll["data"]["version"] > since}

    def items(self, limit=50, itemKey=None, start=1, **kwargs):
        start = start - 1
        if ("format" in kwargs and kwargs["format"] == 'versions'):
            return self.item_versions(**kwargs)
        if (itemKey is not None):
            keys = set(itemKey.split(','))
            if (not (0 < len(keys) < 51)):
                raise Exception("Too many keys")
            items = [i for i in self._items if i["data"]["key"] in keys]
        else:
            items = self._items[start:limit+start]
            if (len(self._items) > limit+start):
                self._next = functools.partialmethod(self.items, limit=limit, start=limit+start, **kwargs)
            else:
                self._next = None
        return items

    def item(self, key, **kwargs):
        items = self.items(itemKey=key)
        if (len(items) > 0):
            return items[0]
        else:
            raise zotero_errors.ResourceNotFound

    def collection(self, key):
        for c in self._collections:
            if (c["data"]["key"] == key):
                return c
        raise zotero_errors.ResourceNotFound

    def collections(self, limit=50, start=1, **kwargs):
        start = start - 1
        if ("format" in kwargs and kwargs["format"] == 'versions'):
            return self.collection_versions(**kwargs)
        colls = self._collections[start:limit+start]
        if (len(self._collections) > limit+start):
            self._next = functools.partialmethod(self.collections, limit=limit, start=limit+start, **kwargs)
        else:
            self._next = None
        return colls

    def deleted(self, since=None, **kwargs):
        if (since is None):
            raise Exception("can't call without a since argument")
        item_dels = [k for k in self._item_deletions if (self.version >= self._item_deletions[k] > since)]
        coll_dels = [k for k in self._collection_deletions if (self.version >= self._collection_deletions[k] > since)]
        return dict(collections=coll_dels, items=item_dels, searches=[], tags=[], settings=[])

    def item_types(self):
        itypes = ["artwork", "audioRecording", "bill", "blogPost", "book", "bookSection", "case",
                  "computerProgram", "conferencePaper", "dictionaryEntry", "document", "email",
                  "encyclopediaArticle", "film", "forumPost", "hearing", "instantMessage", "interview",
                  "journalArticle", "letter", "magazineArticle", "manuscript", "map", "newspaperArticle",
                  "note", "patent", "podcast", "presentation", "radioBroadcast", "report", "statute",
                  "tvBroadcast", "thesis", "videoRecording", "webpage"]
        return [dict(itemType=i, localized=i) for i in itypes]

    def item_fields(self):
        ifields = ['numPages', 'numberOfVolumes', 'abstractNote', 'accessDate', 'applicationNumber',
                   'archive', 'artworkSize', 'assignee', 'billNumber', 'blogTitle', 'bookTitle',
                   'callNumber', 'caseName', 'code', 'codeNumber', 'codePages', 'codeVolume',
                   'committee', 'company', 'conferenceName', 'country', 'court', 'DOI', 'date',
                   'dateDecided', 'dateEnacted', 'dictionaryTitle', 'distributor', 'docketNumber',
                   'documentNumber', 'edition', 'encyclopediaTitle', 'episodeNumber', 'extra',
                   'audioFileType', 'filingDate', 'firstPage', 'audioRecordingFormat',
                   'videoRecordingFormat', 'forumTitle', 'genre', 'history', 'ISBN', 'ISSN',
                   'institution', 'issue', 'issueDate', 'issuingAuthority', 'journalAbbreviation',
                   'label', 'language', 'programmingLanguage', 'legalStatus', 'legislativeBody',
                   'libraryCatalog', 'archiveLocation', 'interviewMedium', 'artworkMedium',
                   'meetingName', 'nameOfAct', 'network', 'pages', 'patentNumber', 'place',
                   'postType', 'priorityNumbers', 'proceedingsTitle', 'programTitle',
                   'publicLawNumber', 'publicationTitle', 'publisher', 'references', 'reportNumber',
                   'reportType', 'reporter', 'reporterVolume', 'rights', 'runningTime', 'scale',
                   'section', 'series', 'seriesNumber', 'seriesText', 'seriesTitle', 'session',
                   'shortTitle', 'studio', 'subject', 'system', 'title', 'thesisType', 'mapType',
                   'manuscriptType', 'letterType', 'presentationType', 'url', 'university',
                   'versionNumber', 'volume', 'websiteTitle', 'websiteType']
        return [dict(field=i, localized=i) for i in ifields]

    def item_type_fields(itemtype):
        item_fields = {'newspaperArticle': [ 'title', 'abstractNote', 'publicationTitle', 'place', 'edition', 'date', 'section', 'pages', 'language', 'shortTitle', 'ISSN', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'audioRecording': ['title', 'abstractNote', 'audioRecordingFormat', 'seriesTitle', 'volume', 'numberOfVolumes', 'place', 'label', 'date', 'runningTime', 'language', 'ISBN', 'shortTitle', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'url', 'accessDate', 'rights', 'extra', ],
                       'book': ['title', 'abstractNote', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'place', 'publisher', 'date', 'numPages', 'language', 'ISBN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'interview': ['title', 'abstractNote', 'date', 'interviewMedium', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'computerProgram': ['title', 'abstractNote', 'seriesTitle', 'versionNumber', 'date', 'system', 'place', 'company', 'programmingLanguage', 'ISBN', 'shortTitle', 'url', 'rights', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'accessDate', 'extra', ],
                       'document': ['title', 'abstractNote', 'publisher', 'date', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'blogPost': ['title', 'abstractNote', 'blogTitle', 'websiteType', 'date', 'url', 'accessDate', 'language', 'shortTitle', 'rights', 'extra', ],
                       'artwork': ['title', 'abstractNote', 'artworkMedium', 'artworkSize', 'date', 'language', 'shortTitle', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'url', 'accessDate', 'rights', 'extra', ],
                       'magazineArticle': ['title', 'abstractNote', 'publicationTitle', 'volume', 'issue', 'date', 'pages', 'language', 'ISSN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'thesis': ['title', 'abstractNote', 'thesisType', 'university', 'place', 'date', 'numPages', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'tvBroadcast': ['title', 'abstractNote', 'programTitle', 'episodeNumber', 'videoRecordingFormat', 'place', 'network', 'date', 'runningTime', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'videoRecording': ['title', 'abstractNote', 'videoRecordingFormat', 'seriesTitle', 'volume', 'numberOfVolumes', 'place', 'studio', 'date', 'runningTime', 'language', 'ISBN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'note': [],
                       'bookSection': ['title', 'abstractNote', 'bookTitle', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'place', 'publisher', 'date', 'pages', 'language', 'ISBN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'map': ['title', 'abstractNote', 'mapType', 'scale', 'seriesTitle', 'edition', 'place', 'publisher', 'date', 'language', 'ISBN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'report': ['title', 'abstractNote', 'reportNumber', 'reportType', 'seriesTitle', 'place', 'institution', 'date', 'pages', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'encyclopediaArticle': ['title', 'abstractNote', 'encyclopediaTitle', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'place', 'publisher', 'date', 'pages', 'ISBN', 'shortTitle', 'url', 'accessDate', 'language', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'statute': ['nameOfAct', 'abstractNote', 'code', 'codeNumber', 'publicLawNumber', 'dateEnacted', 'pages', 'section', 'session', 'history', 'language', 'shortTitle', 'url', 'accessDate', 'rights', 'extra', ],
                       'dictionaryEntry': ['title', 'abstractNote', 'dictionaryTitle', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'place', 'publisher', 'date', 'pages', 'language', 'ISBN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'conferencePaper': ['title', 'abstractNote', 'date', 'proceedingsTitle', 'conferenceName', 'place', 'publisher', 'volume', 'pages', 'series', 'language', 'DOI', 'ISBN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'webpage': ['title', 'abstractNote', 'websiteTitle', 'websiteType', 'date', 'shortTitle', 'url', 'accessDate', 'language', 'rights', 'extra', ],
                       'journalArticle': ['title', 'abstractNote', 'publicationTitle', 'volume', 'issue', 'pages', 'date', 'series', 'seriesTitle', 'seriesText', 'journalAbbreviation', 'language', 'DOI', 'ISSN', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'case': ['caseName', 'abstractNote', 'reporter', 'reporterVolume', 'court', 'docketNumber', 'firstPage', 'history', 'dateDecided', 'language', 'shortTitle', 'url', 'accessDate', 'rights', 'extra', ],
                       'email': ['subject', 'abstractNote', 'date', 'shortTitle', 'url', 'accessDate', 'language', 'rights', 'extra', ],
                       'letter': ['title', 'abstractNote', 'letterType', 'date', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'bill': ['title', 'abstractNote', 'billNumber', 'code', 'codeVolume', 'section', 'codePages', 'legislativeBody', 'session', 'history', 'date', 'language', 'url', 'accessDate', 'shortTitle', 'rights', 'extra', ],
                       'hearing': ['title', 'abstractNote', 'committee', 'place', 'publisher', 'numberOfVolumes', 'documentNumber', 'pages', 'legislativeBody', 'session', 'history', 'date', 'language', 'shortTitle', 'url', 'accessDate', 'rights', 'extra', ],
                       'instantMessage': ['title', 'abstractNote', 'date', 'language', 'shortTitle', 'url', 'accessDate', 'rights', 'extra', ],
                       'radioBroadcast': ['title', 'abstractNote', 'programTitle', 'episodeNumber', 'audioRecordingFormat', 'place', 'network', 'date', 'runningTime', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'podcast': ['title', 'abstractNote', 'seriesTitle', 'episodeNumber', 'audioFileType', 'runningTime', 'url', 'accessDate', 'language', 'shortTitle', 'rights', 'extra', ],
                       'film': ['title', 'abstractNote', 'distributor', 'date', 'genre', 'videoRecordingFormat', 'runningTime', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'patent': ['title', 'abstractNote', 'place', 'country', 'assignee', 'issuingAuthority', 'patentNumber', 'filingDate', 'pages', 'applicationNumber', 'priorityNumbers', 'issueDate', 'references', 'legalStatus', 'language', 'shortTitle', 'url', 'accessDate', 'rights', 'extra', ],
                       'manuscript': ['title', 'abstractNote', 'manuscriptType', 'place', 'date', 'numPages', 'language', 'shortTitle', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
                       'forumPost': ['title', 'abstractNote', 'forumTitle', 'postType', 'date', 'language', 'shortTitle', 'url', 'accessDate', 'rights', 'extra', ],
                       'presentation': ['title', 'abstractNote', 'presentationType', 'date', 'place', 'meetingName', 'url', 'accessDate', 'language', 'shortTitle', 'rights', 'extra' ]}
        return [dict(field=i, localized=i) for i in item_fields[itemtype]]

    def item_creator_types(itemtype):
        creator_types = {'newspaperArticle': ['author', 'contributor', 'reviewedAuthor','translator'],
                                   'audioRecording': ['performer', 'composer', 'contributor', 'wordsBy'],
                                   'book': ['author', 'contributor', 'editor', 'seriesEditor', 'translator'],
                                   'interview': ['interviewee', 'contributor', 'interviewer', 'translator'],
                                   'computerProgram': ['programmer', 'contributor'],
                                   'document': ['author', 'contributor', 'editor', 'reviewedAuthor', 'translator'],
                                   'blogPost': ['author', 'commenter', 'contributor'],
                                   'artwork': ['artist', 'contributor'],
                                   'magazineArticle': ['author', 'contributor', 'reviewedAuthor', 'translator'],
                                   'thesis': ['author', 'contributor'],
                                   'tvBroadcast': ['director', 'castMember', 'contributor', 'guest', 'producer', 'scriptwriter'],
                                   'videoRecording': ['director', 'castMember', 'contributor', 'producer', 'scriptwriter'],
                                   'note': [],
                                   'bookSection': ['author', 'bookAuthor', 'contributor', 'editor', 'seriesEditor', 'translator'],
                                   'map': ['cartographer', 'contributor', 'seriesEditor'],
                                   'report': ['author', 'contributor', 'seriesEditor', 'translator'],
                                   'encyclopediaArticle': ['author', 'contributor', 'editor', 'seriesEditor', 'translator'],
                                   'statute': ['author', 'contributor'],
                                   'dictionaryEntry': ['author', 'contributor', 'editor', 'seriesEditor', 'translator'],
                                   'conferencePaper': ['author', 'contributor', 'editor', 'seriesEditor', 'translator'],
                                   'webpage': ['author', 'contributor', 'translator'],
                                   'journalArticle': ['author', 'contributor', 'editor', 'reviewedAuthor', 'translator'],
                                   'case': ['author', 'contributor', 'counsel'],
                                   'email': ['author', 'contributor', 'recipient'],
                                   'letter': ['author', 'contributor', 'recipient'],
                                   'bill': ['sponsor', 'contributor', 'cosponsor'],
                                   'hearing': ['contributor'],
                                   'instantMessage': ['author', 'contributor', 'recipient'],
                                   'radioBroadcast': ['director', 'castMember', 'contributor', 'guest', 'producer', 'scriptwriter'],
                                   'podcast': ['podcaster', 'contributor', 'guest'],
                                   'film': ['director', 'contributor', 'producer', 'scriptwriter'],
                                   'patent': ['inventor', 'attorneyAgent', 'contributor'],
                                   'manuscript': ['author', 'contributor', 'translator'],
                                   'forumPost': ['author', 'contributor'],
                                   'presentation': ['presenter', 'contributor']}
        return [dict(creatorType=i, localized=i) for i in creator_types[itemtype]]

    def makeiter(self, func):
        yield func
        while(self._next is not None):
            yield self._next()


@pytest.fixture
def zoterolocal():
    return zoterosync.library.ZoteroLibrary(ZoteroLocal())


@pytest.fixture
def mock_small():
    mock = MockPyzotero(doc_data, collection_data)
    mock._delete_items(["52JRNN9E", "6NGR6H7E", "BSKEY"], 5000)
    mock._delete_collections(["2QWF3CPM", "BSKEY"], 6000)
    return mock


@pytest.fixture
def zoteromock_small(mock_small):
    return zoterosync.library.ZoteroLibrary(mock_small)


@pytest.fixture
def zoteromock():
    mock = MockPyzotero(item_data, collection_data)
    return zoterosync.library.ZoteroLibrary(mock)


@pytest.fixture
def zoteroremote():
    return zoterosync.library.ZoteroLibrary.factory(475425, "")


@pytest.fixture
def zotero_write_remote():
    return zoterosync.library.ZoteroLibrary.factory(3661336, "NnfdXD5dmXkCJcGUBDgJTEV9")


@pytest.fixture
def zotero_double_doc():
    zot = zoterosync.library.ZoteroLibrary(ZoteroLocal())
    for i in doc_data:
        zot._recieve_item(i)
    for i in copy.deepcopy(doc_data):
        i['data']['key'] = zot.new_key()
        zot._recieve_item(i)
    return zot



doc_data = [{
    'data': {
        'proceedingsTitle': 'Proceedings of the 15th international conference on Supercomputing'
            ,
        'collections': ['2QWF3CPM'],
        'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/DBQFTAHP'
                      , 'http://zotero.org/users/3661336/items/C6IAXB94'
                      , 'http://zotero.org/users/3661336/items/VEIX2QFM'
                      , 'http://zotero.org/users/3661336/items/DQMM2KFD'
                      , 'http://zotero.org/users/3661336/items/HS74N2BJ'
                      ]},
        'extra': '',
        'volume': '',
        'key': '52JRNN9E',
        'tags': [{'tag': 'parallel'}],
        'itemType': 'conferencePaper',
        'title': 'Global optimization techniques for automatic parallelization of hybrid applications'
            ,
        'url': '',
        'version': 4024,
        'abstractNote': 'This paper presents a novel technique to perform global optimization of communication and preprocessing calls in the presence of array accesses with arbitrary subscripts. Our scheme is presented in the context of automatic parallelization of sequential programs to produce message passing programs for execution on distributed machines. We use the static single assignment (SSA) form for message passing programs as the intermediate representation and then present techniques to perform global optimizations even in the presence of array accesses with arbitrary subscripts. The focus of this paper is in showing that, using a uniform compilation method both at compile-time and at run-time, our framework is able to determine the earliest and the latest legal communication point for a certain distributed array reference even in the presence of arbitrary array addressing functions. Our scheme then heuristically determines the final communication point after considering the interaction between the relevant communication schedules. Owing to combined static and dynamic analysis, a quasi-dynamic method of code generation is implemented. We describe the need for proper interaction between the compiler and the run-time routines for efficient implementation of optimizations as well as for compatible code generation. All of the analyses is initiated at compile-time, static analyses of the program is done as much as possible, and then the run-time routines take over the analyses while building on the data structures initiated at compile time. This scheme has been incorporated in our compiler framework which can use uniform methods to compile, parallelize, and optimize a sequential program irrespective of the subscripts used in array addressing functions. Experimental results for a number of benchmarks on an IBM SP-2 show up to around 10-25% reduction in total run-times in our globally-optimized schemes compared to other state-of-the-art schemes on 16 processors.'
            ,
        'series': '',
        'language': '',
        'libraryCatalog': '',
        'rights': '',
        'shortTitle': '',
        'ISBN': '1-58113-410-X',
        'DOI': '',
        'creators': [{'creatorType': 'author', 'firstName': 'Dhruva R.'
                     , 'lastName': 'Chakrabarti'},
                     {'creatorType': 'author', 'firstName': 'Prithviraj'
                     , 'lastName': 'Banerjee'}],
        'archiveLocation': '',
        'conferenceName': '',
        'accessDate': '',
        'dateModified': '2016-12-24T02:55:29Z',
        'date': '2001',
        'dateAdded': '2013-12-25T01:42:47Z',
        'callNumber': '',
        'publisher': 'ACM',
        'archive': '',
        'place': 'Sorrento, Italy',
        'pages': '166-180',
        },
    }, {
    'data': {
        'proceedingsTitle': 'Proceedings of the Fourth International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS-IV)'
            ,
        'collections': ['2QWF3CPM'],
        'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/RMAPXKX5'
                      , 'http://zotero.org/users/3661336/items/V56X68NG'
                      , 'http://zotero.org/users/3661336/items/MWTCKZGR'
                      , 'http://zotero.org/users/3661336/items/93QMAZC6'
                      ]},
        'extra': '',
        'volume': '',
        'key': '6NGR6H7E',
        'tags': [{'tag': 'Caching'}, {'tag': 'compression'}],
        'itemType': 'conferencePaper',
        'title': 'Combining the Concepts of Compression and Caching for a Two-Level Filesystem'
            ,
        'url': '',
        'version': 4023,
        'abstractNote': '',
        'series': '',
        'language': '',
        'libraryCatalog': '',
        'rights': '',
        'shortTitle': '',
        'ISBN': '',
        'DOI': '',
        'creators': [{'creatorType': 'author', 'firstName': 'V.',
                     'lastName': 'Cate'}, {'creatorType': 'author',
                     'firstName': 'T.', 'lastName': 'Gross'}],
        'archiveLocation': '',
        'conferenceName': '',
        'accessDate': '',
        'dateModified': '2016-12-24T02:53:53Z',
        'date': 'April 1991',
        'dateAdded': '2013-12-25T01:43:24Z',
        'callNumber': '',
        'publisher': '',
        'archive': '',
        'place': 'Santa Clara, CA, USA',
        'pages': '',
        },
    }, {
    'data': {
        'volume': '',
        'collections': ['2QWF3CPM'],
        'seriesTitle': '',
        'extra': '',
        'key': 'C776Z4WN',
        'tags': [{'tag': 'Mixins'}, {'tag': 'Modules'}, {'tag': 'units'
                 }],
        'itemType': 'journalArticle',
        'title': 'Reusable Software Components',
        'url': '',
        'version': 4023,
        'abstractNote': '',
        'pages': '',
        'language': '',
        'journalAbbreviation': '',
        'ISSN': '',
        'publicationTitle': '',
        'shortTitle': '',
        'libraryCatalog': '',
        'DOI': '10.1.1.17.3212',
        'creators': [{'creatorType': 'author', 'firstName': 'Robert S',
                     'lastName': 'Cartwright'}, {'creatorType': 'author'
                     , 'firstName': 'Keith D', 'lastName': 'Cooper'},
                     {'creatorType': 'author', 'firstName': 'David M',
                     'lastName': 'Lane'}, {'creatorType': 'author',
                     'firstName': 'Matthew', 'lastName': 'Flatt'},
                     {'creatorType': 'author', 'firstName': 'Matthew',
                     'lastName': 'Flatt'}],
        'archiveLocation': '',
        'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/I97X2PJP'
                      , 'http://zotero.org/users/3661336/items/FD9QGA45'
                      , 'http://zotero.org/users/3661336/items/NAIHFD2Z'
                      , 'http://zotero.org/users/3661336/items/CU29HTVK'
                      , 'http://zotero.org/users/3661336/items/B4ZQ33SS'
                      ]},
        'issue': '',
        'seriesText': '',
        'accessDate': '',
        'dateModified': '2016-12-24T02:53:45Z',
        'date': '',
        'dateAdded': '2013-12-25T01:43:39Z',
        'callNumber': '',
        'rights': '',
        'archive': '',
        'series': '',
        },
    }, {
    'data': {
        'volume': '24',
        'collections': ['2QWF3CPM'],
        'seriesTitle': '',
        'extra': '',
        'key': 'B2ZDK8C2',
        'tags': [{'tag': 'assignment'}, {'tag': 'single'},
                 {'tag': 'static'}],
        'itemType': 'journalArticle',
        'title': 'The semantics of program dependence',
        'url': 'http://portal.acm.org.ezp-prod1.hul.harvard.edu/citation.cfm?id=74820&dl=GUIDE&coll=GUIDE&CFID=95362746&CFTOKEN=85909789'
            ,
        'version': 4023,
        'abstractNote': 'Optimizing and parallelizing compilers for procedural languages rely on various forms of program dependence graphs (pdgs) to express the essential control and data dependencies among atomic program operations. In this paper, we provide a semantic justification for this practice by deriving two different forms of program dependence graph - the output pdg and the def-order pdg-and their semantic definitions from non-strict generalizations of the denotational semantics of the programming language. In the process, we demonstrate that both the output pdg and the def-order pdg (with minor technical modifications) are conventional data-flow programs. In addition, we show that the semantics of the def-order pdg dominates the semantics of the output pdg and that both of these semantics dominate-rather than preserve-the semantics of sequential execution.'
            ,
        'pages': '13-27',
        'language': '',
        'journalAbbreviation': '',
        'ISSN': '',
        'publicationTitle': 'SIGPLAN Not.',
        'shortTitle': '',
        'libraryCatalog': '',
        'DOI': '',
        'creators': [{'creatorType': 'author', 'firstName': 'Robert',
                     'lastName': 'Cartwright'}, {'creatorType': 'author'
                     , 'firstName': 'Mattias', 'lastName': 'Felleisen'
                     }],
        'archiveLocation': '',
        'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/VGKVCAAB'
                      , 'http://zotero.org/users/3661336/items/5WTUXW9K'
                      , 'http://zotero.org/users/3661336/items/H2TEBGZS'
                      , 'http://zotero.org/users/3661336/items/ZUX5WW8K'
                      , 'http://zotero.org/users/3661336/items/JBHR94RA'
                      ]},
        'issue': '7',
        'seriesText': '',
        'accessDate': '2010-10-17',
        'dateModified': '2016-12-24T02:53:36Z',
        'date': '1989',
        'dateAdded': '2013-12-25T01:42:55Z',
        'callNumber': '',
        'rights': '',
        'archive': '',
        'series': '',
        },
    }, {
    'data': {
        'volume': '7',
        'collections': ['2QWF3CPM'],
        'seriesTitle': '',
        'extra': '',
        'key': 'S8FM6JAD',
        'tags': [{'tag': 'LFS'}],
        'itemType': 'journalArticle',
        'title': 'Optimal Write Batch Size in Log-Structured File Systems'
            ,
        'url': '',
        'version': 4023,
        'abstractNote': '',
        'pages': '263-281',
        'language': '',
        'journalAbbreviation': '',
        'ISSN': '',
        'publicationTitle': 'csys',
        'shortTitle': '',
        'libraryCatalog': '',
        'DOI': '',
        'creators': [{'creatorType': 'author', 'firstName': 'S.',
                     'lastName': 'Carson'}, {'creatorType': 'author',
                     'firstName': 'S.', 'lastName': 'Setia'}],
        'archiveLocation': '',
        'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/UA3WTQN8'
                      , 'http://zotero.org/users/3661336/items/XHQ2NSR8'
                      , 'http://zotero.org/users/3661336/items/H7DG5RDW'
                      , 'http://zotero.org/users/3661336/items/T5ZT9CG8'
                      , 'http://zotero.org/users/3661336/items/QFFS3ME7'
                      ]},
        'issue': '2',
        'seriesText': '',
        'accessDate': '',
        'dateModified': '2016-12-24T02:53:31Z',
        'date': '1994',
        'dateAdded': '2013-12-25T01:42:43Z',
        'callNumber': '',
        'rights': '',
        'archive': '',
        'series': '',
        },
    }]

collection_data = [
    {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 4030,
            'name': 'Complexity',
            'key': 'MI4MCAUA'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'Computer Science',
            'key': '2QWF3CPM'
        }
    }, {
        'data': {
            'parentCollection': '2QWF3CPM',
            'relations': {},
            'version': 3915,
            'name': 'automated theorem proving',
            'key': 'SV8225PC'
        }
    }, {
        'data': {
            'parentCollection': '2QWF3CPM',
            'relations': {},
            'version': 3915,
            'name': 'Type Theory',
            'key': '8JSE99A6'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'pearltrees_export',
            'key': 'ABBIWVPH'
        }
    }, {
        'data': {
            'parentCollection': '4DWAPJ29',
            'relations': {},
            'version': 3915,
            'name': 'Game Theory Handbook 1',
            'key': 'WRIT65X9'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'Physical Books',
            'key': 'A2PNS2TG'
        }
    }, {
        'data': {
            'parentCollection': '4DWAPJ29',
            'relations': {},
            'version': 3915,
            'name': 'Logic',
            'key': 'VMNGPV4W'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'Econish',
            'key': 'ZZIC4VK6'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'crypto',
            'key': 'SMT8V3T2'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'Math',
            'key': '4DWAPJ29'
        }
    }, {
        'data': {
            'parentCollection': '4DWAPJ29',
            'relations': {},
            'version': 3915,
            'name': 'Game Theory Handbook 2',
            'key': 'QR2KPFKR'
        }
    }, {
        'data': {
            'parentCollection': 'VMNGPV4W',
            'relations': {},
            'version': 3915,
            'name': 'Rec Thy',
            'key': 'CNJ8SBZT'
        }
    }, {
        'data': {
            'parentCollection': 'CNJ8SBZT',
            'relations': {},
            'version': 3915,
            'name': 'Admissible',
            'key': '876PTIWU'
        }
    }, {
        'data': {
            'parentCollection': 'VMNGPV4W',
            'relations': {},
            'version': 3915,
            'name': 'Complexity',
            'key': 'T4MFZUCD'
        }
    }, {
        'data': {
            'parentCollection': 'CNJ8SBZT',
            'relations': {},
            'version': 3915,
            'name': 'DST',
            'key': '8KBSB7WN'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'Misc',
            'key': 'MBEJGTQ4'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'Gender & Relationships',
            'key': 'APDSWJ3W'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'phil',
            'key': 'FRQUNR4J'
        }
    }, {
        'data': {
            'parentCollection': False,
            'relations': {},
            'version': 3915,
            'name': 'Educ',
            'key': 'J8NTXJB8'
        }
    }
]

item_data = [
    {
        'version': 4024,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'SI6S32QP',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/52JRNN9E'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/SI6S32QP'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/SI6S32QP'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:55:29Z',
            'key': 'SI6S32QP',
            'tags': [],
            'itemType': 'attachment',
            'title': 'Global optimization techniques for automatic parallelization of hybrid -- Chakrabarti_Banerjee_2001_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4024,
            'path': '/Users/TruePath/Google Drive/Managed Library/Global optimization techniques for automatic parallelization of hybrid -- Chakrabarti_Banerjee_2001_2.pdf'
                ,
            'dateAdded': '2016-12-21T12:04:59Z',
            'linkMode': 'linked_file',
            'parentItem': '52JRNN9E',
            },
        },
    {
        'version': 4024,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': '9ERTZFXC',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/52JRNN9E'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/9ERTZFXC'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/9ERTZFXC'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:55:29Z',
            'key': '9ERTZFXC',
            'tags': [],
            'itemType': 'attachment',
            'title': 'Global optimization techniques for automatic parallelization of hybrid -- Chakrabarti_Banerjee_2001_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4024,
            'path': '/Users/TruePath/Google Drive/Managed Library/Global optimization techniques for automatic parallelization of hybrid -- Chakrabarti_Banerjee_2001_.pdf'
                ,
            'dateAdded': '2016-12-21T11:50:24Z',
            'linkMode': 'linked_file',
            'parentItem': '52JRNN9E',
            },
        },
    {
        'version': 4024,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'U7RNSRU2',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/52JRNN9E'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/U7RNSRU2'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/U7RNSRU2'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:55:29Z',
            'key': 'U7RNSRU2',
            'filename': 'Chakrabarti, Banerjee - 2001 - Global optimization techniques for automatic parallelization of hybrid applications.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4024,
            'dateAdded': '2014-05-14T04:58:29Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '52JRNN9E',
            'md5': None,
            },
        },
    {
        'version': 4024,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'PE3JR5JQ',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/52JRNN9E'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/PE3JR5JQ'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/PE3JR5JQ'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:55:29Z',
            'key': 'PE3JR5JQ',
            'filename': 'Chakrabarti, Banerjee - 2001 - Global optimization techniques for automatic parallelization of hybrid applications.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4024,
            'dateAdded': '2014-05-14T05:00:22Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '52JRNN9E',
            'md5': None,
            },
        },
    {
        'version': 4024,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Chakrabarti and Banerjee',
                 'parsedDate': '2001', 'numChildren': 5},
        'key': '52JRNN9E',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/52JRNN9E'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/52JRNN9E'
                  }},
        'data': {
            'proceedingsTitle': 'Proceedings of the 15th international conference on Supercomputing'
                ,
            'collections': ['2QWF3CPM'],
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/DBQFTAHP'
                          ,
                          'http://zotero.org/users/3661336/items/C6IAXB94'
                          ,
                          'http://zotero.org/users/3661336/items/VEIX2QFM'
                          ,
                          'http://zotero.org/users/3661336/items/DQMM2KFD'
                          ,
                          'http://zotero.org/users/3661336/items/HS74N2BJ'
                          ]},
            'extra': '',
            'volume': '',
            'key': '52JRNN9E',
            'tags': [{'tag': 'parallel'}],
            'itemType': 'conferencePaper',
            'title': 'Global optimization techniques for automatic parallelization of hybrid applications'
                ,
            'url': '',
            'version': 4024,
            'abstractNote': 'This paper presents a novel technique to perform global optimization of communication and preprocessing calls in the presence of array accesses with arbitrary subscripts. Our scheme is presented in the context of automatic parallelization of sequential programs to produce message passing programs for execution on distributed machines. We use the static single assignment (SSA) form for message passing programs as the intermediate representation and then present techniques to perform global optimizations even in the presence of array accesses with arbitrary subscripts. The focus of this paper is in showing that, using a uniform compilation method both at compile-time and at run-time, our framework is able to determine the earliest and the latest legal communication point for a certain distributed array reference even in the presence of arbitrary array addressing functions. Our scheme then heuristically determines the final communication point after considering the interaction between the relevant communication schedules. Owing to combined static and dynamic analysis, a quasi-dynamic method of code generation is implemented. We describe the need for proper interaction between the compiler and the run-time routines for efficient implementation of optimizations as well as for compatible code generation. All of the analyses is initiated at compile-time, static analyses of the program is done as much as possible, and then the run-time routines take over the analyses while building on the data structures initiated at compile time. This scheme has been incorporated in our compiler framework which can use uniform methods to compile, parallelize, and optimize a sequential program irrespective of the subscripts used in array addressing functions. Experimental results for a number of benchmarks on an IBM SP-2 show up to around 10-25% reduction in total run-times in our globally-optimized schemes compared to other state-of-the-art schemes on 16 processors.'
                ,
            'series': '',
            'language': '',
            'libraryCatalog': '',
            'rights': '',
            'shortTitle': '',
            'ISBN': '1-58113-410-X',
            'DOI': '',
            'creators': [{'creatorType': 'author',
                         'firstName': 'Dhruva R.',
                         'lastName': 'Chakrabarti'},
                         {'creatorType': 'author',
                         'firstName': 'Prithviraj',
                         'lastName': 'Banerjee'}],
            'archiveLocation': '',
            'conferenceName': '',
            'accessDate': '',
            'dateModified': '2016-12-24T02:55:29Z',
            'date': '2001',
            'dateAdded': '2013-12-25T01:42:47Z',
            'callNumber': '',
            'publisher': 'ACM',
            'archive': '',
            'place': 'Sorrento, Italy',
            'pages': '166-180',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cate and Gross',
                 'parsedDate': '1991-04', 'numChildren': 0},
        'key': '6NGR6H7E',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/6NGR6H7E'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/6NGR6H7E'
                  }},
        'data': {
            'proceedingsTitle': 'Proceedings of the Fourth International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS-IV)'
                ,
            'collections': ['2QWF3CPM'],
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/RMAPXKX5'
                          ,
                          'http://zotero.org/users/3661336/items/V56X68NG'
                          ,
                          'http://zotero.org/users/3661336/items/MWTCKZGR'
                          ,
                          'http://zotero.org/users/3661336/items/93QMAZC6'
                          ]},
            'extra': '',
            'volume': '',
            'key': '6NGR6H7E',
            'tags': [{'tag': 'Caching'}, {'tag': 'compression'}],
            'itemType': 'conferencePaper',
            'title': 'Combining the Concepts of Compression and Caching for a Two-Level Filesystem'
                ,
            'url': '',
            'version': 4023,
            'abstractNote': '',
            'series': '',
            'language': '',
            'libraryCatalog': '',
            'rights': '',
            'shortTitle': '',
            'ISBN': '',
            'DOI': '',
            'creators': [{'creatorType': 'author', 'firstName': 'V.',
                         'lastName': 'Cate'}, {'creatorType': 'author',
                         'firstName': 'T.', 'lastName': 'Gross'}],
            'archiveLocation': '',
            'conferenceName': '',
            'accessDate': '',
            'dateModified': '2016-12-24T02:53:53Z',
            'date': 'April 1991',
            'dateAdded': '2013-12-25T01:43:24Z',
            'callNumber': '',
            'publisher': '',
            'archive': '',
            'place': 'Santa Clara, CA, USA',
            'pages': '',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'I7TDKJTJ',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/C776Z4WN'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/I7TDKJTJ'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/I7TDKJTJ'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:45Z',
            'key': 'I7TDKJTJ',
            'tags': [],
            'itemType': 'attachment',
            'title': 'Reusable Software Components -- Cartwright et al_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4023,
            'path': '/Users/TruePath/Google Drive/Managed Library/Reusable Software Components -- Cartwright et al_.pdf'
                ,
            'dateAdded': '2016-12-21T11:57:02Z',
            'linkMode': 'linked_file',
            'parentItem': 'C776Z4WN',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'QBAESNX6',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/C776Z4WN'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/QBAESNX6'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/QBAESNX6'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:45Z',
            'key': 'QBAESNX6',
            'filename': 'Reusable Software Components -- Cartwright et al.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Reusable Software Components -- Cartwright et al.pdf'
                ,
            'url': '',
            'mtime': 1482146803000,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2016-12-19T11:26:40Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'C776Z4WN',
            'md5': '52414a4c5fef9827fe796100e58d4670',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'MAZ8D6S8',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/C776Z4WN'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/MAZ8D6S8'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/MAZ8D6S8'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:45Z',
            'key': 'MAZ8D6S8',
            'filename': 'Cartwright et al. - Unknown - Reusable Software Components.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:56:09Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'C776Z4WN',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'M3MDZ9XT',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/C776Z4WN'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/M3MDZ9XT'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/M3MDZ9XT'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:45Z',
            'key': 'M3MDZ9XT',
            'filename': 'Cartwright et al. - Unknown - Reusable Software Components.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:56:13Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'C776Z4WN',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cartwright et al.',
                 'numChildren': 5},
        'key': 'C776Z4WN',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/C776Z4WN'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/C776Z4WN'
                  }},
        'data': {
            'volume': '',
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': 'C776Z4WN',
            'tags': [{'tag': 'Mixins'}, {'tag': 'Modules'},
                     {'tag': 'units'}],
            'itemType': 'journalArticle',
            'title': 'Reusable Software Components',
            'url': '',
            'version': 4023,
            'abstractNote': '',
            'pages': '',
            'language': '',
            'journalAbbreviation': '',
            'ISSN': '',
            'publicationTitle': '',
            'shortTitle': '',
            'libraryCatalog': '',
            'DOI': '10.1.1.17.3212',
            'creators': [{'creatorType': 'author',
                         'firstName': 'Robert S',
                         'lastName': 'Cartwright'},
                         {'creatorType': 'author',
                         'firstName': 'Keith D', 'lastName': 'Cooper'},
                         {'creatorType': 'author',
                         'firstName': 'David M', 'lastName': 'Lane'},
                         {'creatorType': 'author',
                         'firstName': 'Matthew', 'lastName': 'Flatt'},
                         {'creatorType': 'author',
                         'firstName': 'Matthew', 'lastName': 'Flatt'}],
            'archiveLocation': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/I97X2PJP'
                          ,
                          'http://zotero.org/users/3661336/items/FD9QGA45'
                          ,
                          'http://zotero.org/users/3661336/items/NAIHFD2Z'
                          ,
                          'http://zotero.org/users/3661336/items/CU29HTVK'
                          ,
                          'http://zotero.org/users/3661336/items/B4ZQ33SS'
                          ]},
            'issue': '',
            'seriesText': '',
            'accessDate': '',
            'dateModified': '2016-12-24T02:53:45Z',
            'date': '',
            'dateAdded': '2013-12-25T01:43:39Z',
            'callNumber': '',
            'rights': '',
            'archive': '',
            'series': '',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': '4UG9CABG',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/B2ZDK8C2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/4UG9CABG'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/4UG9CABG'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:36Z',
            'key': '4UG9CABG',
            'tags': [],
            'itemType': 'attachment',
            'title': 'The semantics of program dependence -- Cartwright_Felleisen_1989_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4023,
            'path': '/Users/TruePath/Google Drive/Managed Library/The semantics of program dependence -- Cartwright_Felleisen_1989_.pdf'
                ,
            'dateAdded': '2016-12-21T12:16:34Z',
            'linkMode': 'linked_file',
            'parentItem': 'B2ZDK8C2',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'UEXD92ZV',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/B2ZDK8C2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/UEXD92ZV'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/UEXD92ZV'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:36Z',
            'key': 'UEXD92ZV',
            'filename': 'Cartwright, Felleisen - 1989 - The semantics of program dependence.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:55:54Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'B2ZDK8C2',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'SC3VPXIW',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/B2ZDK8C2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/SC3VPXIW'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/SC3VPXIW'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:36Z',
            'key': 'SC3VPXIW',
            'filename': 'The semantics of program dependence -- Cartwright & Felleisen (1989).pdf'
                ,
            'itemType': 'attachment',
            'title': 'The semantics of program dependence -- Cartwright & Felleisen (1989).pdf'
                ,
            'url': '',
            'mtime': 1482139981000,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2016-12-19T09:33:05Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'B2ZDK8C2',
            'md5': '4966e682d21f9b61a94b6d924f2af6d0',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'DA34WA4G',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/B2ZDK8C2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/DA34WA4G'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/DA34WA4G'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:36Z',
            'key': 'DA34WA4G',
            'filename': 'The semantics of program dependence -- Cartwright & Felleisen (1989).pdf'
                ,
            'itemType': 'attachment',
            'title': 'The semantics of program dependence -- Cartwright & Felleisen (1989).pdf'
                ,
            'url': '',
            'mtime': 1482140000000,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2016-12-19T09:33:23Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'B2ZDK8C2',
            'md5': '4966e682d21f9b61a94b6d924f2af6d0',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cartwright and Felleisen',
                 'parsedDate': '1989', 'numChildren': 5},
        'key': 'B2ZDK8C2',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/B2ZDK8C2'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/B2ZDK8C2'
                  }},
        'data': {
            'volume': '24',
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': 'B2ZDK8C2',
            'tags': [{'tag': 'assignment'}, {'tag': 'single'},
                     {'tag': 'static'}],
            'itemType': 'journalArticle',
            'title': 'The semantics of program dependence',
            'url': 'http://portal.acm.org.ezp-prod1.hul.harvard.edu/citation.cfm?id=74820&dl=GUIDE&coll=GUIDE&CFID=95362746&CFTOKEN=85909789'
                ,
            'version': 4023,
            'abstractNote': 'Optimizing and parallelizing compilers for procedural languages rely on various forms of program dependence graphs (pdgs) to express the essential control and data dependencies among atomic program operations. In this paper, we provide a semantic justification for this practice by deriving two different forms of program dependence graph - the output pdg and the def-order pdg-and their semantic definitions from non-strict generalizations of the denotational semantics of the programming language. In the process, we demonstrate that both the output pdg and the def-order pdg (with minor technical modifications) are conventional data-flow programs. In addition, we show that the semantics of the def-order pdg dominates the semantics of the output pdg and that both of these semantics dominate-rather than preserve-the semantics of sequential execution.'
                ,
            'pages': '13-27',
            'language': '',
            'journalAbbreviation': '',
            'ISSN': '',
            'publicationTitle': 'SIGPLAN Not.',
            'shortTitle': '',
            'libraryCatalog': '',
            'DOI': '',
            'creators': [{'creatorType': 'author', 'firstName': 'Robert'
                         , 'lastName': 'Cartwright'},
                         {'creatorType': 'author',
                         'firstName': 'Mattias', 'lastName': 'Felleisen'
                         }],
            'archiveLocation': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/VGKVCAAB'
                          ,
                          'http://zotero.org/users/3661336/items/5WTUXW9K'
                          ,
                          'http://zotero.org/users/3661336/items/H2TEBGZS'
                          ,
                          'http://zotero.org/users/3661336/items/ZUX5WW8K'
                          ,
                          'http://zotero.org/users/3661336/items/JBHR94RA'
                          ]},
            'issue': '7',
            'seriesText': '',
            'accessDate': '2010-10-17',
            'dateModified': '2016-12-24T02:53:36Z',
            'date': '1989',
            'dateAdded': '2013-12-25T01:42:55Z',
            'callNumber': '',
            'rights': '',
            'archive': '',
            'series': '',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Carson and Setia',
                 'parsedDate': '1994', 'numChildren': 0},
        'key': 'S8FM6JAD',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/S8FM6JAD'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/S8FM6JAD'
                  }},
        'data': {
            'volume': '7',
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': 'S8FM6JAD',
            'tags': [{'tag': 'LFS'}],
            'itemType': 'journalArticle',
            'title': 'Optimal Write Batch Size in Log-Structured File Systems'
                ,
            'url': '',
            'version': 4023,
            'abstractNote': '',
            'pages': '263-281',
            'language': '',
            'journalAbbreviation': '',
            'ISSN': '',
            'publicationTitle': 'csys',
            'shortTitle': '',
            'libraryCatalog': '',
            'DOI': '',
            'creators': [{'creatorType': 'author', 'firstName': 'S.',
                         'lastName': 'Carson'}, {'creatorType': 'author'
                         , 'firstName': 'S.', 'lastName': 'Setia'}],
            'archiveLocation': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/UA3WTQN8'
                          ,
                          'http://zotero.org/users/3661336/items/XHQ2NSR8'
                          ,
                          'http://zotero.org/users/3661336/items/H7DG5RDW'
                          ,
                          'http://zotero.org/users/3661336/items/T5ZT9CG8'
                          ,
                          'http://zotero.org/users/3661336/items/QFFS3ME7'
                          ]},
            'issue': '2',
            'seriesText': '',
            'accessDate': '',
            'dateModified': '2016-12-24T02:53:31Z',
            'date': '1994',
            'dateAdded': '2013-12-25T01:42:43Z',
            'callNumber': '',
            'rights': '',
            'archive': '',
            'series': '',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'VU29FAF2',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/UCMWRKGP'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/VU29FAF2'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/VU29FAF2'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:27Z',
            'key': 'VU29FAF2',
            'filename': 'Jouannaud, Okada - 1997 - Abstract data type systems.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:57:01Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'UCMWRKGP',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'RGG6ZJZW',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/UCMWRKGP'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/RGG6ZJZW'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/RGG6ZJZW'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:27Z',
            'key': 'RGG6ZJZW',
            'filename': 'Type Systems -- Cardelli (1997).pdf',
            'itemType': 'attachment',
            'title': 'Type Systems -- Cardelli (1997).pdf',
            'url': '',
            'mtime': 1482144354000,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2016-12-19T10:45:45Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'UCMWRKGP',
            'md5': '6c89731f88ec0dd9a5579bb9104e2a21',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'AGAMQBJD',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/UCMWRKGP'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/AGAMQBJD'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/AGAMQBJD'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:27Z',
            'key': 'AGAMQBJD',
            'filename': 'Jouannaud, Okada - 1997 - Abstract data type systems.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:57:43Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'UCMWRKGP',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'WUBCGSBC',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/UCMWRKGP'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/WUBCGSBC'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/WUBCGSBC'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:27Z',
            'key': 'WUBCGSBC',
            'filename': 'Jouannaud, Okada - 1997 - Abstract data type systems.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:57:30Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'UCMWRKGP',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cardelli', 'parsedDate': '1997',
                 'numChildren': 6},
        'key': 'UCMWRKGP',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/UCMWRKGP'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/UCMWRKGP'
                  }},
        'data': {
            'volume': '',
            'collections': ['2QWF3CPM'],
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/FICV33FA'
                          ,
                          'http://zotero.org/users/3661336/items/G9PIQ86H'
                          ,
                          'http://zotero.org/users/3661336/items/4XNZZRRD'
                          ,
                          'http://zotero.org/users/3661336/items/BKKAX39K'
                          ,
                          'http://zotero.org/users/3661336/items/RSMHQTUF'
                          ]},
            'extra': '',
            'key': 'UCMWRKGP',
            'edition': '',
            'itemType': 'bookSection',
            'title': 'Type Systems',
            'url': '',
            'version': 4023,
            'abstractNote': '',
            'seriesNumber': '',
            'pages': '',
            'language': '',
            'rights': '',
            'libraryCatalog': '',
            'callNumber': '',
            'bookTitle': 'The Handbook of Computer Science and Engineering'
                ,
            'shortTitle': '',
            'ISBN': '',
            'creators': [{'creatorType': 'author', 'firstName': 'Luca',
                         'lastName': 'Cardelli'},
                         {'creatorType': 'editor',
                         'firstName': 'Allen B.', 'lastName': 'Tucker'
                         }],
            'archiveLocation': '',
            'accessDate': '',
            'dateModified': '2016-12-24T02:53:27Z',
            'date': '1997',
            'dateAdded': '2013-12-25T01:42:53Z',
            'tags': [],
            'numberOfVolumes': '',
            'publisher': 'CRC Press',
            'archive': '',
            'place': 'Boca Raton, FL',
            'series': '',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'S86BTQ4R',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/QVHFA7S2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/S86BTQ4R'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/S86BTQ4R'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:19Z',
            'key': 'S86BTQ4R',
            'tags': [],
            'itemType': 'attachment',
            'title': 'On Understanding Types, Data Abstraction, and Polymorphism -- Cardelli_Wegner_1985_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4023,
            'path': '/Users/TruePath/Google Drive/Managed Library/On Understanding Types, Data Abstraction, and Polymorphism -- Cardelli_Wegner_1985_2.pdf'
                ,
            'dateAdded': '2016-12-21T12:12:32Z',
            'linkMode': 'linked_file',
            'parentItem': 'QVHFA7S2',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': '6J6PRXI9',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/QVHFA7S2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/6J6PRXI9'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/6J6PRXI9'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:19Z',
            'key': '6J6PRXI9',
            'filename': 'Cardelli, Wegner - 1985 - On Understanding Types, Data Abstraction, and Polymorphism.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:57:00Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'QVHFA7S2',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'J6Z8BBBZ',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/QVHFA7S2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/J6Z8BBBZ'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/J6Z8BBBZ'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:19Z',
            'key': 'J6Z8BBBZ',
            'filename': 'Cardelli, Wegner - 1985 - On Understanding Types, Data Abstraction, and Polymorphism.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2014-05-14T04:59:30Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'QVHFA7S2',
            'md5': None,
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'I9873X5Z',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/QVHFA7S2'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/I9873X5Z'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/I9873X5Z'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:53:19Z',
            'key': 'I9873X5Z',
            'filename': 'On Understanding Types, Data Abstraction, and Polymorphism -- Cardelli & Wegner (1985).pdf'
                ,
            'itemType': 'attachment',
            'title': 'On Understanding Types, Data Abstraction, and Polymorphism -- Cardelli & Wegner (1985).pdf'
                ,
            'url': '',
            'mtime': 1482147090000,
            'accessDate': '',
            'version': 4023,
            'dateAdded': '2016-12-19T11:31:29Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'QVHFA7S2',
            'md5': '1d0ffe22bc467a7ed478de8c1656a6e9',
            },
        },
    {
        'version': 4023,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cardelli and Wegner',
                 'parsedDate': '1985', 'numChildren': 6},
        'key': 'QVHFA7S2',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/QVHFA7S2'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/QVHFA7S2'
                  }},
        'data': {
            'volume': '17',
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': 'QVHFA7S2',
            'tags': [{'tag': 'types'}],
            'itemType': 'journalArticle',
            'title': 'On Understanding Types, Data Abstraction, and Polymorphism'
                ,
            'url': '',
            'version': 4023,
            'abstractNote': 'Our objective is to understand the notion of type in programming languages, present a model of typed, polymorphic programming languages that reflects recent research in type theory, and examine the relevance of recent research to the design of practical programming languages. Object-oriented languages provide both a framework and a motivation for exploring the interaction among the concepts of type, data abstraction, and polymorphism, since they extend the notion of type to data abstraction and since type inheritance is an important form of polymorphism. We develop a OE>>-calculus-based model for type systems that allows us to explore these interactions in a simple setting, unencumbered by complexities of production programming languages. The evolution of languages from untyped universes to monomorphic and then polymorphic type systems is reviewed. Mechanisms for polymorphism such as overloading, coercion, subtyping, and parameterization are examined. A unifying framework for polymorphic type systems is developed in terms of the typed OE>>-calculus augmented to include binding of types by quantification as well as binding of values by abstraction. The typed OE>>-calculus is augmented by universal quantification to model generic functions with type parameters, existential quantification and packaging (information hiding) to model abstract data types, and'
                ,
            'pages': '471-522',
            'language': '',
            'journalAbbreviation': '',
            'ISSN': '',
            'publicationTitle': 'ACM COMPUTING SURVEYS',
            'shortTitle': '',
            'libraryCatalog': '',
            'DOI': '',
            'creators': [{'creatorType': 'author', 'firstName': 'Luca',
                         'lastName': 'Cardelli'},
                         {'creatorType': 'author', 'firstName': 'Peter'
                         , 'lastName': 'Wegner'}],
            'archiveLocation': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/GS6SDHZR'
                          ,
                          'http://zotero.org/users/3661336/items/RRFMB2KB'
                          ,
                          'http://zotero.org/users/3661336/items/HB7U8HD3'
                          ,
                          'http://zotero.org/users/3661336/items/FRCJAC7T'
                          ,
                          'http://zotero.org/users/3661336/items/AED3I6B6'
                          ]},
            'issue': '4',
            'seriesText': '',
            'accessDate': '',
            'dateModified': '2016-12-24T02:53:19Z',
            'date': '1985',
            'dateAdded': '2013-12-25T01:43:31Z',
            'callNumber': '',
            'rights': '',
            'archive': '',
            'series': '',
            },
        },
    {
        'version': 4022,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'BZ3TCVKI',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/4VDXKA6F'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/BZ3TCVKI'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/BZ3TCVKI'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:52:10Z',
            'key': 'BZ3TCVKI',
            'tags': [],
            'itemType': 'attachment',
            'title': 'Extensible Syntax with Lexical Scoping -- Cardelli et al_1994_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4022,
            'path': '/Users/TruePath/Google Drive/Managed Library/Extensible Syntax with Lexical Scoping -- Cardelli et al_1994_2.pdf'
                ,
            'dateAdded': '2016-12-21T12:15:31Z',
            'linkMode': 'linked_file',
            'parentItem': '4VDXKA6F',
            },
        },
    {
        'version': 4022,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'DISPGBIH',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/4VDXKA6F'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/DISPGBIH'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/DISPGBIH'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:52:10Z',
            'key': 'DISPGBIH',
            'filename': 'Cardelli et al. - 1994 - Extensible Syntax with Lexical Scoping(2).pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4022,
            'dateAdded': '2014-05-14T04:58:41Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '4VDXKA6F',
            'md5': None,
            },
        },
    {
        'version': 4022,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'HJH5MIID',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/4VDXKA6F'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/HJH5MIID'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/HJH5MIID'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:52:10Z',
            'key': 'HJH5MIID',
            'filename': 'Cardelli et al. - 1994 - Extensible Syntax with Lexical Scoping(2).pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4022,
            'dateAdded': '2014-05-14T04:59:10Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '4VDXKA6F',
            'md5': None,
            },
        },
    {
        'version': 4022,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'H2NBAGQ9',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/4VDXKA6F'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/H2NBAGQ9'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/H2NBAGQ9'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-24T02:52:10Z',
            'key': 'H2NBAGQ9',
            'filename': 'Cardelli et al. - 1994 - Extensible Syntax with Lexical Scoping(2).pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4022,
            'dateAdded': '2014-05-14T04:57:14Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '4VDXKA6F',
            'md5': None,
            },
        },
    {
        'version': 4022,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cardelli et al.',
                 'parsedDate': '1994', 'numChildren': 5},
        'key': '4VDXKA6F',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/4VDXKA6F'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/4VDXKA6F'
                  }},
        'data': {
            'volume': '',
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': '4VDXKA6F',
            'tags': [],
            'itemType': 'journalArticle',
            'title': 'Extensible Syntax with Lexical Scoping',
            'url': '',
            'version': 4022,
            'abstractNote': 'A frequent dilemma in programming language design is the choice between a language with a rich set of notations and a small, simple core language. We address this dilemma by proposing extensible grammars, a syntax-definition formalism for incremental language extensions and restrictions. The translation of programs written in rich object languages into a small core language is defined via syntax-directed patterns. In contrast to macroexpansion and program-rewriting tools, our extensible grammars respect scoping rules. Therefore, we can introduce binding constructs while avoiding problems with unwanted name clashes. We develop extensible grammars and illustrate their use by extending the lambda calculus with let-bindings, conditionals, and constructs from database programming languages, such as SQL query expressions. We then give a formal description of the underlying rules for parsing, transformation, and substitution. Finally, we sketch how these rules are exploited in an implementati...'
                ,
            'pages': '',
            'language': '',
            'journalAbbreviation': '',
            'ISSN': '',
            'publicationTitle': '',
            'shortTitle': '',
            'libraryCatalog': '',
            'DOI': '',
            'creators': [{'creatorType': 'author', 'firstName': 'Luca',
                         'lastName': 'Cardelli'},
                         {'creatorType': 'author',
                         'firstName': 'Florian', 'lastName': 'Matthes'
                         }, {'creatorType': 'author',
                         'firstName': 'Martin', 'lastName': 'Abadi'},
                         {'creatorType': 'author',
                         'firstName': 'Robert W', 'lastName': 'Taylor'
                         }],
            'archiveLocation': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/D55E3VDS'
                          ,
                          'http://zotero.org/users/3661336/items/KGMPAN5J'
                          ,
                          'http://zotero.org/users/3661336/items/DQDN25ZC'
                          ,
                          'http://zotero.org/users/3661336/items/GVQ56IMS'
                          ,
                          'http://zotero.org/users/3661336/items/S33GK2AK'
                          ]},
            'issue': '',
            'seriesText': '',
            'accessDate': '',
            'dateModified': '2016-12-24T02:52:10Z',
            'date': '1994',
            'dateAdded': '2013-12-25T01:42:50Z',
            'callNumber': '',
            'rights': '',
            'archive': '',
            'series': '',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'V4JSHNHQ',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/AE3SUFJ8'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/V4JSHNHQ'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/V4JSHNHQ'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:56Z',
            'key': 'V4JSHNHQ',
            'tags': [],
            'itemType': 'attachment',
            'title': 'A semantics of multiple inheritance -- Cardelli_1984_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4019,
            'path': '/Users/TruePath/Google Drive/Managed Library/A semantics of multiple inheritance -- Cardelli_1984_.pdf'
                ,
            'dateAdded': '2016-12-21T11:50:04Z',
            'linkMode': 'linked_file',
            'parentItem': 'AE3SUFJ8',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'TMVJ65ZN',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/AE3SUFJ8'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/TMVJ65ZN'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/TMVJ65ZN'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:56Z',
            'key': 'TMVJ65ZN',
            'filename': 'Cardelli - 1984 - A semantics of multiple inheritance.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4019,
            'dateAdded': '2014-05-14T04:58:00Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'AE3SUFJ8',
            'md5': None,
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'RV5UJEKU',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/AE3SUFJ8'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/RV5UJEKU'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/RV5UJEKU'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:56Z',
            'key': 'RV5UJEKU',
            'filename': 'A semantics of multiple inheritance -- Cardelli (1984).pdf'
                ,
            'itemType': 'attachment',
            'title': 'A semantics of multiple inheritance -- Cardelli (1984).pdf'
                ,
            'url': '',
            'mtime': 1482146513000,
            'accessDate': '',
            'version': 4019,
            'dateAdded': '2016-12-19T11:21:53Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'AE3SUFJ8',
            'md5': '5d6a90d9666f732cb22820a31de928b0',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'KPPZXMI5',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/AE3SUFJ8'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/KPPZXMI5'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/KPPZXMI5'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:56Z',
            'key': 'KPPZXMI5',
            'filename': 'Cardelli - 1984 - A semantics of multiple inheritance.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4019,
            'dateAdded': '2014-05-14T04:56:38Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': 'AE3SUFJ8',
            'md5': None,
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cardelli', 'parsedDate': '1984',
                 'numChildren': 5},
        'key': 'AE3SUFJ8',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/AE3SUFJ8'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/AE3SUFJ8'
                  }},
        'data': {
            'volume': '',
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': 'AE3SUFJ8',
            'tags': [],
            'itemType': 'journalArticle',
            'title': 'A semantics of multiple inheritance',
            'url': 'http://www.springerlink.com/index/Y2T7N53458RN50WT.pdf'
                ,
            'version': 4019,
            'abstractNote': '',
            'pages': '51-67',
            'language': '',
            'journalAbbreviation': '',
            'ISSN': '',
            'publicationTitle': 'Semantics of data types',
            'shortTitle': '',
            'libraryCatalog': '',
            'DOI': '',
            'creators': [{'creatorType': 'author', 'firstName': 'L.',
                         'lastName': 'Cardelli'}],
            'archiveLocation': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/SWTQV2CQ'
                          ,
                          'http://zotero.org/users/3661336/items/3I58FCUC'
                          ,
                          'http://zotero.org/users/3661336/items/CKF5NGIG'
                          ,
                          'http://zotero.org/users/3661336/items/9WV3EQ9E'
                          ,
                          'http://zotero.org/users/3661336/items/X7MVQRIE'
                          ]},
            'issue': '',
            'seriesText': '',
            'accessDate': '2012-12-06',
            'dateModified': '2016-12-23T16:31:56Z',
            'date': '1984',
            'dateAdded': '2013-12-25T01:43:36Z',
            'callNumber': '',
            'rights': '',
            'archive': '',
            'series': '',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': '3UNWCG3D',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/9KIMZEI6'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/3UNWCG3D'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/3UNWCG3D'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:51Z',
            'key': '3UNWCG3D',
            'filename': 'Caplan, Harandi - 1995 - A logical framework for software proof reuse.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4019,
            'dateAdded': '2014-05-14T04:58:38Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '9KIMZEI6',
            'md5': None,
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Caplan and Harandi',
                 'parsedDate': '1995', 'numChildren': 5},
        'key': '9KIMZEI6',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/9KIMZEI6'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/9KIMZEI6'
                  }},
        'data': {
            'proceedingsTitle': 'Proceedings of the 1995 Symposium on Software reusability'
                ,
            'collections': ['2QWF3CPM'],
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/JQH7UV2M'
                          ,
                          'http://zotero.org/users/3661336/items/DJJXICG6'
                          ,
                          'http://zotero.org/users/3661336/items/G3T9CVVG'
                          ,
                          'http://zotero.org/users/3661336/items/SKEUTPVU'
                          ,
                          'http://zotero.org/users/3661336/items/4JIBQFG5'
                          ]},
            'extra': '',
            'volume': '',
            'key': '9KIMZEI6',
            'tags': [{'tag': 'program verification'},
                     {'tag': 'proof-carrying code'}],
            'itemType': 'conferencePaper',
            'title': 'A logical framework for software proof reuse',
            'url': 'http://doi.acm.org.ezp-prod1.hul.harvard.edu/10.1145/211782.211821'
                ,
            'version': 4019,
            'abstractNote': 'We describe a logical framework PR for verification of reusable software components. Within our system, developers can employ the advantages traditionally associated with software reuse to reduce the cost of software verification by reusing abstract proofs and specifications. One can construct an algorithm with parameters, a specification with parameters, and a proof that the algorithm satisfies the specification provided the parameters satisfy certain conditions. Proofs in PRwill themselves contain parameters for subproofs concerning those conditions. In this framework, typing, type checking, and proof checking are decidable.'
                ,
            'series': "SSR '95",
            'language': '',
            'libraryCatalog': '',
            'rights': '',
            'shortTitle': '',
            'ISBN': '0-89791-739-1',
            'DOI': '10.1145/211782.211821',
            'creators': [{'creatorType': 'author',
                         'firstName': 'Joshua E.', 'lastName': 'Caplan'
                         }, {'creatorType': 'author',
                         'firstName': 'Mehdi T.', 'lastName': 'Harandi'
                         }],
            'archiveLocation': '',
            'conferenceName': '',
            'accessDate': '2012-12-02',
            'dateModified': '2016-12-23T16:31:51Z',
            'date': '1995',
            'dateAdded': '2013-12-25T01:42:51Z',
            'callNumber': '',
            'publisher': 'ACM',
            'archive': '',
            'place': 'New York, NY, USA',
            'pages': '106-113',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'QZQH57KI',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/9KIMZEI6'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/QZQH57KI'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/QZQH57KI'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:51Z',
            'key': 'QZQH57KI',
            'tags': [],
            'itemType': 'attachment',
            'title': 'A logical framework for software proof reuse -- Caplan_Harandi_1995_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4019,
            'path': '/Users/TruePath/Google Drive/Managed Library/A logical framework for software proof reuse -- Caplan_Harandi_1995_.pdf'
                ,
            'dateAdded': '2016-12-21T12:20:10Z',
            'linkMode': 'linked_file',
            'parentItem': '9KIMZEI6',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'I2XVB69Q',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/9KIMZEI6'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/I2XVB69Q'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/I2XVB69Q'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:51Z',
            'key': 'I2XVB69Q',
            'filename': 'Caplan, Harandi - 1995 - A logical framework for software proof reuse.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4019,
            'dateAdded': '2014-05-14T04:59:13Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '9KIMZEI6',
            'md5': None,
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': '8HAM8JJP',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/9KIMZEI6'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/8HAM8JJP'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/8HAM8JJP'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:51Z',
            'key': '8HAM8JJP',
            'filename': 'Caplan, Harandi - 1995 - A logical framework for software proof reuse.pdf'
                ,
            'itemType': 'attachment',
            'title': 'Attachment',
            'url': '',
            'mtime': None,
            'accessDate': '',
            'version': 4019,
            'dateAdded': '2014-05-14T04:57:32Z',
            'linkMode': 'imported_file',
            'tags': [],
            'parentItem': '9KIMZEI6',
            'md5': None,
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'ZEVB428T',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/KPHICGWA'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/ZEVB428T'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/ZEVB428T'
                  }},
        'data': {
            'dateModified': '2016-12-23T16:31:44Z',
            'version': 4019,
            'tags': [],
            'note': "<p>Also in USENIX OSDI '94</p>",
            'key': 'ZEVB428T',
            'parentItem': 'KPHICGWA',
            'itemType': 'note',
            'relations': {},
            'dateAdded': '2014-05-14T05:16:14Z',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': '6UQS3W63',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/KPHICGWA'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/6UQS3W63'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/6UQS3W63'
                  }},
        'data': {
            'dateModified': '2016-12-23T16:31:44Z',
            'version': 4019,
            'tags': [],
            'note': "<p>Also in USENIX OSDI '94</p>",
            'key': '6UQS3W63',
            'parentItem': 'KPHICGWA',
            'itemType': 'note',
            'relations': {},
            'dateAdded': '2014-05-14T04:59:53Z',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cao et al.', 'parsedDate': '1994',
                 'numChildren': 6},
        'key': 'KPHICGWA',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/KPHICGWA'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/KPHICGWA'
                  }},
        'data': {
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': 'KPHICGWA',
            'tags': [{'tag': '?'}, {'tag': 'Caching'}],
            'itemType': 'report',
            'title': 'Implementation and Performance of Application-Controlled File Caching'
                ,
            'url': '',
            'reportType': '',
            'abstractNote': '',
            'pages': '',
            'language': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/VT47EZ2P'
                          ,
                          'http://zotero.org/users/3661336/items/MZDWHWVA'
                          ,
                          'http://zotero.org/users/3661336/items/G5C9IITE'
                          ,
                          'http://zotero.org/users/3661336/items/V7IFZ5B3'
                          ,
                          'http://zotero.org/users/3661336/items/84K5NQM5'
                          ]},
            'libraryCatalog': '',
            'rights': '',
            'shortTitle': '',
            'institution': 'Department of Computer Science, Princeton University'
                ,
            'creators': [{'creatorType': 'author', 'firstName': 'P.',
                         'lastName': 'Cao'}, {'creatorType': 'author',
                         'firstName': 'E. W.', 'lastName': 'Felten'},
                         {'creatorType': 'author', 'firstName': 'K.',
                         'lastName': 'Li'}],
            'archiveLocation': '',
            'version': 4019,
            'accessDate': '',
            'dateModified': '2016-12-23T16:31:44Z',
            'date': '1994',
            'dateAdded': '2013-12-25T01:43:34Z',
            'callNumber': '',
            'reportNumber': 'TR-462-94',
            'archive': '',
            'place': 'Princeton, NJ, USA',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'XF6RICVV',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/KPHICGWA'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/XF6RICVV'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/XF6RICVV'
                  }},
        'data': {
            'dateModified': '2016-12-23T16:31:44Z',
            'version': 4019,
            'tags': [],
            'note': "<p>Also in USENIX OSDI '94</p>",
            'key': 'XF6RICVV',
            'parentItem': 'KPHICGWA',
            'itemType': 'note',
            'relations': {},
            'dateAdded': '2014-05-14T04:57:38Z',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'HRQN4HX4',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/KPHICGWA'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/HRQN4HX4'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/HRQN4HX4'
                  }},
        'data': {
            'dateModified': '2016-12-23T16:31:44Z',
            'version': 4019,
            'tags': [],
            'note': "<p>Also in USENIX OSDI '94</p>",
            'key': 'HRQN4HX4',
            'parentItem': 'KPHICGWA',
            'itemType': 'note',
            'relations': {},
            'dateAdded': '2014-05-14T04:53:55Z',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': '4CFC7QGH',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/KPHICGWA'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/4CFC7QGH'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/4CFC7QGH'
                  }},
        'data': {
            'dateModified': '2016-12-23T16:31:44Z',
            'version': 4019,
            'tags': [],
            'note': "<p>Also in USENIX OSDI '94</p>",
            'key': '4CFC7QGH',
            'parentItem': 'KPHICGWA',
            'itemType': 'note',
            'relations': {},
            'dateAdded': '2014-05-14T04:56:26Z',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {'creatorSummary': 'Cao et al.', 'parsedDate': '1994',
                 'numChildren': 0},
        'key': 'P6R7SKQN',
        'links': {'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/P6R7SKQN'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/P6R7SKQN'
                  }},
        'data': {
            'collections': ['2QWF3CPM'],
            'seriesTitle': '',
            'extra': '',
            'key': 'P6R7SKQN',
            'tags': [{'tag': 'Caching'}, {'tag': 'Prefetching'}],
            'itemType': 'report',
            'title': 'A Study of Integrated Prefetching and Caching Strategies'
                ,
            'url': '',
            'reportType': '',
            'abstractNote': '',
            'pages': '',
            'language': '',
            'relations': {'dc:replaces': ['http://zotero.org/users/3661336/items/AXRC86CW'
                          ,
                          'http://zotero.org/users/3661336/items/T66458T5'
                          ,
                          'http://zotero.org/users/3661336/items/7PMEPUDG'
                          ]},
            'libraryCatalog': '',
            'rights': '',
            'shortTitle': '',
            'institution': 'Department of Computer Science, Princeton University'
                ,
            'creators': [{'creatorType': 'author', 'firstName': 'P.',
                         'lastName': 'Cao'}, {'creatorType': 'author',
                         'firstName': 'E. W.', 'lastName': 'Felten'},
                         {'creatorType': 'author', 'firstName': 'A.',
                         'lastName': 'Karlin'}, {'creatorType': 'author'
                         , 'firstName': 'K.', 'lastName': 'Li'}],
            'archiveLocation': '',
            'version': 4019,
            'accessDate': '',
            'dateModified': '2016-12-23T16:31:39Z',
            'date': '1994',
            'dateAdded': '2013-12-25T01:43:46Z',
            'callNumber': '',
            'reportNumber': 'CS-TR-479-94',
            'archive': '',
            'place': '',
            },
        },
    {
        'version': 4019,
        'library': {
            'links': {'alternate': {'type': 'text/html',
                      'href': 'https://www.zotero.org/peter_gerdes'}},
            'name': 'Peter Gerdes',
            'type': 'user',
            'id': 3661336,
            },
        'meta': {},
        'key': 'M2INCF26',
        'links': {'up': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/NZ7WRXGE'
                  }, 'alternate': {'type': 'text/html',
                  'href': 'https://www.zotero.org/peter_gerdes/items/M2INCF26'
                  }, 'self': {'type': 'application/json',
                  'href': 'https://api.zotero.org/users/3661336/items/M2INCF26'
                  }},
        'data': {
            'note': '',
            'charset': '',
            'relations': {},
            'contentType': 'application/pdf',
            'dateModified': '2016-12-23T16:31:33Z',
            'key': 'M2INCF26',
            'tags': [],
            'itemType': 'attachment',
            'title': 'A parallel dynamic compiler for CIL bytecode -- Campanoni et al_2008_.pdf'
                ,
            'url': '',
            'accessDate': '',
            'version': 4019,
            'path': '/Users/TruePath/Google Drive/Managed Library/A parallel dynamic compiler for CIL bytecode -- Campanoni et al_2008_.pdf'
                ,
            'dateAdded': '2016-12-21T11:50:00Z',
            'linkMode': 'linked_file',
            'parentItem': 'NZ7WRXGE',
            },
        },
    ]

assert len(item_data) == 50
