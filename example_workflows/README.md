# Example Workflows

## NEW - 2MP De-Rope Continuation — Working Example

`NEW - 2MP De-Rope Continuation - Working Example.json`

A focused Clip-1 + Extension-1 example for two-pass MiniMax H3 de-rope at 2MP. The continuation uses MAINodes `Jerk Oracle`, `Time Smear`, `Audio Smear`, and `Exact Recover`, plus the H3 latent upscaler.

This is intentionally a **working example rather than a tidy showcase workflow**; the underlying seam, fan, timing, and two-pass plumbing is left visible for inspection.

The seam path is deliberately mask-free at pass 2:

1. take the recovered final 39 frames of Clip 1;
2. fan them with the exact `hold_map_used` from Extension 1;
3. overwrite the beginning of the low-resolution smeared pass-2 init;
4. return the seam-nearest 39 fanned frames at native Clip-1 resolution plus their dynamic target offset;
5. use those frames as one native H3 Motion Context clip at that interior offset;
6. run the 2MP refinement pass and `Exact Recover`;
7. trim the duplicated real-time prefix from the first continuation stage and assemble with the existing exact AV extension nodes.

The guide offset is derived from the hold map at runtime; it is not a fixed frame number. This is conditioning placement, not latent preservation: `target_start` on `H3 Motion Context` is separate from Update 7 (2026-08-18), which introduced `insert_frame` on `H3 Existing Video Masked Context`.

Required external packs for this example include ComfyUI-MAINodes, ComfyUI-KJNodes, ComfyUI-SolAttn_triton, and Comfyui_Minimax_h3_latent_Upscaler.

The bundled example uses `assets/derope_continuation_reference.png`; copy that file into ComfyUI's `input/` folder before running the example, or replace the Load Image node with your own reference.

---

## NEW - V2V Latent Motion Transfer (with upscale and de-rope)

`NEW - V2V Latent Motion Transfer (with upscale and de-rope).json`

Transfers an existing source video's motion and timing into a new H3 generation, then refines it with de-rope and learned latent upscaling. This workflow is meant for **motion transfer rather than source-video restyling**: the source clip provides motion, pose, camera movement, and timing guidance, while the generation can replace the subject's appearance and identity through the normal H3 reference path.

### What the workflow does

The workflow runs in two passes:

1. **Pass 1: latent motion transfer.** The original source video/audio is used directly as the V2V and Ref2VA anchor. A first H3 generation is produced while preserving just enough source-latent structure to carry over motion and timing.
2. **Pass 2: upscale and de-rope refinement.** The pass-1 result is de-roped from generated x0, time-smeared for the second pass, upscaled in latent space, and refined again at the higher resolution.
3. **Final recovery.** `H3ExactRecover` restores the original 24-fps real-time timeline after de-rope processing, so the final clip preserves the intended playback speed and duration.

### Why the fractional mask matters

Keep the V2V stage's `BasicScheduler` denoise at `1.0`; V2V strength is controlled by the **H3 V2V Granular Fractional Denoise** node instead. The important control is `global_strength`, which sets a near-1 denoise mask over the source latent.

This is important because standard denoise handling would force a binary choice:

- preserve too much of the source latent and the result stays too close to the original clip; or
- generate too freely and the motion/performance guidance weakens or collapses.

The granular fractional path lets the workflow keep only a **faint residue** of the source latent inside the target latent. That faint residue is often enough to stabilize motion transfer, pose continuity, and timing while still allowing the subject and look to change.

### Recommended `global_strength` range

For this workflow, the practical range is usually **`0.996` to `0.9997`**. That narrow range is unusually important:

- **too low** (for example clearly below `0.996`) keeps too much of the source video latent, which can make the output cling to the original subject or composition;
- **too high** (approaching or effectively behaving like `1.0`) removes too much of the helpful source-latent residue and can weaken the transferred motion guidance;
- **around `0.9995`** is often a strong starting point, because it still leaves a tiny amount of source residue while giving the model enough freedom to replace identity and appearance.

If the source motion is **not transferring strongly enough**, decrease `global_strength` in small steps. A lower value preserves a little more of the source latent, which strengthens the motion/performance guide. Keep the changes small and tune against the specific source clip; the useful range is intentionally narrow.

