# ComfyUI H3 Motion Context — MultiRef & Latent Masking

A ComfyUI custom-node pack and workflow collection for extending MiniMax H3 video generations with motion continuity, references, audio, and latent masking.

Update 6 reduces RAM and cache pressure during long-form final output, making out-of-memory errors less likely.

Update 7 adds arbitrary-position existing-video inserts, hard-preserved masked keyframes, and H3-aware AV noise-mask utilities. Update 7 was contributed by **Reithan** through [PR #3](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef/pull/3).

Modified fork of [NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

## Main workflows

### NEW - Music Video

Creates a sequence of H3 video clips around a single song.

Example Music Video you can recreate:
https://github.com/user-attachments/assets/33e22c59-d23f-4470-b52a-6fabb0e4a66b

A complete example with reference images and a song is included in:

`example_workflows/NEW - Music Video.json`

The example assets are in:

`example_workflows/assets/`

### NEW - AV Extension

Extends an existing video, or starts from a newly generated T2V/I2V clip and continues it through multiple H3 generations.

Open:

`example_workflows/NEW - AV Extension.json`

The repository also includes utility and legacy workflows for clip bridging, custom keyframes, and earlier Motion Context / hybrid continuation methods.

See [example_workflows/README.md](example_workflows/README.md) for the workflow guide.

## Update 7 — Arbitrary inserts and hard-masked keyframes

Update 7 was contributed by **Reithan** through [PR #3](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef/pull/3).

It adds:

- arbitrary-position preservation with `insert_frame` on `H3 Existing Video Masked Context`;
- `H3 Assemble Interior Insert` for frame/sample-exact source reassembly after interior preservation;
- `H3 Custom Keyframes (Masked)` for hard-preserved still-image anchors;
- `H3 Set AV Noise Mask` and `H3 Clear AV Noise Mask` for H3's separate video/audio mask streams.

`insert_frame` snaps down to H3's 17-frame video phase grid. Multiples of 51 also align exactly with the 40 Hz audio clock. Hard masked keyframes can merge with an existing nested H3 AV mask when they do not overlap an already protected video step; overlapping preservation requests raise explicitly instead of silently overwriting each other.

For H3 AV latents, use the H3 Set/Clear AV Noise Mask nodes when separate video/audio mask behavior matters; stock `Set Latent Noise Mask` does not preserve the same two-stream mask contract.

The merge-preparation servicing of PR #3 added mask-composability checks, overlap diagnostics, documentation cleanup, and regression-test repairs; the Update 7 feature set itself is credited to Reithan's PR.

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

If a workflow opens with missing nodes, install the required node pack and restart ComfyUI.

## Documentation

- [Workflow Guide](example_workflows/README.md) — how to use the included workflows
- [Technical Architecture](TECHNICAL_ARCHITECTURE.md) — implementation and technical details
- [Modifications](MODIFICATIONS.md) — detailed history of changes made in this fork

## Credits

Original project by [NikoDemon80](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

Update 7 — arbitrary-position inserts, hard masked keyframes, and H3 AV noise-mask utilities — was contributed by **Reithan** in [PR #3](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef/pull/3).

See [MODIFICATIONS.md](MODIFICATIONS.md) for additional attribution and implementation history.

## License

GPL-3.0. See [LICENSE](LICENSE).
