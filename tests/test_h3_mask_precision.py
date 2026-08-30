"""Lazy/self-retiring tests for Update 8 H3 mask precision compatibility."""

import importlib.util
import math
import sys
import types
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_fake_module_namespace():
    prefixes = ("precpkg", "comfy")
    before = {
        name: module
        for name, module in sys.modules.items()
        if name == prefixes[0] or name.startswith(prefixes[0] + ".")
        or name == prefixes[1] or name.startswith(prefixes[1] + ".")
    }
    yield
    for name in list(sys.modules):
        if (
            name == prefixes[0] or name.startswith(prefixes[0] + ".")
            or name == prefixes[1] or name.startswith(prefixes[1] + ".")
        ):
            sys.modules.pop(name, None)
    sys.modules.update(before)


def _pack_latents(latents):
    shapes = [x.shape for x in latents]
    return torch.cat([x.reshape(x.shape[0], 1, -1) for x in latents], dim=-1), shapes


def _unpack_latents(combined, shapes):
    out = []
    for shape in shapes:
        n = math.prod(shape[1:])
        out.append(combined[:, :, :n].reshape([combined.shape[0]] + list(shape)[1:]))
        combined = combined[:, :, n:]
    return out


def install_fake(native_precision=False, levels=None):
    for name in list(sys.modules):
        if name == "precpkg" or name.startswith("precpkg.") or name == "comfy" or name.startswith("comfy."):
            sys.modules.pop(name, None)

    pkg = types.ModuleType("precpkg")
    pkg.__path__ = [str(ROOT)]
    sys.modules["precpkg"] = pkg

    compat = types.ModuleType("precpkg.h3_compat")
    compat.ensure_existing_video_compat = lambda: True
    sys.modules["precpkg.h3_compat"] = compat

    comfy = types.ModuleType("comfy")
    model_base = types.ModuleType("comfy.model_base")
    model_management = types.ModuleType("comfy.model_management")
    utils = types.ModuleType("comfy.utils")
    ldm = types.ModuleType("comfy.ldm")
    minimax = types.ModuleType("comfy.ldm.minimax")
    h3m = types.ModuleType("comfy.ldm.minimax.model")

    def cast_to_device(x, device, dtype):
        if hasattr(x, "to"):
            return x.to(device=device, dtype=dtype if dtype is not None else x.dtype)
        return x

    model_management.cast_to_device = cast_to_device
    utils.pack_latents = _pack_latents
    utils.unpack_latents = _unpack_latents

    def convert_tensor(extra, dtype, device):
        if hasattr(extra, "dtype"):
            if extra.dtype != torch.int and extra.dtype != torch.long:
                extra = model_management.cast_to_device(extra, device, dtype)
            else:
                extra = model_management.cast_to_device(extra, device, None)
        return extra

    class BaseModel:
        def _apply_model(self, x, t, c_concat=None, c_crossattn=None, control=None, transformer_options={}, **kwargs):
            sigma = t
            xc = self.model_sampling.calculate_input(sigma, x)
            context = c_crossattn
            dtype = self.get_dtype_inference()
            xc = xc.to(dtype)
            device = xc.device
            t = self.model_sampling.timestep(t).float()
            if context is not None:
                context = model_management.cast_to_device(context, device, dtype)
            extra_conds = {}
            for o in kwargs:
                extra = kwargs[o]
                if native_precision and o in ("denoise_mask", "audio_denoise_mask") and hasattr(extra, "dtype"):
                    extra = model_management.cast_to_device(extra, device, torch.float32)
                elif hasattr(extra, "dtype"):
                    extra = convert_tensor(extra, dtype, device)
                elif isinstance(extra, list):
                    ex = []
                    for ext in extra:
                        ex.append(convert_tensor(ext, dtype, device))
                    extra = ex
                extra_conds[o] = extra
            t = self.process_timestep(t, x=x, **extra_conds)
            model_output = self.diffusion_model(xc, t, context=context, control=control, transformer_options=transformer_options, **extra_conds)
            return self.model_sampling.calculate_denoised(sigma, model_output.float(), x)

    class MiniMaxH3(BaseModel):
        def _pool_masks_to_token_grid(self, masks):
            return masks

        def _token_grid_masks(self, denoise_mask, latent_shapes):
            masks = utils.unpack_latents(denoise_mask, latent_shapes)
            quant_levels = float(levels) if levels is not None else (4096.0 if native_precision else 256.0)
            return [torch.ceil(mask * quant_levels) / quant_levels for mask in self._pool_masks_to_token_grid(masks)]

        def _denoise_mask_values(self, denoise_mask, latent_shapes):
            masks = self._token_grid_masks(denoise_mask, latent_shapes)
            out = {}
            cutoff = 1.0 if native_precision else 1.0 - 1e-3
            if torch.amin(masks[0]).item() < cutoff:
                out["denoise_mask"] = masks[0][:1, :1].clone()
            if torch.amin(masks[1]).item() < cutoff:
                out["audio_denoise_mask"] = masks[1][:1].amax(dim=1, keepdim=True)
            return out

    if native_precision:
        def mask_row_values(mask, latent_t, lat_h, lat_w):
            values = mask.reshape(-1)
            if bool((values >= 1.0).all()):
                return None
            return values

        class MiniMaxH3Model:
            def _forward(self, x=None, timestep=None, context=None, transformer_options={}, minimax_payload=None, denoise_mask=None, audio_denoise_mask=None, **kwargs):
                if audio_denoise_mask is not None:
                    m = audio_denoise_mask[0, 0].to(torch.float32).reshape(-1)
                    if not bool((m >= 1.0).all()):
                        return m
                return None
    else:
        def mask_row_values(mask, latent_t, lat_h, lat_w):
            values = mask.reshape(-1)
            if bool((values >= 1.0 - 1e-3).all()):
                return None
            return values

        class MiniMaxH3Model:
            def _forward(self, x=None, timestep=None, context=None, transformer_options={}, minimax_payload=None, denoise_mask=None, audio_denoise_mask=None, **kwargs):
                if audio_denoise_mask is not None:
                    m = audio_denoise_mask[0, 0].to(torch.float32).reshape(-1)
                    if not bool((m >= 1.0 - 1e-3).all()):
                        return m
                return None

    model_base.BaseModel = BaseModel
    model_base.MiniMaxH3 = MiniMaxH3
    model_base.convert_tensor = convert_tensor
    model_base.torch = torch
    model_base.utils = utils
    model_base.comfy = comfy

    h3m.mask_row_values = mask_row_values
    h3m.MiniMaxH3Model = MiniMaxH3Model
    h3m.torch = torch

    comfy.model_base = model_base
    comfy.model_management = model_management
    comfy.utils = utils
    comfy.ldm = ldm
    ldm.minimax = minimax
    minimax.model = h3m

    sys.modules.update({
        "comfy": comfy,
        "comfy.model_base": model_base,
        "comfy.model_management": model_management,
        "comfy.utils": utils,
        "comfy.ldm": ldm,
        "comfy.ldm.minimax": minimax,
        "comfy.ldm.minimax.model": h3m,
    })

    spec = importlib.util.spec_from_file_location(
        "precpkg.h3_mask_precision", ROOT / "h3_mask_precision.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, MiniMaxH3, h3m


def test_current_style_core_gets_precision_patch_lazily():
    module, cls, h3m = install_fake(native_precision=False)
    before = module.capability_status()
    assert not before["precision_ready"]
    assert before["probe_token_value"] == 1.0
    assert not before["fp32_condition_transport"]
    assert before["fp32_probe_value"] == 1.0

    after = module.ensure_h3_mask_precision()
    assert after["precision_ready"]
    assert after["token_grid_patch_active"]
    assert after["mask_values_patch_active"]
    assert after["video_row_patch_active"]
    assert after["audio_row_patch_active"]
    assert after["fp32_transport_patch_active"]
    assert abs(after["probe_token_value"] - 0.99951171875) < 1e-12
    assert abs(after["probe_token_value_09997"] - 0.999755859375) < 1e-12
    assert abs(after["fp32_probe_value"] - 0.99951171875) < 1e-12

    # Idempotent second call: same functions remain installed.
    token = cls._token_grid_masks
    inner = h3m.MiniMaxH3Model._forward
    module.ensure_h3_mask_precision()
    assert cls._token_grid_masks is token
    assert h3m.MiniMaxH3Model._forward is inner


def test_future_native_precision_self_retires_without_patch():
    module, cls, h3m = install_fake(native_precision=True)
    token = cls._token_grid_masks
    inner = h3m.MiniMaxH3Model._forward
    apply = cls._apply_model
    before = module.capability_status()
    assert before["precision_ready"]
    after = module.ensure_h3_mask_precision()
    assert after["precision_ready"]
    assert cls._token_grid_masks is token
    assert h3m.MiniMaxH3Model._forward is inner
    assert cls._apply_model is apply
    assert not after["token_grid_patch_active"]
    assert not after["fp32_transport_patch_active"]


def test_quantizer_expected_09995_value():
    module, _, _ = install_fake(native_precision=False)
    x = torch.tensor([0.9995], dtype=torch.float32)
    got = float(module.quantize_4096(x)[0])
    assert got == 0.99951171875


def test_2048_grid_is_not_considered_equivalent_precision():
    module, _, _ = install_fake(native_precision=True, levels=2048)
    status = module.capability_status()
    assert status["probe_token_value"] == 0.99951171875
    assert status["probe_token_value_09997"] == 1.0
    assert not status["token_grid_precision"]
    assert not status["precision_ready"]
