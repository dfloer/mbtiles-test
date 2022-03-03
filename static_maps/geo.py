from collections import namedtuple
from typing import Any, Iterable, Tuple, Union

from attrs import define, field, frozen
from attrs.validators import instance_of
from loguru import logger
import mercantile
import math

# This is intended as a convenient shorthand for now, but it should be better handled.
valid_float_int_to_float = field(converter=float, validator=instance_of((float, int)))

_LatLonExtents = namedtuple("LatLonExtents", ("lat, lon, rv"))
_xyExtents = namedtuple("xyExtents", ("x, y, rv"))
# Extents definitions. At some point, if there are more projections needed, well, pyproj4...
LatLonExtents = _LatLonExtents(85.051129, 180, 8)
xyExtents = _xyExtents(20037508.342789244, 20037508.342789244, 8)


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
    """x, y point."""

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
    Note that the coordinates are given in x/y form, which is lon/lat form, *not* lat/lon form.
    """

    left: float = valid_float_int_to_float
    top: float = valid_float_int_to_float
    right: float = valid_float_int_to_float
    bottom: float = valid_float_int_to_float
    crs: str = field(default="", validator=instance_of(str))
    point_type: namedtuple = field(default=Point, init=False, repr=False)

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
        is_inst = isinstance(cmp, type(self))
        if isinstance(cmp, (tuple, list)) and len(cmp) == 4 or is_inst:
            a, b, c, d = cmp
            eq1 = (a, b, c, d) == (self.left, self.top, self.right, self.bottom)
            eq2 = self.crs == cmp.crs if is_inst else True
            eq3 = self.point_type == cmp.point_type if is_inst else True
            return eq1 and eq2 and eq3
        return False

    def __ne__(self, cmp: Any) -> bool:
        return not self.__eq__(cmp)

    def __contains__(self, pnt: Any) -> bool:
        if not isinstance(pnt, self.point_type):
            return False
        pa, pb = pnt
        l, t, r, b = tuple(self)
        return l < pa < r and b < pb < t

    def __getitem__(self, idx: int) -> Union[float, float]:
        try:
            return tuple(self)[idx]
        except Exception as e:
            msg = e.__str__().replace("tuple", type(self).__name__)
            raise e.__class__(msg)

    class BoundsError(Exception):
        def __init__(self, message) -> None:
            self.message = message
            super().__init__(self.message)


@define
class BBox(BBoxBase):
    _aliases: dict = field(init=False, default=None, repr=False)
    # crs: str = field(default="", validator=instance_of(str))  # ToDo: CRS should be here, not the base class.
    """
    This is a bit weird looking, but the goal is to be able to just drop arbitrary bad input on a BBox, and have it (try to) make something reasonable out of it.
    This means a mix of mandatory args and kwargs, and an optional kwarg.
    ToDo: would be really nice to have the same conversion and validation on this as on the point classes.
    """

    def __init__(self, *args, **kwargs):
        bbox_aliases = {
            ("_lln", "maxy", "ymax", "north", "n", "t", "up", "u"): "top",
            ("_lls", "miny", "ymin", "south", "s", "b", "down", "d"): "bottom",
            ("_llw", "minx", "xmin", "west", "w", "l"): "left",
            ("_lle", "maxx", "xmax", "east", "e", "r"): "right",
            ("_llc", "srs"): "crs",
        }
        setattr(self, "_aliases", bbox_aliases)
        # This works for ASCII only, probably.
        kwargs = {k.lower(): v for k, v in kwargs.items()}
        # Map our kwargs keys to the appropriate argument using the aliases.
        a = {self.lookup(kw): v for kw, v in kwargs.items()}
        # Handle args by turning them into kwargs This currently assumes that no args and kwargs overlap.
        b = {k: v for k, v in zip(("left", "top", "right", "bottom", "crs"), args)}
        a.update(b)

        self.__attrs_init__(**a)

    # def __attrs_post_init__(self, *args, **kwargs):
    #     """
    #     This probably makes more sense as a validator.
    #     But idea is to validate that the bbox is valid.
    #     Rules aren't correct yet.
    #     """
    #     err = None

    #     t_g_b = self.top < self.bottom
    #     t_l_b = self.top > self.bottom
    #     r_g_l = self.right > self.left
    #     r_l_l = self.right < self.left

    #     if self.top < self.bottom:
    #         err = f"Top=({self.top}) < bottom=({self.bottom})"
    #         raise self.BoundsError(err)
    #     elif abs(self.right) > abs(self.left):
    #         err = f"Right=({abs(self.right)}) > left=({abs(self.left)})"
    #         raise self.BoundsError(err)
    #     elif self.top == self.bottom or self.right == self.left:
    #         err = f"Lines not supported."
    #         raise NotImplementedError(err)

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
    """
    For EPSG:4326, origin at lat, lon (0, 0).
    North: +lat, South: -lat, West: -lon, East: +lon
    """

    left: float = lon_field
    top: float = lat_field
    right: float = lon_field
    bottom: float = lat_field
    crs: str = field(default="EPSG:4326", init=False)
    point_type: LatLon = field(default=LatLon, init=False, repr=False)

    def __init__(self, *args, **kwargs):
        """
        Underlying store is left, top, right, bottom,
        but lat/lon ordering in top (north), left (west), bottom (south), right (east).
        kwargs should get proper position by virtue of the aliases, but args won't.
        """
        la = len(args)
        if la == 1 and len(kwargs) == 0 and isinstance(args[0], mercantile.LngLatBbox):
            w, s, e, n = args[0]
            args = (n, w, s, e)
        elif la > 5:
            err = f"{type(self).__name__}takes from 4 to 5 positional arguments but {la} were given"
            raise TypeError(err)
        extra_kwargs = {f"_ll{k}": v for k, v in zip("nwsec", args)}
        kwargs.update(extra_kwargs)
        super().__init__(**kwargs)

    @property
    def tl(self) -> Point:
        """Top Left corner point"""
        return self.point_type(self.top, self.left)

    @property
    def br(self) -> Point:
        """Bottom Right corner point"""
        return self.point_type(self.bottom, self.right)

    def __iter__(self) -> Iterable[Tuple[int, int, int, int]]:
        return iter((self.top, self.left, self.bottom, self.right))

    def __str__(self) -> str:
        dirs = ["north", "west", "south", "east"]
        vals = [self.top, self.left, self.bottom, self.right]
        dir_vals = ", ".join([f"{n}={v}" for n, v in zip(dirs, vals)])
        return f"LatLonBBox({dir_vals}, crs={self.crs})"


