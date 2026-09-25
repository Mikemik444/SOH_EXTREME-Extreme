# SOH-EXTREME readable enemy portraits

47 high-resolution pickup textures are recomposed from the supplied original enemy
portraits, with the existing shared soul silhouette kept in the background. No new
enemy models, fonts or original game archives are distributed.

The 128x128 images are separate from the legacy 32x32 message/tracker images.
The game uses bounded, overlapping texture tiles to preserve detail without an
oversized texture block. The one-texel gutters provide bilinear filtering samples
at tile edges. The portrait is unlit, camera-facing and 64 units wide (formerly 48).
The other soul kinds continue to use their existing renderers.

The PNGs are already built; Python is NOT needed to apply/build the game patch.
To reproduce the textures from the repository root with Python, Pillow and NumPy:

```sh
python tools/soul_portraits_hq/rebuild_portraits.py --output .
```

Copy `soh/assets/custom/textures/parameter_static/gExtremeSoul*.rgba32.png` into
`assets/custom/textures/parameter_static/` when root/assets is a separate directory.
The patch installer does this automatically. Do not change the old 32px resource
names to point at 128px files: message and HUD code still uses the legacy sizes.

See `ASSET-NOTES.md` for provenance. No ownership of the original artwork is claimed.
