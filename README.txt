SOH-EXTREME – Castle Grounds left/right torch Wonder check logic fix

Corrects BOTH checks:
  Hc Wonder Left Torch [Child]
  Hc Wonder Right Torch [Child]

Requirements for each check, independent of the path used to enter the region:
  - Swim (in native SoH this is RG_BRONZE_SCALE / RAND_INF_CAN_SWIM;
    in Archipelago it is Swim if Shuffle Swim is on, otherwise innate)
  - Usable Fairy Slingshot (age/cross-age rules still apply)
  - A physical castle approach: Climb OR usable Hookshot/Longshot

Removed the previous Boomerang and optional void-out alternatives for
these TWO checks only. Other moat/castle checks are unchanged.

Included files:
  soh/Enhancements/randomizer/location_access/overworld/castle_grounds.cpp
  soh_extreme.apworld
  tests/test_castle_torch_requirements.py

Install:
  1. Extract over E:\test\bb\ so the C++ file replaces the matching source.
  2. Replace C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
     (or the custom worlds path you already use) with the bundled APWorld.
  3. Rebuild SoH and restart the Archipelago tracker to load new rules.

Based on: latest November 22 GF-upper-reachability APWorld, with only the
castle torch rule changed; castle_grounds.cpp from last uploaded full
source bundle, with only the two torch check conditions changed.
This does not alter item placement or entrance mapping of an existing seed.
Existing saves may still display checks as in logic until tracker reload.

Validation: APWorld ZIP integrity and Python parse; source requirements
regression test. No Windows C++ build or in-game check was performed.
