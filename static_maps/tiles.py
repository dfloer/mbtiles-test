import glob
import os
import time
from collections import namedtuple
from pathlib import Path
from typing import Any, Iterable, Tuple

import mercantile
import requests as stock_requests
from attrs import Factory, define, field, validators
from loguru import logger
from PIL import Image

Point = namedtuple("Point", ("x", "y"))
Coords = namedtuple("Coords", ("lat", "lon"))
Bbox = namedtuple("Bbox", ("left", "bottom", "right", "top"))

BboxT = tuple[float, float, float, float]


@define(frozen=True)
class TileID:
    z: int
    x: int
    y: int
    scheme: str = "xyz"

    @property
    def zoom(self) -> int:
        return self.z

    @property
    def s(self) -> str:
        return self.scheme

    def __iter__(self) -> Iterable[Tuple[int, int, int]]:
        return iter((self.z, self.x, self.y))

    def __len__(self) -> int:
        return 3

    @property
    def as_mercantile(self) -> mercantile.Tile:
        return mercantile.Tile(x=self.x, y=self.y, z=self.z)

    def get_urlform(self, order="zxy"):
        return "/".join([str(getattr(self, a)) for a in order])

    def get_pathform(self, fn_omit=True):
        ty = Path("") if fn_omit else Path(str(self.y))
        return Path(str(self.z)) / Path(str(self.x)) / ty

    @property
    def parent(self) -> "TileID":
        """
        Return the TileId for the parent.
        """
        return TileID(mercantile.parent(self.asmrcantile))

    @property
    def children(self) -> list["TileID"]:
        """
        Returns a list of this tile's 4 child tile ids.
        """
        return [TileID(mt) for mt in mercantile.children(self.asmrcantile)]

    @property
    def siblings(self) -> list["TileID"]:
        """
        Returns a list of this tile's siblings.
        """
        return [
            TileID(mt)
            for mt in mercantile.children(mercantile.parent(self.asmrcantile))
        ]

    def _swap_scheme(self):
        s = "tms" if self.s == "xyz" else "xyz"
        new_y = (2**self.z) - self.y - 1
        return TileID(z=self.z, x=self.x, y=new_y, scheme=s)

    @property
    def get_tms_tid(self):
        if self.s == "tms":
            return self
        return self._swap_scheme()

    @property
    def get_xyz_tid(self):
        if self.s == "xyz":
            return self
        return self._swap_scheme()


@define
class Tile:
    tid: TileID
    img_data: bytes = field(repr=lambda x: f"{len(x)}Bytes")
    name: str = ""
    resolution: int = 256
    fmt: str = "jpeg"

    # def __post_init__(self):
    # self.resolution = self.img.size[0]
    # self.fmt = self.img.format.lower()

    @property
    def s(self):
        return self.tid.s

    @property
    def scheme(self):
        return self.s

    def save(self, path: Path = Path(".")) -> None:
        with open(path, "wb") as f:
            f.write(self.img_data)
        # img = Image.open(self.img_data)
        # fn = path / Path(f"{self.name}")
        # img.save(fn, self.fmt)

    @property
    def pillow_image(self) -> "Image":
        img = Image.open(self.img_data)
        return img

    @property
    def center(self) -> Point:
        """
        Returns the center of the tile as a (lat, lon) pair. Assumes flat projection.
        """
        bbox = self.bounds
        return Point((bbox.left + bbox.right) / 2, (bbox.top + bbox.bottom) / 2)

    @property
    def bounds(self) -> mercantile.Bbox:
        """
        Get a mercantile bounding box for tile.
        """
        mt = mercantile.bounds(self.asmercantile)
        return mt

    @property
    def x(self) -> int:
        return self.tid.x

    @property
    def y(self) -> int:
        return self.tid.y

    @property
    def z(self) -> int:
        return self.tid.z

    @property
    def zoom(self) -> int:
        return self.z

    @property
    def asmercantile(self) -> mercantile.Tile:
        return mercantile.Tile(z=self.z, x=self.x, y=self.y)

    def flip_scheme(self) -> None:
        """
        Mutates this Tile instance and flips the TileID numbering scheme.
        This _might_ be a bad idea...
        """
        t = self.tid
        self.tid = t._swap_scheme()

    def __len__(self) -> int:
        return len(self.img_data)


def get_tile_ids(bbox, zooms):
    logger.debug(f"bbox: {bbox}, zooms: {zooms}")
    tiles = {
        z: [TileID(a.z, a.x, a.y) for a in mercantile.tiles(*bbox, z)] for z in zooms
    }
    return tiles


def estimate_tiles(bbox, zooms):
    tiles = get_tile_ids(bbox, zooms)
    tile_sum = sum([len(list(x)) for x in tiles.values()])
    return tile_sum


def create_dirs_from_tids(tiles, base_path: Path) -> None:
    for zoom, tids in tiles.items():
        print(zoom)
        for t in tids:
            z, x, _ = t
            print(base_path.joinpath(str(z), str(x)))


def make_dirs(dir_path: Path) -> None:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except OSError as e:
        msg = f"Temp dir creation failed with path: {dir_path}, error: {e}."
        logger.critical(msg)
        raise OSError(msg)


def tile_path(tile: Tile, short_ext: bool = True, base_path: Path = Path(".")):
    ext = tile.fmt
    if short_ext and ext == "jpeg":
        ext = "jpg"
    fp = base_path / tile.tid.get_pathform()
    fn = Path(f"{tile.tid.y}").with_suffix(f".{ext}")
    return fp / fn


