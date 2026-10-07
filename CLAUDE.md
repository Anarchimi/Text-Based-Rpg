# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Chronicles of the Shattered Realm** — a text-based RPG played in the browser (mobile-first).

- **Web** (`app.py`): Flask server, state persisted as pickled dicts in `<SAVE_DIR>/<uuid>.pkl` across HTTP requests. `SAVE_DIR` defaults to `instance/saves/` (gitignored) and can be overridden with the `RPG_SAVE_DIR` env var — point it at a persistent volume in production. Saves are written to a temp file and renamed into place, so a crash mid-write can't corrupt one.
- Game logic lives in `player.py`, `enemies.py`, `items.py`, `quests.py`, `abilities.py`, `world.py`, `crafting.py`. Combat is a step-wise state machine: `do_combat_turn` in `combat.py`, one call per round.

The old terminal (CLI) version was removed; there is only one interface.

## Commands

```bash
# Install dependencies (requirements-dev.txt adds pytest)
pip install -r requirements-dev.txt

# Run tests
python -m pytest -q tests

# Balance report: a scripted bot fights every zone/boss/class combination
python tools/balance_sim.py --fights 80

# Run the web server (development)
python app.py

# Run with production WSGI (waitress)
waitress-serve app:app
```

Tests live in `tests/` (pytest). `test_combat_effects.py` asserts that every buff ability and every profession passive actually changes combat — add a test there when adding an ability or profession (`test_every_profession_is_covered` fails until you do). `test_enemies_and_story.py` does the same for every enemy ability, status effect, boss phase and the seals → final boss → ending → NG+ flow, and includes balance regression checks (final boss winnable, regular fights not one-shots) that run the simulator. `test_web.py` clicks random buttons through the whole app, fails on any 500, and plays the endgame through the real forms. `test_trades.py` covers trade gameplay phase by phase (milestone coverage via `TESTED_MILESTONES`, every node's risk/reward with RNG controlled by `FixedRandom`, workshop/alchemy/inventory flows through the web, and a pre-trade save loading and rendering every trade screen); `test_professions.py` covers profession perks. There is no linter configuration.

## Architecture

### Web State Machine (`app.py`)

The web app is a single-page application driven by a `state` dict with a `screen` field. Every POST to `/action` reads state from disk, transitions `state['screen']` based on `action=` form data, saves state, and redirects to `GET /` which re-renders `templates/game.html`.

`templates/game.html` is a thin shell (head, body, sound script) that includes `templates/screens/<state.screen>.html` — one file per screen (title, hub, combat, shop, inn, etc.). The client-side sound/haptics script lives in `templates/partials/scripts.html`. There is no JavaScript routing.

**Screen flow:**
```
title → char_name → char_class → trade_prof_choice → hub
hub → combat → combat_result → hub
hub → explore (choose a path) → explore … or → combat → combat_result → explore
hub → shop / inn / quest_board / world_map / inventory / skills / abilities / gather / craft
hub → profession_choice (triggered at level 5) → hub
hub (zone 5, all five seals) → combat vs Chaos Dragon Lord → ending → hub (New Game+ or keep playing)
```

State dict keys: `screen`, `player` (Player object), `quest_log` (QuestLog object), `zone` (int 1–5), `messages` (list of `{kind, text}` dicts), `combat_enemy`, `combat_turn`, `combat_log`, `shop_stock`, `board_quests`, `narrative_stage` (== `len(seals)`), `seals` (set of zone ids whose boss is dead), `dragon_slain`, `ng_plus` (New Game+ cycle, 0 = first run), `lair_progress`, `depth`, `explore_options`, `return_to` (screen after `combat_result`), `triggered_events` (set of fired one-time event IDs), `craft_skill`. `migrate_state()` fills in keys missing from older saves — add new keys to `fresh_state()` and they migrate automatically.

### Player Stats (`player.py`)

All derived stats (`str`, `dex`, `int`, `vit`, `lck`, `attack`, `defense`, `speed`) are Python `@property` computed on access from:
- `base_*` attributes (set at creation, grown on level-up via `_apply_growth`)
- Skills learned (`skills_learned`, `prof_skills_learned`) — dicts with a `stats` dict (e.g. `{"max_hp": 8, "vit": 2}`) that must match the `desc` text exactly (`test_every_skill_grants_exactly_its_description` parses the description and checks). STR/DEX/INT/VIT/LCK are summed on access via `skill_bonus()` — never also add them to `base_*`; only `max_hp`/`max_mp` are applied when learned.
- Equipped gear (`equipment["weapon"|"armor"|"accessory"]`) — every stat in every equipped `item.stats` counts, via `gear_stat(stat)`; `hp`/`mp` are added to `max_hp`/`max_mp` on equip and removed on unequip; `crit` adds % crit chance (`crit_bonus`)
- Temporary buffs (`temp_buffs` list of `{stat, amount, turns}`)
- Profession passives (inline in the property body, e.g. Knight's +25% DEF)

**Player has two profession layers:**
1. **Trade profession** (chosen at character creation, `player.trade_profession`): Blacksmith, Alchemist, Fisher, Fletcher (`TRADE_PROFESSIONS` in `crafting.py`; "Fletcher" was "Ranger" — renamed on load to avoid clashing with the Rogue's Ranger). Each gives +50% XP in two skills plus two perks listed in its `perks`: a crafting perk (`MASTERWORK_SKILLS` → +10% on the workshop quality roll for the Blacksmith's forge / Fletcher's bench; `DOUBLE_CRAFT_SKILLS` → 30% chance of two consumables) and a field perk (Blacksmith: cheaper upgrades in `items.upgrade_cost(item, player)`; Alchemist: potions ×1.5 and Fisher: food ×1.5 + MP in `Player.use_consumable`, via `BOOSTABLE_EFFECTS` and `item.category == "food"`; Fletcher: trail forage paths go to Woodcutting with +1 wood, and half treasure trap risk, in `world.py`). Tests in `tests/test_professions.py`.

   **Known limitation:** Fisher food restores MP equal to its boosted heal %; balance sim shows the Fisher's edge (a Rare-gear Mage beats the final boss ~57% vs ~35% for an Alchemist with HP + mana potions) comes from getting HP *and* MP from one item in one turn, not from the size of the number — capping the MP % changed nothing in simulation, so it was left as is.
2. **Combat profession** (chosen at level 5): stored in `player.profession`. Options depend on base class (Warrior → Knight/Berserker/Champion, Mage → Sorcerer/Elementalist/Necromancer, Rogue → Assassin/Ranger/Trickster). Each has: a passive and stat bonus (`PROFESSIONS`), a **signature ability** added to `get_abilities()` (`PROFESSION_ABILITIES` in `abilities.py`: Riposte, Blood Frenzy, Rallying Strike, Arcane Overload, Convergence, Soul Harvest, Shadowstrike, Volley, Blinding Powder), and a **capstone perk** on its cost-3 profession skill (`"perk"` key; checked with `player.has_perk(name)`, which looks skills up by name so older saves get it too). Signature and perk effects live in `combat.py`; `tests/test_professions.py` has one test per signature and per perk and fails if a profession lacks either.

### Trade gameplay (`trades.py`)

Trade skills are levelled 1–20 by everyone; milestones at 5/10/15/20 (`TRADE_MILESTONES`: skill → level → (title, text)) unlock behaviour — not every skill has all four: Cooking and Herblore stop at 15 (a level-20 capstone is deliberately deferred rather than filled with a number bump), checked with `has_milestone(player, skill, level)`. **Only implemented unlocks are listed**, and `tests/test_trades.py::TESTED_MILESTONES` must contain each one. Crossing a milestone queues a message in `player.unlock_log`; `app.action()` drains it into the screen messages. The Gather and Craft screens show reached and next milestones (`templates/partials/milestones.html`).

**Profession discoveries** (`PROFESSION_EVENTS`): an extra explore path kind `trade`, offered only to players with that trade profession and the event's skill level (`available_trade_events`), resolved by `resolve_trade_event` into the normal explore event tuples. `player.trade_specialization` is reserved (always `None` for now).

**Special nodes** (shared by all trades): an interactive moment stored as a plain dict in `state['pending_node']` and shown on the `node` screen (`{type, title, text, options: [{key, label, detail}], ...}`); `trades.resolve_node(node, key, player)` dispatches to `NODE_RESOLVERS[type]` and returns explore-style event tuples. Opened from a Gather tap (`app.special_node_for`) or from a trail discovery (event type `node`); `state['node_return']` is `gather` or `explore`. Routine gathering stays one tap.

**Blacksmith loop:** Mining 5+ taps open an ore vein 15% of the time (`VEIN_CHANCE`), and the Blacksmith's trail vein becomes one: Safe (3–4 ore) / Deep (6–8 ore, 25% cave-in for −15% HP and 1–2 ore) / Prospect (Mining 10: gems) — deep veins strike next-zone ore at Mining 15, Starmetal at 20. Smithing "X Gear" recipes (`output_type: "forge"`) open the `workshop` screen: choose weapon or armor and an additive; **crafted quality is the item's rarity**, rolled as `U[0,1) + forge_shift` against `QUALITY_BANDS` (shift: +2%/Smithing level over the recipe up to 10, gems +10/20%, Masterwork +10%); Epic needs investment and Legendary needs Starmetal (Smithing 20). `items.forge_item` makes real named gear ("Steel Sword", "Steel Plate") with a metal trait (`METALS`) and the usual bonus stats; crafted items carry `crafted`, `material`, `kind`, `temper`. **Tempering** (Smithing 15, crafted gear only, once per item, `items.TEMPERS`) reshapes *base* stats — Hone / Reinforce / Heavy Plating (more DEF, −SPD) — so the +1…+5 upgrade ladder builds on it instead of stacking a second ladder.

**Alchemist loop:** every ingredient in `trades.INGREDIENTS` has a (main, secondary) property; `known_properties` reveals main at Herbalism 5 and secondary at 15 (monster reagents always show main). The `alchemy` screen (Herblore tab → Alchemy bench) mixes two ingredients: two MAIN properties matching an `ALCHEMY_RECIPES` pair → discovery (stored in `player.alchemy_journal['recipes']` as name → ingredient pair, survives save/load); one main + the other's SECONDARY → an unstable half-strength version plus a hint (`journal['hints']`); otherwise a failure (sometimes −5% HP). Known recipes brew in one tap (`brew_known`; Herblore 15 → +25% potency, Alchemist Double Brew applies). Recipes use existing consumable effects plus `cure_heal` (Panacea); Phoenix Draught (Starbloom + Restoration) is a craftable revive. Monster reagents (`MONSTER_REAGENTS`: Vampire Fang, Dragon Scale, Shadow Essence) drop from their enemies on victory (`reagent_drop`, 30%); Alchemists also find monster remains on the trail at Herblore 10, which only yield reagents whose source monster can already spawn in that zone (`zone_reagents`, same `zone <=` rule as `spawn_enemy`) — so the event isn't offered in zones 1–2 and can't bypass zone progression. Herbalism 10+ taps can open a herb patch node: quick (3–4 herbs) vs careful (rare next-zone herb, 20% sting); Herbalism 20 adds Starbloom.

**Fisher loop:** Fishing 5+ taps (15%, `BITE_CHANCE`) and the Fisher's trail pool open a **bite** node: the fish has a temperament (`TEMPERAMENTS`: aggressive / heavy / elusive) shown as a cue — named outright at Fishing 10 — and each response (reel / let it tire / steady) has a right (90%), neutral (50%) and wrong (15%) success chance. Fishing 10 adds next-zone fish; only the *best* response can land a trophy (Fishing 15, `TROPHY_FISH`: one unique trophy per zone) or the Ashvale River King (Fishing 20, **zone 1 only** — `LEGENDARY_FISH_ZONE`, checked when the node is built and again when it resolves; a reason to return to the starting river). Trophies go to `player.trophies` (catch log; first catch +150 XP) and cook into feasts (Cooking 10). **Meals** (`MEALS`, Cooking recipes with `output_type: "meal"`) are consumables with `category == "meal"`: eaten outside combat only (`Player.combat_consumables()` excludes them), one active at a time in `player.meal`, adding flat stats (`meal_stat`) or debuff resist for N fights; `combat.end_combat` counts fights down; Cooking 15 adds 2 fights. Meals deliberately don't restore HP/MP, so they don't stack with the Fisher's in-combat HP+MP food advantage.

**Fletcher loop:** logs map to woods (`items.WOODS`: Oak sturdy +HP, Willow flexible +SPD, Maple balanced +crit, Yew powerful +10% ATK, Elder mystic +main stat), visible from Woodcutting 5 (`wood_trait`). Fletching weapon recipes (`output_type: "fletch"`) open the shared workshop as the Fletching bench: pick a **profile** (`items.PROFILES`: Power +25% ATK −SPD / Speed −15% ATK +SPD / Precision +crit) and an additive (Heartwood at Fletching 10, Ancient Heartwood at 20 = the only Legendary path); `items.fletch_item` makes real named weapons ("Yew Longbow", Mages get a "Yew Staff") with `profile`. Woodcutting 10+ taps (and the Fletcher's trail tree) open a **tree** node: fell quickly vs cut the heartwood (20% falling branch); Woodcutting 15 next-zone wood, 20 Ancient Heartwood. **Field tools** (`output_type: "utility"`, `category == "utility"`): Hunting Trap (use outside combat → `player.armed_trap`; `trades.spring_trap` snares the next non-boss fight in `app.start_combat`: −15% HP, Chilled; Fletching 15 adds Bleed), Camping Kit (consumed by the next trail camp: 60% heal, keeps half the depth), Smoke Arrow (combat item: guaranteed escape except the final battle). Fletchers also find animal tracks on the trail (Woodcutting 5) for a free ambush. `trades.bench_craft(player, skill, recipe, choice, additive)` serves both the forge and the bench (`WORKSHOP_ADDITIVES`, `craft_shift`).

**Trade economy (measured in phase 6):** crafting-and-selling earns ~3–35% of combat's gold per click at the same level (crafted items are priced by material, not like loot), so no trade is a gold farm. Against the final boss (Epic gear, bot play) single trade boosts add ~1–5 points; tempered gear + River King Feast + Alchemist Dragonblood together take Mage 79→95%, Rogue 88→96%. Bosses were deliberately not rebalanced around trades.

Basic trail discoveries turn into their node (vein / patch / bite) once the gathering milestone is reached (`DISCOVERY_NODES`).

### Items (`items.py`)

`Item` objects have `item_type` ∈ `{"weapon", "armor", "accessory", "consumable"}`. Consumables carry `effect` (string key), `effect_value`, and `effect_duration`. Effect keys used throughout `player.use_consumable()`: `heal_pct`, `heal_mp_pct`, `heal_hp`, `heal_mp`, `heal_overheal`, `temp_buff_str`, `temp_buff_vit`, `temp_buff_all`, `buff_str`, `buff_int`, `cure`, `revive`.

Items are procedurally generated by `generate_weapon`, `generate_armor`, `generate_accessory`, `generate_consumable`, and `generate_loot` (pass `player_class` so loot fits the player). Rarity tier (`RARITIES`: Common → Legendary) is rolled with `loot_rarity_bonus(level, luck)` — LCK genuinely raises rarity — and scales base stats via `rarity_multiplier`.

**Gear stats:** weapons have base `atk`, armor base `def`, accessories no base stat. On top, `roll_affixes` adds bonus stats from `AFFIX_POOL[slot]` (`str dex int vit lck hp mp spd crit`): Uncommon 1, Rare 2, Epic 3, Legendary 3 (`AFFIX_COUNT`; accessories +1), with the class's main stat 3× as likely. Legendary items also get one `item.legendary` effect from `LEGENDARY_EFFECTS` (Vampiric, Thorns, Executioner, Arcane Flow, Bulwark, Second Wind), implemented in `combat.py` via `player.has_effect(name)` — `test_every_legendary_effect_has_a_test` fails if you add one without a test. Item stats render through `templates/partials/item.html` (`item_stats`, `compare` vs the equipped item in that slot). Consumable prices that shouldn't follow the effect value live in `CONSUMABLE_PRICES`.

**Upgrades** (inventory screen → equipped item → Upgrade): +1 … +5 (`UPGRADE_MAX`), each +12% of the item's base stats (positive stats only — penalties like Heavy Plating's or a Power bow's −SPD stay as they are), paid with gold (`60 × n²`) plus 2 smithed bars of that tier (`UPGRADE_BARS`: Bronze → Adamantite). This is the main gold sink and what connects Smithing to combat. `Item.apply_upgrade()` keeps `base_stats`/`base_name` and renames the item `"<name> +n"`. Each upgrade adds `UPGRADE_VALUE_SHARE` (50%) of its full (undiscounted) gold price to `item.value` — a flat amount, not a multiplier — so selling at `value // 2` refunds 25% of it and upgrade-then-sell never makes gold, even at the Blacksmith's discount (`test_upgrading_then_selling_never_makes_gold`).

### Exploring (`world.py`, `app.py`)

Explore opens the `explore` screen with `EXPLORE_CHOICES` (3) distinct **paths** from `generate_explore_options`: always one fight (enemy pre-spawned, shown with level/HP, flagged as boss / bounty Leader / "above your level"), plus two of treasure (gold, maybe gear, trap % shown), forage (a gathering resource + skill XP), shrine (blessing or curse), strange lights (anything, incl. ambush), camp (only when hurt) and story (the zone's untriggered `NAMED_EVENTS`). Offered paths are stored in `state['explore_options']` and persist until one is taken, so backing out can't reroll them.

`resolve_option` turns the chosen path into `(event_type, value, message)` tuples that `apply_explore_events` in `app.py` applies: `gold`, `heal_pct`, `heal_mp_pct`, `xp`, `trap_pct`, `item` (value: Item), `resource`, `reset_depth`, `encounter` (value: Enemy → `start_combat(..., return_to='explore')`, and winning returns to the trail), `nothing`.

**Trail depth** (`state['depth']`, 0–`MAX_DEPTH`): +1 per path taken. Each point gives enemies +1 level per 3 depth, +10% gold, +3 loot luck (also on trail fight loot) and +2% treasure trap risk (`depth_effects`). Camping, the Inn and travelling reset it — "drink a potion and push on, or rest and lose the bonus" is the core decision.

Every path taken adds 1 to `state['lair_progress'][zone]`; at `LAIR_STEPS` (12) the zone boss's lair is found and the hub offers "Challenge <boss>" (also a rematch after the seal is broken). Bosses can also appear as the fight path (zone `boss_chance`).

### Quests (`quests.py`)

Four types, all advanced by `QuestLog.check_event(event, name)` from `app.py` (`'kill'` with the enemy name on every victory; `'explore'` with the zone name on every non-fight path taken and every victory):
- **kill** — N of a zone enemy.
- **collect** — trophies that drop (`COLLECT_DROP_CHANCE`) only from the enemies listed for them in `COLLECT_ITEMS`; the description names those enemies.
- **explore** — "Scout the <zone>": explore that zone N times. Targets must be real zone names.
- **bounty** — kill the "<enemy> Leader". While a bounty is active, matching encounters become the Leader (`Enemy.make_leader()`, ×1.5 HP, ×2 rewards) with `BOUNTY_LEADER_CHANCE`. `enemy.template_name` keeps the original name for sprites.

### Crafting & Gathering (`crafting.py`)

Players have two skill dictionaries: `gathering_skills` and `crafting_skills`, each mapping skill name → `{level, xp}`. Skill XP is tracked cumulatively; `calc_skill_level(total_xp)` derives the level using a closed-form quadratic formula (O(1)).

`ZONE_RESOURCES` maps zone → skill → list of `(resource_name, weight, level_req)`. `gather_resource` samples eligible resources weighted by `weight`.

`CRAFTING_RECIPES` maps skill name → list of recipe dicts. Each recipe specifies `inputs` (resource name → qty), `output_type` (`"resource"`, `"weapon"`, `"armor"`, or `"consumable"`), `req` (skill level), and `xp`. Trade profession bonuses apply +50% XP and +1 qty chance during gathering.

### Abilities (`abilities.py`)

Six abilities per class, unlocked by `level_req`. Damage abilities deal `mult × Player.ability_power` (ATK for Warriors/Rogues, `spell_power` = INT × `SPELL_INT_MULT` + weapon ATK for Mages); `status`/`status_chance` apply an enemy status on hit (Shield Bash → Stunned, Ice Lance → Chilled, Fireball → Burning). Profession multipliers (e.g. Sorcerer +30% damage, Trickster +2 poison turns) are applied inline in `combat.py`.

Buff abilities put `{name: turns}` into `player.buffs`, which `tick_buffs()` counts down each turn. A buff only does something if code checks for its name: `Berserk` and `Battle Cry` in `Player.attack`/`defense`, `Evasion` and `Mana Shield` in `hit_player()` (`combat.py`), which all enemy damage goes through.

### Combat (`combat.py`, `enemies.py`)

One `do_combat_turn` call = player acts (attack / ability / item / **defend** / flee) → enemy DoT ticks → enemy acts → statuses tick. Flee chance (`flee_chance`) is 40% + 0.8% per SPD, −20% vs bosses, clamped to 10–90%. Defend blocks `defend_reduction(player)`% (50, or 75 with the Knight's Bastion). Abilities with `mp_cost == 0` stay free under Arcane Flow. A refused action (an ability you can't afford, an item `use_consumable` refuses such as a revive item or a capped elixir, a Smoke Arrow in the final battle) costs no turn: `do_combat_turn` returns `'continue'` before the enemy acts. Enemy multi-hit abilities stop as soon as the attacker dies (Riposte/Thorns) and a dead attacker applies no rider effects. Defense is a **percentage** reduction: `mitigate(dmg, def) = dmg × 100 / (100 + def)` — never flat subtraction (that made early bosses harmless and late bosses unkillable).

- **Enemy abilities** are data: `ENEMY_ABILITIES` in `enemies.py` maps every ability name to a spec (`kind` ∈ hit, drain, dot, stun, weaken, enrage, shield, evade; plus `mult`, `hits`, `status`, `turns`, `chance`, `charge`). `test_every_enemy_ability_does_something` fails if a new enemy ability has no effect. Enemies use an ability 30% of turns (bosses 40%, phase 2 55%).
- **Telegraphs**: specs with `charge: True` spend a turn charging (`enemy.charging`) and fire next turn. Players counter by Defending (half damage, no stuns), dodging (Evasion) or stunning the enemy, which interrupts the charge.
- **Player debuffs** live in `player.debuffs` as `{name: {turns, dmg}}`: Poisoned/Burning/Bleeding (DoTs that ignore defense), Weakened (ATK -25%), Stunned (skips the next action, then grants 2 turns of `Steadfast` stun immunity). Antidotes (`cure`) clear them. `end_combat()` clears debuffs whenever a fight ends.
- **Enemy statuses** live in `enemy.statuses` as `{name: turns}`: Chilled, Enraged, Shielded, Evading. Bosses enter **phase 2** below 50% HP (+15% ATK, more abilities, `phase2` flavour text).

### Balance (`tools/balance_sim.py`)

All scaling constants are named knobs at the top of their module: `MOB_HP_MULT`, `MOB_*_GROWTH`, `BOSS_*_GROWTH`, `NG_PLUS_POWER`, `DEF_K` (`enemies.py`), `SPELL_INT_MULT` and `CLASS_GROWTH` (`player.py`). Change them, then run the simulator — it plays each class against every zone's mobs and bosses and the final boss and prints win rate, turns and HP left. The bot is a reasonable player, not an optimal one. Targets used so far: regular fights 2–4 turns ending at 60–90% HP; zone bosses ~70–100% at zone level + 2 with 3 potions; final boss ≥40% for every class with Epic gear. The level cap is 19 (`len(XP_TABLE) - 1`).

### Zones and Level Requirements (`world.py`)

Five zones (ids 1–5) with `ZONE_LEVEL_REQ = {1:1, 2:5, 3:10, 4:15, 5:18}`. Each zone has one boss in `BOSS_TEMPLATES` (Goblin King, Undead Warlord, Arcane Lich King, Shadow Sovereign, Ignaroth the Elder Wyrm); killing it the first time breaks that zone's seal (`state['seals']`), in any order. With all five broken, the hub in zone 5 offers the final battle against `FINAL_BOSS` (Chaos Dragon Lord, `spawn_final_boss`). Winning shows the `ending` screen, which offers **New Game+**: keep the character and gear, reset seals, named events and the trail (depth, offered paths), and every enemy gets `× (1 + NG_PLUS_POWER × cycle)` stats plus better loot luck.

## Key Conventions

- **Adding a new screen** in the web app requires: a new `elif screen == 'new_screen':` block in the `/action` route, a `templates/screens/new_screen.html` file (`test_every_screen_has_a_template` fails without it), and any new state keys initialized in `fresh_state()`.
- **Profession passives** are applied inline via `if player.profession == 'X':` guards in `combat.py` and the `Player` stat properties. Adding a new profession requires updating those guards, `PROFESSIONS` in `player.py`, the template, and a test in `tests/test_combat_effects.py`.
- **Inn**: `inn_prices(player)` → (full, nap): full = 10 + 6·level + missing HP/8 + missing MP/8; nap = 40% of that and restores half of the *missing* HP/MP (`nap_restore`), so repeated naps always cost more than one Full Rest (`test_repeated_naps_never_beat_full_rest`). At full HP/MP the Inn shows no paid rest.
- **Session state** is pickled Python objects. New `Player`/`Enemy` attributes must get a default in that class's `__setstate__` (or a class-level default, as `Item` does) so older saves still load; new state-dict keys go in `fresh_state()` (picked up by `migrate_state()`). When a stat *rule* changes, bump `STATS_VERSION` in `player.py` and add a migration (see `_migrate_stats_v2`).
- The `SECRET_KEY` for Flask sessions should be set via the `SECRET_KEY` environment variable in production; without it a random per-process key is used, so sessions reset on every restart. The session `sid` is validated as a canonical UUID before it is used as a save filename.
