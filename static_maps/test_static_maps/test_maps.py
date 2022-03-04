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
        assert layer.base_url == url

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

    @pytest.mark.parametrize(
        "bb, zl, url",
        [
            (
                (45, -90, -45, 90),
                [0, 2, 4],
                "https://maps/example.com",
            )
        ],
    )
    @pytest.mark.parametrize(
        "ln",
        [
            ("l1"),
            ("l1", "l2"),
            ("l1", "l2", "l3"),
        ],
    )
    def test_insert_map_layers(self, ln, bb, zl, url):
        bmap = BaseMap()
        in_layers = []
        for l in ln:
            lyr = MapLayer(bb, zl, url, name=l)
            bmap.add_layer(lyr)
            in_layers += [MapLayer(bb, zl, url, name=l)]
        assert len(bmap) == len(ln)
        for map_lyr, test_lyr in zip(bmap.layers, in_layers):
            assert isinstance(lyr, MapLayer)
            assert map_lyr == test_lyr

    @pytest.mark.parametrize(
        "z_idx, exp_z_idx, lyr, exc",
        [
            (
                (None,),
                (0,),
                MapLayer((0, 0, 0, 0), [0], ""),
                None,
            ),
            (
                (None, None),
                (0, 1),
                MapLayer((0, 0, 0, 0), [0], ""),
                None,
            ),
            # Insert in increasing order.
            (
                (None, None, 6),
                (0, 1, 6),
                MapLayer((0, 0, 0, 0), [0], ""),
                None,
            ),
            # Insert in decreasing order.
            (
                (None, 6, None, None),
                (0, 6, 7, 8),
                MapLayer((0, 0, 0, 0), [0], ""),
                None,
            ),
            # z clash
            (
                (1, 1),
                ("x", "x"),
                MapLayer((0, 0, 0, 0), [0], ""),
                ValueError,
            ),
            # existing z
            (
                (1, None),
                (1, 2),
                MapLayer((0, 0, 0, 0), [0], ""),
                None,
            ),
            # mixed cases
            (
                (3, None, None, 2, 1, None, None),
                (3, 4, 5, 2, 1, 6, 7),
                MapLayer((0, 0, 0, 0), [0], ""),
                None,
            ),
            (
                (3, None, None, 4, 1, None, None),
                ("x", "x", "x", "x", "x", "x", "x"),
                MapLayer((0, 0, 0, 0), [0], ""),
                ValueError,
            ),
        ],
    )
    def test_insert_map_layers_z_idx(self, z_idx, exp_z_idx, lyr, exc):
        layers = []
        for idx, l in enumerate([lyr] * len(z_idx)):
            l.name = str(idx)
            layers += [l]
        bmap = BaseMap()
        if exc is None:
            for (
                l,
                z,
            ) in zip(layers, z_idx):
                if z is not None:
                    bmap.add_layer(l, z_idx=z)
                else:
                    bmap.add_layer(l)
        else:
            with pytest.raises(exc):
                for (
                    l,
                    z,
                ) in zip(layers, z_idx):
                    if z is not None:
                        bmap.add_layer(l, z_idx=z)
                    else:
                        bmap.add_layer(l)

        if exc is None:
            assert exc is None
            for l_idx, _ in enumerate(layers):
                meta = bmap.get_layer_meta(l_idx)
                assert meta["z_idx"] == exp_z_idx[l_idx]


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
        layer = SlippyMapLayer(
            bbox=bbox, zoom_levels=zl, base_url=url, lazy=lazy, fmt="png"
        )
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
        layer = WmsMapLayer(
            bbox=bbox, zoom_levels=zl, base_url=url, lazy=lazy, fmt="jpeg"
        )
        tiles, meta = layer.get_tiles()
        assert len(layer) == tile_count
        assert len(tiles) == tile_count
        assert meta


class TestCreateMap:
    @pytest.mark.vcr("new")
    @pytest.mark.parametrize(
        "test_input",
        [
            {
                "slippy": {
                    "bbox": [-180, -85, 180, 85],
                    "zoom_levels": [0, 1, 2],
                    "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    "z_idx": 0,
                    "transparency": 1,
                    "lazy": False,
                    "fmt": "png",
                    "exp_count": 21,
                    "tile_dl": SlippyMapLayer,
                },
                "wms": {
                    "name": "wms",
                    "bbox": [-180, -85, 180, 85],
                    "zoom_levels": [0, 1, 2],
                    "url": "https://basemap.nationalmap.gov/arcgis/services/USGSTopo/MapServer/WMSServer?request=GetCapabilities&service=WMS",
                    "z_idx": 42,
                    "transparency": 56.78,
                    "lazy": False,
                    "fmt": "png",
                    "exp_count": 21,
                    "tile_dl": WmsMapLayer,
                },
            },
        ],
    )
    def test_full_map_creation(self, test_input):
        basemap = BaseMap()
        res = {}
        for k, v in test_input.items():
            x = self.map_subtest(v, basemap)
            res[k] = x
        assert len(basemap) == len(test_input)
        # assert len(basemap.layers) == len(basemap.layers_meta)

        for idx, (k, v) in enumerate(res.items()):
            assert v["idx"] == idx
            assert len(v["tiles"]) == test_input[k]["exp_count"]
            assert v["meta"]["_map_source"] in test_input[k]["url"]
            assert v["meta"]["format"] == test_input[k]["fmt"]
            assert isinstance(v["res"], test_input[k]["tile_dl"])

    def map_subtest(self, me, basemap):
        tl = me.get("tile_dl", "")
        bb = me.get("bbox", "")
        zl = me.get("zoom_levels", "")
        zid = me.get("z_idx", "")
        url = me.get("url", "")
        lz = me.get("lazy", "")
        fmt = me.get("fmt", "")
        tr = me.get("tr", "")
        lyr = tl(bbox=bb, zoom_levels=zl, base_url=url, lazy=lz, fmt=fmt)
        lyr_idx, lyr_res = basemap.add_layer(lyr, z_idx=zid, tr=tr)
        lyr_tiles, lyr_meta = lyr_res.get_tiles()
        return {"idx": lyr_idx, "res": lyr_res, "meta": lyr_meta, "tiles": lyr_tiles}
