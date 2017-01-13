import os
import click
import zoterosync
from pathlib import Path
import json
import pickle


class ZoteroLibraryStore(object):

    def __init__(self, conf_path, library_path=None):
        self.library = None
        self.user = None
        self.apikey = None
        self._library_path = library_path
        self._conf_path = conf_path
        self.load_config()

    def load_config(self, conf_path=None):
        conf_path = self._conf_path if conf_path is None else conf_path
        try:
            with conf_path.open(mode='r') as conf_file:
                config = json.load(conf_file)
                self.user = config['user']
                self.apikey = config['apikey']
        except (IOError, FileNotFoundError, PermissionError, KeyError):
            pass

    def write_config(self, conf_path=None):
        if conf_path is None:
            conf_path = self._conf_path
        if (self.user is None or self.apikey is None):
            raise Exception("")
        config = dict(user=self.user, apikey=self.apikey)
        with conf_path.open(mode='w', encoding='utf8') as conf_file:
            json.dump(config, conf_file)

    def init_library(self):
        self.library = zoterosync.ZoteroLibrary.factory(self.user, self.apikey)

    def write_library(self):
        if (self.library is None):
            raise Exception("Can't save non-existant library")
        with self._library_path.open(mode='wb') as lib_file:
            pickle.dump(self.library, lib_file)

    def load_library(self):
        with self._library_path.open(mode='rb') as lib_file:
            self.library = pickle.load(lib_file)

@click.group()
@click.option('--config', type=click.Path(), default='.zoterosync_config')
@click.option('--library', type=click.Path(), default='.zoterosync_library')
@click.pass_context
def cli(ctx, config, library):
    ctx.obj = ZoteroLibraryStore(Path(os.path.abspath(config)), Path(os.path.abspath(library)))


@cli.command()
@click.option('--user', type=int)
@click.option('--key')
@click.pass_obj
def init(store, user, key):
    store.user = user
    store.apikey = key
    store.init_library()
    store.write_config()
    store.write_library()
