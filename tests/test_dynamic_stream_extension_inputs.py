from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
STREAM = ROOT / "h3_streaming_vhs.py"
JS = ROOT / "js" / "h3_stream_extension_inputs.js"
WF = ROOT / "example_workflows" / "NEW - AV Extension.json"


def _load_stream_module():
    spec = spec_from_file_location("_h3_dynamic_stream_test_module", STREAM)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stream_node_declares_wide_backend_range_and_modular_input_count():
    module = _load_stream_module()
    cls = module.MiniMaxH3StreamLiveExtensionAVToVHS
    schema = cls.INPUT_TYPES()
    assert cls.MAX_EXTENSIONS == 64
    assert schema["required"]["input_count"][1]["default"] == 6
    assert schema["required"]["input_count"][1]["max"] == 64
    assert "active_extensions" in schema["optional"]
    for i in (1, 6, 7, 32, 64):
        assert schema["optional"][f"extension_{i}"][0] == "LATENT"
        assert schema["optional"][f"extension_{i}"][1]["lazy"] is True


def test_preview_barrier_declares_wide_backend_range_and_modular_input_count():
    module = _load_stream_module()
    cls = module.MiniMaxH3LastActiveVHSPreviewBarrier
    schema = cls.INPUT_TYPES()
    assert cls.MAX_PREVIEWS == 64
    assert schema["required"]["input_count"][1]["default"] == 6
    assert schema["required"]["input_count"][1]["max"] == 64
    assert "active_extensions" in schema["optional"]
    assert "active_clips" in schema["optional"]
    for i in (1, 6, 7, 20, 64):
        assert schema["optional"][f"preview_{i}"][0] == "VHS_FILENAMES"
        assert schema["optional"][f"preview_{i}"][1]["lazy"] is True


def test_lazy_status_requests_only_connected_extension_sockets_and_allows_gaps():
    module = _load_stream_module()
    node = module.MiniMaxH3StreamLiveExtensionAVToVHS()
    common = dict(
        video_vae=object(), audio_vae=object(), start_mode="existing_video",
        input_count=6, context_frames=39, video_overlap_frames=39,
        source_fps=24.0, crop="disabled", filename_prefix="x", pix_fmt="yuv420p",
        crf=19, save_metadata=False, trim_to_audio=True, save_output=True,
        source_frames=object(), source_audio=object(), starter_latent=None,
    )

    # extension_2 and extension_4 are disconnected (absent). extension_5 is
    # connected but above the controller cap and must stay lazy/unrequested.
    needed = node.check_lazy_status(
        **common,
        active_extensions=4,
        extension_1=None,
        extension_3=None,
        extension_5=None,
    )
    assert needed == ["extension_1", "extension_3"]

    # With no controller cap, custom workflows consider the full configured
    # input count while still ignoring disconnected gaps.
    needed = node.check_lazy_status(
        **common,
        active_extensions=None,
        extension_2=None,
        extension_6=None,
    )
    assert needed == ["extension_2", "extension_6"]


def test_stream_execution_skips_empty_extension_values_instead_of_requiring_contiguous_slots():
    source = STREAM.read_text(encoding="utf-8")
    body = source.split("class MiniMaxH3StreamLiveExtensionAVToVHS:", 1)[1]
    body = body.split("class MiniMaxH3FinalizeVHSOutput:", 1)[0]
    assert 'if name in kwargs and kwargs[name] is None:' in body
    assert 'if value is None:\n                continue' in body
    assert 'extension_{i} is required' not in body
    assert 'connect at least one extension latent' in body


def test_frontend_has_input_count_refresh_button_and_dynamic_socket_management():
    source = JS.read_text(encoding="utf-8")
    assert 'MiniMaxH3StreamLiveExtensionAVToVHS' in source
    assert 'MiniMaxH3StreamLiveMusicVideoToVHS' in source
    assert 'MiniMaxH3LastActiveVHSPreviewBarrier' in source
    assert 'prefix: "extension_"' in source
    assert 'prefix: "clip_"' in source
    assert 'prefix: "preview_"' in source
    assert 'socketType: "VHS_FILENAMES"' in source
    assert 'inferLegacyInputCount: true' in source
    assert '"Update inputs"' in source
    assert 'w.name === "input_count"' in source
    assert 'node.removeInput(i)' in source
    assert 'spec.socketType ?? "LATENT"' in source
    assert 'restoreLegacyInputCount' in source
    assert 'button.serialize = false' in source


