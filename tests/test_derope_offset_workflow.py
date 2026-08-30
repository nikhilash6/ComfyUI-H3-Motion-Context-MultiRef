import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / "example_workflows" / "NEW - 2MP De-Rope Continuation - Working Example.json"

def _load():
    data = json.loads(WF.read_text(encoding="utf-8"))
    return data, {n["id"]: n for n in data["nodes"]}, {l[0]: l for l in data["links"]}

def test_derope_example_uses_one_dynamic_fan_and_offset_motion_context():
    data, nodes, links = _load()
    fans = [n for n in data["nodes"] if n["type"] == "MiniMaxH3FanRecoveredContext"]
    assert len(fans) == 1
    fan = fans[0]
    assert fan["widgets_values_named"]["context_frames"] == 39

    guide = nodes[5004]
    assert guide["type"] == "MiniMaxH3MotionContext"
    assert guide["widgets_values_named"]["context_length"] == 39
    assert guide["widgets_values_named"]["audio_context_length"] == 0

    context_link = links[guide["inputs"][3]["link"]]
    start_link = links[guide["inputs"][8]["link"]]
    assert context_link[1] == fan["id"] and context_link[2] == 1
    assert start_link[1] == fan["id"] and start_link[2] == 2

    # No full-resolution 396-frame guide decode and no pass-2 denoise mask.
    assert 5002 not in nodes and 5003 not in nodes and 5005 not in nodes
    assert not any("ProtectVideoPrefix" in n["type"] for n in data["nodes"])
    latent_link = links[nodes[296]["inputs"][4]["link"]]
    assert nodes[latent_link[1]]["type"] == "H3V2VInit"

def test_derope_example_uses_core_tail_slice_and_existing_final_assembly_nodes():
    _data, nodes, links = _load()
    tail = nodes[363]
    assert tail["type"] == "ImageFromBatch"
    assert tail["widgets_values_named"] == {"batch_index": -39, "length": 39}

    trim = nodes[6001]
    assert trim["type"] == "MiniMaxH3MotionContextTrim"
    trim_count_link = links[trim["inputs"][2]["link"]]
    assert trim_count_link[1] == 417 and trim_count_link[2] == 1

    asm = nodes[347]
    assert asm["type"] == "MiniMaxH3AssembleExtension"
    assert asm["widgets_values_named"] == {"source_fps": 24, "fps": 24, "crop": "disabled"}

def test_derope_example_has_no_development_only_helper_registrations():
    data, _nodes, _links = _load()
    forbidden = {
        "MiniMaxH3TailFrames",
        "MiniMaxH3AssembleTwoPassExtensions",
        "MiniMaxH3ProtectVideoPrefixV6",
        "MiniMaxH3InjectRecoveredVideoContext",
    }
    assert not any(n["type"] in forbidden for n in data["nodes"])

def test_derope_example_reference_asset_is_bundled():
    import hashlib

    _data, nodes, _links = _load()
    image_name = nodes[139]["widgets_values_named"]["image"]
    assert image_name == "derope_continuation_reference.png"
    asset = ROOT / "example_workflows" / "assets" / image_name
    assert asset.exists()
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == "b2a0824913b9122c770d97089bf57c91859ad6aa6e4eccbbe1bac064abd607e6"



def test_derope_example_has_no_stale_loader_model_metadata():
    data, _nodes, _links = _load()
    keys = ("unet_name", "clip_name", "vae_name", "lora_name", "model_name")
    for node in data["nodes"]:
        named = node.get("widgets_values_named") or {}
        models = (node.get("properties") or {}).get("models") or []
        if not models:
            continue
        actual = next((named[k] for k in keys if k in named), None)
        if actual is not None:
            assert actual in [m.get("name") for m in models]
