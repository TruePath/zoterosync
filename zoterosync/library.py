from pyzotero import zotero
import re
import random
import copy
import logging
import datetime
import dateutil.parser
from functools import wraps
import functools
import editdistance

# create logger
logger = logging.getLogger('zoterosync.library')

# SaveFile = "~/zotero.pkl"


# items = zot.top(limit=5)
# col = zot.collections()
# we've retrieved the latest five top-level items in our library
# we can print each item's item type and ID
# for item in items:
# print('Item: {0} | Key: {1}'.format(item['data']['itemType'], item['data']['key']))


def subclassfactory(fact_method):
    """fact_method takes the same args as init and returns the subclass appropriate to those args
    that subclass may in turn override the same factory method and choose amoung it's subclasses.
    If this factory method isn't overridden in the subclass an object of that class is inited.
    fact_method is made into a cls method and must take at least a cls argument
    """
    @wraps(fact_method)
    @classmethod
    def wrapper(cls, *args, **kwargs):
        subclass = fact_method(cls, *args, **kwargs)
        submeth = getattr(subclass, fact_method.__name__)
        curmeth = getattr(cls, fact_method.__name__)
        if (submeth.__func__ == curmeth.__func__):
            return subclass(*args, **kwargs)
        else:
            return submeth(*args, **kwargs)
    return wrapper


class ZoteroLibraryError(Exception):
    """ Generic parent exception
    """
    pass


class ConsistencyError(ZoteroLibraryError):
    """ Cached data is inconsistant with itself or server
    """
    pass


class InvalidData(ZoteroLibraryError):
    """ Raised if the data returned by the server is unexpected.
    """

    def __init__(self, dict, msg="Invalid Data: "):
        self.dict = dict
        self.msg = msg

    def __str__(self):
        return (self.msg + "\n" + self.dict.__str__())


class InvalidProperty(ZoteroLibraryError):
    """ Raised if an attempt is made to set a property to an invalid value
    """
    pass


class EarlyExit(Exception):
    """ Exception raised to exit from code in case of early exit (like SIGINT)
    """

    def __init__(self, revert=False):
        self.revert = revert


