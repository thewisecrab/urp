import json
from pathlib import Path

from urp.adapters import LocalS3Adapter


def _descriptor():
    return json.loads((Path(__file__).resolve().parents[1] / "plugin.json").read_text(encoding="utf-8"))


def create_adapter(state_dir=".urp", tenant="local"):
    return LocalS3Adapter(state_dir, tenant)


def capabilities():
    return LocalS3Adapter().capabilities()


def urp_plugin_v1():
    return {
        "descriptor": _descriptor(),
        "operations": {
            "capabilities": capabilities,
            "create_adapter": create_adapter,
        },
    }
