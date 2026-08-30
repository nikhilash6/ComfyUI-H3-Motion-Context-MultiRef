from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v2v_workflow_readme_explains_two_pass_motion_transfer_and_fractional_range():
    text = (ROOT / "example_workflows" / "README.md").read_text(encoding="utf-8")
    required = (
        "Pass 1: latent motion transfer.",
        "Pass 2: upscale and de-rope refinement.",
        "H3ExactRecover",
        "BasicScheduler` denoise at `1.0`",
        "faint residue",
        "0.996` to `0.9997`",
        "around `0.9995`",
        "not transferring strongly enough",
        "decrease `global_strength`",
        "FP32",
        "OOM territory even on a 5090",
    )
    for item in required:
        assert item in text


def test_workflow_readme_avoids_stale_v2v_extension_and_bridge_guidance():
    text = (ROOT / "example_workflows" / "README.md").read_text(encoding="utf-8")
    v2v = text.split("## NEW - V2V Latent Motion Transfer", 1)[1].split("\n---", 1)[0]
    assert "custom-node folder" not in v2v.lower()
    assert "historical" not in v2v.lower()
    assert "0.3` instead of `0.4`" not in text
    assert "Extensions should be enabled in order" not in text
    assert "independent" not in text.lower() or "hard-coded seconds" not in text.lower()
    assert "automatically enables the required managed extension groups" in text
