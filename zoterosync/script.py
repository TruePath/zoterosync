import os
import click
from zoterosync.library import ZoteroLibrary
from pathlib import Path
import json
import pickle
from shutil import copyfile
from zoterosync.merge import SimpleZDocMerger
import logging

logger = logging.getLogger('zoterosync.cli')


def style_document(doc, key_color='blue', value_color='white', type_color='yellow', background_color='black'):
    output = click.style("@" + doc['itemType'] + "{" + doc["key"] + "\n\n",
                         fg=type_color, bg=background_color,  bold=True, reset=False)
    for key in doc:
        if (key != "itemType"):
            output += click.style(key + " = {", fg=key_color, reset=False)
            output += click.style(str(doc[key]), fg=value_color, reset=False)
            output += click.style("}\n", fg=key_color, reset=False)
    output += click.style("}\n", fg=type_color, bold=True, reset=True)
    return output


def style_merge(merge):
    m = merge.copy()
    m["key"] = "MERGE"
    return style_document(m, key_color='magenta', type_color='red')

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
        except (IOError, FileNotFoundError, PermissionError) as e:
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
