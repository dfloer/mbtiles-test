import os
import sys

import pytest
from loguru import logger
from collections import namedtuple
from itertools import permutations
import mercantile

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


LatLonExtents = namedtuple("LatLonExtents", ("lat, lon, rv"))(85.051129, 180, 8)
xyExtents = namedtuple("xyExtents", ("x, y, rv"))
xyExtents = xyExtents(20037508.342789244, 20037508.342789244, 8)

max_lat, max_lon, rv = LatLonExtents
max_x, max_y, rv = xyExtents
max_x = round(max_x, rv)
max_y = round(max_y, rv)
max_lat = round(max_lat, rv)
max_lon = round(max_lon, rv)
min_x = -max_x
min_y = -max_y
min_lat = -max_lat
min_lon = -max_lon


class TestTestAssumptions:
    """
    This _probably_ isn't needed,
    but it seemed pertinent make sure the default above hadn't changed.
    Some tests would need to be tweaked if this was the case.
    """

    default_lle = namedtuple("LatLonExtents", ("lat, lon, rv"))(85.051129, 180, 8)
    default_xye_nt = namedtuple("xyExtents", ("x, y, rv"))
    default_xye = default_xye_nt(20037508.342789244, 20037508.342789244, 8)

    def test_fail_if_changed_lle(self):
        a, b, c = LatLonExtents
        d, e, f = self.default_lle
        assert a == d, "Lat doesn't match."
        assert b == e, "Lon doesn't match."
        assert c == f, "round value doesn't match."

    def test_fail_if_changed_xye(self):
        a, b, c = xyExtents
        d, e, f = self.default_xye
        assert a == d, "X doesn't match."
        assert b == e, "Y doesn't match."
        assert c == f, "round value doesn't match."


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
            ((100, 200), (max_lat, max_lon)),
            ((-100, -200), (-max_lat, -max_lon)),
            ((-100, 200), (-max_lat, max_lon)),
            ((100, -200), (max_lat, -max_lon)),
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
        x, y = xyPoint(*x_y)
        assert x == exp_val[0]
        assert y == exp_val[1]
        assert isinstance(x, float)
        assert isinstance(y, float)

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
        assert BBoxBase(*in_bbox) != comp

    @pytest.mark.parametrize(
        "in_bbox, prop, res",
        [
            ((1, 2, 3, 4), "area", 4),
            ((0, 0, 7, 7), "center", Point(3.5, 3.5)),
            ((1, 2, 3, 4), "tl", Point(1, 2)),
            ((1, 2, 3, 4), "br", Point(3, 4)),
            ((1, 2, 3, 4), "x_dim", 2),
            ((1, 2, 3, 4), "y_dim", 2),
            ((1, 2, 3, 4), "xy_dims", (2, 2)),
            (
                (
                    0,
                    0,
                    0,
                    0,
                ),
                "center",
                Point(0, 0),
            ),
            (
                (
                    0,
                    0,
                    128,
                    128,
                ),
                "center",
                Point(64, 64),
            ),
            ((12, 45, 39, 124), "xy_dims", (27, 79)),
            ((12, 45, 39, 124), "center", Point(25.5, 84.5)),
            ((12, 45, 39, 124), "area", 2133),
        ],
    )
    def test_base_properties(self, in_bbox, prop, res):
        in_bbox = BBoxBase(*in_bbox)
        a = object.__getattribute__(in_bbox, prop)
        assert a == res
        x = type(res)
        assert type(a) == type(res) if isinstance(res, float) else type(float)

    def test_area(self):
        assert BBoxBase(1, 2, 3, 4).area == 4

    @pytest.mark.parametrize(
        "bbox, point, exp",
        [
            (BBoxBase(-10, 10, 10, -10), Point(0, 0), True),
            (BBoxBase(-10, 10, 0, 0), Point(0, 0), False),
            (BBoxBase(0, 10, 20, 30), Point(0, 0), False),
            (BBoxBase(-200, 100, 200, -100), Point(16, -32), True),
            (BBoxBase(-10, 10, -5, 5), Point(10, 10), False),
        ],
    )
    def test_bbox_contains(self, bbox, point, exp):
        res = point in bbox
        assert res is exp


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
            print(BBox(*args, **kwargs))

    def test_area(self):
        assert BBox(1, 2, 3, 4).area == 4

    @pytest.mark.skip(reason="ToDo: fix alias not properly being set on object.")
    def test_aliases(self):
        res_bbox = BBox(1, 2, 3, 4, crs="x")
        aliases = res_bbox._aliases
        assert aliases

    @pytest.mark.skip("Notimplemented and commented out.")
    @pytest.mark.parametrize(
        "points",
        [
            (1, 2, 1, 3),
            (-10, 10, 0, 0),
        ],
    )
    def test_bbox_bounds_check(self, points):
        with pytest.raises(BBoxBase.BoundsError):
            print(BBox(*points))


