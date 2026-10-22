// Preserved production helper for regression evidence only.
// Original logic.cpp SHA256: 85011ebbbc2f1ca8da0cb0e3a1e53a84fe53976f5ef6756bfe745894d9a0aea6
bool Logic::CanOpenBombGrotto() {
    // SOH-EXTREME: Shovel gates every grotto, while a bomb/rock-hidden grotto
    // still has its physical rock/boulder blocker.  That blocker cannot be
    // removed until Rock / Boulder Soul is owned, and the allowed removal
    // methods are the EXTREME rock rule: explosives OR Grab/Power Bracelet.
    if (ctx->GetOption(RSK_SHUFFLE_SHOVEL) && !HasItem(RG_SHOVEL)) {
        return false;
    }
    return CanBreakRocks() && HasItem(RG_STONE_OF_AGONY);
}
