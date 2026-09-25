$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$File = Join-Path $Root 'soh\Enhancements\randomizer\MegaSouls.cpp'

if (-not (Test-Path -LiteralPath $File)) {
    throw "Could not find $File. Extract this patch into the SOH-EXTREME source root, for example E:\test\bb."
}

$Text = [IO.File]::ReadAllText($File)
$Original = $Text

# ---------------------------------------------------------------------------
# 1. Add a per-pickup age counter. This counts actor/gameplay updates.
#    Ship's game logic runs at the original OoT update rate, so 100 updates is
#    approximately five seconds even when visual interpolation is 60 FPS.
# ---------------------------------------------------------------------------
if ($Text -notmatch 'uint16_t\s+ageFrames\s*=\s*0') {
    $StructWithWater = @'
struct EnemyDefeatDropIdentity {
    int32_t placementIndex = -1;
    int64_t locationId = -1;

    // Octorock Enemy Defeat checks are earned over water. Their physical AP
    // pickup must remain at the water surface instead of falling to the floor
    // below the lake/river where Link may not be able to reach it.
    bool floatsOnWater = false;
    float waterSurfaceY = 0.0f;
};
'@

    $StructWithWaterNew = @'
struct EnemyDefeatDropIdentity {
    int32_t placementIndex = -1;
    int64_t locationId = -1;

    // Octorock Enemy Defeat checks are earned over water. Their physical AP
    // pickup must remain at the water surface instead of falling to the floor
    // below the lake/river where Link may not be able to reach it.
    bool floatsOnWater = false;
    float waterSurfaceY = 0.0f;

    // If the physical AP reward has not been collected after about five
    // seconds, it becomes a pickup magnet and flies to Link.
    uint16_t ageFrames = 0;
    bool magnetizedToPlayer = false;
};
'@

    $StructPlain = @'
struct EnemyDefeatDropIdentity {
    int32_t placementIndex = -1;
    int64_t locationId = -1;
};
'@

    $StructPlainNew = @'
struct EnemyDefeatDropIdentity {
    int32_t placementIndex = -1;
    int64_t locationId = -1;

    // If the physical AP reward has not been collected after about five
    // seconds, it becomes a pickup magnet and flies to Link.
    uint16_t ageFrames = 0;
    bool magnetizedToPlayer = false;
};
'@

    if ($Text.Contains($StructWithWater)) {
        $Text = $Text.Replace($StructWithWater, $StructWithWaterNew)
    } elseif ($Text.Contains($StructPlain)) {
        $Text = $Text.Replace($StructPlain, $StructPlainNew)
    } else {
        throw "Could not find EnemyDefeatDropIdentity. No files were changed."
    }
}

# ---------------------------------------------------------------------------
# 2. Replace the enemy-pickup part of OnActorUpdate.
#    This supports both the prior Octorock floating-pickup patch and a source
#    tree that does not have it yet.
# ---------------------------------------------------------------------------
$OldWaterBlock = @'
        // Keep earned Octorock AP pickups at the water surface. EnItem00 normally
        // applies gravity, which can put these checks on an unreachable floor
        // beneath the water. Clamp only pickups explicitly created from Octorock
        // deaths; every other enemy pickup keeps the normal toss/fall behavior.
        const auto* floatingPickup =
            ObjectExtension::GetInstance().Get<EnemyDefeatDropIdentity>(actor);
        if (floatingPickup != nullptr && floatingPickup->floatsOnWater) {
            actor->gravity = 0.0f;
            actor->velocity.y = 0.0f;
            actor->speedXZ = 0.0f;
            actor->world.pos.y = floatingPickup->waterSurfaceY;
            actor->home.pos.y = floatingPickup->waterSurfaceY;
        }
'@

$NewPickupBlock = @'
        // Physical Enemy Defeat AP rewards get five seconds to behave normally.
        // If Link has not collected one by then, magnetize it to the player so
        // ranged kills, pits, water, cliffs, and awkward enemy positions cannot
        // turn a valid enemy check into an unreachable item.
        auto* enemyPickup =
            ObjectExtension::GetInstance().Get<EnemyDefeatDropIdentity>(actor);
        if (enemyPickup != nullptr) {
            if (enemyPickup->ageFrames < 0xFFFF) {
                ++enemyPickup->ageFrames;
            }

            Player* player = gPlayState != nullptr ? GET_PLAYER(gPlayState) : nullptr;
            if (enemyPickup->ageFrames >= 100 && player != nullptr &&
                !Player_InCsMode(gPlayState)) {
                enemyPickup->magnetizedToPlayer = true;
            }

            if (enemyPickup->magnetizedToPlayer && player != nullptr) {
                // Stop normal Item00 physics and rapidly home to Link. Once the
                // pickup is close, place it directly in Link's collection zone
                // so the normal pickup code can consume/report the AP location.
                actor->gravity = 0.0f;
                actor->velocity.x = 0.0f;
                actor->velocity.y = 0.0f;
                actor->velocity.z = 0.0f;
                actor->speedXZ = 0.0f;

                const float targetX = player->actor.world.pos.x;
                const float targetY = player->actor.world.pos.y + 20.0f;
                const float targetZ = player->actor.world.pos.z;

                Math_ApproachF(&actor->world.pos.x, targetX, 1.0f, 55.0f);
                Math_ApproachF(&actor->world.pos.y, targetY, 1.0f, 55.0f);
                Math_ApproachF(&actor->world.pos.z, targetZ, 1.0f, 55.0f);

                const float dx = actor->world.pos.x - targetX;
                const float dy = actor->world.pos.y - targetY;
                const float dz = actor->world.pos.z - targetZ;
                if ((dx * dx + dy * dy + dz * dz) <= (55.0f * 55.0f)) {
                    actor->world.pos.x = targetX;
                    actor->world.pos.y = targetY;
                    actor->world.pos.z = targetZ;
                }

                actor->home.pos = actor->world.pos;
            } else {
                // Preserve the Octorock water-floating behavior until the
                // five-second magnet timeout. Other enemy pickups keep their
                // original toss/fall physics.
                if (enemyPickup->floatsOnWater) {
                    actor->gravity = 0.0f;
                    actor->velocity.y = 0.0f;
                    actor->speedXZ = 0.0f;
                    actor->world.pos.y = enemyPickup->waterSurfaceY;
                    actor->home.pos.y = enemyPickup->waterSurfaceY;
                }
            }
        }
