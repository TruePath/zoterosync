from pyzotero import zotero
from pyzotero.zotero_errors import PreConditionFailed
from pyzotero.zotero_errors import PyZoteroError
import re
import random
import copy
import logging
import datetime
import dateutil.parser
from functools import wraps
import functools
import itertools
import editdistance
from pathlib import Path
from nameparser import HumanName
import filecmp
import hashlib
import tempfile
import shutil

# create logger
logger = logging.getLogger('zoterosync.library')

# SaveFile = "~/zotero.pkl"


# items = zot.top(limit=5)
# col = zot.collections()
# we've retrieved the latest five top-level items in our library
# we can print each item's item type and ID
# for item in items:
# print('Item: {0} | Key: {1}'.format(item['data']['itemType'], item['data']['key']))

def md5(path):
    hash_md5 = hashlib.md5()
    with path.open(mode="rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


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


class SyncError(ZoteroLibraryError):
    """ Generic parent exception for sync failures, i.e., anything failing on the network """
    pass

class StaleLocalData(SyncError):
    """ Exception raised when local data must be refreshed before changes can be made on server """
    pass


class UpdateRejected(SyncError):
    """ Exception raised when server rejects our update """
    def __init__(self, msg="Update Rejected", response=None):
        self.response = response
        self.msg = msg

    def __str__(self):
        return (self.msg + "\nRESPONSE:\n" + self.response.__str__())


class ConsistencyError(ZoteroLibraryError):
    """ Cached data is inconsistant with itself or server
    """
    
    def __init__(self, msg="Consistency Error", obj=None):
        self.obj = obj
        self.msg = msg

    def __str__(self):
        if (self.obj is not None):
            return (self.msg + "\n" + str(self.obj))
        else:
            return self.msg


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

class InvalidPath(ZoteroLibraryError):
    """ Raised if an attempt is made to use a path that is invalid
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

    @staticmethod
    def parsename(name):
        parsed = HumanName(name)
        parsed.capitalize()
        first = "{title} {first} {middle}".format(**parsed.as_dict()).strip()
        last = "{last} {suffix}".format(**parsed.as_dict()).strip()
        if (last == ""):
            last = first
            first = ""
        return Person(last=last, first=first)

    @property
    def first(self):
        return self.firstname
    
    @property
    def firstname(self):
        return self._firstname

    @property
    def last(self):
        return self.lastname

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

    def first_initials_only(self):
        """Returns true if the firstname is only initials"""
        if (re.match('\A(\s*\w([ .]|\Z)\s*\.?){1,3}\s*\Z', self.firstname.strip()) or re.match('\A\s*[A-Z]\s*[A-Z]\s*\.?\s*\Z', self.firstname.strip())):
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
        firstname = re.sub('[\s]*\.', '.', firstname)
        firstname = firstname[:1].upper() + firstname[1:]
        firstname = re.sub('(?<!\w)(\w)(?![\w.])', "\\1.", firstname)  # Put periods after isolated letters
        if (re.match('\A\s*[A-Z]\s*[A-Z]\s*\.?\s*\Z', self.firstname)):
            firstname = re.sub('\A\s*([A-Z])\s*([A-Z])\s*\.?\s*\Z', "\\1.\\2.", firstname)  # If firstname just two chars put periods after each
        if self.first_initials_only():
            firstname = re.sub(' ', '', firstname)  # if only initials drop spaces
        firstname = firstname.replace('..', '.')
        lastname = re.sub('[^\w\s]', '', lastname.strip())
        lastname = lastname.replace('  ', ' ')
        return Person(last=lastname, first=firstname)

    @staticmethod
    def merge(*people):
        logger.debug("Called Person.merge with args %s", str(people))
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
            first_ini = functools.reduce(lambda x, y: y if counts[y] > counts[x] else x, counts, next(iter(counts)))
            logger.debug("Called Person.merge gave first_ini: %s", first_ini)
            people = [p for p in people if p.first_initial == first_ini]
            people_full_firstnames = [p for p in people if not p.first_initials_only()]
            if (len(people_full_firstnames) > 0):
                people = people_full_firstnames
            counts = dict()
            for p in people:
                first = re.split('[\s.]', p.firstname, 1)[0].casefold()
                if (first):
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
        return "{0} {1}".format(self.firstname, self.lastname).strip()

    def copy(self):
        return Person(self.lastname, self.firstname)

    @property
    def first_initial(self):
        return self.firstname.strip()[:1].upper()

    def __str__(self):
        return self.firstname + ' ' + self.lastname

    def __repr__(self):
        return repr({'firstName':self.firstname, 'lastName':self.lastname})

    def __bool__(self):
        if (self.lastname or self.firstname):
            return True
        else:
            return False


class Creator(object):
    """ Captures the creator object
    """
    def __init__(self, d):
        self._type = d["creatorType"]
        if ("name" in d and "lastName" not in d):
            logger.debug("Creator built with name property")
            self._creator = Person.parsename(d["name"])
        else:
            self._creator = Person(d.get('lastName', ""), d.get('firstName', ""))

    def __str__(self):
        return "<" + self._type + ": " + str(self._creator) + ">"

    def __repr__(self):
        return repr(self.to_dict())

    def clean(self):
        per = self._creator.clean()
        return Creator(dict(creatorType=self.type, lastName=per.lastname, firstName=per.firstname))

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

    @property
    def fullname(self):
        return self._creator.fullname

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
        self._new_objects = set()
        self._tags = dict()
        self._version = None
        self._collkeys_for_refresh = set()
        self._itemkeys_for_refresh = set()
        self._next_version = 0
        self.abort = False
        self.force_update = False
        self.checkpoint_function = None
        self._revert = False
        self.datadir = None
        self.zoterodir = Path(tempfile.gettempdir())
        self.use_relative_paths = False
        self._downloads = set()
        self._uploads = set()
        logger.debug("Initialize ZoteroLibrary")

    def request_download(self, attach):
        self._downloads.add(attach)

    def cancel_download(self, attach):
        if (not attach.download):
            self._downloads.discard(attach)

    def _mark_file_dirty(self, attach):
        self._uploads.add(attach)

    def _mark_file_clean(self, attach):
        self._uploads.discard(attach)

    @property
    def documents(self):
        return self._documents

    @property
    def deleted_objects(self):
        return self._deleted_objects

    @property
    def deleted_documents(self):
        return {d for d in self._deleted_objects if isinstance(d, ZoteroDocument)}

    @property
    def collections(self):
        return self._collections

    @property
    def deleted_collections(self):
        return {d for d in self._deleted_objects if isinstance(d, ZoteroCollection)}

    @property
    def attachments(self):
        return self._attachments

    @property
    def deleted_attachments(self):
        return {d for d in self._deleted_objects if isinstance(d, ZoteroAttachment)}

    def _checkpoint(self):
        logger.info("-- Checkpoint Requested --")
        if (self.checkpoint_function is not None):
            return self.checkpoint_function()
            logger.info("-- Checkpoint Saved --")
        else:
            return True

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
            logger.info("%s Collections Deleted On Server", len(deleted["collections"]))
            logger.info("%s Items Deleted On Server", len(deleted["items"]))
            for key in (i for k in deleted if (k == "items" or k == "collections") for i in deleted[k]):
                logger.debug("Object with key %s is deleted on server", key)
                if (key in self._objects_by_key):
                    obj = self._objects_by_key[key]
                    obj._remove(refresh=True)
                    self._deleted_objects.discard(obj)
        item_vers = self._server.item_versions(**params)
        self._next_version = max(self._next_version, int(self._server.request.headers.get('last-modified-version', 0)))
        for key in item_vers:
            if (key not in self._objects_by_key or self._objects_by_key[key].version < item_vers[key]):
                self._itemkeys_for_refresh.add(key)
        coll_vers = self._server.collection_versions(**params)
        self._next_version = max(self._next_version, int(self._server.request.headers.get('last-modified-version', 0)))
        for key in coll_vers:
            if (key not in self._objects_by_key or self._objects_by_key[key].version < coll_vers[key]):
                self._collkeys_for_refresh.add(key)

    def _process_pull(self):
        self._refresh_queued_collections()
        self._refresh_queued_items()
        if (len(self._collkeys_for_refresh) == 0 and len(self._itemkeys_for_refresh) == 0):
            if (self._next_version):
                self._version = self._next_version
                self._next_version = 0

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

    def push(self, nested=0):
        try:
            try:
                logger.info("---- Initiating Push Request ----\n\tFrom Version: %s", self._version)
                logger.info("Library Contains:\n\tCollections: %s\n\tDocuments: %s\n\tAttachments: %s\n\tTotal Objects: %s\n\tDirty Objects: %s\n\tNew Objects: %s\n\tDeleted Obects: %s",
                        len(self._collections), len(self._documents), len(self._attachments), len(self._objects_by_key), len(self._dirty_objects), len(self._new_objects), len(self._deleted_objects))
                self._push_updates()
                self._push_deleted()
                logger.info("---- Finished Push ----\n\tAt Version: %s", self._version)
            except (PreConditionFailed, StaleLocalData) as e:
                if (nested < 4):
                    logger.info("-- Local Data Stale Initiating Pull --")
                    self.pull()
                    logger.info("-- Reinitiating Push --")
                    logger.info("-- Setting Force to True --")
                    self.force_update = True
                    self.push(nested=(nested + 1))
                    self.force_update = False  # Total hack...ideally should track down why this needed
                else:
                    self.force_update = False
                    raise SyncError from e
        except PyZoteroError as e:
            raise SyncError from e
        self._checkpoint()
        logger.info("---- Finished Push Request ----\n\tAt Version: %s", self._version)

    def upload_missing_attachments(self):
        logger.info("Uploading missing attachments")
        for attach in (i for i in self.attachments if isinstance(i, ZoteroImportedFile) and i.missing and not i.local_missing):
            logger.info("Uploading attachment %s", attach.key)
            self._server.upload_attachments([attach.data])
            logger.info("Finished uploading attachment %s", attach.key)
            self._checkpoint()
        self.pull()

    def _new_items_creation_order(self):
        """ Returns a list of the new objects so that objects always occur before children """
        def append_zobj(list, zobj):
            if zobj in list:
                return list
            elif (zobj.parent in self._new_objects):
                return append_zobj(list, zobj.parent) + [zobj]
            else:
                return list + [zobj]
        result = []
        for obj in self._new_objects:
            result = append_zobj(result, zobj)
        return result

    def _push_updates(self):
        """ Sends changes (new items and changed items) to server """
        updates = self._new_items_creation_order() + list(self._dirty_objects)
        logger.info("-- Updating Objects on Server --")
        logger.info("\t Creating %s objects.  Updating %s objects", len(self._new_objects), len(self._dirty_objects))
        batch_dirty_collections = []
        batch_dirty_items = []
        cur_collections = []
        cur_items = []
        num_items = 0
        num_collections = 0
        for obj in updates:
            if (isinstance(obj, ZoteroItem)):
                num_items += 1
                cur_items.append(obj)
                if (len(cur_items) > 49):
                    batch_dirty_items.append(cur_items)
                    cur_items = []
            elif (isinstance(obj, ZoteroCollection)):
                num_collections += 1
                cur_collections.append(obj)
                if (len(cur_collections) > 49):
                    batch_dirty_collections.append(cur_collections)
                    cur_collections = []
            else:
                raise ConsistencyError("Only Collections and Items Supported Currently")
        if (len(cur_collections) > 0):
            batch_dirty_collections.append(cur_collections)
        if (len(cur_items) > 0):
            batch_dirty_items.append(cur_items)
        logger.info("\t %s Items in %s Batches and %s Collections in %s Batches Queued For Update",
                    num_items, len(batch_dirty_items), num_collections, len(batch_dirty_collections))
        for batch in batch_dirty_collections:
            self._server_update_collections(batch)
        for batch in batch_dirty_items:
            self._server_update_items(batch)
        if (len(self._dirty_objects) > 0 or len(self._new_objects) > 0):
            raise ConsistencyError("All Dirty Objects Should Have Been Processed")
        logger.info("-- Updates Succesfully Processed --")

    def _process_update_response(self, resp, objects):
        """ Handles the server response from an update request """
        self._version = max(self._version, int(self._server.request.headers.get('last-modified-version', 0)))
        for obj in resp["success"].values():
            self._objects_by_key[obj].dirty = False
        for obj in resp["unchanged"].values():
            self._objects_by_key[obj].dirty = False
        self._checkpoint()
        createnew = []
        for idx in resp["failed"]:
            if (int(resp["failed"][idx].get("code", 0)) == 404 and re.match(".*doesn't exist", resp["failed"][idx].get("message", ""))):
                obj = objects[int(idx)]
                obj['version'] = 0
                createnew.append(obj)
            elif (int(resp["failed"][idx].get("code", 0)) == 412):
                raise StaleLocalData
            else:
                raise UpdateRejected("Updated Rejected with failed values", resp)
        if (len(createnew) > 0):
            logger.info("ERROR 404: Some objects didn't exist on server...trying to create them")
            if (isinstance(createnew[0], ZoteroCollection)):
                resp = self._server.create_collections(createnew, last_modified=int(self._server.request.headers.get('last-modified-version', 0)))
            else:
                resp = self._server.create_items(createnew, last_modified=int(self._server.request.headers.get('last-modified-version', 0)))
            self._process_update_response(resp, createnew)
        else:
            logger.info("\tUpdate Succeeded")
            self._version = max(self._version, int(self._server.request.headers.get('last-modified-version', 0)))
            return True

    def _server_update_items(self, items):
        """Takes a list of at most 50 items and updates them on server updating version info"""
        keylist = functools.reduce(lambda x, y: x + y['key'] + ',', items, "")
        keylist = keylist[:-1]  # drop final ,
        logger.info("\tUPDATE ITEM REQUEST: version: %s items: %s", self._version, keylist)
        payload = [i.modified_data for i in items]
        if (self.force_update):
            for i in payload:
                i['version'] = self._version
        resp = self._server.create_items(payload, last_modified=self._version)
        self._process_update_response(resp, payload)
        return True

    def _server_update_collections(self, cols):
        """Takes a list of at most 50 items and updates them on server updating version info"""
        keylist = functools.reduce(lambda x, y: x + y['key'] + ',', cols, "")
        keylist = keylist[:-1]  # drop final ,
        logger.info("\tUPDATE COLLECTION REQUEST: version: %s collections: %s", self._version, keylist)
        payload = [i.modified_data for i in cols]
        resp = self._server.create_collectionss(payload, last_modified=self._version)
        self._process_update_response(resp, payload)
        return True

    def _server_delete_items(self, items):
        """Takes a list of at most 50 items and deletes them on server updating version info"""
        keylist = functools.reduce(lambda x, y: x + y['key'] + ',', items, "")
        keylist = keylist[:-1]  # drop final ,
        logger.info("\tDELETE ITEM REQUEST: version: %s items: %s", self._version, keylist)
        rval = self._server.delete_item(items, last_modified=self._version)
        if (rval):
            self._version = max(self._version, int(self._server.request.headers.get('last-modified-version', 0)))
            self._next_version = 0
            for i in items:
                i.dirty = False
            self._checkpoint()
        else:
            raise Exception("Unreachable as delete_item currently returns true or throws exception")
        return True

    def _server_delete_collections(self, cols):
        """Takes a list of at most 50 collections and deletes them on server updating version info"""
        keylist = functools.reduce(lambda x, y: x + y['key'] + ',', cols, "")
        keylist = keylist[:-1]  # drop final ,
        logger.info("\tDELETE COLLECTION REQUEST: version: %s collections: %s", self._version, keylist)
        rval = self._server.delete_collection(items, last_modified=self._version)
        if (rval):
            self._version = max(self._version, int(self._server.request.headers.get('last-modified-version', 0)))
            self._next_version = 0
            for i in items:
                i.dirty = False
            self._checkpoint()
        else:
            raise Exception("Unreachable as delete_collection currently returns true or throws exception")
        return True

    def _push_deleted(self):
        logger.info("-- Deleting Objects on Server --")
        batch_deleted_collections = []
        batch_deleted_items = []
        cur_collections = []
        cur_items = []
        num_items = 0
        num_collections = 0
        for obj in self._deleted_objects:
            if (isinstance(obj, ZoteroItem)):
                num_items += 1
                cur_items.append(obj)
                if (len(cur_items) > 49):
                    batch_deleted_items.append(cur_items)
                    cur_items = []
            elif (isinstance(obj, ZoteroCollection)):
                num_collections += 1
                cur_collections.append(obj)
                if (len(cur_collections) > 49):
                    batch_deleted_collections.append(cur_collections)
                    cur_collections = []
            else:
                raise ConsistencyError("Only Collections and Items Supported Currently")
        if (len(cur_collections) > 0):
            batch_deleted_collections.append(cur_collections)
        if (len(cur_items) > 0):
            batch_deleted_items.append(cur_items)
        logger.info("\t %s Items in %s Batches and %s Collections in %s Batches Queued For Deletion",
                    num_items, len(batch_deleted_items), num_collections, len(batch_deleted_collections))
        for batch in batch_deleted_items:
            self._server_delete_items(batch)
        for batch in batch_deleted_collections:
            self._server_delete_collections(batch)
        if (len(self._deleted_objects) > 0):
            raise ConsistencyError("All Local Deletes Should Have Been Processed")
        logger.info("-- Local Deletions Succesfully Processed --")


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
        self._new_objects.discard(obj)
        self._deleted_objects.discard(obj)

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
        if (int(dict['data']['version']) < 0):
            raise InvalidData(dict['data'], "Version < 0")
        if ("itemType" not in dict['data']):
            raise InvalidData(dict['data'], "No ItemType")
        try:
            key = dict['data']['key']
            if (key in self._objects_by_key):
                self._objects_by_key[key].refresh(dict)
            else:
                item = ZoteroItem.factory(self, dict)
                if (isinstance(item, ZoteroAttachment) and "itemType" not in item._data):
                    raise ConsistencyError("How did attachment without itemtype get created?", item._data)
            self._itemkeys_for_refresh.discard(key)
            logger.debug("Removing key %s from _itemkeys_for_refresh", key)
            assert key not in self._itemkeys_for_refresh
        except KeyError as e:
            raise InvalidData(dict) from e

    def _recieve_collection(self, dict):
        """Called on any item recieved from self._server
        """
        if (int(dict['data']['version']) < 0):
            raise InvalidData(dict['data'], "Version < 0")
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
        if (not isinstance(obj, ZoteroAttachment)):
            ConsistencyError("Can't register non-attachment as attachment", obj._data)
        self._attachments.add(obj)
        if (obj.md5):
            if (obj.md5 in self._attachments_by_md5s):
                self._attachments_by_md5s[obj.md5].add(obj)
            else:
                self._attachments_by_md5s[obj.md5] = {obj}

    def _register_hash_change(self, obj, oldhash):
        if oldhash in self._attachments_by_md5s:
            self._attachments_by_md5s[oldhash].discard(obj)
        if (obj.md5):
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
        self.new = False
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
            logger.debug("Created empty object with key %s", arg)
            if (isinstance(self, ZoteroAttachment)):
                raise ConsistencyError("Attachments shouldn't get created empty", arg)
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
            if ((k in self._data and (((k == "collections" or k == "tags") and set(self._data[k]) == set(val)) or self._data[k] == val)) or
                ((not self._data.get(k, False)) and (not val))): 
                del self._changed_from[k]
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

    def dirty_key(self, key):
        if (key in ["children", "collections"]):
            return False
        if (self.dirty and key in self._changed_from and (self._data[key] or self._changed_from[key]) and
                self._data[key] != self._changed_from[key]):
            return True
        else:
            return False

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
            self.new = False
            self._changed_from = dict()
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

    @property
    def ancestors(self):
        if (self.parent):
            return self.parent.ancestors + [self.parent]
        else:
            return []

    @property
    def data(self):
        return copy.deepcopy(self._data)
    
    @property
    def modified_data(self):
        if self.new:
            return copy.deepcopy(self._data)
        modified = dict()
        modified["version"] = self._data["version"]
        modified["key"] = self._data["key"]
        if (self.dirty):
            for k in self._changed_from:
                modified[k] = copy.deepcopy(self._data[k])
        return modified


class ZoteroItem(ZoteroObject):
    """Common subclass for Documents and attachments"""

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
            super().__setitem__(pkey, pval)

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
        elif (pkey == "clean_title"):
            return self.clean_title
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
            p != "dateModified" and p != "accessDate" and p != "itemType" and p != "linkMode" and p != "itemType"))

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
    def clean_title(self):
        return re.sub('\W', '', self.title.casefold())

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
        """Should update the date_added value but zotero servers don't support editing this so does nothing"""

        return self.date_added
        # if (val is None):
        #     self._set_property("dateAdded", '')
        #     return None
        # if (isinstance(val, datetime.datetime)):
        #     dt = val
        # else:
        #     dt = dateutil.parser.parse(val)
        # self._set_property("dateAdded", dt.replace(tzinfo=None).isoformat("T") + "Z")
        # return dt

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
        try:
            return self._data["itemType"]
        except KeyError:
            raise ConsistencyError("Object lacking an itemType field", self._data)

    @property
    def url(self):
        return self._data.get("url", "")

    @url.setter
    def url(self, val):
        if (val != self.url):
            return (self._set_property("url", val))

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
        for c in val:
            if not c.creator:
                raise InvalidProperty("Can't have empty name for a creator")
        self._set_property("creators", [c.to_dict() for c in val])


class ZoteroDocument(ZoteroItem):
    """Represents a top level document in a zotero library"""

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

    @property
    def name(self):
        return self.title if self.title else ("#" + self.key)

    def __str__(self):
        return self.type + ": " + self.name

    def remove_dup_linked_file_children(self):
        dups = set()
        for link in (o for o in self.children if o.link_mode == "linked_file" and not o.missing):
            if link in dups:
                continue
            for olink in (o for o in self.children if o.link_mode == "linked_file" and not o.missing and o not in dups and not o == link):
                if link.identical_file(olink):
                    dups.add(olink)
                    logger.debug("Linked File %s has duplicate %s adding %s to dups", link.key, olink.key, olink.key)
        for link in dups:
            logger.debug("Marking linked file %s for deletion", link.key)
            link.delete()

    def remove_dup_child_files(self):
        used = set()
        dup_map = dict()
        for attach in self.children:
            if attach in used:
                continue
            else:
                dup_map[attach] = {attach}
                used.add(attach)
            for oattach in (o for o in self.children if o not in used):
                if attach.identical_file(oattach):
                    used.add(oattach)
                    dup_map[attach].add(oattach)
        for equiv in dup_map.values():
            best = None
            rank = 5
            for attach in equiv:
                if (rank == 0):
                    break
                if (best is None):
                    best = attach
                    continue
                if (isinstance(attach, ZoteroImportedFile) and not attach.missing and not attach.dirty_file):
                    if (isinstance(best, ZoteroLinkedUrl) or isinstance(best, ZoteroImportedUrl) or
                            not attach.local_missing or best.local_missing or best.missing or best.dirty_file or not isinstance(best, ZoteroImportedFile)):
                        best = attach
                        rank = 0
                    continue
                if (rank == 1):
                    continue
                if (isinstance(attach, ZoteroLinkedFile) and not attach.missing):
                    if (isinstance(best, ZoteroLinkedUrl) or isinstance(best, ZoteroImportedUrl) or
                            best.missing or (isinstance(best, ZoteroImportedFile) and best.dirty_file)):
                        best = attach
                        rank = 1
                    continue
                if (rank == 2):
                    continue
                if (isinstance(attach, ZoteroImportedFile) and not attach.local_missing):
                    if (isinstance(best, ZoteroLinkedUrl) or isinstance(best, ZoteroImportedUrl) or (best.local_missing and best.missing )):
                        best = attach
                        rank = 2
                    continue
                if (rank == 3):
                    continue
                if (isinstance(attach, ZoteroImportedUrl) and not attach.local_missing):
                    if (isinstance(best, ZoteroLinkedUrl) or (best.local_missing and best.missing)):
                        best = attach
                        rank = 3
            if (len(equiv) > 1):
                for attach in equiv:
                    logger.debug("Keeping child %s of class %s missing: %s, local_missing: %s, dirty_file %s", best.key, str(best.__class__.__name__), str(best.missing), str(best.local_missing), str(isinstance(best, ZoteroImported) and best.dirty_file))
                    if attach != best:
                        logger.debug("- Deleting child %s of class %s missing: %s, local_missing: %s, dirty_file %s", attach.key, str(attach.__class__.__name__), str(attach.missing), str(attach.local_missing), str(isinstance(attach, ZoteroImported) and attach.dirty_file))
                        attach.delete()


class ZoteroAttachment(ZoteroItem):

    _parent_key = "parentItem"   # override in inherited classes

    @subclassfactory
    def factory(cls, library, dict):
        try:
            if (dict["data"]["linkMode"] == "linked_file"):
                    return ZoteroLinkedFile
            elif (dict["data"]["linkMode"] == "linked_url"):
                    return ZoteroLinkedUrl
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
        if ("itemType" not in self._data):
            raise ConsistencyError("Attachments should never be created without itemTypes", self._data)
        self._md5 = None
        self._fulltext = None
        self._library._register_attachment(self)


    def _file_change(self, old=None, new=None, oldmd5=None):
        """Make any changes required when the attachment data changes"""
        newmd5 = None
        try:
            if (not new or not new.is_file()):
                    self._md5 = None
                    self._library._register_hash_change(self, oldmd5)
                    return False
            else:
                if(old and old.is_file()):                
                    if filecmp.cmp(str(old), str(new), shallow=False):
                        return False
                newmd5 = md5(new)
                if (self._md5 and newmd5 == self._md5):
                    return False
        except (OSError, PermissionError, FileNotFoundError):
            pass
        self._md5 = newmd5
        self._library._register_hash_change(self, oldmd5)
        return True

    def properties(self):
        yield "url"
        yield from super().properties()

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroAttachment")
        if (pkey == "itemType"):
            if (pval != "attachment"):
                raise InvalidProperty("Can't change attachment itemType")
            else:
                return
        else:
            super()._set_property(pkey, pval)

    def __getitem__(self, pkey):
        if (pkey == "md5"):
            return self._data.get("md5", "")
        if (pkey == "mtime"):
            return self._data.get("mtime", '')
        elif (pkey == "sha1"):
            return self._data.get("sha1", "")
        elif (pkey == "url"):
            return self.url
        elif (pkey == "filename"):
            return self.filename
        else:
            return super().__getitem__(pkey)

    def __setitem__(self, pkey, pval):
        if (pkey == "filename"):
            self.filename = pval
        else:
            return super().__setitem__(pkey, pval)

    @property
    def link_mode(self):
        return self._data["linkMode"]

    @property
    def md5(self):
        try:
            if self._md5:
                return self._md5
            if (self.path and self.path.is_file()):
                self._md5 = md5(self.path)
                return self._md5
        except (OSError, PermissionError, FileNotFoundError):
            pass
        return ''

    @property
    def url(self):
            return self._data.get("url", "")

    def __str__(self):
        return self.link_mode + ": " + self.name

    @property
    def local_missing(self):
        if (not self.path or not self.path.is_file()):
            return True
        else:
            return False

    @property
    def remote_md5(self):
        return None 

    def identical_file(self, other):
        if (self.md5 and other.md5 and self.md5 == other.md5):
            return True
        if (self.md5 and not other.md5 and other.remote_md5 == self.md5):
            return True
        if (other.md5 and not self.md5 and self.remote_md5 == other.md5):
            return True
        if (not other.md5 and not self.md5 and self.remote_md5 and self.remote_md5 == other.md5):
            return True
        if (self.path and self.path == other.path):
            return True
        return False

    def rename_file(self, newpath, operation='move', change_missing=False):
        """Renames associated file.  Operation can be move, link or copy.  Avoids overwriting by appending _i
        If change_missing updates path even if path is missing"""
        try:
            if (not isinstance(newpath, Path)):
                newpath = Path(newpath)
            if (self.local_missing):
                if (change_missing):
                    self.path = newpath
                return False
            i = 0
            suffix = ''
            stem = Path(newpath.name)
            while(stem.suffix):
                suffix = stem.suffix + suffix
                stem = Path(stem.stem)
            newpath_stem = str(stem)
            while(newpath.exists()):
                if (filecmp.cmp(str(self.path), str(newpath), shallow=False)):
                    logger.info("Identical file exists at destination")
                    self.path = newpath
                    return True
                newpath = newpath.with_name(newpath_stem + '_' + str(i) + suffix)
                i += 1
            logger.info("Performing %s on %s to %s", operation, self.path, newpath)
            if (operation == 'link'):
                os.link(str(self.path), str(newpath))
            elif (operation == 'copy'):
                shutil.copyfile(str(self.path), str(newpath))
            elif (operation == 'move'):
                shutil.move(str(self.path), str(newpath))
            if (newpath.is_file()):
                self.path = newpath
            else:
                raise ConsistencyError("WTF file wasn't created")
            return True
        except (PermissionError, OSError, IOError):
            logger.error("Rename file %s to %s failed with error", str(self.path), str(newpath))
            return False

    def move_file(self, newdir, operation='move', change_missing=False):
        """Like rename file but moves file to a new directory"""
        if (not isinstance(newdir, Path)):
            newdir = Path(newdir)
        if (not newdir.is_dir()):
            raise InvalidPath("move_file only accepts directories")
        newfile = newdir.joinpath(self.path.name)
        logger.info("Calling rename file with path %s", str(newfile))
        return self.rename_file(newfile, operation=operation, change_missing=change_missing)

    @property
    def inside_datadir(self):
        if (not self._library.datadir):
            raise InvalidPath("datadir unset")
        if (not self.path):
            return True
        try:
            path = self.path.relative_to(self._library.datadir)
            return True
        except ValueError:  # raised if can't relativize to self._library.datadir
            return False


class ZoteroLinkedFile(ZoteroAttachment):

    def __getitem__(self, pkey):
        if (pkey == 'path'):
            return self.path
        else:
            return super().__getitem__(pkey)

    def __setitem__(self, pkey, pval):
        if (pkey == "path"):
            self.path = pval
        else:
            super().__setitem__(pkey, pval)

    def __delitem__(self, pkey):
        if (pkey == 'path'):
            self.path = ''
        else:
            return super().__delitem__(pkey)

    def properties(self):
        yield "path"
        yield from super().properties()

    @property
    def dirty_file(self):
        return False

    @property
    def path(self):
        if (self._data.get('path', '')):
            pth = Path(self._data['path'])
            if (self._library.datadir and isinstance(self._library.datadir, Path)):
                pth = self._library.datadir.joinpath(pth)
            return pth
        else:
            return None

    @path.setter
    def path(self, val):
        orig = self.path
        origmd5 = self.md5
        if (val is None or val == ""):
            self._set_property("path", "")
        if (not isinstance(val, Path)):
            val = Path(val)
        path = val
        if (self._library.use_relative_paths and self._library.datadir):
            try:
                path = val.relative_to(self._library.datadir)
            except ValueError:
                pass
        self._set_property("path", str(path))
        self._file_change(old=orig, new=self.path, oldmd5=origmd5)

    @property
    def filename(self):
        if (self.path):
            return self.path.name
        else:
            return ''

    @filename.setter
    def filename(self, val):
        pval = val if isinstance(val, Path) else Path(val)
        self.path = self.path.parent.joinpath(pval)

    @property
    def missing(self):
        return self.local_missing

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroLinkedFile")
        if (pkey == "linkMode"):
            if (pval != "linked_file"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)

    @property
    def name(self):
        return str(self.path)

class ZoteroImported(ZoteroAttachment):
    """Parent class for ImportedFile and ImportedUrl"""

    def __init__(self, library, arg):
        self._local_file = None
        super().__init__(library, arg)
        self.bdiff_file = None
        if (self.path and self.path.is_file()):
            self._local_file = self.path
        elif (self.filename and self._library.zoterodir.joinpath(self.filename).is_file()):
            self._local_file = self._library.zoterodir.joinpath(self.filename)  # temp downloads saved here
        self._dirty_file = False
        self.dirty_file = (self.missing and not self.local_missing) or (self.md5 and self['md5'] and str(self.md5) != self['md5'])
        self._download = False
        self._remote_file = self.path if self.md5 == self['md5'] else None

    @property
    def dirty_file(self):
        return self._dirty_file

    @property
    def remote_md5(self):
        return self['md5']

    @dirty_file.setter
    def dirty_file(self, val):
        self._dirty_file = val
        if (val):
            self._library._mark_file_dirty(self)
        else:
            self._library._mark_file_clean(self)
            self._clear_bdiff()

    @property
    def download(self):
        return self._download

    @download.setter
    def dirty_file(self, val):
        self._download = val
        if (val):
            self._library.request_download(self)
        else:
            self._library.cancel_download(self)

    @property
    def local_file(self):
        return self._local_file

    def _build_bdiff():
        if (not self._remote_file or not self._remote_file.is_file() or not self.local_file or not self.local_file.is_file()):
            raise ConsistencyError("Can't create bdiff without two inputs")
        name = self._local_file.name + '.bsdiff-patch'
        newpath = self.zoterodir.joinpath(name)
        if newpath.exists():
            i = 0
            newpath = self.zoterodir.joinpath(name + '.' + str(i))
            while (newpath.exists()):
                i += 1
                newpath = newpath.with_suffix('.' + str(i))
        logger.info("Creating binary diff from %s to %s and saving in %s", str(self._remote_file), str(self.local_file), str(newpath))
        bsdiff4.file_diff(str(self._remote_file), str(self.local_file), str(newpath))
        self.bdiff_file = newpath

    def _clear_bdiff():
        if (self.bdiff_file and self.bdiff_file.is_file()):
            os.remove(str(self.bdiff_file))
        self.bdiff_file = None

    @local_file.setter
    def local_file(self, newfile):
        oldmd5 = self.md5
        self._file_change(old=self.local_file, new=self.path, oldmd5=oldmd5)

    def _file_change(self, old=None, new=None, oldmd5=None):
        if (not new or not new.is_file()):
            self.dirty_file = False
            self._download = False
        self._local_file = new
        if (super()._file_change(old=old, new=new, oldmd5=oldmd5)):  # ensures new and new.is_file() and new differs from old in some way
            if self.md5 == self['md5']:
                self._remote_file = self._local_file
                self.dirty_file = False
                self.download = False
            else:
                self.dirty_file = True
                if (not self.missing):
                    if (self._remote_file):
                        self._build_bdiff()
                    else:
                        self.download = True  # we need a copy of old file to update


    def properties(self):
        yield "filename"
        yield from super().properties()

    @property
    def missing(self):
        if (not self['md5'] and not self['sha1']):
            return True
        else:
            return False

    @property
    def path(self):
        if (self.local_file):
            return self.local_file
        if (self.filename):
            pth = Path(self.filename)
            if (self._library.datadir and isinstance(self._library.datadir, Path)):
                pth = self._library.datadir.joinpath(pth)
            return pth
        else:
            return None

    @path.setter
    def path(self, val):
        oldmd5 = self.md5
        if (val is None or val == ""):
            self.filename = ""
        if (not isinstance(val, Path)):
            val = Path(val)
        path = val
        if (self._library.use_relative_paths and self._library.datadir):
            try:
                path = val.relative_to(self._library.datadir)
            except ValueError:
                pass
        self.filename = str(path)
        self._file_change(old=self.local_file, new=self.path, oldmd5=oldmd5)

    @property
    def name(self):
        return self.filename

    @property
    def filename(self):
        return self._data.get("filename", "")

    @filename.setter
    def filename(self, val):
        return (self._set_property("filename", val))


class ZoteroImportedFile(ZoteroImported):


    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroImportedFile")
        if (pkey == "linkMode"):
            if (pval != "imported_file"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)


class ZoteroImportedUrl(ZoteroImported):

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroImportedFile")
        if (pkey == "linkMode"):
            if (pval != "imported_url"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)


class ZoteroLinkedUrl(ZoteroAttachment):

    def _set_property(self, pkey, pval):
        # logger.debug("called _set_property in ZoteroImportedFile")
        if (pkey == "linkMode"):
            if (pval != "linked_url"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)

    @property
    def inside_datadir(self):
        return True

    @property
    def filename(self):
        return None

    @filename.setter
    def filename(self, val):
        raise InvalidProperty("linked_url can't accept filename")

    @property
    def local_file(self):
        return None

    @property
    def path(self):
        return None

    @path.setter
    def path(self, val):
        pass
        # raise InvalidProperty("linked_url can't accept path values")

    @property
    def name(self):
        return self.url

    @property
    def missing(self):
        if (not self.url):
            return True
        else:
            return False

    @property
    def local_missing(self):
        return True


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
        yield "size"
        yield from super().properties()

    def __getitem__(self, pkey):
        if (pkey == "size"):
            return self.size
        else:
            return super().__getitem__(pkey)

    @property
    def size(self):
        return len(self.members)

    @property
    def name(self):
        return self._data.get("name", "")

    @name.setter
    def name(self, val):
        return (self._set_property("name", val))

    def __str__(self):
        return "<" + (self.name if self.name else ("#" + self.key)) + ">"
