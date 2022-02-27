import argparse
from urllib.parse import scheme_chars
from loguru import logger
from pathlib import Path

from output import create_mbtiles, mbt_metadata

from tiles import get_tiles_slippy, get_tile_ids


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
    tile_sum = sum([len(list(x)) for x in tiles])
    return tile_sum


if __name__ == "__main__":
    options = parse_command_line()
    bbox = options.bbox
    output = Path(options.output)
    url = options.url
    zoom_levels = options.zoom_levels

    # td = Path("./temp_test")
    td = None
    cd = Path("./cache_test")
    # cd = None

    tile_files, tiles_meta = get_tiles_slippy(
        url=url,
        bbox=bbox,
        zoom_levels=zoom_levels,
        headers={},
        fields={},
        temp_path=td,
        cache_path=cd,
    )

    metadata = mbt_metadata(other_data=tiles_meta, bounds=bbox)

    create_mbtiles(tile_files, metadata, output_path=output)

    # if options.debug:
    #     logging.basicConfig(level=logging.DEBUG)
    # else:
    #     logging.basicConfig(level=logging.INFO)

    # if "wms" in url.lower():
    #     get_tiles_wms(url, bbox, zoom_levels, output)
    # else:
    #     get_tiles_xyz(url, bbox, zoom_levels, output)
