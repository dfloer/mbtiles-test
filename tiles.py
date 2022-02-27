# from dataclasses import dataclass, field
from attrs import define, field, Factory
from PIL import Image
from io import BytesIO
from collections import namedtuple
import mercantile
from typing import Tuple, Union, Any, Iterable
from pathlib import Path
import os
import time
from pprint import pprint
from loguru import logger
from urllib.parse import urlparse
import requests as stock_requests
from queue import Queue
import glob
from collections import Counter

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
    name: str = "tile"
    resolution: int = 256
    fmt: str = "jpeg"

    # def __post_init__(self):
    # self.resolution = self.img.size[0]
    # self.fmt = self.img.format.lower()

    @property
    def scheme(self):
        return self.tid.s

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


def get_tile_ids(bbox, zooms):
    logger.debug(f"bbox: {bbox}, zooms: {zooms}")
    tiles = {
        z: [TileID(a.z, a.x, a.y) for a in mercantile.tiles(*bbox, z)] for z in zooms
    }
    return tiles


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
    url: str
    params: dict = field(default=Factory(dict))
    fields: dict = field(default=Factory(dict))
    headers: dict = field(default=Factory(dict))
    requests: Any = stock_requests
    tile_size: int = 256
    retries: int = 5

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

    class DownloadError(Exception):
        def __init__(self, message) -> None:
            self.message = message
            super().__init__(self.message)

    def download_or_local(self, tid: TileID, folder: "TileFolder" = None) -> Tile:
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


@define
class TileFolder:
    # ToDo: Add a method to track actually missing tiles on requests (such as tiles don't cover an area).
    name: str
    base_path: Path = None
    path_name: Path = Path("")
    full_path: Path = field(
        init=False, default=Path(""), repr=lambda x: f"{x}/z/x/y.fmt"
    )
    temporary: bool = False  # ToDo: This doesn't to anything.
    _storage: dict = field(
        init=False, repr=lambda x: f"local:{len(x) if x else 0}", default=None
    )

    def __attrs_post_init__(self):
        if self.base_path is not None:
            self.full_path = self.base_path / self.path_name
            make_dirs(self.full_path)
        else:
            self._storage = {}
            self.temporary = True
        logger.info(f"Created TileFolder: {self}")

    def add_tile(self, tile: Tile) -> None:
        fmt = tile.fmt
        if self._storage:
            self._add_storage(tile)
        else:
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
        if self._storage:
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


def get_tiles_slippy(
    url: str,
    bbox: BboxT,
    zoom_levels: list[int],
    headers: dict = {},
    fields: dict = {},
    fmt: str = "jpeg",
    temp_path: Path = None,
    cache_path: Path = None,
    scheme: str = "xyz",
    **params: dict,
) -> Union[None, Tuple[Path, dict[int, list[int, int, str]]]]:
    """
    Gets the tiles for a bbox from the given url, at the specified zoom levels.

    Note that only one of temp_path and cache_path should be set.

    For URL parameter filling, consider this URL: "https://maps.example.com/{api_ver}/{style}/{crs}/{z}/{x}/{y}.{fmt}"
    The parameters z, x, y, and fmt already exist in the TileID object, and fmt is an argument for this function.
    This means that fields would need to be {"api_ver": api_version, "style": map_style, "crs" = coordindate_reference_system}
    Args:
        url (str): Url of the slippy mays server. Any parameters in {} will be filled in as needed, from the Tile or from the fields attribute.
        bbox (BboxT): Bounding box of the area to get tiles for.
        headers (dict, optional): Optional HTTP headers to pass to requests, for exmaple an "X-Api-Key" header for an API key. Defaults to {}.
        fields (dict, optional): Optional fields to fill in the url with. Defaults to {}.
        zoom_levels (list[int]): List of zoom levels to get tiles for. This can be discontinuous.
        tile_format (str, optional): Type of image to download. Presently "jpeg" and "png" are supported/tested. Defaults to "jpeg".
        temp_dir (Path, optional): Path to store temporary files in. This folder is wiped after each run. Blank means store everything in memory, which could be bad. Defaults to None.
        cache_dir (Path, optional): Path to store cached files in. Blank means store everything in memory, which could be bad.. Defaults to None.
    Returns:
        None: If an mbtiles file is written, nothing is returned.
        Fixme: ----> Tuple[Path, dict[int, TileID]]: If a temp_dir is set, this will be the path to the downloaded tiles there. Also included are the tile_ids
    """
    output_meta = {}
    tile_ids = get_tile_ids(bbox, zoom_levels)
    t = list(tile_ids.values())
    logger.info(len(t))

    url_pieces = urlparse(url)
    output_meta["map_sourse"] = url_pieces.netloc
    output_meta["format"] = fmt

    path_name = Path(url_pieces.netloc.replace(".", "_"))

    logger.info(path_name)
    fields["fmt"] = fmt

    downloader = TileDownloader(url, fields=fields, headers=headers, params=params)

    if temp_path is not None and cache_path is not None:
        msg = f"temp_path={temp_path} and cache_path={cache_path} can't be set at the same time."
        assert False, msg
    elif temp_path is not None:
        file_storage = TileFolder("temporary_storage", temp_path, path_name, True)
    elif cache_path is not None:
        file_storage = TileFolder("cache_storage", cache_path, path_name, False)
    else:
        file_storage = TileFolder("local_storage", None)

    logger.debug(f"file_storage={file_storage}")

    tile_paths = {}
    for _, tiles in tile_ids.items():
        for tile in tiles:
            t = downloader.download_or_local(tile, file_storage)
            if t is None:
                continue
            k = tile_path(t, base_path=file_storage.full_path)
            tile_paths[k] = t
    # ToDo: tile_paths has all of the tiles in it. This is a recipe to run out of memory.

    if file_storage.name == "local_storage":
        raise NotImplementedError("In memory storage of tiles not supported.")
    return tile_paths, output_meta
    # logger.debug(pprint(tile_paths))
