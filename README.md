# ComfyUI H3 Motion Context — MultiRef & Latent Masking

A ComfyUI custom-node pack and workflow collection for extending MiniMax H3 video generations with motion continuity, references, audio, and latent masking.


Update 7 (**dated 2026-08-18; merged to main 2026-08-30**) adds arbitrary-position existing-video inserts, hard-preserved masked keyframes, and H3-aware AV noise-mask utilities. Update 7 was contributed by **Reithan** through [PR #3](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef/pull/3).

Update 8 (**released 2026-08-30**) adds the user-facing features and bug fixes summarized below.

See [MODIFICATIONS.md](MODIFICATIONS.md) for the complete dated update history.

Modified fork of [NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

## Main workflows

### NEW - V2V Latent Motion Transfer (with upscale and de-rope)

Transfers motion, camera timing, and performance from an existing source video through fractional H3 V2V denoise, then applies generated-x0 de-rope, learned latent upscaling, and a second refinement pass before exact timeline recovery.

The integrated V2V node is **H3 V2V Granular Fractional Denoise**; “granular” refers to its continuous H3 denoise-mask levels rather than a binary preserve/generate mask.

Open:

`example_workflows/NEW - V2V Latent Motion Transfer (with upscale and de-rope).json`


### NEW - 2MP De-Rope Continuation — Working Example

Demonstrates seamless two-pass continuation when de-rope stretches the protected seam into a variable-length smear. The workflow fans the recovered tail with the exact `H3 Time Smear` hold map, repairs the second-pass V2V baseline, and places one native 39-frame `H3 Motion Context` guide at the dynamically calculated interior seam offset. The second pass remains mask-free.

This is a **working example**, not a tidied showcase graph: the seam/timing plumbing is intentionally left exposed so the dynamic de-rope continuation path can be inspected and modified.

Open:

`example_workflows/NEW - 2MP De-Rope Continuation - Working Example.json`

### NEW - Music Video

Creates a sequence of H3 video clips around a single song.

Example Music Video you can recreate:
https://github.com/user-attachments/assets/33e22c59-d23f-4470-b52a-6fabb0e4a66b

A complete example with reference images and a song is included in:

`example_workflows/NEW - Music Video.json`

The final Music Video streamer is modular: set **Input Count**, click **Update inputs**, and use a contiguous `clip_1...clip_N` prefix. The bundled controller mirrors **Active Clips** into a cache-isolated internal parameter, so changing the active clip count does not alter existing sampler inputs; already-generated clips remain cache-reusable while newly activated continuation clips are added. The last enabled clip preview is explicitly completed before final assembly begins.

The example assets are in:

`example_workflows/assets/`

### NEW - AV Extension

Extends an existing video, or starts from a newly generated T2V/I2V clip and continues it through multiple H3 generations.
Existing Video keeps the normal VideoHelperSuite loader/preview, while its lazy VHS audio socket stays unconnected. The AV source-audio policy safely preserves the selected file's soundtrack (or exact-duration silence for a silent container) or can regenerate the complete source soundtrack with H3.
The final H3-to-VHS streamer is modular: set **Input Count**, click **Update inputs**, and connect the extension sampler latents you want. Empty extension sockets are skipped; the bundled controller still caps execution to the active extension count. In the bundled workflow, the highest enabled extension VHS preview is completed before final assembly begins, and bypassing/disconnecting the final streamer leaves a safe no-op terminal sink instead of a prompt error.

Open:

`example_workflows/NEW - AV Extension.json`

The repository also includes utility and legacy workflows for clip bridging, custom keyframes, and earlier Motion Context / hybrid continuation methods.

See [example_workflows/README.md](example_workflows/README.md) for the workflow guide.

## Update 7 — Arbitrary inserts and hard-masked keyframes — 2026-08-18

Update 7 was contributed by **Reithan** through [PR #3](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef/pull/3). The PR changelog entry is dated **2026-08-18**; it was merged into `main` on **2026-08-30**.

It adds:

- arbitrary-position preservation with `insert_frame` on `H3 Existing Video Masked Context`;
- `H3 Assemble Interior Insert` for frame/sample-exact source reassembly after interior preservation;
- `H3 Custom Keyframes (Masked)` for hard-preserved still-image anchors;
- `H3 Set AV Noise Mask` and `H3 Clear AV Noise Mask` for H3's separate video/audio mask streams.

`insert_frame` snaps down to H3's 17-frame video phase grid. Multiples of 51 also align exactly with the 40 Hz audio clock. Hard masked keyframes can merge with an existing nested H3 AV mask when they do not overlap an already protected video step; overlapping preservation requests raise explicitly instead of silently overwriting each other.

For H3 AV latents, use the H3 Set/Clear AV Noise Mask nodes when separate video/audio mask behavior matters; stock `Set Latent Noise Mask` does not preserve the same two-stream mask contract.

The merge-preparation servicing of PR #3 added mask-composability checks, overlap diagnostics, documentation cleanup, and regression-test repairs; the Update 7 feature set itself is credited to Reithan's PR.

## Update 8 — released 2026-08-30

Update 8 focuses on making long-form H3 generation more reusable, predictable, and flexible while adding fractional V2V and de-rope-aware continuation. Important changes:

- **Changing the controller clip/extension count no longer forces earlier generated clips to regenerate.** `Active Clips` / `Active Extensions` are mirrored into cache-isolated internal execution parameters instead of becoming sampler inputs. Previously generated sampler branches therefore keep the same input hashes and remain cache-reusable; increasing the count activates the newly requested continuation work instead of invalidating the earlier clips.
- **Final AV/Music assembly no longer requires every predefined group/socket to be connected.** `H3 Stream AV Extensions to VHS` and `H3 Stream Final Music Video to VHS` expose **Input Count** plus **Update inputs**. AV Extension skips disconnected `extension_N` sockets, so a custom workflow can assemble only the extension groups that are actually connected. Music Video accepts unused trailing sockets while still rejecting middle holes, because compacting a middle clip would move visuals against the unchanged master-song timeline.
- **Preview scheduling is deterministic.** `H3 Last Active VHS Preview Barrier` makes the highest enabled intermediate preview finish before final assembly requests the clip latents, so previews appear in the intended generation order rather than being overtaken by the final stream. The VHS refresh workaround also reloads completed previews when VideoHelperSuite reuses the same temporary filename.
- **Added a complete V2V motion-transfer workflow.** `NEW - V2V Latent Motion Transfer (with upscale and de-rope)` takes an existing source video as a motion/performance guide, transfers that motion and timing to new reference-driven subjects, applies generated-x0 de-rope, performs learned latent upscaling, and finishes with a second refinement pass plus exact timeline recovery. Its first pass uses **H3 V2V Granular Fractional Denoise** so a very small amount of source-latent structure can remain as a motion guide while the model still has enough denoise freedom to replace identity and appearance.
- **Added `H3 V2V Granular Fractional Denoise`.** V2V source strength is carried by H3's denoise mask instead of by lowering sampler denoise; the Pass-1 `BasicScheduler` remains at `1.0`. Granular mask values provide continuous preserve→generate control, including useful near-1 values such as `0.9995`.
- **Fractional-mask precision compatibility is applied lazily and only when needed.** When the V2V node executes, Update 8 probes the installed ComfyUI H3 implementation. If native behavior is insufficient, the runtime compatibility layer quantizes H3 token-mask values on a **1/4096** grid, changes the video/audio shortcut so only an exact `1.0` means fully generative, and keeps `denoise_mask` / `audio_denoise_mask` in **FP32** as they are transported into the H3 diffusion model. This prevents near-1 strengths from being rounded or thresholded into `1.0`. If upstream ComfyUI already provides equivalent behavior, no precision patch is installed; the runtime patch is H3-specific and disappears on restart.
- **Exact H3 40 Hz audio-grid handling is shared across the new paths.** PCM is constructed to the exact number of H3 audio latent cells before AudioVAE encode, avoiding generic VAE center-crop/endpoint drift and keeping final seam timing frame-derived.
- **Added de-rope-aware seamless continuation.** `H3 Motion Context` gains a `target_start` placement control and the new `H3 Fan Recovered Context` node uses the exact `H3 Time Smear` hold map to fan/recover the previous seam, repair the smeared second-pass baseline, and calculate the native guide's dynamic interior offset. The bundled **2MP De-Rope Continuation — Working Example** demonstrates this path.
- **AV Bridge timing is calculated from shared controls.** Preserve frames, target frames, and FPS drive both visual overlap and H3-grid audio trimming from the same controls.

These are the current high-level changes; [MODIFICATIONS.md](MODIFICATIONS.md) contains the complete dated step history and [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) documents the implementation details.

## Installation

Clone the repository into ComfyUI's `custom_nodes` directory:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef.git
```

Restart ComfyUI and refresh the browser.

MiniMax H3 model files are not included.

## Dependencies

Some included workflows use:

- ComfyUI-VideoHelperSuite
- ComfyUI-KJNodes
- rgthree-comfy
- ComfyUI-MAINodes (used by the V2V and 2MP de-rope examples)
- ComfyUI-SolAttn_triton (used by the 2MP de-rope continuation example)
- Comfyui_Minimax_h3_latent_Upscaler (used by the V2V learned latent-upscale stage)

If a workflow opens with missing nodes, install the required node pack and restart ComfyUI.

## Documentation

- [Workflow Guide](example_workflows/README.md) — how to use the included workflows
- [Technical Architecture](TECHNICAL_ARCHITECTURE.md) — implementation and technical details
- [Modifications](MODIFICATIONS.md) — detailed history of changes made in this fork

## Credits

Original project by [NikoDemon80](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

Update 7 (2026-08-18) — arbitrary-position inserts, hard masked keyframes, and H3 AV noise-mask utilities — was contributed by **Reithan** in [PR #3](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef/pull/3).

See [MODIFICATIONS.md](MODIFICATIONS.md) for additional attribution and implementation history.

## License

GPL-3.0. See [LICENSE](LICENSE).