class Person(object):

    def __init__(self, last, first):
        self._lastname = last
        self._firstname = first

    @property
    def firstname(self):
        return self._firstname

    @property
    def lastname(self):
        return self._lastname

    def same(self, other):
        norm_self_last = re.sub('[^\w\s]', '', self.lastname.strip().casefold())
        norm_other_last = re.sub('[^\w\s]', '', other.lastname.strip().casefold())
        if (norm_self_last == norm_other_last):
            self_first = re.sub('[^\w\s.]', '', self.firstname.strip().casefold())
            other_first = re.sub('[^\w\s.]', '', self.firstname.strip().casefold())
            if (len(self_first) == 0 or len(other_first) == 0):
                return True
            self_first_start = re.split('[.\s]', self_first)[0]
            other_first_start = re.split('[\.s]', other_first)[0]
            if (len(self_first) == len(self_first_start) == 2 and self_first_start.isupper()):  # heuristic for initials e.g. PG Odifreddi
                self_first_start = self_first_start[0]  # Skip 3 initials like WVO b/c too many names are 3 letters
            if (len(other_first_start) == len(other_first) == 2 and other_first_start.isupper()):
                other_first_start = other_first_start[0]
            s = self_first_start.casefold()
            o = other_first_start.casefold()
            if (s.startswith(o) or o.startswith(s)):
                return True
        return False

    def first_initial_only(self):
        if (re.match('\A\w([ .]|\Z)', self.firstname.strip()) or
            (len(self.firstname.strip()) == 2 and self.firstname.strip().isalpha() and
                self.firstname.strip().isupper())):
            return True
        else:
            return False

    def distance(self, other):
        if (self.firstname == '' or other.firstname == ''):
            first_dis = 0
        elif (self.first_initial_only() or other.first_initial_only()):
            first_dis = 0 if self.first_initial == other.first_initial else 1
        else:
            self_clean_first = re.split('[\s.]', self.clean().firstname.casefold())[0]
            other_clean_first = re.split('[\s.]', other.clean().firstname.casefold())[0]
            first_dis = editdistance.eval(self_clean_first, other_clean_first)/(min(len(self_clean_first), len(other_clean_first)))
        self_clean_last = self.clean().lastname.casefold()
        other_clean_last = other.clean().lastname.casefold()
        last_dis = editdistance.eval(self_clean_last, other_clean_last)/(min(len(self_clean_last), len(other_clean_last)))
        return last_dis + first_dis

    def clean(self):
        firstname = self.firstname
        lastname = self.lastname
        firstname = re.sub('[^\w.\s]', '', firstname.strip())
        firstname = firstname.replace('  ', ' ')
        firstname = re.sub('[ ]\.', '.', firstname)
        firstname = firstname[:1].upper() + firstname[1:]
        firstname = re.sub('(\A|\s|\.)(\w)(\s|\Z)(?!\s*\.)', "\\1\\2.\\3", firstname)
        if (self.first_initial_only()):
            firstname = re.sub('\A(\w)(\w)\.?\Z', "\\1.\\2.", firstname)
        firstname = firstname.replace('..', '.')
        lastname = re.sub('[^\w\s]', '', lastname.strip())
        lastname = lastname.replace('  ', ' ')
        return Person(last=lastname, first=firstname)

    @staticmethod
    def merge(*people):
        if (len(people) == 0):
            return Person('', '')
        people = [p.clean() for p in people]
        last_norm_counts = dict()
        for p in people:
            norm_last = p.lastname.replace(' ', '').casefold()
            last_norm_counts[norm_last] = last_norm_counts.get(norm_last, 0) + 1
        norm_last = functools.reduce(lambda x, y: y if last_norm_counts[y] > last_norm_counts[x] else x,
                                     last_norm_counts)
        people = [p for p in people if p.lastname.replace(' ', '').casefold() == norm_last]
        best_last = next(filter(lambda p: (p.lastname != p.lastname.lower() and p.lastname != p.lastname.upper()), people), people[0]).lastname
        counts = dict()
        for p in (p for p in people if p.first_initial):
                counts[p.first_initial] = counts.get(p.first_initial, 0) + 1
        best_first = ""
        if (len(counts) > 0):
            first_ini = functools.reduce(lambda x, y: y if counts[y] > counts[x] else x, counts)
            people = [p for p in people if p.first_initial == first_ini]
            counts = dict()
            for p in people:
                first = re.split('[\s.]', p.firstname, 1)[0].casefold()
                if (len(first) > 1 and not (len(p.firstname) == 2 and p.firstname.isupper() and p.firstname.isalpha())):  # test for two cap chars being initial
                    counts[first] = counts.get(first, 0) + 1
            if (len(counts) > 0):
                first = functools.reduce(lambda x, y: y if counts[y] > counts[x] else x, counts)
                people = [p for p in people if re.split('[\s.]+', p.firstname, 1)[0].casefold() == first]
        # figure we let second initial alone
                best_first = people[0].firstname
                for p in people[1:]:
                    if (len(p.firstname) > len(best_first)):
                        best_first = p.firstname
        return Person(last=best_last, first=best_first).clean()

    def __hash__(self):
        return hash((self.lastname, self.firstname))

    def __eq__(self, other):
        return (self.lastname == other.lastname and self.firstname == other.firstname)

    @property
    def fullname(self):
        return "{0} {1}".format(self.firstname, self.lastname)

    def copy(self):
        return Person(self.lastname, self.firstname)

    @property
    def first_initial(self):
        return self.firstname.strip()[:1].upper()


class Creator(object):
    """ Captures the creator object
    """
    def __init__(self, d):
        self._type = d["creatorType"]
        self._creator = Person(d.get('lastName', ""), d.get('firstName', ""))

    @staticmethod
    def factory(first, last, type):
        return Creator(dict(creatorType=type, lastName=last, firstName=first))

    def __eq__(self, other):
        return (self.creator == other.creator and self.type == other.type)

    def __hash__(self):
        return hash((self.creator, self.type))

    def same(self, other):
        return self.creator.same(other.creator)

    def to_dict(self):
        return dict(creatorType=self.type, lastName=self.lastname, firstName=self.firstname)

    def copy(self):
        return Creator(self.to_dict())

    @property
    def type(self):
        return self._type

    @property
    def creator(self):
        return self._creator

    @property
    def first_initial(self):
        return self.creator.first_initial

    @property
    def lastname(self):
        return self.creator.lastname

    @property
    def firstname(self):
        return self.creator.firstname

    def first_initial_only(self):
        return self.creator.first_initial_only()


