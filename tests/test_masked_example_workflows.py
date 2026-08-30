"""Static checks for the Update 3 masked example workflows."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / "example_workflows"


def _load(name):
    data = json.loads((WF / name).read_text(encoding="utf-8"))
    ids = {n["id"] for n in data["nodes"]}
    link_ids = {link[0] for link in data["links"]}
    assert len(ids) == len(data["nodes"])
    for link in data["links"]:
        assert link[1] in ids
        assert link[3] in ids
    for node in data["nodes"]:
        for inp in node.get("inputs", []):
            lid = inp.get("link")
            if lid is not None:
                assert lid in link_ids
        for out in node.get("outputs", []):
            for lid in out.get("links") or []:
                assert lid in link_ids
    return data


def _types(data):
    return [n["type"] for n in data["nodes"]]


def _node(data, type_name):
    return next(n for n in data["nodes"] if n["type"] == type_name)



def test_masked_two_video_bridge_example():
    data = _load("UTILITY - AV Bridge.json")
    types = _types(data)
    assert "MiniMaxH3MaskedAVBridge" in types
    assert "MiniMaxH3AddGuide" not in types

    by_id = {n["id"]: n for n in data["nodes"]}
    links = {link[0]: link for link in data["links"]}

    # Three shared timing controls drive target length, preserve length, and FPS.
    target_frames = by_id[70]
    preserve_frames = by_id[71]
    fps = by_id[72]
    assert target_frames["type"] == "PrimitiveInt"
    assert target_frames["widgets_values"][0] == 192
    assert preserve_frames["type"] == "PrimitiveInt"
    assert preserve_frames["widgets_values"][0] == 39
    assert fps["type"] == "PrimitiveFloat"
    assert fps["widgets_values"][0] == 24.0

    target = _node(data, "MiniMaxH3ImageToVideo")
    target_length = next(i for i in target["inputs"] if i["name"] == "length")
    assert links[target_length["link"]][1:4] == [70, 0, 20]

    bridge = _node(data, "MiniMaxH3MaskedAVBridge")
    assert next(i for i in bridge["inputs"] if i["name"] == "preserve_frames")["link"] == 36
    assert next(i for i in bridge["inputs"] if i["name"] == "start_fps")["link"] == 37
    assert next(i for i in bridge["inputs"] if i["name"] == "end_fps")["link"] == 38

    # Visual stitching follows the validated bridge preserve_frames output.
    stitches = [n for n in data["nodes"] if n["type"] == "ImageBatchExtendWithOverlap"]
    assert len(stitches) == 2
    overlap_links = [next(i for i in n["inputs"] if i["name"] == "overlap")["link"] for n in stitches]
    assert overlap_links == [39, 40]
    assert links[39][1:5] == [21, 2, 50, 2]
    assert links[40][1:5] == [21, 2, 51, 2]

    # Decoded bridge audio removes the protected H3 audio-grid head/tail.
    math_nodes = [n for n in data["nodes"] if n["type"] == "ComfyMathExpression"]
    assert {n["widgets_values"][0] for n in math_nodes} == {
        "round(a / b * 40) / 40",
        "(round(a / c * 40) - 2 * round(b / c * 40)) / 40",
    }
    trim = _node(data, "TrimAudioDuration")
    assert next(i for i in trim["inputs"] if i["name"] == "start_index")["link"] == 47
    assert next(i for i in trim["inputs"] if i["name"] == "duration")["link"] == 48

    # Default 192 / 39 / 24 still evaluates to the historical exact values.
    target_steps = round(192 / 24 * 40)
    preserve_steps = round(39 / 24 * 40)
    assert preserve_steps / 40 == 1.625
    assert (target_steps - 2 * preserve_steps) / 40 == 4.75

    create_video = _node(data, "CreateVideo")
    assert next(i for i in create_video["inputs"] if i["name"] == "fps")["link"] == 41
