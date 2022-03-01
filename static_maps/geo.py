from collections import namedtuple
from typing import Any, Iterable, Tuple, Union

from attrs import define, field, frozen
from attrs.validators import instance_of
from loguru import logger
import mercantile
import math

# This is intended as a convenient shorthand for now, but it should be better handled.
valid_float_int_to_float = field(converter=float, validator=instance_of((float, int)))

LatLonExtents = namedtuple("LatLonExtents", ("lat, lon, rv"))(85.051129, 180, 100)
xyExtents = namedtuple("xyExtents", ("x, y, rv"))(
    20037508.342789244, 20037508.342789244, 100
)


def clamp(a: Union[float, int], v: Union[float, int]) -> Union[float, int]:
    """Clamps a to [-v, +v]"""
    assert v >= 0, f"Clamp value must be positive, not {v}."
    return min(max(a, -v), v)


def lat_converter(lat: Union[int, float]) -> float:
    """Convenience function for clamp_float_round fot lat"""
    lle = LatLonExtents
    return clamp_float_round(lat, lle.lat, lle.rv)


def lon_converter(lon: Union[int, float]) -> float:
    """Convenience function for clamp_float_round fot lon"""
    lle = LatLonExtents
    return clamp_float_round(lon, lle.lon, lle.rv)


def x_xy_converter(x_xy: Union[int, float]) -> float:
    """Convenience function for clamp_float_round fot x"""
    xye = xyExtents
    return clamp_float_round(x_xy, xye.x, xye.rv)


def y_xy_converter(y_xy: Union[int, float]) -> float:
    """Convenience function for clamp_float_round fot y"""
    xye = xyExtents
    return clamp_float_round(y_xy, xye.y, xye.rv)


def clamp_float_round(
    v: Union[int, float], ex: Union[int, float], rv: int
) -> Union[float, Any]:
    """
    Clamps the value v to the extent given as ex, and rounds to rv.
    Args:
        v (Union[int, float]): Value to clamp.
        ex (Union[int, float]): EXtent to clamp the value to, inclusive.
        rv (Union[int, float]): Roundint places Value.
    Returns:
        Union[float, Any]: either the rounded, clamped float, or a passthrough to the underlying validator.
    """
    try:
        cc = clamp(v, ex)
        r = float(round(cc, rv))
        return r
    except Exception:
        return v


lat_field = field(converter=lat_converter, validator=instance_of(float))
lon_field = field(converter=lon_converter, validator=instance_of(float))

x_field = field(converter=x_xy_converter, validator=instance_of(float))
y_field = field(converter=y_xy_converter, validator=instance_of(float))


@frozen(slots=True, weakref_slot=False)
class BasePoint:
    """
    Baseclass with no attributes. Probably don't use this.
    """

    def __iter__(self) -> Iterable[Tuple[float, float]]:
        """
        __slots__ contains all the attributes of the class. We only want to iterate over the data containing attrs.
        For the child classes, this means removing the crs. For this class, the __weakref__.
        __match_args__ would work better, but it's Python >=3.10 feature with the latest attrs.
        """
        x = [
            getattr(self, s)
            for s in list(self.__slots__)
            if s not in ["crs", "__weakref__"]
        ]
        return iter(x)

    def __len__(self) -> int:
        return len([x for x in self.__slots__ if x not in ["crs", "__weakref__"]])

    def __getitem__(self, idx: int) -> Union[float, float]:
        try:
            return tuple(self)[idx]
        except Exception as e:
            msg = e.__str__().replace("tuple", type(self).__name__)
            raise e.__class__(msg)


@frozen(slots=True)
class Point(BasePoint):
    """x, y point with a CRS and bounds clamping."""

    x: float = valid_float_int_to_float
    y: float = valid_float_int_to_float


# Alias for point.
Pixel = Point


@frozen(slots=True)
class xyPoint(BasePoint):
    """X, Y point with a CRS and bounds clamping."""

    x: float = x_field
    y: float = y_field
    crs: str = field(default="EPSG:3857", init=False)


