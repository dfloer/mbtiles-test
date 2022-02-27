import os
import sys
from pathlib import Path

import mercantile
import pytest
from attrs.exceptions import FrozenInstanceError

sys.path.append(os.getcwd())

import PIL.Image as Img
from tiles import Bbox, Coords, Point, Tile, TileID, get_tile_ids


def create_blank_image(size=256, mode="RGB"):
    return Img.new(mode, (size, size))


class TestTileIDs:
    @pytest.mark.parametrize(
        "input_tileid, expected_tileid",
        [
            (
                (0, 0, 0),
                (0, 0, 0),
            ),
            (
                (35, 11, 8),
                (35, 11, 8),
            ),
            (
                (2, -1, 0),
                (2, -1, 0),
            ),
            (
                (0, 64, 64),
                (0, 64, 64),
            ),
        ],
    )
    def test_creation(self, input_tileid, expected_tileid):
        new_tid = TileID(*input_tileid)
        rz = new_tid.z
        rx = new_tid.x
        ry = new_tid.y
        assert expected_tileid == (rz, rx, ry)

    def test_assignment_fail(self):
        new_tid = TileID(0, 0, 0)
        with pytest.raises(AttributeError):
            new_tid.z = 42

    @pytest.mark.parametrize(
        "input_val, exc",
        [
            (
                (2),
                TypeError,
            ),
            (
                (2, 1),
                TypeError,
            ),
            (
                (2, 1, 6, 4, 9),
                TypeError,
            ),
        ],
    )
    def test_exceptions(self, input_val, exc):
        with pytest.raises(exc):
            new_tid = TileID(*input_val)

    def test_assignment_fail(self):
        new_tid = TileID(0, 0, 0)
        with pytest.raises(FrozenInstanceError):
            new_tid.z = 42

    @pytest.mark.parametrize(
        "test_id",
        [
            (8, 4, 2),
        ],
    )
    # Test to make sure the custom iterator works and returns values in the correct orders.
    def test_iterable_tileid(self, test_id):
        z, x, y = TileID(*test_id)
        assert (z, x, y) == (test_id)

    @pytest.mark.parametrize(
        "test_id",
        [
            (8, 4, 2),
        ],
    )
    # Test to make sure the custom iterator works and returns values in the correct orders.
    def test_iterable_tileid(self, test_id):
        z, x, y = TileID(*test_id)
        assert (z, x, y) == (test_id)

    @pytest.mark.parametrize(
        "test_id, expected_form, fn_omit",
        [
            (TileID(8, 4, 2), Path("8") / Path("4") / Path("2"), False),
            (TileID(8, 4, 2), Path("8") / ("4") / Path(""), True),
        ],
    )
    def test_path_form(self, test_id, expected_form, fn_omit):
        form = test_id.get_pathform(fn_omit)
        assert form == expected_form

    @pytest.mark.parametrize(
        "test_id, expected, form",
        [
            (TileID(8, 4, 2), "8/4/2", None),
            (TileID(8, 4, 2), "8/4/2", "zxy"),
            (TileID(8, 4, 2), "4/2/8", "xyz"),
            (TileID(8, 4, 2), "8/4", "zx"),
            (TileID(8, 4, 2), "2/8/4", "yzx"),
        ],
    )
    def test_url_form(self, test_id, expected, form):
        if form is None:
            res = test_id.get_urlform()
        else:
            res = test_id.get_urlform(form)
        assert res == expected

    @pytest.mark.parametrize(
        "test_id, form",
        [
            (TileID(8, 4, 2), "abc"),
        ],
    )
    def test_url_form(self, test_id, form):
        with pytest.raises(AttributeError):
            res = test_id.get_urlform(form)
            print(res)

    @pytest.mark.parametrize(
        "test_id, expected_tid, scheme",
        [
            (TileID(8, 4, 2, "xyz"), TileID(8, 4, 2, "xyz"), "xyz"),
            (TileID(8, 4, 2, "tms"), TileID(8, 4, 253, "xyz"), "xyz"),
            (TileID(8, 4, 2, "xyz"), TileID(8, 4, 253, "tms"), "tms"),
            (TileID(8, 4, 2, "tms"), TileID(8, 4, 2, "tms"), "tms"),
        ],
    )
    def test_scheme_conversion(self, test_id, expected_tid, scheme):
        res = getattr(test_id, f"get_{scheme}_tid")
        assert expected_tid == res


class TestTile:
    @pytest.mark.parametrize(
        "tile_ids, images, names, tile_size",
        [
            (
                [TileID(0, 0, 0)],
                [bytes()],
                ["test_tile_creation"],
                256,
            ),
        ],
    )
    def test_creation(self, tile_ids, images, names, tile_size):
        for tid, img_data, name in zip(tile_ids, images, names):
            tile = Tile(tid=tid, img_data=img_data, name=name)
            assert tile.tid == tid
            assert tile.img_data == img_data
            assert tile.name == name
            assert tile.resolution == tile_size

    @pytest.mark.parametrize(
        "test_tile, m_tile",
        [
            (
                Tile(TileID(8, 4, 2), img_data=bytes()),
                mercantile.Tile(z=8, x=4, y=2),
            ),
            (
                Tile(TileID(4, 10, 9), img_data=bytes()),
                mercantile.Tile(z=4, x=10, y=9),
            ),
        ],
    )
    def test_to_mercantile(self, test_tile, m_tile):
        assert test_tile.asmercantile == m_tile

    @pytest.mark.parametrize(
        "tile, bounds",
        [
            (
                Tile(TileID(4, 10, 9), img_data=bytes()),
                Bbox(
                    left=45.0,
                    bottom=-40.97989806962013,
                    right=67.5,
                    top=-21.943045533438177,
                ),
            ),
        ],
    )
    def test_tile_bounds(self, tile, bounds):
        assert tile.bounds == bounds

    @pytest.mark.parametrize(
        "test_id, expected_tid",
        [
            (TileID(8, 4, 253, "xyz"), TileID(8, 4, 2, "tms")),
            (TileID(8, 4, 2, "tms"), TileID(8, 4, 253, "xyz")),
        ],
    )
    def test_scheme_swap(self, test_id, expected_tid):
        res = Tile(test_id, img_data=bytes())
        res.flip_scheme()
        assert expected_tid == res.tid


class TestMisc:
    def test_something(self):
        pass
