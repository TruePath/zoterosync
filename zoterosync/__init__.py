from pyzotero import zotero
import re
import random
import copy
import logging
import pickle
import datetime
import dateutil.parser

# create logger
logger = logging.getLogger('zotero_sync')
logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)


# SaveFile = "~/zotero.pkl"


# items = zot.top(limit=5)
# col = zot.collections()
# we've retrieved the latest five top-level items in our library
# we can print each item's item type and ID
# for item in items:
# print('Item: {0} | Key: {1}'.format(item['data']['itemType'], item['data']['key']))


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


class Person(object):

    def __init__(self, last, first):
        self.lastname = last
        self.firstname = first

    def same(self, other):
        norm_self_last = re.sub('[\s-_\+:~*&().,]', '', self.lastname.lower())
        norm_other_last = re.sub('[\s-_\+:~*&().,]', '', other.lastname.lower())
        if (norm_self_last == norm_other_last):
            self_first = re.sub('[-_\+:*&()]', '', self.firstname.strip().lower())
            other_first = re.sub('[-_\+:*&()]', '', self.firstname.strip().lower())
            if (len(self_first) == 0 or len(other_first) == 0):
                return True
            self_first_start = re.split('[\s.,_~]+', self_first)[0]
            other_first_start = re.split('[\s.,_~]+', other_first)[0]
            if (len(self_first_start) == 2 and self_first_start.isupper()):  # heuristic for initials e.g. PG Odifreddi
                self_first_start = self_first_start[0]  # Skip 3 initials like WVO b/c too many names are 3 letters
            if (len(other_first_start) == 2 and other_first_start.isupper()):
                other_first_start = other_first_start[0]
            s = self_first_start.lower()
            o = other_first_start.lower()
            if (s.startswith(o) or o.self_first_start.startswith(s)):
                return True
        return False

    def __eq__(self, other):
        return (self.lastname == other.lastname and self.firstname == other.firstname)

    @property
    def fullname(self):
        return "{0} {1}".format(self.firstname, self.lastname)

    def copy(self):
        return Person(self.lastname, self.firstname)


class Creator(object):
    """ Captures the creator object
    """
    def __init__(self, d):
        self.type = d["creatorType"]
        self.creator = Person(d['lastName'], d['firstName'])

    def __eq__(self, other):
        return (self.creator == other.creator and self.type == other.type)

    def same(self, other):
        return self.creator.same(other.creator)

    def to_dict(self):
        return dict(creatorType=self.type, lastName=self.lastname, firstName=self.firstname)

    def copy(self):
        return Creator(self.to_dict())

    def find_same(self, list):
        for i in list:
            if (self.same(i)):
                return i
        return None

    @property
    def lastname(self):
        return self.creator.lastname

    @lastname.setter
    def lastname(self, val):
        self.creator.lastname = val

    @property
    def firstname(self):
        return self.creator.firstname

    @firstname.setter
    def firstname(self, val):
        self.creator.firstname = val


class ZoteroLibrary(object):
    """ Captures the cached library
    """
    AllowedKeyChars = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"

    def __init__(self, userid, apikey):
        self._zot = zotero.Zotero(userid, "user", apikey)
        self._documents_by_name = dict()
        self._attachments_by_md5s = dict()
        self.item_types = ["artwork", "audioRecording", "bill", "blogPost", "book", "bookSection", "case",
                           "computerProgram", "conferencePaper", "dictionaryEntry", "document", "email",
                           "encyclopediaArticle", "film", "forumPost", "hearing", "instantMessage", "interview",
                           "journalArticle", "letter", "magazineArticle", "manuscript", "map", "newspaperArticle",
                           "note", "patent", "podcast", "presentation", "radioBroadcast", "report", "statute",
                           "tvBroadcast", "thesis", "videoRecording", "webpage"]
        self._collections = set()
        self._documents = set()
        self._attachments = set()
        self._objects_by_key = dict()
        self._dirty_objects = set()
        self._deleted_objects = set()
        self._tags = dict()

    def _update_item_types(self):
        self.item_types = [d["itemType"] for d in self._zot.item_types()]

    def mark_dirty(self, obj):
        self._dirty_objects.add(obj)

    def mark_clean(self, obj):
        self._dirty_objects.remove(obj)

    def mark_for_deletion(self, obj):
        if (not obj.deleted):
            del self._objects_by_key[obj.key]
            self._dirty_objects.remove(obj)
            if (isinstance(obj, ZoteroCollection)):
                for item in obj.members:
                    item.remove_collection(obj)
                self._collections.remove(obj)
                self._deleted_objects.add(obj)
            elif (isinstance(obj, ZoteroDocument)):
                key = self.build_name_key(obj.title)
                if (key in self._documents_by_name):
                    del self._documents_by_name[key]
                self._documents.remove(obj)
            elif (isinstance(obj, ZoteroAttachment)):
                md5 = obj.md5
                if (md5 in self._attachments_by_md5s):
                    del self._attachments_by_md5s[md5]
                self._attachments.remove(obj)
            self._deleted_objects.add(obj)

    def new_key(self):
        newkey = ""
        while(newkey == "" or newkey in self.items):
            newkey = ""
            for i in range(8):
                newkey += random.choice(ZoteroLibrary.AllowedKeyChars)
        return newkey

    @staticmethod
    def build_name_key(string):
        return re.sub('[\s-_\+:~*&()]', '', string.lower())

    def get_obj_by_tag(self, tag):
        if (tag in self._objects_by_tag):
            return self._objects_by_tag[tag]
        else:
            return None

    def _register_parent(self, obj, pkey):
        if (obj.parent is not None):
            obj.parent.children.remove(obj)
        if (pkey is not None and pkey != "false"):
            if (isinstance(pkey, ZoteroObject)):
                pkey = pkey.key
            if (pkey not in self._objects_by_key):
                if (isinstance(obj, ZoteroItem)):
                    parent = ZoteroDocument(self, pkey)
                    self._objects_by_key[pkey] = parent
                    self._documents.add(parent)
                elif (isinstance(obj, ZoteroCollection)):
                    parent = ZoteroCollection(self, pkey)
                    self._objects_by_key[pkey] = parent
                    self._collections.add(parent)
            else:
                parent = self._objects_by_key[pkey]
            parent.children.add(obj)
            return parent
        else:
            return None

    def _register_into_collection(self, obj, ckey):
        if (isinstance(ckey, ZoteroObject)):
            ckey = ckey.key
        logger.debug("called _register_into_collection in ZoteroLibrary with obj.key=%s and " +
                     "collection key=%s", obj.key, ckey)
        if (ckey not in self._objects_by_key):
            col = ZoteroCollection(self, ckey)
            self._objects_by_key[ckey] = col
            self._collections.add(col)
        else:
            col = self._objects_by_key[ckey]
        col.members.add(obj)
        return col

    def _register_outof_collection(self, obj, ckey):
        if (isinstance(ckey, ZoteroObject)):
            col = ckey
        else:
            col = self._objects_by_key[ckey]
        col.members.remove(obj)
        return col

    def _register_into_tag(self, obj, tag):
        if (tag not in self._tags):
            self._tags[tag] = set()
        self._tags[tag].add(obj)
        return self._tags[tag]

    def _register_outof_tag(self, obj, tag):
        if (tag in self._tags):
            self._tags[tag].remove(obj)
            if (len(self._tags[tag]) == 0):
                del self._tags[tag]