@frozen(slots=True)
class LatLon(BasePoint):
    """lat, lon point with a CRS and bounds clamping."""

    lat: float = lat_field
    lon: float = lon_field
    crs: str = field(default="EPSG:4326", init=False)


@define
class BBoxBase:
    """
    Base class for the bounding box. This could be used directly as a generic bounding box, if needed.
    """

    left: float = valid_float_int_to_float
    top: float = valid_float_int_to_float
    right: float = valid_float_int_to_float
    bottom: float = valid_float_int_to_float
    point_type: namedtuple = field(default=Point, init=False, repr=False)
    crs: str = field(default="", validator=instance_of(str))

    @property
    def tl(self) -> Point:
        """Top Left corner point"""
        return self.point_type(self.left, self.top)

    @property
    def br(self) -> Point:
        """Bottom Right corner point"""
        return self.point_type(self.right, self.bottom)

    @property
    def x_dim(self) -> Union[float, int]:
        """x (left-right) dimension"""
        return max(self.left, self.right) - min(self.left, self.right)

    @property
    def y_dim(self) -> Union[float, int]:
        """y (top-bottom) dimension"""
        return max(self.top, self.bottom) - min(self.top, self.bottom)

    @property
    def xy_dims(self) -> Tuple[Union[float, int], Union[float, int]]:
        """x and y dimensions"""
        return self.x_dim, self.y_dim

    @property
    def area(self) -> int:
        """Naive are calculation. crs setting would affect this."""
        return self.x_dim * self.y_dim

    @property
    def center(self) -> Point:
        """Center of this bbox."""
        c_x = self.left + (self.right - self.left) / 2
        c_y = self.top + (self.bottom - self.top) / 2
        return self.point_type(c_x, c_y)

    def __iter__(self) -> Iterable[Tuple[int, int, int, int]]:
        return iter((self.left, self.top, self.right, self.bottom))

    def __eq__(self, cmp: Any) -> bool:
        if (
            isinstance(cmp, (tuple, list))
            and len(cmp) == 4
            or isinstance(cmp, type(self))
        ):
            a, b, c, d = cmp
            if (a, b, c, d) == (self.left, self.top, self.right, self.bottom):
                return True
        return False

    def __ne__(self, cmp: Any) -> bool:
        return not self.__eq__(cmp)


@define()
class BBox(BBoxBase):
    _aliases: dict = field(init=False, default=None)
    """
    This is a bit weird looking, but the goal is to be able to just drop arbitrary bad input on a BBox, and have it (try to) make something reasonable out of it.
    This means a mix of mandatory args and kwargs, and an optional kwarg.
    ToDo: would be really nice to have the same conversion and validation on this as on the point classes.
    """

    def __init__(self, *args, **kwargs):
        bbox_aliases = {
            ("maxy", "ymax", "north", "n", "t", "up", "u"): "top",
            ("miny", "ymin", "south", "s", "b", "down", "d"): "bottom",
            ("minx", "xmin", "west", "w", "l"): "left",
            ("maxx", "xmax", "east", "e", "r"): "right",
            ("srs"): "crs",
        }
        setattr(self, "_aliases", bbox_aliases)
        logger.debug(f"args: {args}, kwargs: {kwargs}")
        # This works for ASCII only, probably.
        kwargs = {k.lower(): v for k, v in kwargs.items()}
        # Map our kwargs keys to the appropriate argument using the aliases.
        a = {self.lookup(kw): v for kw, v in kwargs.items()}
        # Handle args by turning them into kwargs This currently assumes that no args and kwargs overlap.
        b = {k: v for k, v in zip(("left", "top", "right", "bottom"), args)}
        a.update(b)
        logger.debug(f"new kwargs: {a}")

        self.__attrs_init__(**a)

    def lookup(self, k):
        """
        Given k, return which of the 4 attrs it corresponds to.
        """
        for a, v in self._aliases.items():
            if k in a or k == v:
                return v
        err = f"{k} is not a supported alias."
        raise TypeError(err)


