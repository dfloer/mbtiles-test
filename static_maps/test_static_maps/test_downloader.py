import os
import sys

sys.path.append(os.getcwd())
from pathlib import Path

import pytest
import requests as stock_requests
from pytest_mock import mocker
from static_maps.tiles import SlippyTileDownloader, Tile, TileDownloader, TileStorage, TileID


class TestTileDownloader:
    @pytest.mark.parametrize(
        "url, params, fields, headers, requests, tile_size, retries, empty",
        [
            tuple([None] * 7 + [True]),
            ("", {}, {}, {}, None, 0, 0, False),
        ],
    )
    def test_creation(
        self, url, params, fields, headers, requests, tile_size, retries, empty
    ):
        if empty:
            td = TileDownloader()
            assert td.requests == stock_requests
        else:
            td = TileDownloader(
                url, params, fields, headers, requests, tile_size, retries
            )
            assert td.url == url
            assert td.params == params
            assert td.fields == fields
            assert td.headers == headers
            assert td.requests == requests
            assert td.tile_size == tile_size
            assert td.retries == retries

    @pytest.mark.vcr("new")
    @pytest.mark.parametrize(
        "url, params, fields, headers, tile_ids",
        [
            (
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                {},
                {},
                {},
                [TileID(0, 0, 0)],
            ),
        ],
    )
    def test_download_slippy(self, url, params, fields, headers, tile_ids):
        td = SlippyTileDownloader(url, params, fields, headers)
        tiles = [td.download_tile(t) for t in tile_ids]
        # Make sure we got all tiles back.
        print(tiles)
        assert all([isinstance(t, Tile) for t in tiles])
        # Make sure we got the same number of tiles as we were expecting.
        assert len(tiles) == len(tile_ids)
        # Make sure that there is actually an image in the tile (doesn't check if it's a valid image).
        assert [len(t) > 0 for t in tiles]


class TestTileStorage:
    pass

    # def test_folder_creation(self, mocker):
    #     mocker.patch.object(tiles, "make_dirs")
    #     temp_folder = TileStorage("temp", Path("temp"), Path("") , True)
    #     perm_folder = TileStorage("cache", Path("cache"), Path('') , False)