class ZoteroObject(object):

    _parent_key = None   # override in inherited classes

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
        logger.debug("called _register_property in ZoteroObject with pkey=%s and pval=%s", pkey, pval)
        if (isinstance(pval, ZoteroObject)):
            pval = pval.key
        self._data[pkey] = pval
        if (pkey == self._parent_key):
            self._register_parent(pval)

    def _set_property(self, pkey, pval):  # Deals with underlying representation
        logger.debug("called _set_property in ZoteroObject")
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
                elif (pkey == 'collections' or pkey == 'tags' or pkey == 'creators'):
                    self._changed_from[pkey] = list()
                elif (pkey == 'relations'):
                    self._changed_from[pkey] = dict()
                else:
                    self._changed_from[pkey] = None
            if (pkey in self._data):
                if (pkey == 'relations'):
                    self._data[pkey] = dict()
                elif (pkey == 'collections' or pkey == 'tags' or pkey == 'creators'):
                    self._data[pkey] = list()
                else:
                    self._data[pkey] = ''
            if (pkey == self._parent_key):
                self._register_parent(None)
                self._data[self._parent_key] = "false"

    def update(self, dict):
        for k in dict.keys():
            if (k != "key" and k != "version"):
                self._set_property(k, dict[k])

    def __iter__(self):
        return self.properties().__iter__()

    def properties(self):
        yield "children"
        if (self._parent_key is not None):
            yield "parent"
        yield from (p for p in self._data if (p != self._parent_key and p != "key" and p != "version"))

    def _register_parent(self, ptag):
        self._parent = self._library._register_parent(self, ptag)

    def delete(self):
        self._deleted = True
        self._library.mark_for_deletion(self)

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
        logger.debug("called dirty setter in ZoteroObject")
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


class ZoteroItem(ZoteroObject):

    def __init__(self, library, arg):
        self._collections = set()
        super().__init__(library, arg)

    def _register_property(self, pkey, pval):
        logger.debug("called _register_property in ZoteroItem with pkey=%s and pval=%s", pkey, pval)
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

    def properties(self):
        yield "dateModified"
        yield from (p for p in super().properties() if (p != "dateModified" and p != "itemType" and p != "linkMode"))

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, val):
        logger.debug("called dirty setter in ZoteroItem")
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
        newcols = set()
        for c in val:
            if (isinstance(c, ZoteroCollection)):
                newcols.add(c.key)
            else:
                newcols.add(c)
        self._set_property("collections", newcols)

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

    def _set_property(self, pkey, pval):
        logger.debug("called _set_property in ZoteroDocument with pkey=%s and pval=%s", pkey, pval)
        if (pkey == "itemType" and pval not in self._library.item_types):
            raise InvalidProperty("Tried to set itemType to {}".format(pval))
        super()._set_property(pkey, pval)


class ZoteroAttachment(ZoteroItem):

    _parent_key = "parentItem"   # override in inherited classes

    def _set_property(self, pkey, pval):
        logger.debug("called _set_property in ZoteroAttachment")
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


class ZoteroLinkedFile(ZoteroAttachment):

    def _set_property(self, pkey, pval):
        logger.debug("called _set_property in ZoteroLinkedFile")
        if (pkey == "linkMode"):
            if (pval != "linked_file"):
                raise InvalidProperty("Can't change attachment linkMode")
            else:
                return
        else:
            super()._set_property(pkey, pval)


class ZoteroImportedFile(ZoteroAttachment):

    def _set_property(self, pkey, pval):
        logger.debug("called _set_property in ZoteroImportedFile")
        if (pkey == "linkMode"):
            if (pval != "imported_file"):
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


# try:
#     pkl = open(SaveFile, "rb")
#     library = pickle.load(pkl)
# except IOError:
#     zot = zotero.Zotero(3661336, "user", "NnfdXD5dmXkCJcGUBDgJTEV9")
#     library = ZoteroLibrary(zot)
# finally:
#     pkl.close()