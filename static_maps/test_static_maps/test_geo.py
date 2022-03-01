from ast import Index
import os
import sys

import pytest
from loguru import logger
from collections import namedtuple

logger.remove()
logger.add(sys.stderr, level="DEBUG")
sys.path.append(os.getcwd())
from static_maps.geo import (
    BBox,
    BBoxBase,
    Pixel,
    Point,
    LatLon,
    LatLonBBox,
    xyBBox,
    xyPoint,
    Projector,
    BasePoint,
)
import static_maps.geo as geo


@pytest.mark.parametrize(
    "a, k",
    [
        ((0, 0), {}),
        ((), {"x": 0, "y": 0}),
        ((0,), {"y": 0}),
    ],
)
class TestPoint:
    def test_create_point(self, a, k):
        _ = Point(*a, **k)

    def test_create_pixel(self, a, k):
        _ = Pixel(*a, **k)

    def test_create_latlon(self, a, k):
        m = {"x": "lat", "y": "lon"}
        k = {m[a]: v for a, v in k.items()}
        _ = LatLon(*a, **k)


class TestBasePoint:
    def test_create_bp(self):
        _ = BasePoint()

    def test_len_bp(self):
        bp = BasePoint()
        assert len(bp) == 0

    def test_iter_bp(self):
        bp = BasePoint()
        assert tuple(bp) == ()


class TestLatLon:
    max_lat, max_long, _ = geo.LatLonExtents

    def test_create_llp(self):
        llp = LatLon(0, 0)
        assert llp

    def test_llp_iter(self):
        llp = LatLon(0, 0)
        assert tuple(llp) == (0, 0)

    def test_llp_len(self):
        llp = LatLon(0, 0)
        assert len(llp) == 2

    def test_llp_getitem(self):
        llp = LatLon(1, 2)
        assert llp[0] == 1
        assert llp[1] == 2

    def test_llp_getitem_index_fail(self):
        llp = LatLon(0, 0)
        with pytest.raises(IndexError):
            assert llp[2] == 0

    def test_llp_getitem_type_fail(self):
        llp = LatLon(0, 0)
        with pytest.raises(TypeError):
            assert llp["4"] == 4

    @pytest.mark.parametrize(
        "latlon, exp_val",
        [
            ((0, 0), (0, 0)),
            ((10, 10), (10.0, 10.0)),
            ((100, 200), (max_lat, max_long)),
            ((-100, -200), (-max_lat, -max_long)),
            ((-100, 200), (-max_lat, max_long)),
            ((100, -200), (max_lat, -max_long)),
        ],
    )
    def test_llp_conv_verif(self, latlon, exp_val):
        llp = LatLon(*latlon)
        assert tuple(llp) == exp_val
        assert isinstance(llp.lat, float)
        assert isinstance(llp.lon, float)

    def test_llp_conv_verif_fail(self):
        with pytest.raises(TypeError):
            _ = LatLon("12.0", "14.0")


class TestxyPoint:
    max_x, max_y, _ = geo.xyExtents

    def test_create_xyp(self):
        xyp = xyPoint(0, 0)
        assert xyp.x == 0 and xyp.y == 0

    @pytest.mark.parametrize(
        "x_y, exp_val",
        [
            ((0, 0), (0, 0)),
            ((max_x, max_y), (max_x, max_y)),
            ((-max_x, -max_y), (-max_x, -max_y)),
            ((max_x * 2, max_y * 2), (max_x, max_y)),
            ((max_x * 2, -max_y * 2), (max_x, -max_y)),
            ((max_x, max_y * 2), (max_x, max_y)),
            ((-max_x * 2, max_y), (-max_x, max_y)),
        ],
    )
    def test_xyp_conv_verify(self, x_y, exp_val):
        xyp = xyPoint(*x_y)
        assert tuple(xyp) == exp_val
        assert isinstance(xyp.x, float)
        assert isinstance(xyp.y, float)

    def test_xyp_conv_verif_fail(self):
        with pytest.raises(TypeError):
            _ = xyPoint("12.0", "14.0")

    def test_xyp_iter(self):
        xyp = xyPoint(0, 0)
        assert tuple(xyp) == (0, 0)

    def test_xyp_len(self):
        xyp = xyPoint(0, 0)
        assert len(xyp) == 2


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
        x = type(res)
        assert type(a) == type(res) if isinstance(res, float) else type(float)

    def test_area(self):
        assert BBoxBase(1, 2, 3, 4).area == 4


