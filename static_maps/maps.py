from collections import namedtuple
from multiprocessing.sharedctypes import Value
from pathlib import Path
from pprint import pprint
from typing import Iterable, Tuple, Union, Any
from urllib.parse import urlparse
from uuid import uuid4

from attr import field
from attrs import Factory, define, field, validators
from loguru import logger

from static_maps.tiles import (
    BboxT,
    SlippyTileDownloader,
    Tile,
    TileDownloader,
    TileID,
    TileStorage,
    WmsTileDownloader,
    get_tile_ids,
    tile_path,
)

from static_maps.geo import BBox


def simple_map(
    bbox: BboxT,
    zoom_levels: list[int],
    url: str,
    temp_path: Path = None,
    cache_path: Path = None,
    map_type: str = "xyz",
    headers: dict = {},
    fields: dict = {},
    **params,
):
    if "wms" in url.lower() or map_type.lower() == "wms":
        map = BaseMap()
        wms_layer = WmsMapLayer(
            bbox=bbox,
            zoom_levels=zoom_levels,
            base_url=url,
            temp_path=temp_path,
            cache_path=cache_path,
        )
        _, layer = map.add_layer(wms_layer)
        return layer.get_tiles(headers=headers, fields=fields, **params)
    else:
        map = BaseMap()
        slippy_layer = SlippyMapLayer(
            bbox=bbox,
            zoom_levels=zoom_levels,
            base_url=url,
            temp_path=temp_path,
            cache_path=cache_path,
        )
        _, layer = map.add_layer(slippy_layer)
        return layer.get_tiles(headers=headers, fields=fields, **params)


@define
class BaseMap:
    name: str = "BaseMap"
    layers: list = field(default=Factory(list), init=False, repr=False)
    layers_meta: dict = field(default=Factory(dict), init=False, repr=False)

    def add_layer(
        self, layer: "MapLayer", z_idx: int = None, tr: float = 0.0
    ) -> Tuple[int, "MapLayer"]:
        """
        Add a layer to the map.
        Args:
            layer (MapLayer): Actual layer object to add.
            z_idx (int, optional): z-index of the layer (for compositing). If None, generate by insert order. Defaults to None.
            tr (float, optional): transparency. 0=opaque, 100=invisible. Defaults to 0.
        Returns:
            Tuple[int, MapLayer]: (The layer index of the new layer, the actual layer object)
        """
        self.layers += [layer]
        lidx = len(self.layers) - 1
        if z_idx is None:
            z_idx = self.z_max + 1
        if not self._check_z_idx(z_idx):
            raise ValueError("Layer insertion failed.")
        self.layers_meta[lidx] = {"z_idx": z_idx, "tr": tr}
        return lidx, self.layers[lidx]

    def _check_z_idx(self, new_z: int) -> bool:
        try:
            l = self.z_idxs.index(new_z)
        except ValueError:
            return True
        err = f"z-index: {new_z} already assigned to layer {l}"
        raise ValueError(err)

    def get_layer(self, idx: int) -> "MapLayer":
        return self._lookup_wrapper(self.layers, idx, "layers")

    def get_layer_meta(self, idx: int) -> dict[str, Any]:
        return self._lookup_wrapper(self.layers_meta, idx, "layers metadata")

    def _lookup_wrapper(self, l: Union[list, dict], i: Any, n: str) -> Union[Any, None]:
        try:
            msg = f"map {n} does not contain {i}"
            return l[i]
        except IndexError:
            raise IndexError(msg)
        except KeyError:
            raise KeyError(msg)

    @property
    def z_idxs(self) -> list[int]:
        return [a["z_idx"] for a in self.layers_meta.values()]

    @property
    def z_max(self) -> int:
        if not self.z_idxs:
            return -1
        return max(self.z_idxs)

    def __len__(self):
        return len(self.layers)


