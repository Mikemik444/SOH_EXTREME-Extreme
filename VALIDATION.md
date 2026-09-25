# 0.11.21d validation

- `python -m py_compile` succeeded for the modified AP world source.
- Native transformation audit found exactly 66 target house-pot rules:
  - Kokiri Forest house interiors: 5
  - Market house interiors: 58
  - Lon Lon Ranch Talon's House: 3
- Every transformed native rule retains `CanBreakPots()` (and therefore Pot Soul) but additionally requires at least one non-explosive indoor break/lift method.
- The AP post-pass uses the same residential families and its strict branch contains no Bomb Bag/Bombchu/explosive rule.
- `EnemySoulDraw.cpp` no longer passes the `__OTR__...` resource-name token directly to `gDPLoadTextureBlock`; it resolves the resource with `ResourceMgr_LoadTexOrDListByName()` and loads the returned texture data.

Not performed: full MSVC build, live renderer capture, or complete seed simulation.
