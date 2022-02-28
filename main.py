import argparse
import sys
from pathlib import Path

from loguru import logger

from mbtiles import create_mbtiles, mbt_metadata
from static_maps.tiles import estimate_tiles, get_tile_ids
from static_maps.maps import simple_map


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Directory to save converted maps to.",
        metavar="OUTFILE",
        required=True,
    )
    parser.add_argument(
        "-u",
        "--url",
        dest="url",
        help="Url to download.",
        metavar="URL",
        required=True,
        type=str,
    )
    parser.add_argument(
        "-s",
        "--sleep",
        dest="sleep_time",
        help="Sleep time, in seconds, between each download call.",
        metavar="SECONDS",
        required=False,
        default=0,
        type=float,
    )
    parser.add_argument(
        "-b",
        "--bbox",
        dest="bbox",
        help="Bounding box to cover.",
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        required=True,
        nargs=4,
        type=float,
    )
    parser.add_argument(
        "-z",
        "--zooms",
        dest="zoom_levels",
        help="Zoom levels to cover",
        metavar="ZOOM",
        required=True,
        default=[],
        nargs="+",
        type=int,
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="Turn on debugging.",
        required=False,
        action="store_true",
    )
    args = parser.parse_args()
    return args


def estimate_tiles(bbox, zooms):
    tiles = get_tile_ids(bbox, zooms)
    tile_sum = sum([len(list(x)) for x in tiles.values()])
    return tile_sum


if __name__ == "__main__":
    options = parse_command_line()
    bbox = options.bbox
    output = Path(options.output)
    url = options.url
    zoom_levels = options.zoom_levels
    debug = options.debug

    if debug:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    # td = Path("./temp_test")
    td = None
    cd = Path("./cache_test")
    # cd = None

    print(f"Estimated tile cound: {estimate_tiles(bbox, zoom_levels)}.")

    tile_files, tiles_meta = simple_map(bbox, zoom_levels, url, td, cd)
    metadata = mbt_metadata(other_data=tiles_meta, bounds=bbox)
    create_mbtiles(tile_files, metadata, output_path=output)
