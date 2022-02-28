from pathlib import Path
from pymbtiles import MBtiles
from pymbtiles import Tile as MBTile
from datetime import datetime
from loguru import logger


def create_mbtiles(
    file_list: dict,
    metadata: dict,
    output_name: str = "out",
    output_path: Path = Path("."),
    scheme: str = "tms",
):
    """
    Create an mbtiles files form the tiles in file_list.
    Args:
        file_list (dict): List of tiles to include.
        metadata (dict): Metadata to include in the mbtiles file.
        output_name (str, optional): Name out the output file to generate. Defaults to "out".
        output_path (Path, optional): Path to save "output_name.mbtiles" to. Defaults to Path('.').
        scheme (str, optional): Which scheme to use. Options are "xyz" and "tms". "xyz" is standard for web-maps, but mbtiles prefers "tms". Defaults to "tms".
    """
    # make_dirs(output_path)
    output_file = output_path.with_suffix(".mbtiles")
    logger.info(f"Creating {output_file} with {len(file_list)} tiles.")
    tiles = []
    for image_path, tile in file_list.items():
        if tile.scheme != scheme:
            tile.flip_scheme()
        z, x, y = tile.tid
        # with open(image_path, 'rb') as f:
        #     tile_data = f.read()
        #     assert tile_data == tile.img_data
        tiles += [MBTile(z, x, y, tile.img_data)]

    with MBtiles(output_file, mode="w") as out:
        logger.info(f"Started mbtiles creation.")
        out.write_tiles(tiles)
        out.meta = metadata


def mbt_metadata(other_data: dict = {}, **kwargs):
    """
    Creates the mbtiles metadata, including the "required" keys.
    Args:
        other_data (dict, optional): Extra metadata to include. Defaults to {}.
    """
    logger.debug(f"{other_data}")
    meta = {k: v for k, v in other_data.items()}
    meta["name"] = get_from_two("name", other_data, kwargs, "mbtiles-test")
    meta["type"] = "overlay"
    meta["version"] = 0
    meta["description"] = "It's a map..."
    meta["format"] = get_from_two("fmt", other_data, kwargs, "jpg")
    bounds = get_from_two("bounds", other_data, kwargs, (-180.0, -85, 180, 85))
    if len(bounds) == 4:
        bounds = ", ".join([str(x) for x in bounds])
    meta["bounds"] = bounds
    meta["scheme"] = get_from_two("scheme", other_data, kwargs, "tms")
    meta["created_by"] = "github.com/dfloer/mbtiles-test"
    meta["map_source"] = get_from_two("map_source",other_data, kwargs, "")
    meta["map_license"] = get_from_two("map_license",other_data, kwargs, "")
    meta["creation_date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    logger.debug(f"{meta}")
    return meta


def get_from_two(k, d1, d2, d):
    """
    Basically dict.get(key, first_choice, second_choice, default)
    """
    return d1.get(k, d2.get(k, d))