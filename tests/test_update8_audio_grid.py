"""Regression tests for Update-7 V2V source-audio grid alignment.

These tests deliberately model ComfyUI's current generic VAE center-crop: audio
input that is not a multiple of the 800-sample H3 hop is narrowed to a floor
multiple before MiniMaxH3AudioVAE.encode() sees it.  The V2V node should avoid
that preprocessing loss by supplying an exact target-grid PCM span up front.
"""

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import torch

ROOT = Path(__file__).resolve().parents[1]
pkg = types.ModuleType("u7audiopkg")
pkg.__path__ = [str(ROOT)]
sys.modules["u7audiopkg"] = pkg
spec = importlib.util.spec_from_file_location(
    "u7audiopkg.h3_v2v_fractional", ROOT / "h3_v2v_fractional.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ComfyStyleH3AudioVAE:
    audio_sample_rate = 32000
    first_stage_model = SimpleNamespace(samples_per_latent=800)

    def __init__(self):
        self.last_input_samples = None
        self.last_crop_offset = None
        self.last_cropped_samples = None

    def encode(self, x):
        # x is generic Comfy VAE input [B, samples, channels].
        length = int(x.shape[1])
        ratio = 800
        cropped = (length // ratio) * ratio
        offset = (length % ratio) // 2
        self.last_input_samples = length
        self.last_crop_offset = offset
        self.last_cropped_samples = cropped
        # The H3 encoder itself would then see exactly `cropped` samples and
        # return one latent for every 800 samples.
        return torch.zeros((1, 32, 2, cropped // ratio), dtype=torch.float32)


def _audio(samples):
    return {
        "waveform": torch.arange(samples, dtype=torch.float32).reshape(1, 1, -1),
        "sample_rate": 32000,
    }


def _picture_samples(frames):
    return round(frames / 24 * 32000)


def _target_steps(frames):
    return round(frames / 24 * 40)


def test_historical_328_frame_case_explains_546_to_547_and_center_shift():
    frames = 328
    picture = _picture_samples(frames)
    target = _target_steps(frames)
    assert picture == 437333
    assert target == 547

    # This is what the old path effectively handed to generic VAE.encode().
    vae = ComfyStyleH3AudioVAE()
    old = vae.encode(torch.zeros((1, picture, 2)))
    assert old.shape[-1] == 546
    # Generic Comfy preprocessing removes remainder//2 from the beginning too.
    assert vae.last_crop_offset == 266

    # New path constructs exactly the target H3 audio grid first.
    pcm, diag = module._audio_slice_for_target_grid(
        _audio(picture), vae, start_frame=0, frame_count=frames, target_audio_steps=target
    )
    assert pcm.shape[-1] == target * 800 == 437600
    assert diag["grid_minus_picture_samples"] == 267
    assert diag["pcm_tail_pad_samples"] == 267

    new = vae.encode(pcm.movedim(1, -1))
    assert new.shape[-1] == target
    assert vae.last_crop_offset == 0


def test_round_down_case_is_also_start_aligned_not_center_cropped():
    # 56 H3 frames map to 93.333 audio ticks -> target rounds DOWN to 93.
    # The old exact-picture path happened to return the right token count, but
    # generic VAE preprocessing still shifted its start by 133 samples (~4.2 ms).
    frames = 56
    picture = _picture_samples(frames)
    target = _target_steps(frames)
    assert picture == 74667
    assert target == 93

    vae = ComfyStyleH3AudioVAE()
    old = vae.encode(torch.zeros((1, picture, 2)))
    assert old.shape[-1] == target
    assert vae.last_crop_offset == 133

    # Give more than enough source audio. The exact target-grid slice should be
    # 74,400 samples and should start at the requested timeline origin.
    pcm, diag = module._audio_slice_for_target_grid(
        _audio(picture + 2000), vae, start_frame=0, frame_count=frames, target_audio_steps=target
    )
    assert pcm.shape[-1] == 74400
    assert diag["grid_minus_picture_samples"] == -267
    assert diag["pcm_tail_pad_samples"] == 0
    new = vae.encode(pcm.movedim(1, -1))
    assert new.shape[-1] == target
    assert vae.last_crop_offset == 0


def test_integral_case_needs_no_adjustment():
    # 39 frames -> exactly 65 audio ticks.
    frames = 39
    target = _target_steps(frames)
    picture = _picture_samples(frames)
    assert target == 65
    assert picture == 52000 == target * 800

    vae = ComfyStyleH3AudioVAE()
    pcm, diag = module._audio_slice_for_target_grid(
        _audio(picture), vae, start_frame=0, frame_count=frames, target_audio_steps=target
    )
    assert pcm.shape[-1] == picture
    assert diag["grid_minus_picture_samples"] == 0
    assert diag["pcm_tail_pad_samples"] == 0


def test_nonzero_start_uses_absolute_timeline_and_real_lookahead_when_available():
    # For a selected interval in the middle of a longer source, the rounded-up
    # grid should consume real source audio beyond the picture endpoint instead
    # of padding it.
    start = 17
    frames = 328
    target = _target_steps(frames)
    start_sample = round(start / 24 * 32000)
    grid_end = start_sample + target * 800
    source = _audio(grid_end + 1000)
    vae = ComfyStyleH3AudioVAE()

    pcm, diag = module._audio_slice_for_target_grid(
        source, vae, start_frame=start, frame_count=frames, target_audio_steps=target
    )
    assert pcm.shape[-1] == target * 800
    assert diag["pcm_tail_pad_samples"] == 0
    # The ramp lets us prove the slice begins exactly at the requested origin.
    assert pcm[0, 0, 0].item() == float(start_sample)


def test_real_audio_shortage_is_not_hidden_as_grid_rounding():
    frames = 328
    picture = _picture_samples(frames)
    target = _target_steps(frames)
    vae = ComfyStyleH3AudioVAE()

    # Expected grid overhang is only 267 samples. Being 2000 samples short of
    # picture duration is a real source-audio problem and must still fail.
    source = _audio(picture - 2000)
    try:
        module._audio_slice_for_target_grid(
            source, vae, start_frame=0, frame_count=frames, target_audio_steps=target
        )
    except ValueError as exc:
        assert "only 267 samples are explained" in str(exc)
    else:
        raise AssertionError("genuine source-audio shortfall was silently padded")


def test_structure_no_longer_fabricates_or_trims_latent_audio_tokens():
    text = (ROOT / "h3_v2v_fractional.py").read_text(encoding="utf-8")
    assert "torch.nn.functional.pad(source_audio_latent" not in text
    assert "source_audio_latent[..., -target_audio_steps:]" not in text
    assert "source_audio_latent[..., :target_audio_steps]" not in text
    shared = (ROOT / "h3_audio_grid.py").read_text(encoding="utf-8")
    assert "audio-VAE wrapper/encoder contract mismatch" in shared
    assert '"audio_one_latent_step_pad"' not in text

    motion = (ROOT / "nodes.py").read_text(encoding="utf-8")
    assert "_unused_overhang" not in motion
    assert "caller compensates the placement" not in motion


def test_repo_audio_encode_paths_are_centralized_or_proven_exact_boundary():
    direct = []
    for path in ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "audio_vae.encode(" in text:
            direct.append(path.name)
    assert direct == ["h3_audio_grid.py"]

    # ExistingVideoMaskedContext is mathematically exact-grid already, but it
    # also routes through the shared strict helper for one repo-wide contract.
    existing = (ROOT / "existing_video_extension.py").read_text(encoding="utf-8")
    assert "while run >= 5 and not is_exact_av_boundary(run):" in existing
    assert "context_samples != grid_samples" in existing
    assert "encode_exact_audio_grid(" in existing
