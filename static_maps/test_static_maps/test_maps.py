import os
import sys
from pprint import pprint

import pytest
from loguru import logger

logger.remove()


sys.path.append(os.getcwd())
from static_maps.maps import (
    BaseMap,
    MapLayer,
    SlippyMapLayer,
    SlippyTileDownloader,
    WmsMapLayer,
)
from static_maps.tiles import TileDownloader, TileStorage


class TestBaseMap:
    def test_creation(self):
        map = BaseMap()
        assert map.layers == []
        assert map.layers_meta == {}


class TestMapLayer:
    def test_empty_creation(self):
        with pytest.raises(TypeError):
            layer = MapLayer()

    @pytest.mark.parametrize(
        "bbox, zl, url",
        [
            (
                (0, 0, 0, 0),
                [0],
                "",
            ),
            (
                (-180, -85, 180, 85),
                [0, 2, 4, 6, 8, 10, 12],
                "https://example.com/tiles/{z}/{x}/{y}.png",
            ),
        ],
    )
    def test_basic_creation(self, bbox, zl, url):
        layer = MapLayer(bbox, zl, url)
        assert layer.bbox == bbox
        assert layer.zoom_levels == zl
        assert layer.url == url

    @pytest.mark.parametrize(
        "max_z, zooms, exc",
        [
            (None, [0, 2, 4, 5, 6], None),
            (None, [], ValueError),
            (None, [-1, 100], ValueError),
            (None, [-1], ValueError),
            (None, [100], ValueError),
            (None, [0, 2, 4, 6, 7, 4, 4, 0], ValueError),
        ],
    )
    def test_zoom_validator(self, max_z, zooms, exc):
        if exc is not None:
            with pytest.raises(exc):
                layer = MapLayer((0, 0, 0, 0), zooms, "")
        else:
            layer = MapLayer((0, 0, 0, 0), zooms, "")


class TestSlippyMapLayer:
    @pytest.mark.vcr("new")
    @pytest.mark.parametrize(
        "bbox, zl, url, lazy, tile_count",
        [
            (
                (-180, -85, 180, 85),
                [0, 1, 2],
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                False,
                21,  # 4**0 + 4**1 + 4**1
            ),
        ],
    )
    def test_download_tiles(self, bbox, zl, url, lazy, tile_count):
        layer = SlippyMapLayer(bbox=bbox, zoom_levels=zl, url=url, lazy=lazy, fmt="png")
        tiles, meta = layer.get_tiles()
        assert len(layer) == tile_count
        assert len(tiles) == tile_count
        assert meta


class TestWmsLayer:
    @pytest.mark.vcr("new")
    @pytest.mark.parametrize(
        "bbox, zl, url, lazy, tile_count",
        [
            (
                (28.402123, -178.334698, 18.910361, -154.806773),
                [0, 1, 2, 3],
                "https://basemap.nationalmap.gov/arcgis/services/USGSTopo/MapServer/WMSServer?request=GetCapabilities&service=WMS",
                False,
                43,
            ),
        ],
    )
    def test_metadata_get(self, bbox, zl, url, lazy, tile_count):
        layer = WmsMapLayer(bbox=bbox, zoom_levels=zl, url=url, lazy=lazy, fmt="jpeg")
        tiles, meta = layer.get_tiles()
        assert len(layer) == tile_count
        assert len(tiles) == tile_count
        assert meta


class TestCreateMap:
    @pytest.mark.vcr("new")
    @pytest.mark.parametrize(
        "bbox, zl, url, lazy, tile_count",
        [
            (
                (-180, -85, 180, 85),
                [0, 1, 2],
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                False,
                21,
            ),
        ],
    )
    def test_slippy_map_creation(self, bbox, zl, url, lazy, tile_count):
        smap = BaseMap()
        layer = SlippyMapLayer(bbox=bbox, zoom_levels=zl, url=url, lazy=lazy, fmt="png")
        res = smap.add_layer(layer)
        tiles, meta = res.get_tiles()
        assert len(smap) == 1
        assert len(tiles) == tile_count
        assert len(smap.layers) == len(smap.layers_meta)
        assert meta