class TestLatLonBBox:
    @pytest.mark.parametrize(
        "in_bbox, prop, res",
        [
            (LatLonBBox(55, -70, -45, 90), "tl", LatLon(55, -70)),
            (LatLonBBox(55, -70, -45, 90), "br", LatLon(-45, 90)),
        ],
    )
    def test_lat_lon_corner(self, in_bbox, prop, res):
        a, b = object.__getattribute__(in_bbox, prop)
        assert (a, b) == (res[0], res[1])

    @pytest.mark.parametrize(
        "in_points, res",
        [
            ((75, -150, 55, 110), LatLonBBox(n=75, w=-150, s=55, e=110)),
            (
                (max_lat, -max_lon, -max_lat, max_lon),
                LatLonBBox(n=max_lat, w=-max_lon, s=-max_lat, e=max_lon),
            ),
            ((0, -0, -max_lat, max_lon), LatLonBBox(n=0, w=-0, s=-max_lat, e=max_lon)),
            ((max_lat, -0, -0, max_lon), LatLonBBox(n=max_lat, w=-0, s=-0, e=max_lon)),
            ((max_lat, -max_lon, -0, 0), LatLonBBox(n=max_lat, w=-max_lon, s=-0, e=0)),
        ],
    )
    def test_last_lon_creation_order(self, in_points, res):
        ll_bb = LatLonBBox(*in_points)
        assert ll_bb == res

    @pytest.mark.skip("Notimplemented and commented out.")
    @pytest.mark.parametrize(
        "in_points,",
        [
            (-75, -150, 55, 110),
            (-75, 150, 55, -110),
        ],
    )
    def test_last_lon_bounds_error(self, in_points):
        with pytest.raises(BBoxBase.BoundsError):
            print(LatLonBBox(*in_points))

    @pytest.mark.parametrize(
        "in_points, out_bbox",
        [
            ((75, -150, 55, 110), LatLonBBox(75, -150, 55, 110)),
            (
                (47 / 3, -0.0123456789, 40 / 9, 11.0),
                LatLonBBox(15.66666667, w=-0.01234568, s=4.44444444, e=11.0),
            ),
        ],
    )
    def test_ll_bbox_converter(self, in_points, out_bbox):
        res = LatLonBBox(*in_points)
        assert res == out_bbox

    @pytest.mark.parametrize(
        "points",
        [
            (35, -42, -47, 171),
            (max_lat, min_lon, min_lat, max_lon),
            (max_lat / 2, min_lon / 6, min_lat / 4, max_lon / 8),
        ],
    )
    def test_ll_bbox_mercantile(self, points):
        n, w, s, e = points
        mt = mercantile.LngLatBbox(north=n, west=w, south=s, east=e)
        ll_bbox = LatLonBBox(top=n, left=w, bottom=s, right=e)
        assert LatLonBBox(mt) == ll_bbox

    @pytest.mark.parametrize(
        "points",
        [
            (75, -150, -55, 110),
            (max_lat, min_lon, min_lat, max_lon),
            (max_lat / 2, min_lon / 6, min_lat / 4, max_lon / 8),
        ],
    )
    def test_ll_bbox_mercantile_fail(self, points):
        n, w, s, e = points
        mt = mercantile.LngLatBbox(*points)
        ll_bbox = LatLonBBox(north=n, west=w, south=s, east=e)
        assert mt.north != ll_bbox.top
        assert mt.south != ll_bbox.bottom
        assert mt.east != ll_bbox.right
        assert mt.west != ll_bbox.left

    def test_ll_bbox_subscriptible(self):
        bbox = (5, -42, -47, 171)
        ll_bbox = LatLonBBox(*bbox)
        assert all([bbox[x] == ll_bbox[x] for x in range(4)])

    def test_ll_attrs(self):
        bbox = (5, -42, -47, 171)
        ll_bbox = LatLonBBox(*bbox)
        assert ll_bbox.top == bbox[0]
        assert ll_bbox.left == bbox[1]
        assert ll_bbox.bottom == bbox[2]
        assert ll_bbox.right == bbox[3]

    def test_wgs84_order(self):
        bbox = LatLonBBox(n=80.5, w=-178.8, s=-84.4, e=179.9)
        res = bbox.wgs84_order
        assert res == (-178.8, -84.4, 179.9, 80.5)

    @pytest.mark.parametrize(
        "in_bbox, exp",
        [
            (
                (min_lon, min_lat, max_lon, max_lat),
                (max_lat, min_lon, min_lat, max_lon),
            ),
            (
                (f"{min_lon}, {min_lat}, {max_lon}, {max_lat}",),
                (max_lat, min_lon, min_lat, max_lon),
            ),
            (
                (f"{min_lon},{min_lat},{max_lon},{max_lat}",),
                (max_lat, min_lon, min_lat, max_lon),
            ),
            (
                ((min_lon, min_lat, max_lon, max_lat),),
                (max_lat, min_lon, min_lat, max_lon),
            ),
            (
                [
                    (min_lon, min_lat, max_lon, max_lat),
                ],
                (max_lat, min_lon, min_lat, max_lon),
            ),
        ],
    )
    def test_from_wgs84_order(self, in_bbox, exp):
        res = LatLonBBox.from_wgs84_order(*in_bbox)
        assert res == LatLonBBox(*exp)

    @pytest.mark.parametrize(
        "s, exp",
        [
            (
                f"{max_lat}, {min_lon}, {min_lat}, {max_lon}",
                (max_lat, min_lon, min_lat, max_lon),
            ),
            (
                f"{max_lat},{min_lon},{min_lat},{max_lon}",
                (max_lat, min_lon, min_lat, max_lon),
            ),
        ],
    )
    def test_from_string(self, s, exp):
        assert LatLonBBox.from_string(s) == LatLonBBox(*exp)

    @pytest.mark.parametrize(
        "in_bbox",
        (
            (max_lat, min_lon, min_lat, max_lon),
            (max_lat, min_lon, max_lon, min_lat),
            (max_lat, min_lat, min_lon, max_lon),
            (max_lat, min_lat, max_lon, min_lon),
            (max_lat, max_lon, min_lon, min_lat),
            (max_lat, max_lon, min_lat, min_lon),
            (min_lon, max_lat, min_lat, max_lon),
            # (min_lon, max_lat, max_lon, min_lat),
            (min_lon, min_lat, max_lat, max_lon),
            # (min_lon, min_lat, max_lon, max_lat),
            (min_lon, max_lon, max_lat, min_lat),
            (min_lon, max_lon, min_lat, max_lat),
            (min_lat, max_lat, min_lon, max_lon),
            (min_lat, max_lat, max_lon, min_lon),
            (min_lat, min_lon, max_lat, max_lon),
            (min_lat, min_lon, max_lon, max_lat),
            (min_lat, max_lon, max_lat, min_lon),
            (min_lat, max_lon, min_lon, max_lat),
            # (max_lon, max_lat, min_lon, min_lat),
            (max_lon, max_lat, min_lat, min_lon),
            (max_lon, min_lon, max_lat, min_lat),
            (max_lon, min_lon, min_lat, max_lat),
            (max_lon, min_lat, max_lat, min_lon),
            # (max_lon, min_lat, min_lon, max_lat),
        ),
    )
    def test_from_wgs84_order_fail(self, in_bbox):
        print(in_bbox)
        with pytest.raises(ValueError):
            _ = LatLonBBox.from_wgs84_order(*in_bbox)


