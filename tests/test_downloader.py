import sys
import os

sys.path.append(os.getcwd())
from tiles import TileDownloader, TileFolder, make_dirs
import tiles
from pathlib import Path
from pytest_mock import mocker


class TestTileDownloader:

    def test_x(self):
        pass


class TestTileFolder:
    
    


    def test_folder_creation(self, mocker):
        mocker.patch.object(tiles, "make_dirs")
        temp_folder = TileFolder("temp", Path("temp"), Path("") , True)
        perm_folder = TileFolder("cache", Path("cache"), Path('') , False)