class TestBBox:
    @pytest.mark.parametrize(
        "in_bbox",
        [
            {"left": 1, "top": 2, "right": 3, "bottom": 4},
            {"left": 1, "top": 2, "right": 3, "bottom": 4, "crs": "x"},
            {"left": 1, "top": 2, "right": 3, "bottom": 4, "srs": "x"},
            {"minx": 1, "maxy": 2, "maxx": 3, "miny": 4},
            {"mInx": 1, "MAXy": 2, "maXX": 3, "MINY": 4},
            {"W": 1, "S": 2, "N": 3, "E": 4},
        ],
    )
    def test_creation_kwargs(self, in_bbox):
        res_bbox = BBox(**in_bbox)
        rv = ["left", "top", "right", "bottom", "crs"]
        assert [getattr(res_bbox, a) == b for a, b in zip(rv, in_bbox.values())]

    @pytest.mark.parametrize(
        "in_bbox",
        [
            {"left": 1, "top": 2, "right": 3, "xxx": 4},
            {"left": 1, "top": 2, "right": 3, "crs": "x"},
            {"left": 1, "top": 2, "right": 3, "bottom": 4, "potato": 0, "srs": "x"},
            {"minx": 1, "maxy": 2},
            {},
        ],
    )
    def test_creation_kwargs_err(self, in_bbox):
        with pytest.raises(TypeError):
            _ = BBox(**in_bbox)

    @pytest.mark.parametrize(
        "args, kwargs",
        [
            ([1, 2, 3, 4], {}),
            ([1, 2, 3, 4], {"crs": "x"}),
            ([1, 2, 3, 4], {"srs": "x"}),
            ([], {"left": 1, "top": 2, "right": 3, "bottom": 4}),
            ([1, 2], {"right": 3, "bottom": 4}),
            ([1, 2], {"xmax": 3, "ymin": 4, "srs": "x"}),
            ([], {"left": 1, "top": 2, "right": 3, "bottom": 4, "crs": "x"}),
            ([1, 2, 3, 4, "x"], {}),
            # This is presently allowed, but not reccomended.
            ([1, 2, 3, 4], {"up": 12, "crs": "x"}),
        ],
    )
    def test_creation_args_kwargs(self, args, kwargs):
        res_bbox = BBox(*args, **kwargs)
        rv = ["left", "top", "right", "bottom", "crs"]
        x = args + list(kwargs.values())
        assert [getattr(res_bbox, a) == b for a, b in zip(rv, x)]

    @pytest.mark.parametrize(
        "args, kwargs, exc",
        [
            ([1, 2, 3], {}, TypeError),
            (["x", 1, 2, 3, 4], {}, ValueError),
            ([], {}, TypeError),
        ],
    )
    def test_creation_args_kwargs_err(self, args, kwargs, exc):
        with pytest.raises(exc):
            res = BBox(*args, **kwargs)
            print(res)

    def test_area(self):
        assert BBox(1, 2, 3, 4).area == 4

    @pytest.mark.skip(reason="ToDo: fix alias not properly being set on object.")
    def test_aliases(self):
        res_bbox = BBox(1, 2, 3, 4, crs="x")
        aliases = res_bbox._aliases
        assert aliases


class TestProjector:
    # max_lat, max_lon, _ = geo.LatLonExtents
    # max_x, max_y, _ = geo.xyExtents
    @pytest.mark.parametrize(
        "crs",
        [
            "EPSG:4326",
            "EPSG:3857",
        ],
    )
    def test_create(self, crs):
        p = Projector(crs)
        assert p.out_crs == crs

    @pytest.mark.skip("WiP")
    @pytest.mark.parametrize(
        "in_bbox, in_crs, exp_bbox, exp_crs",
        [
            [(-45, -90, 45, 90), "EPSG:4326", (5, 6, 7, 8), "EPSG:3857"],
        ],
    )
    def test_project_bbox(self, in_bbox, in_crs, exp_bbox, exp_crs):
        p = Projector(in_crs)
        bbox = LatLonBBox(*in_bbox)
        res = p.project(bbox)
        # assert res.crs == exp_crs
        assert tuple(x for x in res) == exp_bbox

    @pytest.mark.skip("Need to figure out a better way to compare floats.")
    @pytest.mark.parametrize(
        "latlon, xy",
        [
            (LatLon(0, 0), xyPoint(0, 0)),
            (LatLon(45, 85.06), xyPoint(10018754.17139462, 5621521.48619207)),
            (LatLon(-85.06, -180), xyPoint(-20037508.34278924, -242528680.94374272)),
            (LatLon(85.06, 180), xyPoint(20037508.34278924, 242528680.94374272)),
            (LatLon(56.47876683, 11.09030405), xyPoint(1234567, 7654321)),
        ],
    )
    def test_latlon_and_xy_conversion(self, latlon, xy):
        p = Projector(None)
        res = p.latlon_to_xy(latlon)
        print(res)
        assert res[0] == pytest.approx(xy[0])
        assert res[1] == pytest.approx(xy[1])
        res2 = p.xy_to_latlon(xy)
        print(res2)
        assert res2[0] == pytest.approx(latlon[0])
        assert res2[1] == pytest.approx(latlon[1])

    @pytest.mark.parametrize(
        "typ, pnt",
        [
            ("ll", (200, 0)),
            ("ll", (0, 200)),
            ("ll", (200, 200)),
            ("xy", (20037510, 0)),
            ("xy", (0, 242528681)),
            ("xy", (20037510, 242528681)),
        ],
    )
    def test_fail_latlon_and_xy_conversion(self, typ, pnt):
        p = Projector(None)
        if typ == "ll":
            with pytest.raises(AssertionError):
                print(p.latlon_to_xy(pnt))
        else:
            with pytest.raises(AssertionError):
                print(p.xy_to_latlon(pnt))


class TestGeoUtils:
    @pytest.mark.parametrize(
        "in_val, clamp_val,  exp_val, exc",
        [
            (100, 200, 100, None),
            (100, 20, 20, None),
            (-100.2, 20.02, -20.02, None),
            (10, -10, -10, AssertionError),
            (-10, -20, -10, AssertionError),
        ],
    )
    def test_bp_clamp(self, in_val, clamp_val, exp_val, exc):
        bp = BasePoint()
        if exc:
            with pytest.raises(exc):
                r = geo.clamp(in_val, clamp_val)
        else:
            r = geo.clamp(in_val, clamp_val)
            assert r == exp_val

    @pytest.mark.parametrize(
        "in_val, clamp_val,  exp_val, round_val",
        [
            (100, 200, 100.0, 8),
            (100, 20, 20.0, 8),
            (-100.2, 20.08, -20.1, 1),
            (-100.2, 20.05, -20.0, 0),
            (-100.0123456789, 200, -100.01234568, 8),
        ],
    )
    def test_cfr(self, in_val, clamp_val, exp_val, round_val):
        cv = geo.clamp_float_round(in_val, clamp_val, round_val)
        assert cv == exp_val