Update 8's granular fractional-denoise support is what makes this usable: it carries the H3 denoise-mask values in FP32 and preserves near-1 values instead of collapsing them to plain `1.0`. Without that precision, settings such as `0.9995` would lose their intended meaning.

### Practical workflow notes

- The workflow already includes the second-pass de-rope and latent upscale stages; you do not need a separate refinement workflow after it.
- Streamed blocks are kept intentionally because this workflow is memory-heavy; removing them can easily push large runs into OOM territory even on a 5090, especially once de-rope multiplies the internal frame count.

The granular fractional V2V node (`H3V2VGranularFractionalDenoise`, displayed as `H3 V2V Granular Fractional Denoise`) is supplied by this MultiRef repository in Update 8 (started 2026-08-30).

This workflow additionally uses ComfyUI-MAINodes and the LBH-123-AI MiniMax H3 latent upscaler custom node.

---

## NEW - Music Video

`NEW - Music Video.json`

Creates a multi-clip music video around one song.

The included workflow comes with a complete example using the files in:

`example_workflows/assets/`

Copy the example images and song into your ComfyUI `input/` folder before running it.

### Main controls

**Active Clips**
Sets how many clip sections are used.

**Previews**
Controls which clip previews are generated.

**Reference Images**
Use the included references or replace them with your own.

**Master Song**
The song used by the workflow. Replace it with your own audio when starting a new project.

The workflow contains up to 20 clip sections. Only the number selected by **Active Clips** is used. Changing that count does not alter existing clip-sampler inputs, so cached clips can be reused while newly activated continuation clips are generated. The final streamer and last-active preview barrier both support a standalone dynamic **Input Count / Update inputs** interface; Music Video clip connections must remain a contiguous prefix so their visuals stay aligned to the master-song timeline.

---

## NEW - AV Extension

`NEW - AV Extension.json`

Continues a video across multiple H3 generations.

It can start from either:

- an existing video;
- a new T2V generation;
- a new I2V generation.

### Start mode

Choose whether the workflow begins with an existing video or generates the first clip itself. Existing Video uses the normal VHS loader so the source clip has an inline preview. Its VHS audio output is deliberately unconnected; **Keep source audio** extracts audio safely inside the MultiRef node and treats a genuinely silent container as silence, while **Regenerate with H3** protects the full source picture and synthesizes a replacement soundtrack.

### Extensions

Set **Active Extensions** to the number of continuation sections you want to run. The bundled controller automatically enables the required managed extension groups and bypasses the inactive ones; no manual group-enabling order is required.

The final **H3 Stream AV Extensions to VHS** node can also be reused in custom workflows. Set **Input Count**, click **Update inputs**, and connect any number of extension latents up to the configured count. Disconnected sockets are skipped. The optional `active_extensions` input is only a cap; leave it disconnected when using the node outside the bundled controller workflow. The bundled graph also routes the enabled per-extension VHS previews through a last-active preview barrier. The barrier has its own **Input Count / Update inputs** control, so only the preview sockets you need are shown; the highest enabled preview completes before the final stream starts. Its terminal sink is optional-input/bypass-safe.

### References

Optional reference images can be used when needed.

### Previews

Use the preview control to enable or disable extension previews.

---


## UTILITY - AV Bridge

`UTILITY - AV Bridge.json`

Creates a generated H3 audiovisual bridge between the ending of one source clip and the beginning of another. The workflow exposes shared target-frame, preserve-frame, and FPS controls. These values drive the bridge masks, visual overlap, output FPS, and the decoded generated-audio trim. The decoded generated-audio trim is calculated on H3's 40-Hz audio grid from the shared target-frame, preserve-frame, and FPS controls.

The default `192` target frames with `39` preserved frames per side at `24` fps still produce the same exact bridge middle: `1.625 s` protected audio at each side and `4.75 s` of generated middle audio.

---

The folder also contains utility workflows for AV bridging and custom keyframes, plus legacy Motion Context and hybrid workflows retained from earlier versions.

## More information

For implementation details, timing, masking, audio handling, and other internals, see:

[../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)

For the detailed update history, see:

[../MODIFICATIONS.md](../MODIFICATIONS.md)