def test_av_extension_example_uses_six_visible_inputs_and_keeps_controller_cap():
    data = json.loads(WF.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data["nodes"]}
    links = {l[0]: l for l in data["links"]}
    final = next(n for n in nodes.values() if n["type"] == "MiniMaxH3StreamLiveExtensionAVToVHS")
    assert final["widgets_values"][0] == 6
    assert final["widgets_values_named"]["input_count"] == 6
    assert "active_extensions" not in final["widgets_values_named"]
    for i in range(1, 7):
        inp = next(x for x in final["inputs"] if x["name"] == f"extension_{i}")
        assert inp["link"] is not None
    cap = next(x for x in final["inputs"] if x["name"] == "active_extensions")
    cap_link = links[cap["link"]]
    cap_source = nodes[cap_link[1]]
    assert cap_source.get("properties", {}).get("h3_av_param") == "active_extensions"


def test_final_stream_waits_for_preview_gate_before_requesting_latents():
    module = _load_stream_module()
    node = module.MiniMaxH3StreamLiveExtensionAVToVHS()
    common = dict(
        video_vae=object(), audio_vae=object(), start_mode="existing_video",
        input_count=6, context_frames=39, video_overlap_frames=39,
        source_fps=24.0, crop="disabled", filename_prefix="x", pix_fmt="yuv420p",
        crf=19, save_metadata=False, trim_to_audio=True, save_output=True,
        source_frames=None, source_audio=None, starter_latent=None,
        active_extensions=3,
        preview_gate=None,
        extension_1=None,
        extension_2=None,
        extension_3=None,
    )
    assert node.check_lazy_status(**common) == ["preview_gate"]

    common["preview_gate"] = ["preview-finished"]
    needed = node.check_lazy_status(**common)
    assert needed == ["source_frames", "source_audio", "extension_1", "extension_2", "extension_3"]


def test_preview_barrier_waits_only_for_highest_connected_active_preview():
    module = _load_stream_module()
    barrier = module.MiniMaxH3LastActiveVHSPreviewBarrier()

    # Preview 3 is the highest connected input inside the active cap. Preview 2
    # can also be connected/pending, but final assembly only needs to wait for
    # the last active preview.
    needed = barrier.check_lazy_status(
        input_count=6,
        active_extensions=4,
        preview_1=["done-1"],
        preview_2=None,
        preview_3=None,
    )
    assert needed == ["preview_3"]
    assert barrier.select(
        input_count=6,
        active_extensions=4,
        preview_1=["done-1"],
        preview_2=None,
        preview_3=["done-3"],
    ) == (["done-3"],)

    # Disabled/bypassed preview groups disappear from kwargs and are therefore
    # ignored. With no enabled preview the barrier is a harmless no-op.
    assert barrier.check_lazy_status(input_count=6, active_extensions=4) == []
    assert barrier.select(input_count=6, active_extensions=4) == ([],)

    # The visible Input Count is also a backend cap. A stale/legacy preview
    # socket above the configured count must not be requested.
    assert barrier.check_lazy_status(
        input_count=6,
        active_extensions=None,
        preview_7=None,
    ) == []
    assert barrier.check_lazy_status(
        input_count=20,
        active_clips=20,
        preview_19=None,
        preview_20=None,
    ) == ["preview_20"]


def test_final_sink_is_safe_when_upstream_final_stream_is_bypassed_or_disconnected():
    module = _load_stream_module()
    sink = module.MiniMaxH3FinalizeVHSOutput()
    assert "filenames" in sink.INPUT_TYPES()["optional"]
    assert sink.check_lazy_status() == []
    assert sink.finalize() == ()
    assert sink.check_lazy_status(filenames=None) == ["filenames"]
    assert sink.finalize(filenames=[]) == ()


def test_av_example_orders_last_preview_before_final_stream_and_has_bypass_safe_sink():
    data = json.loads(WF.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data["nodes"]}
    links = {l[0]: l for l in data["links"]}

    final = next(n for n in nodes.values() if n["type"] == "MiniMaxH3StreamLiveExtensionAVToVHS")
    barrier = next(n for n in nodes.values() if n["type"] == "MiniMaxH3LastActiveVHSPreviewBarrier")
    sink = next(n for n in nodes.values() if n["type"] == "MiniMaxH3FinalizeVHSOutput")

    assert barrier["widgets_values"] == [6]
    assert barrier["widgets_values_named"]["input_count"] == 6
    assert not any(x["name"] == "preview_7" for x in barrier["inputs"])

    gate_input = next(x for x in final["inputs"] if x["name"] == "preview_gate")
    gate_link = links[gate_input["link"]]
    assert gate_link[1] == barrier["id"]

    for i in range(1, 7):
        preview_input = next(x for x in barrier["inputs"] if x["name"] == f"preview_{i}")
        preview_link = links[preview_input["link"]]
        src = nodes[preview_link[1]]
        assert src["type"] == "VHS_VideoCombine"
        assert src.get("title") == f"Extension {i} - VHS Video Combine"

    final_out = final["outputs"][0]["links"]
    assert len(final_out) == 1
    assert links[final_out[0]][3] == sink["id"]