class testxyBBox:
    @pytest.mark.parametrize(
        "in_points, exp_txt",
        [
            (
                (-1, 1, 0, 0),
                "-1,1,0,0",
            ),
            (
                (-5009377, 5240034, 2504688, -1594323),
                "-5009377,5240034,2504688,-1594323",
            ),
        ],
    )
    def test_wms_text(self, in_points, exp_txt):
        ll_bb = LatLonBBox(*in_points)
        assert ll_bb.wms_str == exp_txt


class TestProjector:
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

    @pytest.mark.parametrize(
        "latlon, xy",
        [
            (LatLon(0, 0), xyPoint(0, 0)),
            (LatLon(-45, 0), xyPoint(0, -5621521.486192066)),
            (LatLon(0, max_lon / 4), xyPoint(max_x / 4, 0)),
            (LatLon(0, -max_lon / 4), xyPoint(-max_x / 4, 0)),
            (LatLon(-max_lat, 0), xyPoint(0, -max_y)),
            (LatLon(max_lat, -max_lon / 2), xyPoint(-max_x / 2, max_y)),
            (LatLon(-max_lat, -max_lon), xyPoint(-max_x, -max_y)),
            (LatLon(max_lat, max_lon), xyPoint(max_x, max_y)),
            (LatLon(56.47876683, 11.09030405), xyPoint(1234567, 7654321)),
            (
                LatLon(40.979897, 66.513260),
                xyPoint(7404222.234200611, 5009376.92797668),
            ),
        ],
    )
    def test_point_latlon_and_xy_conversion(self, latlon, xy):
        p = Projector(None)
        res = p.latlon_to_xy(latlon)
        assert res[0] == pytest.approx(xy[0])
        assert res[1] == pytest.approx(xy[1])
        res2 = p.xy_to_latlon(xy)
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

    @pytest.mark.parametrize(
        "ll_bbox, xy_bbox",
        [
            (
                LatLonBBox(max_lat, min_lon, min_lat, max_lon),
                xyBBox(min_x, max_y, max_x, min_y),
            ),
            (
                LatLonBBox(0, min_lon, min_lat, 0),
                xyBBox(min_x, 0, 0, min_y),
            ),
            (
                LatLonBBox(max_lat / 3, min_lon / 4, min_lat, max_lon),
                xyBBox(min_x / 4, 3293220.4782726, max_x, min_y),
            ),
            (
                LatLonBBox(0, 0, min_lat, max_lon),
                xyBBox(0, 0, max_x, min_y),
            ),
            (
                LatLonBBox(max_lat / 2, min_lon / 4, min_lat / 6, max_lon / 8),
                xyBBox(
                    -5009377.08569731,
                    5240034.48734388,
                    2504688.54284866,
                    -1594323.1251003,
                ),
            ),
            (
                LatLonBBox(0, min_lon, 0, max_lon),
                xyBBox(min_x, 0, max_x, 0),
            ),
            (
                LatLonBBox(12, -24, -36, 48),
                xyBBox(
                    -2671667.77903856,
                    1345708.40840910,
                    5343335.55807713,
                    -4300621.37204427,
                ),
            ),
        ],
    )
    def test_bbox_latlon_and_xy_conversion(self, ll_bbox, xy_bbox):
        p3857 = Projector("EPSG:3857")
        p4326 = Projector("EPSG:4326")
        res = p3857.project(ll_bbox)
        for a, b in zip(res, xy_bbox):
            assert pytest.approx(a) == b
        res2 = p4326.project(xy_bbox)
        for a, b in zip(res2, ll_bbox):
            assert pytest.approx(a) == b


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
            (47 / 3, 200, 15.66666667, 8),
        ],
    )
    def test_cfr(self, in_val, clamp_val, exp_val, round_val):
        cv = geo.clamp_float_round(in_val, clamp_val, round_val)
        assert cv == exp_val

    @pytest.mark.parametrize(
        "in_tid, out_bbox",
        [
            (
                (0, 0, 0),
                xyBBox(min_x, max_y, max_x, min_y),
            ),
        ],
    )
    def test_tid_to_xy_bbox(self, in_tid, out_bbox):
        bbox = geo.tid_to_xy_bbox(in_tid)
        assert bbox == out_bbox
