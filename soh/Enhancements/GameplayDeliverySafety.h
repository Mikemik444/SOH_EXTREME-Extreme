#pragma once

#include "soh/Enhancements/game-interactor/GameInteractor.h"
extern "C" {
#include "z64.h"
#include "macros.h"
#include "functions.h"
#include "variables.h"
}

namespace SohExtreme {

// Only start a queued reward while the engine is accepting normal gameplay.
// transitionTrigger clears before the transitionMode fade has finished, and a
// queued cutscene can precede both the player flag and the cutscene context.
inline bool CanReceiveGameplayReward(PlayState* play) {
    if (play == nullptr || gSaveContext.health <= 0 ||
        play->gameOverCtx.state != GAMEOVER_INACTIVE ||
        play->transitionTrigger != TRANS_TRIGGER_OFF || play->transitionMode != TRANS_MODE_OFF ||
        play->csCtx.state != CS_STATE_IDLE || gSaveContext.cutsceneTrigger != 0 ||
        GameInteractor::IsGameplayPaused()) {
        return false;
    }
    Player* player = GET_PLAYER(play);
    if (player == nullptr || Player_InBlockingCsMode(play, player)) {
        return false;
    }
    return !(player->stateFlags1 &
             (PLAYER_STATE1_LOADING | PLAYER_STATE1_INPUT_DISABLED | PLAYER_STATE1_TALKING |
              PLAYER_STATE1_DEAD | PLAYER_STATE1_GETTING_ITEM | PLAYER_STATE1_CARRYING_ACTOR |
              PLAYER_STATE1_HANGING_OFF_LEDGE | PLAYER_STATE1_CLIMBING_LEDGE | PLAYER_STATE1_CLIMBING_LADDER |
              PLAYER_STATE1_IN_ITEM_CS | PLAYER_STATE1_IN_CUTSCENE | PLAYER_STATE1_FLOOR_DISABLED)) &&
           !(player->stateFlags2 &
             (PLAYER_STATE2_GRABBED_BY_ENEMY | PLAYER_STATE2_FROZEN | PLAYER_STATE2_PAUSE_MOST_UPDATING |
              PLAYER_STATE2_CRAWLING | PLAYER_STATE2_OCARINA_PLAYING | PLAYER_STATE2_FORCED_VOID_OUT)) &&
           !(player->stateFlags3 & (PLAYER_STATE3_PAUSE_ACTION_FUNC | PLAYER_STATE3_FLYING_WITH_HOOKSHOT));
}

inline bool IsPlayerOnDryGround(const Player* player) {
    // Iron Boots can set GROUND while Link is underwater; use water collision
    // and diving flags as well as the ordinary swimming flag.
    return player != nullptr && (player->actor.bgCheckFlags & BGCHECKFLAG_GROUND) &&
           !(player->actor.bgCheckFlags & BGCHECKFLAG_WATER) &&
           !(player->stateFlags1 & PLAYER_STATE1_IN_WATER) &&
           !(player->stateFlags2 & (PLAYER_STATE2_UNDERWATER | PLAYER_STATE2_DIVING));
}

inline bool CanTriggerGameplayTrap(PlayState* play) {
    return CanReceiveGameplayReward(play) && IsPlayerOnDryGround(GET_PLAYER(play));
}

} // namespace SohExtreme