# @frozen
@define
class LatLonBBox(BBox):
    crs: str = field(default="EPSG:4326", init=False)
    point_type: LatLon = field(default=LatLon, init=False, repr=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@frozen
class xyBBox(BBox):
    crs: str = field(default="EPSG:3857", init=False)
    point_type: xyPoint = field(default=xyPoint, init=False, repr=False)

    def wms_str(self):
        return f"{self.left},{self.bottom},{self.top},{self.right}"


@define
class Projector:
    # Currently only supports 4326 and 3857.
    out_crs: str

    size_of_earth: int = field(default=6378137, init=False)  # WGS84
    earth_circ: float = field(default=20037508.342789244, init=False)  # in meters
    latlon_extents: namedtuple = field(default=LatLonExtents, init=False)
    xy_extents: namedtuple = field(default=xyExtents, init=False)

    def project(self, obj):
        if obj.crs == self.out_crs:
            return obj
        if isinstance(obj, BBoxBase):
            return self._project_bbox(obj)
        else:
            raise NotImplementedError

    def project_bbox(self, bbox, in_crs):
        """
        Project the given bbox into our crs.
        """
        # degrees form
        if "4326" in in_crs:
            mt = mercantile.bounding_tile(*bbox)
            l, b, r, t = mercantile.xy_bounds(*mt)
            return xyBBox(left=l, top=t, right=r, bottom=b)
        # XY form
        if "3857" in in_crs:
            mt = mercantile.bounding_tile(*bbox)
            l, b, r, t = mercantile.xy_bounds(mt)
            nl, nt = self._project_point(l, t)
            nr, nb = self._project_point(r, b)
            return LatLonBBox(left=nl, top=nt, right=nr, bottom=nb)

    def project_point(self, pnt, in_crs):
        """Protects the given point into our crs."""
        # degrees form
        if "4326" in in_crs:
            return self.latlon_to_xy(pnt)
        # XY form
        if "3857" in in_crs:
            return self.xy_to_latlon(pnt)

    def latlon_to_xy(self, pnt: Point) -> xyPoint:
        """Converts 4326 to 3857"""
        lat, lon = pnt
        # Unclear if these checks are even needed, but they seem like a good idea anyways.
        lat_ext, lon_ext, rounv_v = self.latlon_extents
        assert abs(lat) <= lat_ext, f"lat ({lat}) must be in [-{lat_ext}, {lat_ext}]."
        assert abs(lon) <= lon_ext, f"lon ({lon}) must be in [-{lon_ext}, {lon_ext}]."

        mx = lon * self.earth_circ / 180.0
        y = math.log(math.tan((90 + lat) * math.pi / 360.0)) / (math.pi / 180.0)
        my = y * self.earth_circ / 180.0
        return xyPoint(round(mx, rounv_v), round(my, rounv_v))

    def xy_to_latlon(self, pnt: Point) -> LatLon:
        """Converts 3857 to 4326"""
        mx, my = pnt
        # Unclear if these checks are even needed, but they seem like a good idea anyways.
        x_ext, y_ext, rounv_v = self.xy_extents
        assert abs(mx) <= x_ext, f"x {mx} must be in [-{x_ext}, {x_ext}]."
        assert abs(my) <= y_ext, f"y {my} must be in [-{-y_ext}, {y_ext}]."

        lon = mx / self.earth_circ * 180.0
        y = my / self.earth_circ * 180.0
        x = math.atan(math.exp(y * math.pi / 180.0))
        lat = 180 / math.pi * (2 * x - math.pi / 2.0)
        return LatLon(round(lat, rounv_v), round(lon, rounv_v))


def tid_to_xy_bbox(tid) -> xyBBox:
    z, x, y = tid
    print(tid)
    w, s, e, n = mercantile.xy_bounds(z, x, y)
    # ll_bb = LatLonBBox(n=n, s=s, w=w, e=e)
    # print(ll_bb)
    # p = Projector(out_crs="EPSG:3857")
    # xy_bb = p.project_bbox(ll_bb, "EPSG:4326")
    # print(xy_bb)
    return xyBBox(w, n, e, s)
    # return xy_bb
