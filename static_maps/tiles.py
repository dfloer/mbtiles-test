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
from urllib.parse import urlencode

BboxT = tuple[float, float, float, float]

from static_maps.geo import BBox, Point, tid_to_xy_bbox


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
        l, b, r, t = mercantile.bounds(self.asmercantile)
        mt = BBox(l, t, r, b)
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
class Downloader:
    url: str = ""
    params: dict = field(default=Factory(dict))
    fields: dict = field(default=Factory(dict))
    headers: dict = field(default=Factory(dict))
    requests: Any = stock_requests
    retries: int = 5
    backoff_time: int = 1

    def download_tile(self, tid: TileID) -> Tile:
        raise NotImplementedError

    class DownloadError(Exception):
        def __init__(self, message) -> None:
            self.message = message
            super().__init__(self.message)

    def download(
        self,
        url: str,
        acceptable_status: list = list([]),
        params_override: dict = {},
        fields_override: dict = {},
        headers_override: dict = {},
        params_extra: dict = {},
        fields_extra: dict = {},
        headers_extra: dict = {},
    ) -> "requests.Response.content":
        """
        Raw downloader. Uses any parameters, fields and headers set on this object.
        the *_extra arguments all replace the existing entries, if they exist. If override is set, *_extra arguments are ignored.
        Args:
            url (str): URL to download from.
            acceptable_status (list, optional): These error codes are treated as acceptable, and any content is returned as is. Defaults to [].
            params_override (dict, optional): If set, fully replace this object's params. Defaults to {}.
            fields_override (dict, optional): If set, fully replace this object's fields. Defaults to {}.
            headers_override (dict, optional): If set, fully replace this object's headers. Defaults to {}.
            params_extra (dict, optional): If set, add to this object's params. Defaults to {}.
            fields_extra (dict, optional): If set, add to this object's fields. Defaults to {}.
            headers_extra (dict, optional): If set, add this object's headers. Defaults to {}.

        Raises:
            self.DownloadError: If the status code is not 200 or in acceptable_status.
            self.DownloadError: If the connection failed and retries were exceeded.
        Returns:
            requests.Response.content: Content of the response.
        """
        params = self._extra_override("params", params_override, params_extra)
        fields = self._extra_override("fields", fields_override, fields_extra)
        headers = self._extra_override("headers", headers_override, headers_extra)
        logger.debug(f"Final: p: {params}, f: {fields}, h: {headers}")
        final_url = url.format(**fields)
        backoff_time = self.backoff_time
        for tries in range(self.retries):
            try:
                resp = self.requests.get(final_url, headers=headers, params=params)
                if resp.status_code == 200:
                    return resp.content
                elif resp.status_code in acceptable_status:
                    logger.debug(
                        f"Status code: {resp.status_code}, url: {final_url}, headers: {headers}."
                    )
                    return resp.content
                raise self.DownloadError(
                    f"Status code: {resp.status_code}, url: {final_url}, headers: {headers}."
                )
            except self.requests.exceptions.ConnectionError as e:
                logger.debug(
                    f"ConnectionError: {e}, url: {final_url}, headers: {headers}. Tries: {tries}, backoff: {backoff_time}s."
                )
                time.sleep(backoff_time)
                # Exponential backoff.
                backoff_time = backoff_time**2
        raise self.DownloadError(
            f"Failed downloading url: [{final_url}] after {self.retries}."
        )

    def _extra_override(self, name: str, override: dict, extra: dict) -> None:
        """
        Handles replacing/adding *_override and *_extra values.
        """
        self_v = getattr(self, name)
        self_v.update(extra) if extra else self_v
        d = override if override else self_v
        return d


@define
class TileDownloader(Downloader):
    tile_size: int = 256

    def download_or_local(self, tid: TileID, folder: "TileStorage" = None) -> Tile:
        if folder:
            res = folder.get_tile(tid)
            if res:
                return res
            else:
                res = self.download_tile(tid)
                if res is None:
                    return None
                t = Tile(tid, res)
                folder.add_tile(t)
        return t

    def download_tile(
        self,
        final_url: str,
        acceptable_status: list = list([]),
        **kwargs,
    ):
        return super().download(final_url, acceptable_status, **kwargs)


