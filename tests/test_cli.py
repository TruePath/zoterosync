import pytest
from zoterosync import script
from zoterosync.library import ZoteroLibrary
import click
from click.testing import CliRunner
from pathlib import Path
import json
import os
import zoterosync
import pickle


def test_cli_init():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(script.cli, ['--config=.zoterosync_config', 'conf', '--key=testbalh', '--user=57867', '--library=.zoterosync_library'])
        assert result.exit_code == 0
        with Path(os.path.abspath('.zoterosync_config')).open(mode='r', encoding='utf8') as conf_file:
            config = json.load(conf_file)
        assert "user" in config
        assert "apikey" in config
        assert "backups" in config
        assert config["user"] == 57867
        assert config["apikey"] == 'testbalh'
        assert config["backups"] == 0
        with Path(os.path.abspath('.zoterosync_library')).open(mode='rb') as lib_file:
            lib = pickle.load(lib_file)
        assert isinstance(lib, ZoteroLibrary)
