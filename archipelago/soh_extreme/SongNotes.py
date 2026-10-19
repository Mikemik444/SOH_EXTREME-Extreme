"""Stable song identities and selection for progressive individual notes."""
from __future__ import annotations

import re
from Options import OptionError

# Order and lengths are the native client's existing 74 note flags and the
# twelve existing Progressive song network IDs. Selection never renumbers them.
SONG_NOTE_LAYOUT = (
    ("Zelda's Lullaby", 6),
    ("Epona's Song", 6),
    ("Saria's Song", 6),
    ("Sun's Song", 6),
    ("Song of Time", 6),
    ("Song of Storms", 6),
    ("Minuet of Forest", 6),
    ("Bolero of Fire", 8),
    ("Serenade of Water", 5),
    ("Requiem of Spirit", 6),
    ("Nocturne of Shadow", 7),
    ("Prelude of Light", 6),
)
SONG_NOTE_KEYS = (
    "zeldas_lullaby", "eponas_song", "sarias_song", "suns_song",
    "song_of_time", "song_of_storms", "minuet_of_forest", "bolero_of_fire",
    "serenade_of_water", "requiem_of_spirit", "nocturne_of_shadow", "prelude_of_light",
)
SONG_NAMES_BY_KEY = {key: song for key, (song, _) in zip(SONG_NOTE_KEYS, SONG_NOTE_LAYOUT)}


def normalize_song_selection(values) -> set[str]:
    """Accept YAML keys or full song names, while preserving the all choice."""
    result = set()
    for name in values:
        if not isinstance(name, str):
            raise OptionError("Song Note Songs must contain song names or 'all'.")
        key = re.sub(r"[^a-z0-9]+", "_", name.casefold().replace("'", "").replace("’", "")).strip("_")
        if key != "all" and key not in SONG_NAMES_BY_KEY:
            raise OptionError(
                f"Unknown individual-note song {name!r}. Choose 'all' or: "
                + ", ".join(SONG_NOTE_KEYS)
            )
        result.add(key)
    return {"all"} if "all" in result else result


def selected_song_names(options) -> frozenset[str]:
    mode = getattr(options, "song_note_shuffle", None)
    if mode is None or not mode.value:
        return frozenset()
    selection = getattr(options, "song_note_songs", None)
    keys = normalize_song_selection(selection.value if selection is not None else {"all"})
    if "all" in keys:
        return frozenset(SONG_NAMES_BY_KEY.values())
    return frozenset(SONG_NAMES_BY_KEY[key] for key in keys)


def song_note_mask(options) -> int:
    selected = selected_song_names(options)
    return sum(1 << index for index, (song, _) in enumerate(SONG_NOTE_LAYOUT) if song in selected)