'@

if ($Text.Contains($OldWaterBlock)) {
    $Text = $Text.Replace($OldWaterBlock, $NewPickupBlock)
} elseif ($Text -notmatch 'Physical Enemy Defeat AP rewards get five seconds') {
    # No Octorock patch: insert the generic magnet code immediately after the
    # actor nullptr guard. In that case omit the water-only fallback.
    $Needle = @'
        Actor* actor = static_cast<Actor*>(actorRef);
        if (actor == nullptr) return;
'@

    $GenericBlock = @'
        Actor* actor = static_cast<Actor*>(actorRef);
        if (actor == nullptr) return;

        // Physical Enemy Defeat AP rewards get five seconds to behave normally.
        // If Link has not collected one by then, magnetize it to the player.
        auto* enemyPickup =
            ObjectExtension::GetInstance().Get<EnemyDefeatDropIdentity>(actor);
        if (enemyPickup != nullptr) {
            if (enemyPickup->ageFrames < 0xFFFF) {
                ++enemyPickup->ageFrames;
            }

            Player* player = gPlayState != nullptr ? GET_PLAYER(gPlayState) : nullptr;
            if (enemyPickup->ageFrames >= 100 && player != nullptr &&
                !Player_InCsMode(gPlayState)) {
                enemyPickup->magnetizedToPlayer = true;
            }

            if (enemyPickup->magnetizedToPlayer && player != nullptr) {
                actor->gravity = 0.0f;
                actor->velocity.x = 0.0f;
                actor->velocity.y = 0.0f;
                actor->velocity.z = 0.0f;
                actor->speedXZ = 0.0f;

                const float targetX = player->actor.world.pos.x;
                const float targetY = player->actor.world.pos.y + 20.0f;
                const float targetZ = player->actor.world.pos.z;

                Math_ApproachF(&actor->world.pos.x, targetX, 1.0f, 55.0f);
                Math_ApproachF(&actor->world.pos.y, targetY, 1.0f, 55.0f);
                Math_ApproachF(&actor->world.pos.z, targetZ, 1.0f, 55.0f);

                const float dx = actor->world.pos.x - targetX;
                const float dy = actor->world.pos.y - targetY;
                const float dz = actor->world.pos.z - targetZ;
                if ((dx * dx + dy * dy + dz * dz) <= (55.0f * 55.0f)) {
                    actor->world.pos.x = targetX;
                    actor->world.pos.y = targetY;
                    actor->world.pos.z = targetZ;
                }

                actor->home.pos = actor->world.pos;
            }
        }
'@

    if (-not $Text.Contains($Needle)) {
        throw "Could not find the OnActorUpdate actor guard. No files were changed."
    }

    # Only change the OnActorUpdate occurrence nearest the existing enemy retry
    # logic rather than every actor guard in the file.
    $HookMarker = 'COND_HOOK(OnActorUpdate, shouldRegister, [handleEnemyDeath](void* actorRef) {'
    $HookStart = $Text.IndexOf($HookMarker)
    if ($HookStart -lt 0) {
        throw "Could not find enemy OnActorUpdate hook. No files were changed."
    }
    $GuardPos = $Text.IndexOf($Needle, $HookStart)
    if ($GuardPos -lt 0) {
        throw "Could not find actor guard inside enemy OnActorUpdate hook. No files were changed."
    }
    $Text = $Text.Substring(0, $GuardPos) + $GenericBlock + $Text.Substring($GuardPos + $Needle.Length)
}

if ($Text -eq $Original) {
    throw "The five-second pickup magnet was already installed; no changes required."
}

$BackupDir = Join-Path $Root 'patch-backups'
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Backup = Join-Path $BackupDir ("MegaSouls-before-5sec-pickup-magnet-$Stamp.cpp")
Copy-Item -LiteralPath $File -Destination $Backup

[IO.File]::WriteAllText($File, $Text, [Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "SOH-EXTREME 5-second Enemy AP Pickup Magnet installed." -ForegroundColor Green
Write-Host "Changed: $File"
Write-Host "Backup:  $Backup"
Write-Host ""
Write-Host "Behavior:"
Write-Host "  1. Enemy AP item spawns where the enemy dies."
Write-Host "  2. You have about 5 seconds to pick it up normally."
Write-Host "  3. If still uncollected, it rapidly flies to Link."
Write-Host "  4. Octorock pickups still float on water during those first 5 seconds."
Write-Host "  5. Normal non-AP enemy refill drops are unchanged."
Write-Host ""
Write-Host "No build.cmd, CMake, APWorld, APCpp, or soul-rendering files were changed."
