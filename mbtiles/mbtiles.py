from pathlib import Path
from pymbtiles import MBtiles
from pymbtiles import Tile as MBTile
from datetime import datetime
from loguru import logger
from static_maps.geo import LatLonBBox
from attrs import define, field, Factory
from typing import Any

# MB tiles version requirements.
required_1_1 = ["name", "type", "version", "description", "format"]
optional_1_1 = ["bounds"]
required_1_2 = ["name", "type", "version", "description", "format"]
optional_1_2 = ["bounds", "attribution"]
required_1_3 = ["name", "format"]
should_optional_1_3 = ["bounds", "center", "minzoom", "maxzoom"]
may_optional_1_3 = ["attribution", "description", "type", "version"]

vers_val = lambda s, a, v: v[-1] in ("1", "2", "3")
opt_val = lambda s, a, v: v in ("all", "none", "required", "optional", "should", "may")


@define
class MBTiles:
    spec_version: str = field(default="1.1", validator=vers_val)
    spec_optional: str = field(default="all", validator=opt_val)
    extra_meta: bool = True
    _meta_expected: list[str] = field(default=list, init=False, repr=False)

    def __attrs_post_init__(self):
        # Parse the version to determine which metadata is expected to be present.
        meta_exp = []
        opts_1_12 = ["optional", "all", "should", "may"]
        if self.spec_version == "1.1":
            meta_exp += required_1_1
            if self.spec_optional in opts_1_12:
                meta_exp += optional_1_1
        elif self.spec_version == "1.2":
            meta_exp += required_1_2
            if self.spec_optional in opts_1_12:
                meta_exp += optional_1_2
        elif self.spec_version == "1.3":
            meta_exp += required_1_3
            if self.spec_optional in ["optional", "all", "may"]:
                meta_exp += may_optional_1_3
            if self.spec_optional in ["should"]:
                meta_exp += should_optional_1_3
        self._meta_expected = meta_exp

    def validate_metadata(self, metadata: dict) -> bool:
        """
        Simple metadata validation. Just checks that the required keys exist.
        Does not validate actual metadata
        Args:
            metadata (dict): mbtiles metadata dictionary.
        Raises:
            ValueError: If a key or a key's value is missing.
        Returns:
            bool: True if valid.
        """
        mk = [k for k in self._meta_expected if k not in metadata.keys()]
        if mk:
            msg = f"Missing metadata keys: {', '.join(mk)}"
            msg += f" for version {self.spec_version}."
            raise ValueError(msg)
        # 0 is not an empty value for version, and the two zoom levels.
        mv = [k for k, v in metadata.items() if not v and not isinstance(v, int)]
        if mv:
            msg = f"Missing metadata values for keys: ({', '.join(mv)})"
            msg += f" for spec version v{self.spec_version}."
            raise ValueError(msg)
        return True

    def create_mbtiles_file(
        self,
        file_list: dict,
        metadata: dict,
        output_name: str = "out",
        output_path: Path = Path("."),
        scheme: str = "tms",
        valid: bool = True,
    ):
        """
        Create an mbtiles files form the tiles in file_list.
        Args:
            file_list (dict): List of tiles to include.
            metadata (dict): Metadata to include in the mbtiles file.
            output_name (str, optional): Name out the output file to generate. Defaults to "out".
            output_path (Path, optional): Path to save "output_name.mbtiles" to. Defaults to Path('.').
            scheme (str, optional): Which scheme to use. Options are "xyz" and "tms". "xyz" is standard for web-maps, but mbtiles prefers "tms". Defaults to "tms".
            valid (bool, optional): If "meta", validates metadata. Defaults to True.
        """
        # make_dirs(output_path)
        output_file = output_path.with_suffix(".mbtiles")
        logger.info(f"Creating {output_file} with {len(file_list)} tiles.")
        # This should really take a map as an argument...
        tiles = []
        for image_path, tile in file_list.items():
            # Make sure that the tile is the requested tile index scheme, and if not, flip it.
            if tile.scheme != scheme:
                tile.flip_scheme()
            z, x, y = tile.tid
            # with open(image_path, 'rb') as f:
            #     tile_data = f.read()
            #     assert tile_data == tile.img_data
            tiles += [MBTile(z, x, y, tile.img_data)]
        self.save_mbtiles(output_file, tiles, metadata, valid)

    def save_mbtiles(
        self, out: Path, tiles: Any, meta: dict, valid: bool = True
    ) -> None:
        """
        Saves the mbtiles file with the given path, tiles and metadata.
        Also (optionally) does some basic validation of metadata.
        Args:
            out (Path): output path to save the file to.
            tiles (Any): tiles to add to mbtiles file.
            meta (dict): metadata to add to mbtiles file
            valid (bool, optional): If "meta", validates metadata. Defaults to True.
        """
        if valid:
            _ = self.validate_metadata(meta)
        with MBtiles(out, mode="w") as out:
            logger.info(f"Started mbtiles creation.")
            out.write_tiles(tiles)
            out.meta = meta
        logger.info(f"Finished mbtiles creation.")

    def mbt_metadata(self, other_data: dict = {}, **kwargs) -> dict:
        """
        Creates the mbtiles metadata, including the "required" keys.
        Note that there are some extra values added, with an _ in front.
            This is controlled by setting self.extra_meta to True or False.
        Args:
            other_data (dict, optional): Extra metadata to include. Defaults to {}.
            kwargs: other keyword arguments to pass to creator.
        Returns:
            dict: filled in metadata.
        """
        logger.debug(f"{other_data}")
        logger.debug(f"{kwargs}")
        meta = {k: v for k, v in other_data.items()}

        ll_bbox = None
        if "bounds" in self._meta_expected:
            bounds = get_from_two("bounds", other_data, kwargs, (-180.0, -85, 180, 85))
            ll_bbox = LatLonBBox.from_wgs84_order(*bounds)
            bounds = ",".join([str(x) for x in ll_bbox.wgs84_order])
            meta["bounds"] = bounds

        min_zoom = int(get_from_two("minzoom", other_data, kwargs, 0))
        max_zoom = int(get_from_two("maxzoom", other_data, kwargs, 22))
        df = f"0,0,{min_zoom}"
        if ll_bbox is not None:
            df = ",".join([str(x) for x in ll_bbox.center] + [str(min_zoom)])
        map_source = get_from_two("_map_source", other_data, kwargs, "")
        attribution = get_from_two("attribution", other_data, kwargs, map_source)

        to_include = {
            "name": "mbtiles-test",
            "format": "jpg",
            "center": df,
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "type": "baselayer",
            "version": 0,
            "description": "It's a map...",
            "attribution": attribution,
        }

        for key, default in to_include.items():
            if key in self._meta_expected:
                td = type(default)
                val = get_from_two(key, other_data, kwargs, default)
                meta[key] = td(val)

        if self.extra_meta:
            meta["_scheme"] = get_from_two("scheme", other_data, kwargs, "tms")
            meta["_created_by"] = "github.com/dfloer/mbtiles-test"
            meta["_creation_date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            meta["_mbtiles_version"] = f"{self.spec_version}"
            if "attribution" not in meta and map_source:
                meta["_map_source"] = map_source

        return meta


def get_from_two(k, d1, d2, d):
    """
    Basically dict.get(key, first_choice, second_choice, default)
    """
    return d1.get(k, d2.get(k, d))
