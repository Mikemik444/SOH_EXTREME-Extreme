# SOH-EXTREME

**SOH-EXTREME** is a heavily customized **Ship of Harkinian** fork with deep **Archipelago** integration and a large set of extra progression systems, shuffle categories, and tracker/client features designed around the user's custom randomizer rules.

This repository contains the game client and related code for the SOH-EXTREME experience.

---

## Main Goals

SOH-EXTREME is built around four big goals:

1. **Native Archipelago support** for SOH-EXTREME as its own game/client behavior.
2. **Much deeper shuffle logic** than stock SoH / OoT randomizers.
3. **New progression systems** such as souls, abilities, notes, and special access items.
4. **A strong in-game tracker/UI experience** so the player can actually understand what the seed expects.

---

## Core Client Features

### Native Archipelago Client Behavior

SOH-EXTREME includes dedicated Archipelago client-side behavior instead of only relying on a generic randomizer implementation.

Features include:

- Native **SOH-EXTREME Archipelago slot support**.
- Archipelago-specific **file/select labeling**.
- Archipelago-aware **save handling**.
- AP item delivery integrated directly into the game client.
- Support for **world-to-world item sending/receiving**.
- In-game **Archipelago chat display**.
- Archipelago connection flow designed around actual gameplay use.

### Safer Archipelago Session Flow

The client is intended to:

- Connect at appropriate gameplay moments rather than unstable early-title timing.
- Persist AP receive state per save file.
- Avoid double-granting already-received items.
- Keep queue behavior aligned with real in-game receipt rather than just network arrival.

### DeathLink / TrapLink

SOH-EXTREME supports Archipelago multiplayer tags and options including:

- **DeathLink**
- **TrapLink**

### Item Notification Behavior

The client separates major vs minor item presentation:

- **Important / major items** can use stronger presentation.
- **Minor / low-importance items** can be shown through lighter side notifications.
- Cross-world items are designed to use distinct Archipelago presentation.

---

## Major Gameplay Systems

## 1) Soul System

One of the biggest SOH-EXTREME systems is the **Soul System**.

Instead of every interactable or destructible category always working by default, many categories are gated behind collectible **Soul** items.

### Soul Categories

SOH-EXTREME supports multiple soul categories, including:

- **Enemy Soul**
- **NPC Soul**
- **Animal Soul**
- **Pot Soul**
- **Crate Soul**
- **Grass / Bush Soul**
- **Rock / Boulder Soul**
- **Tree Soul**
- **Beehive Soul**
- **Sign Soul**
- **Skulltula Soul**
- **Business Scrub Soul**
- **Boss Souls**
- **Bean Souls**
- Individual enemy-specific souls
- Individual animal-specific souls

### Soul Visibility / Spawn Behavior

The intended SOH-EXTREME rules are:

- **Crates** and **Rocks/Boulders** stay physically present before their soul is obtained.
  - They should appear visually locked / tainted.
  - They should be unbreakable until the soul is owned.
- Most other soul-controlled object classes are intended to be **hidden / absent** until their soul is obtained.

### Soul Rendering

Souls are intended to be recognizable as unique pickups, with custom rendering support for:

- Boss souls
- Enemy souls
- Category souls
- Animal souls
- Bean souls

---

## 2) Ability / Progression Item System

SOH-EXTREME adds several important progression abilities that can be shuffled and logically required.

These include:

- **Roll**
- **Crawl**
- **Climb**
- **Grab**
- **Speak**
- **Open Chest**
- **Flow of Time**
- **Shovel**
- **Progressive Scale / Swim access handling**
- **Song Notes**

### Examples

- **Speak** is used as real progression and is important for NPC interaction logic.
- **Open Chest** can be progression-sensitive.
- **Flow of Time** affects day/night access logic.
- **Shovel** gates grotto access.
- **Grab** matters for object interaction like pots, crates, grass, and rocks depending on settings.

---

## 3) Song Note Shuffle

SOH-EXTREME supports **individual song note progression**.

Instead of learning songs all at once, the player can collect notes individually. The client and tracker are intended to support:

- Individual note collection
- Per-song note requirements
- Song completion after enough notes are collected
- In-game note-progress display / tracking

---

## 4) Enhanced Check / Shuffle Categories

SOH-EXTREME adds or expands many check categories beyond a standard OoT randomizer setup.

Examples include:

- Pots
n- Crates
- Grass / bushes
- Rocks / boulders
- Trees
- Beehives
- Signs
- Hidden rupees
- Wonder items
- Silver rupees
- Bean-related checks
- Enemy defeat checks
- NPC interaction / speech checks
- Business Scrubs
- House / building keys
- Overworld keys
- Fishing Pole
- Boss souls
- Ocarina buttons / notes
- Special ability checks

### Enemy Defeat Checks

Enemy defeat checks are intended to be handled at the **placed-enemy level**, not just by enemy species. That means each placed enemy can represent its own check.

### NPC Speech Checks

SOH-EXTREME supports **NPC speech / first-talk checks**, including the concept of **Speak** as progression.

### Wonder / Hidden Check Support

