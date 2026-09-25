SOH-EXTREME targeted patch

Extract this ZIP over the ROOT of the SOH-EXTREME checkout that the supplied files came from.
Only changed source files are included.

Changes included:
- Lost Woods Underwater Shortcut Rupees require Golden Scale / 2 Progressive Scale levels.
- Deku Theater is Shovel-gated when Shovel shuffle is enabled.
- Central tracker/logic gate blocks every SCENE_GROTTOS check until Shovel is obtained.
- Zora's River Near Open Grotto PoH uses the cucco/Animal Soul route.
- Gerudo Valley Waterfall PoH requires cucco/Animal Soul or swimming access.
- Market Wonder Night Balcony 1/2 require Flow of Time when time is shuffled.
- Enemy Soul is now Off / Gone Until Found / Invincible Until Found.
- Invincible enemies stay alive and receive a dark lock filter until Enemy Soul is found.
- Gone mode removes ordinary enemies until Enemy Soul is found.
- Missing NPC Soul now stops NPC actor updates, preventing guards/NPC AI from acting.

APWorld:
BUILD_FIXED_APWORLD.py patches your current soh_extreme_*.apworld and writes soh_extreme_fixed.apworld.
Place the current APWorld beside the script before running APPLY_PATCH.cmd.
