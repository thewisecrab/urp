import json
from pathlib import Path

from urp.verifiers import verify_sha256


def _descriptor():
    return json.loads((Path(__file__).resolve().parents[1] / "plugin.json").read_text(encoding="utf-8"))


def verify(data, expected_sha256):
    return verify_sha256(bytes(data), str(expected_sha256)).to_dict()


def urp_plugin_v1():
    return {
        "descriptor": _descriptor(),
        "operations": {"verify": verify},
    }
