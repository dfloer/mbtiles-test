import os
import sys

import pytest
from loguru import logger

logger.remove()
sys.path.append(os.getcwd())
from static_maps.geo import BBox, BBoxBase, Pixel, Point


class TestBboxBase:
    @pytest.mark.parametrize(
        "in_bbox",
        [
            (
                1,
                2,
                3,
                4,
            ),
        ],
    )
    def test_creation(self, in_bbox):
        res_bbox = BBoxBase(*in_bbox)
        assert res_bbox == in_bbox

    @pytest.mark.parametrize(
        "in_bbox",
        [
            (
                1,
                2,
                3,
                4,
                5,
            ),
        ],
    )
    def test_creation_fail(self, in_bbox):
        with pytest.raises(TypeError):
            res_bbox = BBoxBase(*in_bbox)
            assert res_bbox == in_bbox

    @pytest.mark.parametrize(
        "in_bbox, comp",
        [
            (
                (
                    1,
                    2,
                    3,
                    4,
                ),
                (1, 2, 3, 4),
            ),
            (
                (
                    1,
                    2,
                    3,
                    4,
                ),
                [1, 2, 3, 4],
            ),
            (
                (
                    1,
                    2,
                    3,
                    4,
                ),
                BBoxBase(1, 2, 3, 4),
            ),
        ],
    )
    def test_equal(self, in_bbox, comp):
        print(BBoxBase(*in_bbox))
        assert BBoxBase(*in_bbox) == comp

    @pytest.mark.parametrize(
        "in_bbox, comp",
        [
            (
                (
                    1,
                    2,
                    3,
                    0,
                ),
                (1, 2, 3, 4),
            ),
            (
                (
                    1,
                    2,
                    3,
                    0,
                ),
                [1, 2, 3, 4],
            ),
            (
                (
                    1,
                    2,
                    3,
                    0,
                ),
                BBoxBase(1, 2, 3, 4),
            ),
        ],
    )
    def test_not_equal(self, in_bbox, comp):
        print(BBoxBase(*in_bbox))
        assert BBoxBase(*in_bbox) != comp

    @pytest.mark.parametrize(
        "in_bbox, prop, res",
        [
            (BBoxBase(1, 2, 3, 4), "area", 4),
            (BBoxBase(0, 0, 7, 7), "center", Point(3.5, 3.5)),
            (BBoxBase(1, 2, 3, 4), "tl", Point(1, 2)),
            (BBoxBase(1, 2, 3, 4), "br", Point(3, 4)),
            (BBoxBase(1, 2, 3, 4), "x_dim", 2),
            (BBoxBase(1, 2, 3, 4), "y_dim", 2),
            (BBoxBase(1, 2, 3, 4), "xy_dims", (2, 2)),
            (
                BBoxBase(
                    0,
                    0,
                    0,
                    0,
                ),
                "center",
                Point(0, 0),
            ),
            (
                BBoxBase(
                    0,
                    0,
                    128,
                    128,
                ),
                "center",
                Point(64, 64),
            ),
            (BBoxBase(12, 45, 39, 124), "xy_dims", (27, 79)),
            (BBoxBase(12, 45, 39, 124), "center", Point(25.5, 84.5)),
            (BBoxBase(12, 45, 39, 124), "area", 2133),
        ],
    )
    def test_base_properties(self, in_bbox, prop, res):
        a = object.__getattribute__(in_bbox, prop)
        assert a == res
        assert type(a) == type(res)

    def test_area(self):
        assert BBoxBase(1, 2, 3, 4).area == 4


class TestBBox:
    @pytest.mark.parametrize(
        "in_bbox",
        [
            {"left": 1, "top": 2, "right": 3, "bottom": 4},
            {"minx": 1, "maxy": 2, "maxx": 3, "miny": 4},
        ],
    )
    def test_creation_kwargs(self, in_bbox):
        res_bbox = BBox(**in_bbox)
        assert tuple(res_bbox) == tuple(in_bbox.values())

    def test_area(self):
        assert BBox(1, 2, 3, 4).area == 4
