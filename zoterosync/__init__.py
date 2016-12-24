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


class ZoteroLibrary(object):

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

    def register_parent(self, obj, pkey):
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
        if (ckey not in self._objects_by_key):
            col = ZoteroCollection(self, ckey)
            self._objects_by_key[ckey] = col
            self._collections.add(col)
        else:
            col = self._objects_by_key[ckey]
        col.members.add(col)
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
        self.library = library
        self._dirty = False
        self._deleted = False
        self._parent = None
        self._changed_from = dict()
        if (type(arg) == dict):
            try:
                data = arg["data"]
                self.data = dict(key=data["key"], version=data["version"])
                for k in (q for q in data if (q != "key" and q != "version")):
                    self._register_property(k, data[k])
            except KeyError as e:
                raise InvalidData(dict) from e
        else:
            self.data = dict(key=arg, version=-1)


    def refresh(self, dict):
        try:
            if (self.version < dict["data"]["version"]):
                raise ConsistencyError("Tried to update an item with version: " + self.version +
                                       " with data versioned at: " + dict["data"]["version"])
            self.data["version"] = dict["data"]["version"]
            for k in (q for q in dict["data"] if (q != "key" and q != "version")):
                self._refresh_property(k, dict["data"][k])
            if (self._parent_key in self.data and self._parent_key not in dict["data"]):
                self._refresh_property(self._parent_key, None)
        except KeyError as e:
            raise InvalidData(dict) from e

    def _refresh_property(self, k, val):
        if (k not in self._changed_from):
            self._register_property(k, val)
        else:
            self._changed_from[k] = val

    def _register_property(self, pkey, pval):
        if (isinstance(pval, ZoteroObject)):
            pval = pval.key
        self.data[pkey] = pval
        if (pkey == self._parent_key):
            self._register_parent(pval)

    def set_property(self, pkey, pval):
        if (pkey == "dateModified" or pkey == 'version'):
            return
        self.dirty = True
        if (pval is None):
            self.delete_property(pkey)
        else:
            if (pkey in self.data):
                fromval = self.data[pkey]
            else:
                fromval = None
            self._register_property(pkey, pval)
            if (pkey not in self._changed_from):
                self._changed_from[pkey] = fromval

    def get_property(self, pkey):
        if (pkey in self.data):
            return self.data[pkey]
        else:
            return None

    def delete_property(self, pkey):
        self.dirty = True
        if (pkey not in self._changed_from):
            if (pkey in self.data):
                self._changed_from[pkey] = self.data[pkey]
            else:
                self._changed_from[pkey] = None
        if (pkey in self.data):
            if (pkey == 'relations'):
                self.data[pkey] = dict()
            elif (pkey == 'collections' or pkey == 'tags' or pkey == 'creators'):
                self.data[pkey] = list()
            else:
                self.data[pkey] = ''
        if (pkey == self._parent_key):
            self._register_parent(None)
            self.data[self._parent_key] = "false"

    def update(self, dict):
        for k in dict.keys():
            if (k != "key" and k != "version"):
                self.set_property(k, dict[k])

    def _register_parent(self, ptag):
        self._parent = self.library.register_parent(self, ptag)

    def delete(self):
        self._deleted = True
        self.library.mark_for_deletion(self)

    @property
    def version(self):
        try:
            return self.data["version"]
        except KeyError as e:
            raise InvalidData(dict) from e

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, val):
        if (val is True):
            self._dirty = True
            self.library.mark_dirty(self)
        else:
            self._dirty = False
            self.library.mark_clean(self)

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
        self.set_property(self._parent_key, pkey)

    @parent.deleter
    def parent(self):
        self.delete_property(self._parent_key)

    @property
    def children(self):
        return self._children

    @property
    def key(self):
        return self.data["key"]


class ZoteroItem(ZoteroObject):

    def __init__(self, library, arg):
        self._collections = set()
        super().__init__(library, arg)

    def _register_property(self, pkey, pval):
        if (pkey == "collections"):
            for c in self._collections:
                self.library._register_outof_collection(self, c)
            self._collections = {self.library._register_into_collection(self, ckey)
                                 for ckey in self.data["collections"]}
        if (pkey == "tags"):
            for tag in self.tags:
                self.library._register_outof_tag(self, tag)
            for tag in {t["tag"] for t in pval}:
                self.library._register_into_tag(self, tag)
        super()._register_property(pkey, pval)

    def _refresh_property(self, pkey, pval):
        if (pkey == "collections"):
            update_keys = {ckey for ckey in pval}
            if ("collections" in self._changed_from):
                orig_keys = {ckey for ckey in self._changed_from["collections"]}
                if ("collections" in self.data):
                    cur_cols = {ckey for ckey in self.data["collections"]}
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
                if ("tags" in self.data):
                    cur_tags = {t["tag"] for t in self.data["tags"]}
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
                self.data["dateModified"] = pval
            else:
                self.data["dateModified"] = max(cur_mod, dateutil.parser.parse(pval)
                                                ).replace(tzinfo=None).isoformat("T") + "Z"
        else:
            super()._refresh_property(pkey, pval)

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, val):
        if (val is True):
            self._dirty = True
            self.library.mark_dirty(self)
            self.data["dateModified"] = datetime.datetime.utcnow().isoformat("T") + "Z"
        else:
            self._dirty = False
            self.library.mark_clean(self)

    @property
    def collections(self):
        return self._collections

    @property
    def tags(self):
        if ("tags" in self.data):
            return {t["tag"] for t in self.data["tags"]}
        else:
            return set()

    @property
    def title(self):
        return self.get_property('title')

    @title.setter
    def title(self, val):
        self.set_property("title", val)

    @property
    def date_modified(self):
        if ("dateModified" in self.data):
            return dateutil.parser.parse(self.data["dateModified"])
        else:
            return None

    @property
    def date_added(self):
        if ("dateAdded" in self.data):
            return dateutil.parser.parse(self.data["dateAdded"])
        else:
            return None

    @date_added.setter
    def date_added(self, val):
        if (val is None):
            self.set_property("dateAdded", '')
            return None
        if (isinstance(val, datetime.datetime)):
            dt = val
        else:
            dt = dateutil.parser.parse(val)
        self.set_property("dateAdded", dt.replace(tzinfo=None).isoformat("T") + "Z")
        return dt

    @property
    def date(self):
        if ("date" in self.data):
            return self.data["date"]
        else:
            return None

    @date.setter
    def date(self, val):
        self.set_property("date", val)


class ZoteroDocument(ZoteroItem):

    @property
    def type(self):
        return self.get_property("itemType")

    @type.setter
    def type(self, val):
        return self.set_property("itemType", val)

    def _register_property(self, pkey, pval):
        if (pkey == "itemType"):
            if (pval not in self.library.item_types):
                raise InvalidProperty("Tried to set itemType to {}".format(pval))
        super()._register_property(pkey, pval)


class ZoteroAttachment(ZoteroItem):

    _parent_key = "parentItem"   # override in inherited classes

    def _register_property(self, pkey, pval):
        if (pkey == "itemType"):
            if (pval != "attachment"):
                raise InvalidProperty("Can't change attachment itemType")
        super()._register_property(pkey, pval)


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
