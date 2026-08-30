from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODES = (ROOT / "nodes.py").read_text(encoding="utf-8")
V2V = (ROOT / "h3_v2v_fractional.py").read_text(encoding="utf-8")
PREC = (ROOT / "h3_mask_precision.py").read_text(encoding="utf-8")


def test_fractional_v2v_node_is_registered_under_release_name():
    assert '"H3V2VGranularFractionalDenoise"' in NODES
    assert 'H3 V2V Granular Fractional Denoise' in NODES
    assert 'H3V2VNativeFractionalMaskDebugSource' not in NODES
    assert 'H3V2VFractionalDenoise' not in NODES
    assert 'H3 V2V Fractional Denoise' not in NODES


def test_precision_module_is_lazy_from_v2v_execution():
    assert "from .h3_mask_precision import" not in NODES
    assert "from .h3_mask_precision import capability_status, ensure_h3_mask_precision" in V2V
    assert "def prepare(" in V2V


def test_scheduler_semantics_and_precision_contract_are_explicit():
    assert "BasicScheduler denoise must remain 1.0" in V2V
    assert "4096.0" in PREC
    assert '"denoise_mask"' in PREC
    assert '"audio_denoise_mask"' in PREC