@define
class SlippyTileDownloader(TileDownloader):
    crs: str = "EPSG:4326"

    def download_tile(self, tid: TileID) -> Tile:
        """
        Downloads a tile with the given tileID.
        """
        logger.debug(
            f"Downloading tile at {self.url}, with header: {self.headers} and params: {self.params}."
        )
        z, x, y = tid
        logger.debug(f"Downloading tile at z={z}, x={x}, y={y}")
        fe = {"z": z, "x": x, "y": y}
        resp = super().download_tile(self.url, fields_extra=fe)
        if resp is None:
            return None

        # Preserve the default Tile format, rather than guess.
        f = self.fields.get("fmt", None)
        fmt = {"fmt": f} if f is not None else {}
        return Tile(tid=tid, img_data=resp, **fmt)


@define
class WmsTileDownloader(TileDownloader):
    crs: str = "EPSG:3857"
    tile_width: int = 256
    tile_height: int = 256
    metadata: dict = field(default=dict, init=False, repr=False)

    def download_metadata(self, url: str) -> Any:
        """Convenience function."""
        return self.download(url)

    def download_tile(self, tid: TileID) -> Tile:
        # These are static* (*make sure are actually static).
        get_params = {
            # "request": "GetCapabilities",  # ???
            "service": "WMS",
            "request": "GetMap",
        }

        # k is the param key to lookup, value is the default if self.params[k] has nothing.
        default_params = {
            "version": "1.1.1",
            "styles": "default",
            "format": "image/jpeg",
            "scheme": "wmts",
            "transparent": True,
            "layers": 0,
        }
        req_params = self.params

        req_params["width"] = self.tile_width
        req_params["height"] = self.tile_height

        req_params.update(get_params)
        defaults_set = {k: req_params.get(k, v) for k, v in default_params.items()}
        req_params.update(defaults_set)

        # Should these be included as defaults? Probably not, these should be added somewhere higher.
        required = ["bbox", "width", "height"]

        crs_name = "crs"  # renamed in v1.3.0
        if req_params["version"] == "1.1.1":
            crs_name = "srs"
        required += [crs_name]

        xy_bbox1 = tid_to_xy_bbox(tid)
        if req_params["scheme"] == "wmts":
            logger.debug("WMTS: swapping tid scheme.")
            tid = tid._swap_scheme()

        # Feels like the correct way to do this would be to pass an empty Tile to the downloader, in hindsight.
        xy_bbox = tid_to_xy_bbox(tid)
        logger.info(xy_bbox)
        logger.info(xy_bbox1)

        req_params["bbox"] = xy_bbox
        req_params["srs"] = xy_bbox.crs

        z, x, y = tid
        logger.info(f"Downloading tile at z={z}, x={x}, y={y}")
        logger.info(f"{req_params}")

        missing = [k for k in required if k not in req_params.keys()]

        if missing:
            err = (
                f"WmsTileDownloader missing required parameters: {', '.join(missing)}."
            )
            raise ValueError(err)

        tu = "https://basemap.nationalmap.gov/arcgis/services/USGSTopo/MapServer/WMSServer?request=GetCapabilities&service=WMS?service=WMS&request=GetMap&version=1.1.1&styles=default&format=image%2Fpng&scheme=wmts&transparent=True&layers=0&width=256&height=256&srs=EPSG%3A3857&bbox=-20037508.342789244,-7.081154551613622e-10,-10018754.171394622,10018754.171394618"
        url = self.metadata["tile_url"]
        # if z == 2 and x == 0 and y == 1:
        logger.warning(tid)
        logger.info(f"url: {url}")
        logger.info(f"t_url: {tu}")

        return super().download_tile(
            url, tid, params_extra=req_params
        )  # , fields_extras=fe)


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
