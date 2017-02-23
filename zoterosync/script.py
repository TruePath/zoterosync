import os
import click
from zoterosync.library import ZoteroLibrary
from zoterosync.library import ZoteroObject
from zoterosync.library import ZoteroDocument
from zoterosync.library import ZoteroAttachment
from zoterosync.library import ZoteroCollection
from zoterosync.library import Creator
from pathlib import Path
import json
import pickle
from shutil import copyfile
from zoterosync.merge import SimpleZDocMerger
import logging
import re

logger = logging.getLogger('zoterosync.cli')


def style_document(doc, key_color='blue', value_color='white', type_color='yellow', background_color='black'):
    output = click.style("@" + doc['itemType'] + "{", fg=type_color, bg=background_color,  bold=True, reset=False)
    output += click.style(doc["key"] + "\n", fg=value_color, bold=True, reset=False)
    for key in doc:
        if (key != "itemType" and doc[key]):
            output += click.style("\t" + key + " = {", fg=key_color, reset=False)
            sep = ""
            if (isinstance(doc[key], list)):
                output += click.style("[", fg=value_color, reset=False, bold=True)
                for member in doc[key]:
                    output += sep + click.style(str(member), fg=value_color, reset=False)
                    sep = ", "
                output += click.style("]", fg=value_color, reset=False, bold=True)
            elif (isinstance(doc[key], set)):
                for member in doc[key]:
                    output += sep + click.style(str(member), fg=value_color, reset=False)
                    sep = ", "
            else:
                output += click.style(str(doc[key]), fg=value_color, reset=False)
            output += click.style("}\n", fg=key_color, reset=False)
    output += click.style("}\n", fg=type_color, bold=True, reset=True)
    return output


def style_merge(merge):
    m = merge.copy()
    m["key"] = "MERGE"
    return style_document(m, key_color='magenta', type_color='red')


def style_doc_listing(doc, long=False, full=False, key_color='white', value_color='blue', type_color='yellow',
                      modified_color='magenta', background_color='black'):
    if (long or full):
        display_keys = ["title", "creators", "collections", "tags", "children"]
        if (full):
            display_keys = iter(doc)
        output = click.style("@" + doc['itemType'] + "{", fg=type_color, bg=background_color,  bold=True, reset=False)
        if (doc.dirty):
            output += click.style(doc["key"] + " (modified)\n", fg=modified_color, bold=True, reset=False)
        else:
            output += click.style(doc["key"] + "\n", fg=value_color, bold=True, reset=False)
        for key in display_keys:
            if (doc[key]):
                output += click.style("\t" + key, fg=(modified_color if doc.dirty_key(key) else key_color), reset=False)
                output += click.style(" = {", fg=key_color, reset=False)
                sep = ""
                if (isinstance(doc[key], list)):
                    output += click.style("[", fg=value_color, reset=False, bold=True)
                    for member in doc[key]:
                        output += sep + click.style(str(member), fg=value_color, reset=False)
                        sep = ", "
                    output += click.style("]", fg=value_color, reset=False, bold=True)
                elif (isinstance(doc[key], set)):
                    for member in doc[key]:
                        output += sep + click.style(str(member), fg=value_color, reset=False)
                        sep = ", "
                else:
                    output += click.style(str(doc[key]), fg=value_color, reset=False)
                output += click.style("}\n", fg=key_color, reset=False)
        output += click.style("}\n", fg=type_color, bold=True, reset=True)
    else:
        output = click.style(doc['key'], fg=(modified_color if doc.dirty else key_color), bg=background_color,  bold=False, reset=False)
        output += click.style(" -- ", fg=value_color,  bold=True, reset=False)
        output += click.style(doc['itemType'], fg=type_color, bold=False, reset=False)
        output += click.style(" -- ", fg=value_color,  bold=True, reset=False)
        output += click.style(doc["title"], fg=value_color, bold=False, reset=True)
    return output