@frozen
class xyBBox(BBox):
    """
    For EPSG:3857, origin at lat, lon (0, 0).
    North: +Y, South: -Y, West: -X, East: +X
    """

    left: float = x_field
    top: float = y_field
    right: float = x_field
    bottom: float = y_field

    crs: str = field(default="EPSG:3857", init=False)
    point_type: xyPoint = field(default=xyPoint, init=False, repr=False)

    def wms_str(self):
        return f"{self.left},{self.bottom},{self.right},{self.top}"


@define
class Projector:
    """
    Project from one CRS to another.
    Or, if created with None, can be used to "swap" the CRS of objects.
    Currently only supports EPSG:4326 and EPSG:3857.
    """

    out_crs: str = field(validator=instance_of(Union[str, int, None]))
    size_of_earth: int = field(default=6378137, init=False)  # WGS84
    earth_circ: float = field(default=20037508.342789244, init=False)  # in meters
    latlon_extents: namedtuple = field(default=LatLonExtents, init=False)
    xy_extents: namedtuple = field(default=xyExtents, init=False)

    @out_crs.validator
    def _valid_crs(self, attrib, crs):
        if crs is None:
            return True
        val_crs = ["4326", "3857"]
        crs_val = [1 for x in val_crs if x in crs.lower()]
        if len(crs_val) != 1:
            crs_str = ["EPSG:" + x for x in val_crs]
            err = f"{crs} not in supported. Supported: {', '.join(crs_str)}."
            raise ValueError(err)

    def project(self, obj: Union[BBox, Point]) -> Union[BBox, Point]:
        """
        Takes an objects and projects it into the projector's current crs.
        For objects without a crs (BBoxBase, Point, Pixel, Basepoint), it will be converted to out_crs.
        Note that while much of this project uses EPSG:4326 which is lat/lon, EPSG:3857 (aka XY): is lon/lat.
        This is an important distinction to make!
        Args:
            obj (Union[BBox, Point]): Object to convert. Presently only works for objects that derive from BBoxBase and BasePoint.
        Raises:
            NotImplementedError: Obj type is not supported yet.
        Returns:
            Union[BBox, Point]: Projected version of the input object, with crs attached.
        """
        try:
            if obj.crs == self.out_crs:
                return obj
        except AttributeError:
            pass
        if isinstance(obj, BBoxBase):
            return self.project_bbox(obj)
        elif isinstance(obj, BasePoint):
            return self.project_point(obj)
        else:
            raise NotImplementedError(f"{type(obj).__name__} not supported yet.")

    def project_bbox(self, bbox):
        """
        Project the given bbox into our crs.
        """
        ll_crs = "4326"
        xy_crs = "3857"
        # degrees form
        if xy_crs == self.out_crs or isinstance(bbox, LatLonBBox):
            nl, nt = self.project_point(bbox.tl)
            nr, nb = self.project_point(bbox.br)
            return xyBBox(left=nl, top=nt, right=nr, bottom=nb)
        # XY form
        if ll_crs == self.out_crs or isinstance(bbox, xyBBox):
            tl = self.project_point(bbox.tl)
            br = self.project_point(bbox.br)
            return LatLonBBox(n=tl.lat, w=tl.lon, s=br.lat, e=br.lon)

    def project_point(self, pnt):
        """Protects the given point into our crs."""
        # degrees form
        ll_crs = "4326"
        xy_crs = "3857"
        if xy_crs == self.out_crs or isinstance(pnt, LatLon):
            return self.latlon_to_xy(pnt)
        # XY form
        if ll_crs == self.out_crs or isinstance(pnt, xyPoint):
            return self.xy_to_latlon(pnt)

    def latlon_to_xy(self, pnt: Point) -> xyPoint:
        """Converts 4326 to 3857"""
        lat, lon = pnt
        # Unclear if these checks are even needed, but they seem like a good idea anyways.
        lat_ext, lon_ext, rounv_v = self.latlon_extents
        assert abs(lat) <= lat_ext, f"lat ({lat}) must be in [-{lat_ext}, {lat_ext}]."
        assert abs(lon) <= lon_ext, f"lon ({lon}) must be in [-{lon_ext}, {lon_ext}]."

        mx = lon * self.earth_circ / 180.0
        y = math.degrees(math.log(math.tan((90 + lat) * math.pi / 360.0)))
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
        x = math.atan(math.exp(math.radians(y)))
        lat = 180 / math.pi * (2 * x - math.pi / 2.0)
        return LatLon(round(lat, rounv_v), round(lon, rounv_v))


def tid_to_xy_bbox(tid: Iterable) -> xyBBox:
    z, x, y = tid
    bounds = mercantile.bounds(x, y, z)
    ll_bbox = LatLonBBox(bounds)
    p = Projector(None)
    xy_bb = p.project(ll_bbox)
    return xy_bb