class ZoteroLibrary(object):
    """ Captures the cached library
    """
    AllowedKeyChars = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"

    @staticmethod
    def factory(userid, apikey):
        return ZoteroLibrary(zotero.Zotero(userid, "user", apikey))

    def __init__(self, src):
        self._server = src
        self._attachments_by_md5s = dict()
        self.item_types = ["artwork", "audioRecording", "bill", "blogPost", "book", "bookSection", "case",
                           "computerProgram", "conferencePaper", "dictionaryEntry", "document", "email",
                           "encyclopediaArticle", "film", "forumPost", "hearing", "instantMessage", "interview",
                           "journalArticle", "letter", "magazineArticle", "manuscript", "map", "newspaperArticle",
                           "note", "patent", "podcast", "presentation", "radioBroadcast", "report", "statute",
                           "tvBroadcast", "thesis", "videoRecording", "webpage"]
        self.all_item_fields = ['numPages', 'numberOfVolumes', 'abstractNote', 'accessDate', 'applicationNumber',
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
        self.special_fields = ['creators', 'relations', 'collections', 'tags', 'children']
        self.item_fields = {'newspaperArticle': [ 'title', 'abstractNote', 'publicationTitle', 'place', 'edition', 'date', 'section', 'pages', 'language', 'shortTitle', 'ISSN', 'url', 'accessDate', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'rights', 'extra', ],
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
        self.item_creator_types = {'newspaperArticle': ['author', 'contributor', 'reviewedAuthor','translator'],
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
        self._collections = set()
        self._documents = set()
        self._attachments = set()
        self._objects_by_key = dict()
        self._dirty_objects = set()
        self._deleted_objects = set()
        self._tags = dict()
        self._version = None
        self._collkeys_for_refresh = set()
        self._itemkeys_for_refresh = set()
        self._next_version = None
        self.abort = False
        self._revert = False
        logger.debug("Initialize ZoteroLibrary")

    @property
    def documents(self):
        return self._documents

    @property
    def collections(self):
        return self._collections

    @property
    def attachments(self):
        return self._attachments

    def _early_abort(self):
        """If abort flag is set raises EarlyExit
        """
        if (self.abort):
            self.abort = False
            raise EarlyExit(self._revert)

    def _queue_pull(self):  # fix to use functions I added to pyzotero when out
        params = dict()
        if (self._version is not None):
            params['since'] = self._version
            deleted = self._server.deleted(**params)
            logger.info("%s Objects Deleted On Server", len(deleted))
            for key in (i for k in deleted if (k == "items" or k == "collections") for i in deleted[k]):
                if (key in self._objects_by_key):
                    obj = self._objects_by_key[key]
                    obj._remove(refresh=True)
                    self._deleted_objects.discard(obj)
        item_vers = self._server.item_versions(**params)
        self._next_version = int(self._server.request.headers.get('last-modified-version', 0))
        for key in item_vers:
            if (key not in self._objects_by_key or self._objects_by_key[key].version < item_vers[key]):
                self._itemkeys_for_refresh.add(key)
        coll_vers = self._server.collection_versions(**params)
        for key in coll_vers:
            if (key not in self._objects_by_key or self._objects_by_key[key].version < coll_vers[key]):
                self._collkeys_for_refresh.add(key)

    def _process_pull(self):
        self._refresh_queued_collections()
        self._refresh_queued_items()
        if (len(self._collkeys_for_refresh) == 0 and len(self._itemkeys_for_refresh) == 0):
            if (self._next_version is not None):
                self._version = self._next_version
                self._next_version = None

    def pull(self):
        logger.info("---- Initiating Pull Request ----\n\tFrom Version: %s", self._version)
        logger.info("Library Contains:\n\tCollections: %s\n\tDocuments: %s\n\tAttachments: %s\n\tTotal Objects: %s",
                    len(self._collections), len(self._documents), len(self._attachments), len(self._objects_by_key))
        self._queue_pull()
        logger.info("-- Pull Request Queued --")
        logger.info("\tItems Queued For Refresh: %s\n\tCollections Queued For Refresh: %s",
                    len(self._itemkeys_for_refresh), len(self._collkeys_for_refresh))
        self._process_pull()
        logger.info("---- Finished Pull Request ----\n\tAt Version: %s", self._version)
        logger.info("Library Contains:\n\tCollections: %s\n\tDocuments: %s\n\tAttachments: %s\n\tTotal Objects: %s",
                    len(self._collections), len(self._documents), len(self._attachments), len(self._objects_by_key))
        logger.info("\tItems Remaining For Refresh: %s\n\tCollections Remaining For Refresh: %s",
                    len(self._itemkeys_for_refresh), len(self._collkeys_for_refresh))

    @staticmethod
    def _fifty_keys_from_set(set):
        idstring = ""
        num = 0
        for key in set:
            idstring = idstring + key
            num = num + 1
            if (num >= 50):
                return idstring
            else:
                idstring = idstring + ","
        return idstring[:-1]  # kill final ,

    def _refresh_queued_items(self):
        while(len(self._itemkeys_for_refresh) > 0):
            ikeys = self._fifty_keys_from_set(self._itemkeys_for_refresh)
            logger.debug("Asking server for the following item string: %s", ikeys)
            newitems = self._server.items(itemKey=ikeys)
            for i in newitems:
                logger.debug("Recieving item: %s", i['data']['key'])
                self._recieve_item(i)
            self._early_abort()

    def _refresh_queued_collections(self):
        keys = self._collkeys_for_refresh.copy()
        for key in keys:
                logger.debug("Recieving Collection: %s", key)
                self._recieve_collection(self._server.collection(key))
                self._early_abort()

    def _update_template_data(self):
        self.item_types = [d["itemType"] for d in self._server.item_types()]
        self.all_item_fields = [d['field'] for d in self._server.item_fields()]
        self.item_fields = {i: [d['field'] for d in self._server.item_type_fields(i)] for i in self.item_types}
        self.item_creator_types = {i: [d['creatorType'] for d in self._server.item_creator_types(i)
                                       ] for i in self.item_types}

    def mark_dirty(self, obj):
        self._dirty_objects.add(obj)

    def mark_clean(self, obj):
        self._dirty_objects.discard(obj)

    def _remove(self, obj):
        """ Removes an object from all containers obj._remove is responsible for removing the relations
        """
        self._dirty_objects.discard(obj)
        if (isinstance(obj, ZoteroCollection)):
            self._collections.discard(obj)
        elif (isinstance(obj, ZoteroDocument)):
            self._documents.discard(obj)
        elif (isinstance(obj, ZoteroAttachment)):
            md5 = obj.md5
            if (md5 in self._attachments_by_md5s):
                del self._attachments_by_md5s[md5]
            self._attachments.discard(obj)

    def _mark_for_deletion(self, obj):
        self._deleted_objects.add(obj)

    def new_key(self):
        newkey = ""
        while(newkey == "" or newkey in self._objects_by_key):
            newkey = ""
            for i in range(8):
                newkey += random.choice(ZoteroLibrary.AllowedKeyChars)
        return newkey

    def get_obj_by_key(self, key):
        if (key in self._objects_by_key):
            return self._objects_by_key[key]
        else:
            return None

    def _recieve_item(self, dict):
        """Called on any item recieved from self._server
        """
        try:
            key = dict['data']['key']
            if (key in self._objects_by_key):
                self._objects_by_key[key].refresh(dict)
            else:
                ZoteroItem.factory(self, dict)
            self._itemkeys_for_refresh.discard(key)
            logger.debug("Removing key %s from _itemkeys_for_refresh", key)
            assert key not in self._itemkeys_for_refresh
        except KeyError as e:
            raise InvalidData(dict) from e

    def _recieve_collection(self, dict):
        """Called on any item recieved from self._server
        """
        try:
            key = dict['data']['key']
            if (key in self._objects_by_key):
                self._objects_by_key[key].refresh(dict)
            else:
                ZoteroCollection.factory(self, dict)
            self._collkeys_for_refresh.discard(key)
            logger.debug("Removing key %s from _collkeys_for_refresh", key)
        except KeyError as e:
            raise InvalidData(dict) from e

    def _get_items(self, **kwargs):
        """Get all items satisfying kwargs from self._server and update/record them
        """
        for items in self._server.makeiter(self._server.items(**kwargs)):
            for i in items:
                self._recieve_item(i)

    def _get_collections(self, **kwargs):
        """Get all items satisfying kwargs from self._server and update/record them
        """
        for items in self._server.makeiter(self._server.collections(**kwargs)):
            for i in items:
                self._recieve_collection(i)

    def _register_obj(self, obj):
        self._objects_by_key[obj.key] = obj

    def _register_collection(self, obj):
        self._collections.add(obj)

    def _register_document(self, obj):
        self._documents.add(obj)

    def _register_attachment(self, obj):
        self._attachments.add(obj)
        if (obj.md5 is not None):
            if (obj.md5 in self._attachments_by_md5s):
                self._attachments_by_md5s[obj.md5].add(obj)
            else:
                self._attachments_by_md5s[obj.md5] = {obj}

    def _register_parent(self, obj, pkey):
        if (obj.parent is not None):
            obj.parent.children.discard(obj)
        if (pkey and pkey != "false"):
            if (isinstance(pkey, ZoteroObject)):
                pkey = pkey.key
            if (pkey not in self._objects_by_key):
                if (isinstance(obj, ZoteroItem)):
                    parent = ZoteroDocument(self, pkey)
                elif (isinstance(obj, ZoteroCollection)):
                    parent = ZoteroCollection(self, pkey)
            else:
                parent = self._objects_by_key[pkey]
            parent.children.add(obj)
            return parent
        else:
            return None

    def _register_into_collection(self, obj, ckey):
        if (isinstance(ckey, ZoteroObject)):
            ckey = ckey.key
        # logger.debug("called _register_into_collection in ZoteroLibrary with obj.key=%s and " +
        #              "collection key=%s", obj.key, ckey)
        if (ckey not in self._objects_by_key):
            col = ZoteroCollection(self, ckey)
        else:
            col = self._objects_by_key[ckey]
        col.members.add(obj)
        return col

    def _register_outof_collection(self, obj, ckey):
        if (isinstance(ckey, ZoteroObject)):
            col = ckey
        else:
            col = self._objects_by_key[ckey]
        col.members.discard(obj)
        return col

    def _register_into_tag(self, obj, tag):
        if (tag not in self._tags):
            self._tags[tag] = set()
        self._tags[tag].add(obj)
        return self._tags[tag]

    def _register_outof_tag(self, obj, tag):
        if (tag in self._tags):
            self._tags[tag].discard(obj)
            if (len(self._tags[tag]) == 0):
                del self._tags[tag]

    @property
    def num_docs(self):
        return len(self._documents)

    @property
    def num_collections(self):
        return len(self._collections)

    @property
    def num_attachments(self):
        return len(self._attachments)

    @property
    def num_items(self):
        return self.num_docs + self.num_attachments


class ZoteroObject(object):

    _parent_key = None   # override in inherited classes

    @subclassfactory
    def factory(cls, library, dict):
        try:
            if ("itemType" in dict["data"]):
                if (dict["data"]["itemType"] == "attachment"):
                    return ZoteroAttachment
                else:
                    return ZoteroDocument
            else:
                return ZoteroCollection
        except KeyError as e:
            raise InvalidData(dict) from e

    def __init__(self, library, arg):
        self._library = library
        self._dirty = False
        self._deleted = False
        self._parent = None
        self._children = set()
        self._changed_from = dict()
        if (isinstance(arg, dict)):
            try:
                data = arg["data"]
                self._data = dict(key=data["key"], version=data["version"])
                for k in (q for q in data if (q != "key" and q != "version")):
                    self._register_property(k, data[k])
            except KeyError as e:
                raise InvalidData(dict) from e
        else:
            self._data = dict(key=arg, version=-1)
        self._library._register_obj(self)

    def __repr__(self):
        return self.__class__.__name__ + "(" + self._library.__repr__() + ", " + self._data.__repr__() + ")"

    def __str__(self):
        return self.name if (len(self.name) > 0) else "Untitled #" + self.key

    def refresh(self, dict):
        try:
            if (self.version >= dict["data"]["version"]):
                raise ConsistencyError("Tried to update an item with version: " +
                                       "{} with data versioned at: {}".format(self.version,  dict["data"]["version"]))
            self._data["version"] = dict["data"]["version"]
            for k in (q for q in dict["data"] if (q != "key" and q != "version")):
                self._refresh_property(k, dict["data"][k])
            if (self._parent_key in self._data and self._parent_key not in dict["data"]):
                self._refresh_property(self._parent_key, None)
        except KeyError as e:
            raise InvalidData(dict) from e

    def _refresh_property(self, k, val):
        if (k not in self._changed_from):
            self._register_property(k, val)
        else:
            self._changed_from[k] = val

    def _register_property(self, pkey, pval):
        # logger.debug("called _register_property in ZoteroObject with pkey=%s and pval=%s", pkey, pval)
        if (isinstance(pval, ZoteroObject)):
            pval = pval.key
        self._data[pkey] = pval
        if (pkey == self._parent_key):
            self._register_parent(pval)
            if (pval is None):
                del self._data[pkey]

    def _set_property(self, pkey, pval):  # Deals with underlying representation
        # logger.debug("called _set_property in ZoteroObject")
        if (pkey == "key"):
            raise InvalidProperty("Can't change key")
        if (pkey == "dateModified" or pkey == 'version'):
            return
        self.dirty = True
        if (pval is None):
            del self[pkey]
        else:
            if (pkey in self._data):
                fromval = self._data[pkey]
            elif (pkey == 'collections' or pkey == 'tags' or pkey == 'creators'):
                fromval = list()
            elif (pkey == 'relations'):
                fromval = dict()
            else:
                fromval = None
            self._register_property(pkey, pval)
            if (pkey not in self._changed_from):
                self._changed_from[pkey] = fromval

    def __setitem__(self, pkey, pval):
        if (pkey == "parent"):
            self.parent = pval
        elif (pkey == "children"):
            self.children = pval
        else:
            self._set_property(pkey, pval)

    def __getitem__(self, pkey):
        if (pkey == "parent"):
            return self.parent
        elif (pkey == "children"):
            return self.children
        elif (pkey == "key"):
            return self.key
        elif (pkey in self._data):
            return self._data[pkey]
        else:
            return None

    def __delitem__(self, pkey):
        if (pkey == "children"):
            del self.children
        else:
            self.dirty = True
            if (pkey not in self._changed_from):
                if (pkey in self._data):
                    self._changed_from[pkey] = self._data[pkey]
                elif (pkey == 'creators'):
                    self._changed_from[pkey] = list()
                elif (pkey == 'relations'):
                    self._changed_from[pkey] = dict()
                else:
                    self._changed_from[pkey] = None
            if (pkey in self._data):
                if (pkey == 'relations'):
                    self._data[pkey] = dict()
                elif (pkey == 'creators'):
                    self._data[pkey] = list()
                else:
                    self._data[pkey] = ''
            if (pkey == self._parent_key):
                self._register_parent(None)
                self._data[self._parent_key] = False

    def update(self, dict):
        for k in dict.keys():
            if (k != "key" and k != "version"):
                self._set_property(k, dict[k])

    def __iter__(self):
        return self.properties().__iter__()

    def properties(self):
        if (self._parent_key is not None):
            yield "parent"
        yield from (p for p in self._data if (p != self._parent_key and p != "key" and p != "version"))

    def _register_parent(self, ptag):
        self._parent = self._library._register_parent(self, ptag)

    def delete(self):
        self._library._mark_for_deletion(self)
        self._remove()
        self._deleted = True

    def _remove(self, refresh=False):
        """removes object from the library.  Responsible for taking out of all containers and relations.
        """
        if self.deleted:
            return
        self._library._remove(self)
        self._library._register_parent(self, None)  # remove from any children collections
        if (refresh):
            for c in self._children.copy():
                c._refresh_property(c._parent_key, None)
        else:
            for c in self._children.copy():
                c.parent = None

    @property
    def version(self):
        try:
            return self._data["version"]
        except KeyError as e:
            raise InvalidData(dict) from e

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, val):
        # logger.debug("called dirty setter in ZoteroObject")
        if (val):
            self._dirty = True
            self._library.mark_dirty(self)
        else:
            self._dirty = False
            self._library.mark_clean(self)

    @property
    def deleted(self):
        return self._deleted

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, pkey):
        if (isinstance(pkey, ZoteroObject)):
            pkey = pkey.key
        self._set_property(self._parent_key, pkey)

    @parent.deleter
    def parent(self):
        del self[self._parent_key]

    @property
    def children(self):
        return self._children

    @children.setter
    def children(self, pval):
        for child in self._children.difference(pval):
            child.parent = None
        for child in pval.difference(self._children):
            child.parent = self
        self._children = pval.copy()

    @children.deleter
    def children(self):
        for child in self._children:
            child.parent = None
        self._children = set()

    @property
    def key(self):
        return self._data["key"]

    @property
    def name(self):
        return (self._data["name"] if "name" in self._data else '')


class ZoteroItem(ZoteroObject):

    def __init__(self, library, arg):
        self._collections = set()
        super().__init__(library, arg)

    def _register_property(self, pkey, pval):
        # logger.debug("called _register_property in ZoteroItem with pkey=%s and pval=%s", pkey, pval)
        if (pkey == "collections"):
            for c in self._collections:
                self._library._register_outof_collection(self, c)
            self._collections = {self._library._register_into_collection(self, ckey)
                                 for ckey in pval}
        if (pkey == "tags"):
            for tag in self.tags:
                self._library._register_outof_tag(self, tag)
            for tag in {t["tag"] for t in pval}:
                self._library._register_into_tag(self, tag)
        super()._register_property(pkey, pval)

    def _refresh_property(self, pkey, pval):
        if (pkey == "collections"):
            update_keys = {ckey for ckey in pval}
            if ("collections" in self._changed_from):
                orig_keys = {ckey for ckey in self._changed_from["collections"]}
                if ("collections" in self._data):
                    cur_cols = {ckey for ckey in self._data["collections"]}
                else:
                    cur_cols = set()
                cols = cur_cols.difference(orig_keys.difference(update_keys)).union(
                                            update_keys.difference(orig_keys))
                self._changed_from["collections"] = [c for c in update_keys]
            else:
                cols = update_keys
            self._register_property("collections", [c for c in cols])
        elif (pkey == "tags"):
            update_tags = {t["tag"] for t in pval}
            if ("tags" in self._changed_from):
                orig_tags = {t["tag"] for t in self._changed_from["tags"]}
                if ("tags" in self._data):
                    cur_tags = {t["tag"] for t in self._data["tags"]}
                else:
                    cur_tags = set()
                tags = cur_tags.difference(orig_tags.difference(update_tags)).union(
                            update_tags.difference(orig_tags))
                self._changed_from["tags"] = [dict(tag=t) for t in update_tags]
            else:
                tags = update_tags
            self._register_property("tags", [dict(tag=t) for t in tags])
        elif (pkey == "dateModified"):
            cur_mod = self.date_modified
            if (cur_mod is None):
                self._data["dateModified"] = pval
            else:
                self._data["dateModified"] = max(cur_mod, dateutil.parser.parse(pval)
                                                 ).replace(tzinfo=None).isoformat("T") + "Z"
        else:
            super()._refresh_property(pkey, pval)

    def __setitem__(self, pkey, pval):
        if (pkey == "collections"):
            self.collections = pval
        elif (pkey == "tags"):
            self.tags = pval
        elif (pkey == "relations"):
            self.relations = pval
        elif (pkey == "title"):
            self.title = pval
        elif (pkey == "dateModified"):
            return  # can't change date_modified
        elif (pkey == "dateAdded"):
            self.date_added = pval
        elif (pkey == "date"):
            self.date = pval
        elif (pkey == "itemType"):
            self.type = pval
        elif (pkey == "creators"):
            self.creators = pval
        else:
            super().__setitem__(pkey, pval, pval)

    def __getitem__(self, pkey):
        if (pkey == "collections"):
            return self.collections
        elif (pkey == "tags"):
            return self.tags
        elif (pkey == "relations"):
            return self.relations
        elif (pkey == "title"):
            return self.title
        elif (pkey == "dateModified"):
            return self.date_modified
        elif (pkey == "dateAdded"):
            return self.date_added
        elif (pkey == "date"):
            return self.date
        elif (pkey == "creators"):
            return self.creators
        else:
            return super().__getitem__(pkey)

    def __delitem__(self, pkey):
        if (pkey == "collections"):
            self.collections = set()
        elif (pkey == "tags"):
            self.tags = set()
        elif (pkey == "dateModified"):
            return  # can't delete this property
        elif (pkey == "dateAdded"):
            self.date_added = None
        elif (pkey == "creators"):
            self.creators = list()
        else:
            super().__delitem__(pkey)

    def properties(self):
        yield from (p for p in super().properties() if (
            p != "dateModified" and p != "itemType" and p != "linkMode" and p != "itemType"))

    def _remove(self, refresh=False):
        if self.deleted:
            return
        super()._remove(refresh=refresh)
        for c in self.collections:
            self._library._register_outof_collection(self, c)
        for t in self.tags:
            self._library._register_outof_tag(self, t)

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, val):
        # logger.debug("called dirty setter in ZoteroItem")
        if (val):
            self._dirty = True
            self._library.mark_dirty(self)
            self._data["dateModified"] = datetime.datetime.utcnow().isoformat("T") + "Z"
        else:
            self._dirty = False
            self._library.mark_clean(self)

    @property
    def collections(self):
        return self._collections

    @collections.setter
    def collections(self, val):
        for c in self._collections.difference(val):
            self._library._register_outof_collection(self, c)
        for c in val.difference(self._collections):
            self._library._register_into_collection(self, c)
        newcols = list()
        for c in val:
            if (isinstance(c, ZoteroCollection)):
                newcols.append(c.key)
            else:
                newcols.append(c)
        self._set_property("collections", newcols)

    def remove_from_collection(self, col, refresh=False):
        if (isinstance(col, str)):
            col = self._library.get_obj_by_key(col)
        if (col in self.collections):
            if (refresh):
                self._refresh_property("collections", [c.key for c in self.collections if c != col])
            else:
                self._set_property("collections", [c.key for c in self.collections if c != col])
        self._library._register_outof_collection(self, col)

    def add_to_collection(self, col):
        if (isinstance(col, str)):
            ckey = col
            col = self._library.get_obj_by_key(col)
        else:
            ckey = col.key
        if (col not in self.collections):
            newcols = [c.key for c in self.collections]
            newcols.append(ckey)
            self._library._register_into_collection(self, col)

    @property
    def tags(self):
        if ("tags" in self._data):
            return {t["tag"] for t in self._data["tags"]}
        else:
            return set()

    @tags.setter
    def tags(self, val):
        for c in self.tags.difference(val):
            self._library._register_outof_tag(self, c)
        for c in val.difference(self.tags):
            self._library._register_into_tag(self, c)
        self._set_property("tags", [dict(tag=t) for t in val])

    def add_tag(self, tag):
        if (tag not in self.tags):
            self.tags = self.tags.add(tag)

    def remove_tag(self, tag):
        if (tag in self.tags):
            self.tags = self.tags.discard(tag)

    @property
    def relations(self):
        if ("relations" in self._data):
            return self._data["relations"].copy()
        else:
            return dict()

    @relations.setter
    def relations(self, val):
        self._set_property("relations", val.copy())

    @property
    def title(self):
        if ('title' in self._data):
            return self._data['title']
        else:
            return ''

    @title.setter
    def title(self, val):
        self._set_property("title", val)

    @property
    def date_modified(self):
        if ("dateModified" in self._data):
            return dateutil.parser.parse(self._data["dateModified"])
        else:
            return None

    @property
    def date_added(self):
        if ("dateAdded" in self._data):
            return dateutil.parser.parse(self._data["dateAdded"])
        else:
            return None

    @date_added.setter
    def date_added(self, val):
        if (val is None):
            self._set_property("dateAdded", '')
            return None
        if (isinstance(val, datetime.datetime)):
            dt = val
        else:
            dt = dateutil.parser.parse(val)
        self._set_property("dateAdded", dt.replace(tzinfo=None).isoformat("T") + "Z")
        return dt

    @property
    def date(self):
        if ("date" in self._data):
            return self._data["date"]
        else:
            return None

    @date.setter
    def date(self, val):
        self._set_property("date", val)

    @property
    def type(self):
        return self._data["itemType"]

    @type.setter
    def type(self, val):
        return (self._set_property("itemType", val))

    @property
    def creators(self):
        if ("creators" in self._data):
            return [Creator(d) for d in self._data["creators"]]
        else:
            return list()

    @creators.setter
    def creators(self, val):
        self._set_property("creators", [c.to_dict() for c in val])