class ZoteroLibraryStore(object):

    def __init__(self, conf_path=Path(os.path.abspath('.zoterosync_config')), library_path=None, num_backups=0):
        self.library = None
        self.user = None
        self.apikey = None
        self.force = False
        self.dangerous = False
        self.dirty = False
        self._library_path = library_path
        self._conf_path = conf_path
        self._num_backups = num_backups
        self.load()

    def load(self):
        self.load_config()
        self.load_library()

    def pull(self):
        self.library.pull()
        self.dirty = True

    def load_config(self, conf_path=None):
        conf_path = self._conf_path if conf_path is None else conf_path
        try:
            with conf_path.open(mode='r') as conf_file:
                config = json.load(conf_file)
                self.user = config['user']
                self.apikey = config['apikey']
                self._num_backups = config.get('backups', self._num_backups)
        except (IOError, FileNotFoundError, PermissionError, KeyError):
            pass

    def save(self):
        if self.write_library():
            return self.write_config()
        return False

    def write_config(self, conf_path=None):
        if conf_path is None:
            conf_path = self._conf_path
        if (self.user is None or self.apikey is None):
            raise Exception("")
        config = dict(user=self.user, apikey=self.apikey, backups=self._num_backups)
        with conf_path.open(mode='w', encoding='utf8') as conf_file:
            json.dump(config, conf_file)

    def init_library(self):
        self.library = ZoteroLibrary.factory(self.user, self.apikey)
        self.dirty = True
        self.dangerous = True
        logger.info("Initialized Library")

    def write_library(self, dest=None):
        if (self.dirty is not True):
            return True
        if (self.library is None):
            raise Exception("Can't save non-existant library")
        if (self.dangerous and not self.force):
            click.echo("Pass the --force option to enable dangerous changes!")
            raise Exception("Can't save non-existant library")
        if (dest is None):
            dest = self._library_path
        with dest.open(mode='wb') as lib_file:
            pickle.dump(self.library, lib_file)
        return True

    def load_library(self):
        try:
            with self._library_path.open(mode='rb') as lib_file:
                self.library = pickle.load(lib_file)
        except (IOError, FileNotFoundError, PermissionError):
            return False
        return True

    def backup_library(self):
        if (self._library_path is None):
            raise Exception("Must specify library path and backup to backup")
        self._num_backups += 1
        try:
            copyfile(str(self._library_path), str(self._library_path.with_suffix('.backup-' + str(self._num_backups))))
        except (IOError, FileNotFoundError, PermissionError) as e:
            self._num_backups -= 1
            raise Exception("Backup Failed") from e
        else:
            self.write_config()

    def revert_library(self):
        if (self._library_path is None or self._num_backups == 0):
            raise Exception("Must specify library path and backup to revert")
        try:
            copyfile(str(self._library_path.with_suffix('.backup-' + str(self._num_backups))), str(self._library_path))
            os.remove(str(self._library_path.with_suffix('.backup-' + str(self._num_backups))))
        except (IOError, FileNotFoundError, PermissionError) as e:
            raise Exception("Restore Failed") from e
        else:
            self._num_backups -= 1
            self.write_config()

    def discard_backup(self):
        if (self._num_backups == 0):
            raise Exception("No backup to discard")
        try:
            os.remove(str(self._library_path.with_suffix('.backup-' + str(self._num_backups))))
        except (IOError, FileNotFoundError, PermissionError) as e:
            raise Exception("Discard Failed") from e
        else:
            self._num_backups -= 1
            self.write_config()

    def clear_backups(self):
        while (self._num_backups):
            self.discard_backup()

    def term_merger(self, merger):
        merges = iter(merger.interactive_merge())
        try:
            proposed = next(merges)
            auto_merge = False
            while True:
                self.dirty = True
                output = ""
                result = proposed[1]
                mtuple = proposed[0]
                c = ''
                if (auto_merge is False):
                    output += click.style("Proposed Duplicates:\n\n", fg="white", bg="black", bold=True, reset=False)
                    for d in mtuple:
                        output += style_document(d)
                        output += click.style("\n-----------------\n", fg="white", bg="black", bold=True, reset=False)
                    output += click.style("Proposed Merge:\n\n", fg="white", bg="black", bold=True, reset=False)
                    output += style_merge(result)
                    output += click.style("\n-----------------\n", fg="white", bg="black", bold=True, reset=False)
                    output += click.style("Accept Merge [Yes/No/All/Quit]", fg="white", bg="black", bold=True, reset=True)
                    click.echo(output, nl=False)
                    while (c not in ('y', 'n', 'a', 'q')):
                        c = click.getchar().casefold()
                response = False
                if (c == 'a'):
                    auto_merge = True
                if (auto_merge is True or c == 'y'):
                    response = result
                if (c == 'q'):
                    break
                proposed = merges.send(response)
        except StopIteration:
            pass
        click.echo("Finished Merge!!")

    def match_objects(self, object_type, modified={True, False}, deleted=False, regexps=None):
        if (regexps is None):
            regexps = dict()
        objs = set()
        if deleted:
            objs = {d for d in self.library.deleted_objects if isinstance(d, object_type)}
        else:
            if (object_type == ZoteroDocument):
                objs = self.library.documents
            elif (object_type == ZoteroAttachment):
                objs = self.library.attachments
            elif (object_type == ZoteroCollection):
                objs = self.library.collections
        objs = {d for d in objs if d.dirty in modified}

        def filter_func(x):
            if (isinstance(x, Creator)):
                return rex.match(x.type + "\n" + x.firstname + " " + x.lastname)
            elif (isinstance(x, ZoteroCollection)):
                if (rex.match(x.name) or rex.match("#" + x.key)):
                    return True
            elif (isinstance(x, ZoteroAttachment)):
                if (rex.match(x.link_mode + "\n" + x.name) or rex.match("#" + x.key)):
                    return True
            else:
                return rex.match(str(x))

        def match_element(container):
            return next(filter(filter_func, container), False)

        for pkey in regexps:
            rex = re.compile(regexps[pkey])
            objs = {d for d in objs if (((isinstance(d[pkey], list) or isinstance(d[pkey], set)) and match_element(d[pkey])) or 
                                        rex.match(str(d[pkey])))}
        return objs

    def list_docs(self, long=False, modified={True, False}, deleted=False, sortby=None, reverse=False, full=False, regexps=None):
        displayed = 0
        docs = self.match_objects(ZoteroDocument, modified=modified, deleted=deleted, regexps=regexps)
        output = dict()
        for doc in docs:
            if (doc.dirty in modified):
                displayed += 1
                order_key = doc[sortby] if sortby else displayed
                output[order_key] = output.get(order_key, "") + style_doc_listing(doc, long=long, full=full) + "\n"
        out = ""
        for i in sorted(output.keys(), reverse=reverse):
            out += output[i]
        click.echo(out)
        if deleted:
            click.secho("Displayed {} deleted docs from library with {} non-deleted docs".format(displayed, len(self.library.documents)), bold=True)
        else:
            click.secho("Displayed {} docs / {} total (non-deleted) docs".format(displayed, len(self.library.documents)), bold=True)


