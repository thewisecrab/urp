import json
from pathlib import Path

from urp.transforms import ZstdLikePlugin


def _descriptor():
    return json.loads((Path(__file__).resolve().parents[1] / "plugin.json").read_text(encoding="utf-8"))


def compress(data, level=3):
    result = ZstdLikePlugin(level=int(level)).try_compress(bytes(data))
    return {
        "transform": result.transform,
        "codec": result.codec,
        "original_size": result.original_size,
        "stored_size": result.stored_size,
        "data": result.data,
        "useful": result.useful,
    }


def decompress(data, codec):
    return ZstdLikePlugin(codec=str(codec)).decompress(bytes(data))


def urp_plugin_v1():
    return {
        "descriptor": _descriptor(),
        "operations": {"compress": compress, "decompress": decompress},
    }