@define
class MapLayer:
    bbox: BboxT
    zoom_levels: list = field(validator=validators.instance_of(list))
    base_url: str
    tile_downloader: TileDownloader = TileDownloader()
    temp_path: Path = None
    cache_path: Path = None
    metadata: dict = {}
    _tiles: dict[TileID, Tile] = field(init=False, default=Factory(dict))
    _max_zoom: list[int] = 22
    _storage: TileStorage = None
    fmt: str = "jpeg"
    lazy: bool = True
    name: str = ""
    scheme: str = "xyz"
    tile_size: int = 256

    def __attrs_post_init__(self):
        if not self.name:
            self.name = self.__class__.__name__

    @zoom_levels.validator
    def zoom_bounds(self, _, zoom_levels):
        if len(zoom_levels) == 0:
            raise ValueError(f"zoom_levels must have at least one zoom level.")
        if max(zoom_levels) > self._max_zoom or min(zoom_levels) < 0:
            raise ValueError(f"zoom_levels must be between 0 and {self._max_zoom}.")
        dupes = set([x for x in zoom_levels if zoom_levels.count(x) > 1])
        if dupes:
            raise ValueError(f"zoom_levels has duplicates: {dupes}.")

    def get(self, tid: TileID) -> Tile:
        return self._tiles.get(tid, None)

    def put(self, t: Tile) -> None:
        self._tiles[t.tid] = Tile

    def setup_storage(self, path_name: Path):
        if self.temp_path is not None and self.cache_path is not None:
            msg = f"temp_path={self.temp_path} and cache_path={self.cache_path} can't be set at the same time."
            assert False, msg
        elif self.temp_path is not None:
            self._storage = TileStorage(
                "temporary_storage", self.temp_path, path_name, True
            )
        elif self.cache_path is not None:
            self._storage = TileStorage(
                "cache_storage", self.cache_path, path_name, False
            )
        else:
            self._storage = TileStorage("local_storage", None)

    def get_tiles(
        self,
        headers: dict = {},
        fields: dict = {},
        **params: dict,
    ) -> Union[None, Tuple[Path, dict[int, list[int, int, str]]]]:
        """
        Gets the tiles for a bbox from this layer's url, at the specified zoom levels.

        Note that only one of temp_path and cache_path should be set.

        For URL parameter filling, consider this URL: "https://maps.example.com/{api_ver}/{style}/{crs}/{z}/{x}/{y}.{fmt}"
        The parameters z, x, y, and fmt already exist in the TileID object, and fmt is an argument for this function.
        This means that fields would need to be {"api_ver": api_version, "style": map_style, "crs" = coordindate_reference_system}
        Args:
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
        logger.info("Starting tile download...")
        output_meta = {}
        tile_ids = get_tile_ids(self.bbox, self.zoom_levels)
        t = list(tile_ids.values())

        url_pieces = urlparse(self.base_url)

        output_meta["_map_source"] = url_pieces.netloc
        output_meta["format"] = self.fmt
        path_name = Path(url_pieces.netloc.replace(".", "_"))

        self.setup_storage(path_name)

        logger.debug(path_name)
        fields["fmt"] = self.fmt

        self.tile_downloader.url = self.base_url
        self.tile_downloader.fields = fields
        self.tile_downloader.headers = headers
        self.tile_downloader.params = params

        logger.debug(f"file_storage={self._storage}")

        total_tiles = sum([len(list(x)) for x in tile_ids.values()])
        # Print progress, at least every 10 tiles, but at most every 50.
        ts = max(10, min(50, total_tiles // 10))
        idx = 0
        for _, tiles in tile_ids.items():
            for tile in tiles:
                idx += 1
                t = self.tile_downloader.download_or_local(tile, self._storage)
                if t is None:
                    continue
                k = tile_path(t, base_path=self._storage.full_path)
                self._tiles[k] = t
                if idx % ts == 0:
                    logger.info(f"Downloaded: {idx}/{total_tiles} tiles.")
        # ToDo: tile_paths has all of the tiles in it. This is a recipe to run out of memory.

        # if self._storage.name == "local_storage":
        #     raise NotImplementedError("In memory storage of tiles not supported.")
        logger.info("Finished tile download.")
        return self._tiles, output_meta

    def __len__(self):
        return len(self._tiles)


class AuthMissingError(Exception):
    def __init__(self, msg: str = "", name: str = "") -> None:
        if not msg:
            msg = f"Missing auth for maplayer"
        if name:
            msg += f": {name}"
        super().__init__(msg)


@define
class SlippyMapLayer(MapLayer):
    _allowed_schemes = ("xyz", "tms")
    tile_downloader: TileDownloader = SlippyTileDownloader()


@define
class WmsMapLayer(MapLayer):
    _allowed_schemes = "wms"
    tile_downloader: TileDownloader = WmsTileDownloader()
    full_metadata: dict = field(default=Factory(dict), init=False)

    def __attrs_post_init__(self):
        self.tile_downloader.tile_width = self.tile_size
        self.tile_downloader.tile_height = self.tile_size
        self.tile_downloader.meta_url = self.base_url
        self.full_metadata = self.tile_downloader.get_metadata()


@define
class MapBoxLayer(SlippyMapLayer):
    api_key: str = ""
    url: str = field(
        init=False, default="https://api.mapbox.com/v4/{style}/{z}/{x}/{y}{hr}.{fmt}"
    )
    fmt: str = "jpg90"
    style: str = "mapbox.satellite"
    high_res: bool = True

    def get_tiles(self) -> Union[None, Tuple[Path, dict[int, list[int, int, str]]]]:
        if not self.api_key:
            raise AuthMissingError(name=self.name)
        hr = "@2x" if self.high_res else ""
        fields = {"fmt": self.fmt, "style": self.style, "hr": hr}
        return super().get_tiles(fields=fields)
