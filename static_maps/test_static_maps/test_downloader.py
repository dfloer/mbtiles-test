import os
import sys

sys.path.append(os.getcwd())
from pathlib import Path

import pytest
import requests as stock_requests
from pytest_mock import mocker

from static_maps.tiles import (
    SlippyTileDownloader,
    Tile,
    TileDownloader,
    TileID,
    TileStorage,
)


class TestTileDownloader:
    @pytest.mark.parametrize(
        "url, params, fields, headers, requests, retries, backoff_time, tile_size, empty",
        [
            tuple([None] * 8 + [True]),
            ("", {}, {}, {}, None, 0, 0, 0, False),
            ("url", {"p": "p"}, {"f": "f"}, {"h": "h"}, None, 1, 2, 512, False),
        ],
    )
    def test_creation(
        self,
        url,
        params,
        fields,
        headers,
        requests,
        retries,
        backoff_time,
        tile_size,
        empty,
    ):
        if empty:
            td = TileDownloader()
            assert td.requests == stock_requests
        else:
            td = TileDownloader(
                url, params, fields, headers, requests, retries, backoff_time, tile_size
            )
            print(td)
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
        assert all([isinstance(t, Tile) for t in tiles])
        # Make sure we got the same number of tiles as we were expecting.
        assert len(tiles) == len(tile_ids)
        # Make sure that there is actually an image in the tile (doesn't check if it's a valid image).
        assert [len(t) > 0 for t in tiles]

    @pytest.mark.parametrize(
        "var, self_v, over, ext, exp",
        [
            # No overrides/extra
            ("params", {"p": "p"}, {}, {}, {"p": "p"}),
            ("fields", {"f": "f"}, {}, {}, {"f": "f"}),
            ("headers", {"h": "h"}, {}, {}, {"h": "h"}),
            # override only
            ("params", {"p": "p"}, {"a": "a"}, {}, {"a": "a"}),
            ("fields", {"f": "f"}, {"b": "b"}, {}, {"b": "b"}),
            ("headers", {"h": "h"}, {"c": "c"}, {}, {"c": "c"}),
            # override + extra
            ("params", {"p": "p"}, {"a": "a"}, {"x": "x"}, {"a": "a"}),
            ("fields", {"f": "f"}, {"b": "b"}, {"y": "y"}, {"b": "b"}),
            ("headers", {"h": "h"}, {"c": "c"}, {"z": "z"}, {"c": "c"}),
            # extras only
            ("params", {"p": "p"}, {}, {"x": "x"}, {"x": "x", "p": "p"}),
            ("fields", {"f": "f"}, {}, {"y": "y"}, {"y": "y", "f": "f"}),
            ("headers", {"h": "h"}, {}, {"z": "z"}, {"z": "z", "h": "h"}),
            # extras replace
            ("params", {"p": "p"}, {}, {"p": "u", "x": "x"}, {"x": "x", "p": "u"}),
            ("fields", {"f": "f"}, {}, {"f": "v", "y": "y"}, {"y": "y", "f": "v"}),
            ("headers", {"h": "h"}, {}, {"h": "w", "z": "z"}, {"z": "z", "h": "w"}),
        ],
    )
    def test_override(self, var, self_v, over, ext, exp):
        val = {var: self_v}
        td = TileDownloader(**val)
        x = ["params", "fields", "headers"]
        x.pop(x.index(var))
        assert getattr(td, var) == self_v
        # Check and make sure we didn't set the wrong attribute.
        assert getattr(td, x[0]) == {}, f"{x[0]}"
        assert getattr(td, x[1]) == {}, f"{x[1]}"
        res = td._extra_override(var, over, ext)
        assert res == exp


class TestTileStorage:
    pass

    # def test_folder_creation(self, mocker):
    #     mocker.patch.object(tiles, "make_dirs")
    #     temp_folder = TileStorage("temp", Path("temp"), Path("") , True)
    #     perm_folder = TileStorage("cache", Path("cache"), Path('') , False)