@define
class TileDownloader:
    url: str = ""
    params: dict = field(default=Factory(dict))
    fields: dict = field(default=Factory(dict))
    headers: dict = field(default=Factory(dict))
    requests: Any = stock_requests
    tile_size: int = 256
    retries: int = 5

    def download_tile(self, tid: TileID) -> Tile:
        raise NotImplementedError

    def download_or_local(self, tid: TileID, folder: "TileStorage" = None) -> Tile:
        if folder:
            res = folder.get_tile(tid)
            if res:
                return res
            else:
                res = self.download_tile(tid)
                if res is None:
                    return None
                folder.add_tile(res)
        return res

    class DownloadError(Exception):
        def __init__(self, message) -> None:
            self.message = message
            super().__init__(self.message)


@define
class SlippyTileDownloader(TileDownloader):
    def download_tile(self, tid: TileID) -> Tile:
        """
        Downloads a tile with the given tileID.
        Args:
            tid (TileID): TileID of the tile to download.

        Raises:
            self.DownloadError: _description_
            self.DownloadError: _description_

        Returns:
            Tile: _description_
        """
        z, x, y = tid
        logger.debug(f"Downloading tile at z={z}, x={x}, y={y}")
        self.fields["z"] = z
        self.fields["x"] = x
        self.fields["y"] = y
        final_url = self.url.format(**self.fields)
        logger.debug(
            f"Downloading tile at {final_url}, with header: {self.headers} and params: {self.params}."
        )
        backoff_time = 1
        for tries in range(self.retries):
            try:
                resp = self.requests.get(
                    final_url, headers=self.headers, params=self.params
                )
                if resp.status_code == 200:
                    t = Tile(
                        tid=tid, img_data=resp.content, fmt=self.fields.get("fmt", "")
                    )
                    return t
                elif resp.status_code == 404:
                    logger.warning(
                        f"Status code: {resp.status_code}, url: {final_url}, headers: {self.headers}."
                    )
                    return None
                raise self.DownloadError(
                    f"Status code: {resp.status_code}, url: {final_url}, headers: {self.headers}."
                )

            except self.requests.exceptions.ConnectionError as e:
                logger.debug(
                    f"url: {final_url}, headers: {self.headers}. Tries: {tries}, backoff: {backoff_time}s."
                )
                time.sleep(backoff_time)
                # Exponential backoff.
                backoff_time = backoff_time**2
        raise self.DownloadError(f"Failed downloading url: {final_url}.")


class WmsTileDownloader(TileDownloader):
    wms_metadata: dict

    def download_metadata(self, url: str) -> Any:
        resp = self.requests.get(url, headers=self.headers, params=self.params)
        if resp.status_code == 200:
            return resp.content
        elif resp.status_code == 404:
            msg = (
                f"Status code: {resp.status_code}, url: {url}, headers: {self.headers}."
            )
            logger.warning(msg)
            return None
        err = f"Status code: {resp.status_code}, url: {url}, headers: {self.headers}."
        raise self.DownloadError(err)

    def download_tile(self, tid: TileID) -> Tile:
        z, x, y = tid
        logger.debug(f"Downloading tile at z={z}, x={x}, y={y}")


@define
class TileStorage:
    # ToDo: Add a method to track actually missing tiles on requests (such as tiles don't cover an area).
    name: str
    base_path: Path = None
    path_name: Path = Path("")
    full_path: Path = field(
        init=False, default=Path(""), repr=lambda x: f"{x}/z/x/y.fmt"
    )
    temporary: bool = False  # ToDo: This doesn't to anything.
    _storage: dict = field(
        init=False, repr=lambda x: f"local:{len(x) if x else 'disk:0'}", default=None
    )

    def __attrs_post_init__(self):
        if self.base_path is not None:
            self.full_path = self.base_path / self.path_name
            make_dirs(self.full_path)
        else:
            self._storage = {}
            self.temporary = True
        logger.debug(f"Created TileStorage: {self}")

    def add_tile(self, tile: Tile) -> None:
        fmt = tile.fmt
        logger.debug(f"storage: {self._storage}, {bool(self._storage)}.")
        if self._storage is not None:
            logger.debug(f"Adding tile: {tile.tid} to memory storage.")
            self._add_storage(tile)
        else:
            logger.debug(f"Adding tile: {tile.tid} to disk storage.")
            file_path = self.full_path / tile.tid.get_pathform()
            try:
                make_dirs(file_path)
                fn = Path(f"{tile.tid.y}").with_suffix(f".{fmt}")
                fp = file_path / fn
                tile.save(fp)
                logger.debug(f"{tile} saved at: {file_path}")
            except Exception as e:
                raise self.StorageError(f"{file_path} saving failed, error: {e}")

    def get_tile(self, tile_id: TileID) -> Tile:
        if self._storage is not None:
            return self._get_storage(tile_id)
        else:
            file_path = self.full_path / tid_path(tile_id)
            g = glob.glob(f"{file_path}.*")
            if g:
                with open(g[0], "rb") as f:
                    img_data = f.read()
                t = Tile(tile_id, img_data)
                logger.debug(f"Storage: {tile_id} in {self.name}. Tile: {t}.")
                return t
            else:
                return None  # Raise exception?

    def _add_storage(self, tile: Tile) -> None:
        self._storage[tile.tid.get_urlform()] = tile
        logger.debug(f"Local storage added tile with tid={tile.tid}")

    def _get_storage(self, tile_id: TileID) -> Tile:
        res = self._storage.get(tile_id.get_urlform(), None)
        logger.debug(f"Local storage got tile with tid={tile_id} => {res}")
        return res

    class StorageError(Exception):
        def __init__(self, message) -> None:
            self.message = message
            super().__init__(self.message)


def tid_path(tid: TileID) -> Path:
    return Path("").joinpath(str(tid.z), str(tid.x), str(tid.y))
