// Unmodified bodies retained from the user-provided upload/haha.zip.
// Original src/code/z_parameter.c SHA256: 6d6b9e470d87821c14b7b9505248ba45620be35c5947a395bfdbbea299cd843a
// Original soh/Enhancements/ExtraTraps.cpp SHA256: da66331b070c5aecbb0ba8d76d41c98748fd9ecded40fcc46989c206a12638e1

void Inventory_ChangeAmmo(s16 item, s16 ammoChange) {
    // "Item = (%d)    Amount = (%d + %d)"
    osSyncPrintf("アイテム = (%d)    数 = (%d + %d)  ", item, AMMO(item), ammoChange);

    if (item == ITEM_STICK) {
        AMMO(ITEM_STICK) += ammoChange;

        if (AMMO(ITEM_STICK) >= CUR_CAPACITY(UPG_STICKS)) {
            AMMO(ITEM_STICK) = CUR_CAPACITY(UPG_STICKS);
        } else if (AMMO(ITEM_STICK) < 0) {
            AMMO(ITEM_STICK) = 0;
        }
    } else if (item == ITEM_NUT) {
        AMMO(ITEM_NUT) += ammoChange;

        if (AMMO(ITEM_NUT) >= CUR_CAPACITY(UPG_NUTS)) {
            AMMO(ITEM_NUT) = CUR_CAPACITY(UPG_NUTS);
        } else if (AMMO(ITEM_NUT) < 0) {
            AMMO(ITEM_NUT) = 0;
        }
    } else if (item == ITEM_BOMBCHU) {
        AMMO(ITEM_BOMBCHU) += ammoChange;

        if (GameInteractor_Should(VB_CHECK_BOMBCHU_CAPACITY, true)) {
            if (AMMO(ITEM_BOMBCHU) > 50) {
                AMMO(ITEM_BOMBCHU) = 50;
            }
        } else if (AMMO(ITEM_BOMBCHU) < 0) {
            AMMO(ITEM_BOMBCHU) = 0;
        }
    } else if (item == ITEM_BOW) {
        AMMO(ITEM_BOW) += ammoChange;

        if (AMMO(ITEM_BOW) >= CUR_CAPACITY(UPG_QUIVER)) {
            AMMO(ITEM_BOW) = CUR_CAPACITY(UPG_QUIVER);
        } else if (AMMO(ITEM_BOW) < 0) {
            AMMO(ITEM_BOW) = 0;
        }
    } else if ((item == ITEM_SLINGSHOT) || (item == ITEM_SEEDS)) {
        AMMO(ITEM_SLINGSHOT) += ammoChange;

        if (AMMO(ITEM_SLINGSHOT) >= CUR_CAPACITY(UPG_BULLET_BAG)) {
            AMMO(ITEM_SLINGSHOT) = CUR_CAPACITY(UPG_BULLET_BAG);
        } else if (AMMO(ITEM_SLINGSHOT) < 0) {
            AMMO(ITEM_SLINGSHOT) = 0;
        }
    } else if (item == ITEM_BOMB) {
        AMMO(ITEM_BOMB) += ammoChange;

        if (AMMO(ITEM_BOMB) >= CUR_CAPACITY(UPG_BOMB_BAG)) {
            AMMO(ITEM_BOMB) = CUR_CAPACITY(UPG_BOMB_BAG);
        } else if (AMMO(ITEM_BOMB) < 0) {
            AMMO(ITEM_BOMB) = 0;
        }
    } else if (item == ITEM_BEAN) {
        AMMO(ITEM_BEAN) += ammoChange;
    }

    osSyncPrintf("合計 = (%d)\n", AMMO(item)); // "Total = (%d)"

    if (ammoChange < 0) {
        GameplayStats_UpdateAmmoUsed(item, -ammoChange);
    }
}

case ADD_AMMO_TRAP:
                AMMO(ITEM_STICK) = static_cast<int8_t>(floor(AMMO(ITEM_STICK) * 0.5f));
                AMMO(ITEM_NUT) = static_cast<int8_t>(floor(AMMO(ITEM_NUT) * 0.5f));
                AMMO(ITEM_SLINGSHOT) = static_cast<int8_t>(floor(AMMO(ITEM_SLINGSHOT) * 0.5f));
                AMMO(ITEM_BOW) = static_cast<int8_t>(floor(AMMO(ITEM_BOW) * 0.5f));
                AMMO(ITEM_BOMB) = static_cast<int8_t>(floor(AMMO(ITEM_BOMB) * 0.5f));
                AMMO(ITEM_BOMBCHU) = static_cast<int8_t>(floor(AMMO(ITEM_BOMBCHU) * 0.5f));
                Audio_PlaySfxGeneral(NA_SE_VO_FR_SMILE_0, &gSfxDefaultPos, 4, &gSfxDefaultFreqAndVolScale,
                                     &gSfxDefaultFreqAndVolScale, &gSfxDefaultReverb);
                break;
// END LEGACY TRAP