@click.group()
@click.option('--config', type=click.Path(), default='.zoterosync_config')
@click.option('--library', type=click.Path(), default='.zoterosync_library')
@click.pass_context
def cli(ctx, config, library):
    conf_path = Path(os.path.abspath(config))
    library_path = Path(os.path.abspath(library))
    ctx.obj = ZoteroLibraryStore(conf_path=conf_path, library_path=library_path)


@cli.command()
@click.option('--user', type=int)
@click.option('--key')
@click.pass_obj
def init(store, user, key):
    store.user = user
    store.apikey = key
    store.force = True
    store.clear_backups()
    store.init_library()
    store.save()


@cli.command()
@click.pass_obj
def pull(store):
    store.load()
    store.pull()
    store.save()


def set_force(ctx, param, value):
    ctx.obj.force = value


@cli.command()
@click.option('--force', is_flag=True, callback=set_force, expose_value=False)
@click.pass_obj
def reset(store):
    store.init_library()
    store.save()


@cli.command()
@click.pass_obj
def revert(store):
    store.revert_library()


@cli.command()
@click.pass_obj
def backup(store):
    store.backup_library()


@cli.command()
@click.pass_obj
def dedup(store):
    store.load()
    merger = SimpleZDocMerger(store.library)
    store.term_merger(merger)
    store.save()


@cli.command()
@click.option('--title', '-t', default=None, help="regex matching against document['title']")
@click.option('--key', '-k', default=None, help="regex matching against document['key']")
@click.option('--creator', default=None, help='regex matching against creator strings of form: type\\nfirstname lastname')
@click.option('--child', default=None, help="regex matching against document['children'] where attachment strings have form: " +
                                                "link_mode\\nname where name is filename if present or #key")
@click.option('--itemtype', '--itemType', '-i', default=None, help="regex matching against document['itemType']")
@click.option('--collection', '-c', default=None, help="regex matching against document['collections'] try against both name and #key")
@click.option('--tag', default=None, help="regex matching against document['tags']")
@click.option('--sort', '-s', type=click.Choice(['t', 'T', 'k', 'K', 'i', 'I', 'c', 'C', 'N']),
              help="Sort by title, key, itemType, cleaned_title (cleaned lowercase title) by passing first letter.  Capitalize to reverse. 'N' reverse without sorting.")
@click.option('--deleted', '-d', is_flag=True)
@click.option('--full', '-f', is_flag=True)
@click.option('--long', '-l', is_flag=True)
@click.option('--modified', '-m', 'show_modified', flag_value={True})
@click.option('--unmodified', '-M', 'show_modified', flag_value={False})
@click.option('--any-modified', 'show_modified', flag_value={True, False}, default=True)
@click.pass_obj
def lsdoc(store, long, show_modified, deleted, sort, full, title, key, creator, child, itemtype, collection, tag):
    sortby = None
    reverse = False
    regex = dict()
    if (title is not None):
        regex["title"] = title
    if (key is not None):
        regex["key"] = key
    if (creator is not None):
        regex["creators"] = creator
    if (child is not None):
        regex["children"] = child
    if (itemtype is not None):
        regex["itemType"] = itemtype
    if (collection is not None):
        regex["collections"] = collection
    if (tag is not None):
        regex["tags"] = tag
    if (sort):
        if (sort.casefold() == 't'):
            sortby = "title"
        elif (sort.casefold() == 'k'):
            sortby = "key"
        elif (sort.casefold() == 'i'):
            sortby = "itemType"
        elif (sort.casefold() == 'c'):
            sortby = "clean_title"
        if (sort.isupper()):
            reverse = True
    store.list_docs(long=long, modified=show_modified, deleted=deleted, sortby=sortby, reverse=reverse, full=full, regexps=regex)