The project is designed to include and report otherwise easy-to-miss content such as:

- Wonder items
- Hidden rupees
- Silver rupees

---

## 5) Bean Soul System

SOH-EXTREME includes **Bean Souls**, allowing bean-spot progression to be handled as a broader collectible/progression concept.

Examples shown by the tracker include bean souls for locations such as:

- DMC
- DMT
- DC
- GV
- GY
- KF
- LH
- LWB
- LWT
- ZR

---

## 6) Boss Soul System

Bosses can be split into their own soul progression.

Supported boss soul categories include:

- Gohma
- King Dodongo
- Barinade
- Phantom Ganon
- Volvagia
- Morpha
- Bongo Bongo
- Twinrova
- Ganon

Boss souls also serve as the primary visual inspiration for the higher-end soul rendering style used elsewhere in the project.

---

## Tracker / UI Features

SOH-EXTREME includes a large amount of tracker/UI work to make the custom progression understandable.

### In-Game Item Tracker

The tracker supports many separate sections, including:

- Inventory items
- Equipment
- Misc items
- Dungeon rewards
- Songs
- Dungeon items
- Triforce pieces
- Boss souls
- Mega/category souls
- Animal souls
- Enemy souls
- Ocarina buttons
- Overworld keys
- Silver rupees
- Fishing Pole
- Notes / personal notes
- Total checks

### Tracker Display Options

The tracker supports configurable display styles such as:

- Hidden
- Main window
- Separate window
- Extended display handling for some sections
- Floating / windowed behavior
- Icon sizing / spacing
- Counts / number modes

### Song Note Progress Display

The tracker includes support for a detailed song-note section showing progress toward songs such as:

- Zelda's Lullaby
- Epona's Song
- Saria's Song
- Sun's Song
- Song of Time
- Song of Storms
- Minuet of Forest
- Bolero of Fire
- Serenade of Water
- Requiem of Spirit
- Nocturne of Shadow
- Prelude of Light

### Identifiers / QoL

The tracker/UI also supports special identifiers and QoL tracking such as:

- Hookshot identifiers
- Open Chest identifiers
- Personal notes
- Silver-rupee status presentation

---

## Custom Item / Texture Support

SOH-EXTREME contains custom item-icon / texture / rendering support for a variety of added progression items, such as:

- Boss souls
- Enemy souls
- Category souls
- Grab / Climb / Crawl
- Open Chest
- Shovel
- Roll
- Flow of Time
- Ocarina button items / note-related items
- Fishing Pole
- Rocs Feather
- Triforce Piece

This applies both to in-world rendering and tracker / GUI icon presentation.

---

## Randomizer / Logic Philosophy

SOH-EXTREME is designed around **custom logic**, not just stock OoT rules.

That means the project is intended to keep logic consistent across:

- The in-game client
- The SOH-EXTREME Archipelago world logic
- The tracker / check finder
- The actual in-world interaction rules

Examples of custom logic expectations include:

- Object interaction methods matter (bombs, sword, boomerang, grab, etc.).
- Day/night logic can be altered by **Flow of Time**.
- Grotto access is governed by **Shovel**.
- Cucco/animal requirements are tied into **Animal Soul** logic.
- Silver rupees and other extended shuffle pools must be tracked accurately.
- AP / tracker / in-game logic should all agree.

---

## Multiplayer / Archipelago-Oriented Design Goals

SOH-EXTREME is built with multiplayer randomizer play in mind.

Key multiplayer-oriented goals include:

- Correct location reporting
- Reliable item receive behavior
- Persistent received-item state
- Cross-world item presentation
- DeathLink / TrapLink support
- Universal Tracker integration / support
- In-game AP messaging
- Distinct handling for major vs minor received items

---

## Build Notes

SOH-EXTREME is a Windows-focused C++ project using CMake / Visual Studio.

Typical environment expectations include:

- **Visual Studio 2022**
- **CMake**
- **x64 build target**
- **vcpkg** toolchain for dependencies when needed

If you are using a custom local setup, keep your dependency paths consistent and ensure the build is configured with the intended toolchain.

---

## Project Status

SOH-EXTREME is an actively customized fork and is under ongoing development.

That means some systems may still be under active tuning, especially around:

- Visual presentation of custom items/souls
- Archipelago stability edge cases
- Tracker consistency
- Fine details of custom logic
- Additional custom assets / item models

---

## Summary of What Makes SOH-EXTREME Different

Compared to a more standard SoH or OoT randomizer setup, SOH-EXTREME stands out because it combines:

- Native **Archipelago-aware client behavior**
- A large **Soul-based progression system**
- Many extra **shuffle categories**
- Shuffled **abilities / movement / interaction progression**
- **Song-note progression**
- Strong **tracker / UI integration**
- Extended **multiplayer quality-of-life features**

---

## Credits / Notes

SOH-EXTREME builds on the broader Ship of Harkinian and Archipelago ecosystems while introducing its own custom gameplay, logic, and client behavior.

If you are browsing the repository, this README is intended as a high-level feature overview for the custom client and game logic contained here.
