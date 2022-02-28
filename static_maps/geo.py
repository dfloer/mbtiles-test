from collections import namedtuple
from typing import Any, Iterable, Tuple, Union

from attrs import define, field

Point = namedtuple("Point", ("x", "y"))
Pixel = namedtuple("Pixel", ("x", "y"))


@define
class BBoxBase:
    left: float
    top: float
    right: float
    bottom: float
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
    def __init__(self, *args, **kwargs):
        bbox_aliases = {
            ("maxy", "ymax", "north", "n" "t"): "top",
            ("miny", "ymin", "south", "s" "b"): "bottom",
            ("minx", "xmin", "west", "w" "l"): "left",
            ("maxx", "xmin", "east", "e" "r"): "right",
        }
        if len(kwargs) + len(args) != 4:
            err = f"{__name__}.__init__() got {len(kwargs) + len(args)} arguments, expecting 4."
            raise AttributeError(err)
        # Map our kwargs keys to the appropriate argument.
        a = {self.lookup(kw, bbox_aliases): v for kw, v in kwargs.items()}
        # Handle args. This currently assumes that no args and kwargs overlap.
        b = {k: v for k, v in zip(("left", "bottom", "right", "top"), args)}
        a.update(b)
        if len(a) != 4:
            err = f"{__name__}.__init__() got overlapping kwargs and args, total: {len(a)}."
            raise AttributeError(err)
        self.__attrs_init__(
            left=a["left"], bottom=a["bottom"], right=a["right"], top=a["top"]
        )

    def lookup(self, k, ba):
        """
        Given k, return which of the 4 attrs it corresponds to.
        """
        for a, v in ba.items():
            if k in a or k == v:
                return v
        err = f"{k} is not a supported alias."
        raise ValueError(err)
