from collections import namedtuple
from typing import Any, Iterable, Tuple, Union

from attrs import define, field
from attrs.validators import instance_of
from loguru import logger

Point = namedtuple("Point", ("x", "y"))
Pixel = namedtuple("Pixel", ("x", "y"))


@define
class BBoxBase:
    left: float = field(converter=float, validator=instance_of((float, int)))
    top: float = field(converter=float, validator=instance_of((float, int)))
    right: float = field(converter=float, validator=instance_of((float, int)))
    bottom: float = field(converter=float, validator=instance_of((float, int)))
    crs: str = field(default="EPSG:3857", validator=instance_of(str))
    point_type: namedtuple = field(default=Point, init=False, repr=False)

    @property
    def tl(self) -> int:
        return self.point_type(self.left, self.top)

    @property
    def br(self) -> int:
        return self.point_type(self.right, self.bottom)

    @property
    def x_dim(self) -> int:
        return max(self.left, self.right) - min(self.left, self.right)

    @property
    def y_dim(self) -> int:
        return max(self.top, self.bottom) - min(self.top, self.bottom)

    @property
    def xy_dims(self) -> Tuple[int, int]:
        return self.x_dim, self.y_dim

    @property
    def area(self) -> int:
        return self.x_dim * self.y_dim

    @property
    def center(self) -> Any:
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
