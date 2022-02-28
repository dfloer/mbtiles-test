from pathlib import Path
from typing import Tuple, Union
from urllib.parse import urlparse
from uuid import uuid4

from attr import field
from attrs import Factory, define, field, validators
from loguru import logger

from tiles import (
    BboxT,
    SlippyTileDownloader,
    Tile,
    TileDownloader,
    TileStorage,
    TileID,
    WmsTileDownloader,
    get_tile_ids,
    tile_path,
)


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
        raise NotImplementedError("WMS maps not supported yet.")
        # map = BaseMap()
        # slippy_layer = WmsMapLAyer(
        #     bbox=bbox,
        #     zoom_levels=zoom_levels,
        #     url=url,
        #     temp_path=temp_path,
        #     cache_path=cache_path,
        # )
        # layer = map.add_layer(slippy_layer)
        # return layer.get_tiles(headers=headers, fields=fields, **params)
    else:
        map = BaseMap()
        slippy_layer = SlippyMapLayer(
            bbox=bbox,
            zoom_levels=zoom_levels,
            url=url,
            temp_path=temp_path,
            cache_path=cache_path,
        )
        layer = map.add_layer(slippy_layer)
        return layer.get_tiles(headers=headers, fields=fields, **params)


@define
class BaseMap:
    layers: list = Factory(list)
    layers_meta: dict = Factory(dict)

    def add_layer(self, layer: "MapLayer") -> "MapLayer":
        self.layers += [layer]
        lidx = len(self.layers) - 1
        self.layers_meta[lidx] = {"uuid": str(uuid4())}
        return self.layers[lidx]

    def __len__(self):
        return len(self.layers)


@define
class MapLayer:
    bbox: BboxT
    zoom_levels: list = field(validator=validators.instance_of(list))
    url: str
    tile_downloader: TileDownloader = TileDownloader
    temp_path: Path = None
    cache_path: Path = None
    metadata: dict = {}
    _tiles: dict[TileID, Tile] = field(init=False, default=Factory(dict))
    _max_zoom: list[int] = 22
    _storage: TileStorage = None
    fmt: str = "jpeg"
    lazy: bool = True
    name: str = "maplayer"
    scheme: str = "xyz"

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
        tile_ids = get_tile_ids(self.bbox, self.zoom_levels)
        t = list(tile_ids.values())

        url_pieces = urlparse(self.url)

        output_meta["map_source"] = url_pieces.netloc
        output_meta["format"] = self.fmt
        path_name = Path(url_pieces.netloc.replace(".", "_"))

        self.setup_storage(path_name)

        logger.debug(path_name)
        fields["fmt"] = self.fmt

        downloader = self.tile_downloader(
            self.url, fields=fields, headers=headers, params=params
        )

        logger.debug(f"file_storage={self._storage}")

        for _, tiles in tile_ids.items():
            for tile in tiles:
                t = downloader.download_or_local(tile, self._storage)
                if t is None:
                    continue
                k = tile_path(t, base_path=self._storage.full_path)
                self._tiles[k] = t
        # ToDo: tile_paths has all of the tiles in it. This is a recipe to run out of memory.

        # if self._storage.name == "local_storage":
        #     raise NotImplementedError("In memory storage of tiles not supported.")
        return self._tiles, output_meta

    def __len__(self):
        return len(self._tiles)


@define
class SlippyMapLayer(MapLayer):
    _allowed_schemes = ("xyz", "tms")
    tile_downloader: TileDownloader = SlippyTileDownloader


@define
class WmsMapLAyer(MapLayer):
    _allowed_schemes = "wms"
    tile_downloader: TileDownloader = WmsTileDownloader