class ZoteroDocument(ZoteroItem):

    def __init__(self, library, arg):
        super().__init__(library, arg)
        self._library._register_document(self)

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroDocument with pkey=%s and pval=%s", pkey, pval)
        if (pkey == "itemType" and pval not in self._library.item_types):
            raise InvalidProperty("Tried to set itemType to {}".format(pval))
        super()._set_property(pkey, pval)

    def properties(self):
        yield "children"
        yield from super().properties()


class ZoteroAttachment(ZoteroItem):

    _parent_key = "parentItem"   # override in inherited classes

    @subclassfactory
    def factory(cls, library, dict):
        try:
            if (dict["data"]["linkMode"] == "linked_file"):
                    return ZoteroLinkedFile
            elif (dict["data"]["linkMode"] == "imported_file"):
                    return ZoteroImportedFile
            elif (dict["data"]["linkMode"] == "imported_url"):
                    return ZoteroImportedUrl
            else:
                raise InvalidData(dict, "Unkown attachment type")
        except KeyError as e:
            raise InvalidData(dict) from e

    def __init__(self, library, arg):
        super().__init__(library, arg)
        self._library._register_attachment(self)

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroAttachment")
        if (pkey == "itemType"):
            if (pval != "attachment"):
                raise InvalidProperty("Can't change attachment itemType")
            else:
                return
        else:
            super()._set_property(pkey, pval)

    @property
    def link_mode(self):
        return self._data["linkMode"]

    @property
    def md5(self):
        if ("md5" in self._data):
            return self._data["md5"]
        else:
            return None


class ZoteroLinkedFile(ZoteroAttachment):

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroLinkedFile")
        if (pkey == "linkMode"):
            if (pval != "linked_file"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)


class ZoteroImportedFile(ZoteroAttachment):

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroImportedFile")
        if (pkey == "linkMode"):
            if (pval != "imported_file"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)


class ZoteroImportedUrl(ZoteroAttachment):

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroImportedFile")
        if (pkey == "linkMode"):
            if (pval != "imported_url"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)


class ZoteroCollection(ZoteroObject):

    _parent_key = "parentCollection"   # override in inherited classes

    def __init__(self, library, arg):
        self.members = set()
        super().__init__(library, arg)
        self._library._register_collection(self)

    def _remove(self, refresh=False):
        if self.deleted:
            return
        for i in self.members.copy():
            i.remove_from_collection(self, refresh=refresh)
        super()._remove(refresh=refresh)

    def properties(self):
        yield "children"
        yield from super().properties()