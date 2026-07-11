import json
from dataclasses import asdict
from pathlib import Path

from urp.classifier import classify


def _descriptor():
    return json.loads((Path(__file__).resolve().parents[1] / "plugin.json").read_text(encoding="utf-8"))


def classify_work_unit(work_unit):
    result = asdict(classify(work_unit))
    result["detected_kind"] = result["detected_kind"].value
    return result


def urp_plugin_v1():
    return {
        "descriptor": _descriptor(),
        "operations": {"classify_work_unit": classify_work_unit},
    }
