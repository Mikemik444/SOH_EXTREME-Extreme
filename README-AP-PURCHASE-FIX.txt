SOH-EXTREME AP scrub/shop price fix - 2026-09-29

For the SOH_EXTREME-Extreme checkout already patched with AP Audit v2.
This is an add-on to that update; the previous gameplay fixes are retained.

SOURCE INSTALL
1. Extract the CONTENTS of SOH-EXTREME-AP-Purchase-Prices-Source-Patch.zip
   over E:\test\bb (your source root beside CMakeLists.txt and build.cmd).
   Merge folders and replace matching files.
2. Open a fresh Command Prompt in E:\test\bb and run build.cmd.
3. After BUILD COMPLETE, restart Archipelago/Universal Tracker and launch
   E:\test\bb\soh.exe.

The .patch file is for review/Git users; do not apply it after copying the
replacement files. Six source/test files are included. Your current v2
build.cmd and APWorld are suitable; no new seed is required for this fix.

READY-BUILT ALTERNATIVE
Close the game, then extract soh.exe and APCpp.dll from
SOH-EXTREME-AP-Purchase-Prices-Windows-x64.zip over both matching files in
your existing game folder. This executable includes the previous AP Audit
v2 fixes plus the price correction. Keep the existing assets and APWorld.
Use the source patch too if you plan to build the game again later.

CAUSE AND CORRECTION
AP sends exact scrub, shop, and merchant prices by location. The client
stored those as ordinary item prices, then changing the location's item
model reset them to the displayed item's default price, commonly zero.
Scrub actors could cache that zero; late scout responses could also make
the displayed price and cached payment amount disagree.

AP prices now have explicit location-price priority, survive model changes,
and load without waiting for scout responses. Scrubs and shops refresh
prices before caching/accepting a purchase so affordability and payment use
the same amount. Explicit zero prices remain zero. Shop and scrub settings
stay independent; this patch does not force scrubs to a particular price.
If your seed actually assigns a scrub zero rupees, it remains free.

VALIDATION
- Windows x64 Release rebuilt with MSVC 2022; APCpp.dll loaded successfully.
- Production price/placement and transaction functions passed controlled
  tests for local/remote items, stock-item models, ice-trap disguises,
  delayed scouts, stale actor caches, insufficient rupees, completed checks,
  zero-priced shops/scrubs, and normal local-save isolation.
- A real AP 0.6.7 world configured with zero-priced shops and 40-rupee scrubs
  generated those prices independently; all 36 scrub prices were preserved
  in exported slot data.
- The incremental patch was checked against the v2 source update, and ZIP
  contents/hashes were verified.

These are build and controlled code tests, not a live gameplay playthrough.
Detailed results are in VALIDATION-AP-PURCHASE-PRICES.json.

To rerun the price regression from a VS x64 developer terminal:
  python validation/test_ap_purchase_prices.py --output work/ap-purchase-tests
