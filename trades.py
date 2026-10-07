"""Trade profession gameplay: skill milestones and profession discoveries on the trail.

Trade skills (Mining, Smithing, Herbalism, ...) are levelled 1–20 by everyone; the
trade profession only speeds two of them up (+50% XP, see crafting.TRADE_PROFESSIONS).
Milestones are keyed to those existing skill levels — there is no separate mastery bar.

Rule: TRADE_MILESTONES lists only unlocks that are implemented. Each entry names its
behaviour and has a test (tests/test_trades.py checks coverage).
"""
import random

MILESTONE_LEVELS = (5, 10, 15, 20)

# skill -> {level: (title, what it unlocks)}
TRADE_MILESTONES = {
    "Smithing":  {5: ("Battlefield Salvage", "Blacksmiths can find old battlefields on the trail: metal bars and salvaged gear.")},
    "Herblore":  {5: ("Abandoned Apothecary", "Alchemists can find ruined apothecaries on the trail: potions and rare herbs.")},
    "Cooking":   {5: ("Smokehouse Ruins", "Fishers can find old smokehouses on the trail: preserved food.")},
    "Fletching": {5: ("Hunter's Cache", "Fletchers can find hunters' caches on the trail: seasoned timber and a hunting weapon.")},
}


def skill_level(player, skill):
    for table in (player.gathering_skills, player.crafting_skills):
        if skill in table:
            return table[skill]["level"]
    return 0


def has_milestone(player, skill, level):
    return level in TRADE_MILESTONES.get(skill, {}) and skill_level(player, skill) >= level


def milestones_between(skill, old_level, new_level):
    """Milestones crossed when `skill` went from old_level to new_level."""
    return [(lv, *TRADE_MILESTONES[skill][lv]) for lv in sorted(TRADE_MILESTONES.get(skill, {}))
            if old_level < lv <= new_level]


def next_milestone(player, skill):
    lv = skill_level(player, skill)
    for m in sorted(TRADE_MILESTONES.get(skill, {})):
        if m > lv:
            return (m, *TRADE_MILESTONES[skill][m])
    return None


# ── Profession discoveries on the trail ────────────────────────────────────────
# Offered as an extra explore path kind ("trade") only to players with the trade
# profession, and only once its skill requirement is met.

def _zone_res(zone, skill):
    from crafting import ZONE_RESOURCES
    return [name for name, _, _ in ZONE_RESOURCES.get(zone, ZONE_RESOURCES[1]).get(skill, [])]


# The level-1 discovery of each trade: its gathering skill yields a bigger haul.
BASIC_DISCOVERY_SKILL = {"ore_vein": "Mining", "herb_patch": "Herbalism",
                         "hidden_pool": "Fishing", "fallen_tree": "Woodcutting"}

# Basic discovery -> (node builder, intro) once its milestone is reached (builders defined below).
DISCOVERY_NODES = {
    "ore_vein":    ("make_vein_node", "You find an exposed vein."),
    "herb_patch":  ("make_patch_node", "You find a lush herb patch."),
    "hidden_pool": ("make_bite_node", "Something big moves in the pool."),
}

ZONE_BAR = {1: "Bronze Bar", 2: "Iron Bar", 3: "Steel Bar", 4: "Mithril Bar", 5: "Adamantite Bar"}

PROFESSION_EVENTS = {
    "Blacksmith": [
        {"id": "ore_vein", "skill": "Mining", "level": 1, "icon": "⛏",
         "title": "Exposed ore vein", "detail": "Ore lies bare in the rock · 3–5 ore"},
        {"id": "salvage", "skill": "Smithing", "level": 5, "icon": "⚔",
         "title": "Old battlefield", "detail": "Salvage metal bars, maybe gear"},
    ],
    "Alchemist": [
        {"id": "herb_patch", "skill": "Herbalism", "level": 1, "icon": "🌿",
         "title": "Wild herb patch", "detail": "Untouched herbs · 3–5 herbs"},
        {"id": "apothecary", "skill": "Herblore", "level": 5, "icon": "⚗",
         "title": "Abandoned apothecary", "detail": "Dusty shelves · potions and rare herbs"},
    ],
    "Fisher": [
        {"id": "hidden_pool", "skill": "Fishing", "level": 1, "icon": "🎣",
         "title": "Hidden pool", "detail": "Fish teem in still water · 3–5 fish"},
        {"id": "smokehouse", "skill": "Cooking", "level": 5, "icon": "🍖",
         "title": "Smokehouse ruins", "detail": "Preserved food left behind"},
    ],
    "Fletcher": [
        {"id": "fallen_tree", "skill": "Woodcutting", "level": 1, "icon": "🪵",
         "title": "Fallen tree", "detail": "Storm-felled timber · 3–5 logs"},
        {"id": "hunter_cache", "skill": "Fletching", "level": 5, "icon": "🏹",
         "title": "Hunter's cache", "detail": "Seasoned timber, maybe a weapon"},
    ],
}


def available_trade_events(player, zone):
    """Discoveries this player can be offered here (profession + skill level + zone resources)."""
    out = []
    for ev in PROFESSION_EVENTS.get(player.trade_profession, []):
        if skill_level(player, ev["skill"]) < ev["level"]:
            continue
        gather_skill = BASIC_DISCOVERY_SKILL.get(ev["id"])
        if gather_skill and not _zone_res(zone, gather_skill):
            continue
        if ev["id"] == "remains" and not zone_reagents(zone):
            continue
        out.append(ev)
    return out


def describe_trade_event(event_id, trade):
    ev = next(e for e in PROFESSION_EVENTS[trade] if e["id"] == event_id)
    return f"{ev['icon']} {ev['title']}", f"{trade} discovery · {ev['detail']}"


def _grant(player, name, qty):
    player.add_resource(name, qty)
    return f"{qty}× {name}"


def resolve_trade_event(event_id, player, zone, depth):
    """Outcome tuples in the explore event format (see world.resolve_option)."""
    from items import Item, generate_armor, generate_weapon
    lvl = player.level
    if event_id in DISCOVERY_NODES:
        # Once the gathering milestone is reached, the basic find becomes an interactive node.
        builder, intro = DISCOVERY_NODES[event_id]
        node = globals()[builder](player, zone)
        if node:
            return [("node", node, intro)]
    if event_id in BASIC_DISCOVERY_SKILL:
        skill = BASIC_DISCOVERY_SKILL[event_id]
        got = [_grant(player, random.choice(_zone_res(zone, skill)), 1) for _ in range(random.randint(3, 5))]
        player.gain_skill_xp("gathering", skill, 20 + 5 * zone)
        return [("resource", 0, f"You harvest the find: {', '.join(got)} (+{20 + 5 * zone} {skill} XP)")]
    if event_id == "remains":
        return _resolve_remains(player, zone)
    if event_id == "tracks":
        player.armed_trap = True
        player.gain_skill_xp("gathering", "Woodcutting", 15)
        return [("resource", 0, "You set an ambush along the tracks. Your next fight starts with the enemy snared.")]
    if event_id == "salvage":
        msg = f"You pick through the wreckage: {_grant(player, ZONE_BAR[zone], random.randint(1, 3))}"
        events = [("resource", 0, msg)]
        if random.random() < 0.4:
            gear = random.choice([generate_weapon(player.player_class, lvl), generate_armor(lvl, player_class=player.player_class)])
            events.append(("item", gear, "Half-buried in the mud:"))
        return events
    if event_id == "apothecary":
        herbs = _zone_res(zone, "Herbalism")
        events = [("resource", 0, f"Among the shelves: {_grant(player, herbs[-1], random.randint(2, 3))}")]
        potion = Item("Greater Health Potion", "consumable", "Common", 100, effect="heal_pct", effect_value=50)
        events.append(("item", potion, "A sealed flask survived:"))
        return events
    if event_id == "smokehouse":
        fish = _zone_res(zone, "Fishing")[0]
        cooked = "Cooked " + fish.replace("Raw ", "")
        food = Item(cooked, "consumable", "Common", 20, effect="heal_pct", effect_value=15 + 5 * zone)
        food.category = "food"
        return [("item", food, "Hanging in the smoke, still good:"),
                ("resource", 0, f"And in a barrel: {_grant(player, fish, 2)}")]
    if event_id == "hunter_cache":
        logs = _zone_res(zone, "Woodcutting")
        events = [("resource", 0, f"Seasoned timber: {_grant(player, logs[-1], random.randint(2, 4))}")]
        if random.random() < 0.35:
            events.append(("item", generate_weapon(player.player_class, lvl), "A hunter's spare weapon:"))
        return events
    return [("nothing", 0, "Whatever was here is gone.")]


# ── Special nodes (shared) ─────────────────────────────────────────────────────
# A node is an interactive moment (ore vein, hard bite, pristine patch, ancient tree).
# It's a plain dict stored in state['pending_node'] and shown on the `node` screen:
#   {"type", "title", "text", "options": [{"key", "label", "detail"}], ...type data}
# resolve_node(node, key, player) returns explore-style event tuples.

def resolve_node(node, key, player):
    if key == "leave":
        return [("nothing", 0, "You leave it be.")]
    return NODE_RESOLVERS[node["type"]](node, key, player)


# ── Blacksmith: ore veins ──────────────────────────────────────────────────────
VEIN_CHANCE = 0.15            # chance a Mining tap at Mining 5+ uncovers a special vein
CAVE_IN_CHANCE = 0.25
CAVE_IN_DAMAGE_PCT = 15
STARMETAL = "Starmetal"
GEMS = ("Rough Gem", "Flawless Gem")

TRADE_MILESTONES.setdefault("Mining", {}).update({
    5:  ("Ore Sense", "Special veins can appear while mining: choose safe or deep extraction."),
    10: ("Prospecting", "Prospect a vein for gems (forge additives) instead of ore."),
    15: ("Deep Veins", "Deep mining can strike the richer ore of the next zone."),
    20: ("Starmetal", "Deep mining and prospecting can unearth Starmetal, a legendary forging material."),
})
TRADE_MILESTONES["Smithing"].update({
    10: ("Gem Inlay", "Set a gem into a forging to raise its quality odds."),
    15: ("Tempering", "Temper crafted gear once: Hone, Reinforce or Heavy Plating."),
    20: ("Starforging", "Forge with Starmetal: the only way to craft Legendary gear."),
})


def _best_ore(player, zone):
    from crafting import ZONE_RESOURCES
    lv = skill_level(player, "Mining")
    ores = [(req, -i, n) for i, (n, _, req) in enumerate(ZONE_RESOURCES.get(zone, {}).get("Mining", [])) if lv >= req]
    return max(ores)[2] if ores else None  # the zone's main ore: highest level, first listed (Iron over Coal)


def _deep_ore(zone):
    from crafting import ZONE_RESOURCES
    nxt = ZONE_RESOURCES.get(min(zone + 1, 5), {}).get("Mining", [])
    return nxt[0][0] if nxt else None


def make_vein_node(player, zone):
    ore = _best_ore(player, zone)
    if not ore or not has_milestone(player, "Mining", 5):
        return None
    deep_ore = _deep_ore(zone) if has_milestone(player, "Mining", 15) else None
    star = has_milestone(player, "Mining", 20)
    deep_detail = f"6–8 {ore}" + (f", may strike {deep_ore}" if deep_ore and deep_ore != ore else "") \
        + (", rare Starmetal" if star else "") + f" · {int(CAVE_IN_CHANCE * 100)}% cave-in risk (−{CAVE_IN_DAMAGE_PCT}% HP, 1–2 ore)"
    options = [
        {"key": "safe", "label": "⛏ Safe extraction", "detail": f"3–4 {ore} · no risk"},
        {"key": "deep", "label": "⚒ Deep mining", "detail": deep_detail},
    ]
    if has_milestone(player, "Mining", 10):
        options.append({"key": "prospect", "label": "💎 Prospect",
                        "detail": "1–2 ore · 60% chance of a gem (1 in 6 flawless)" + (", rare Starmetal" if star else "")})
    options.append({"key": "leave", "label": "↩ Leave it", "detail": ""})
    return {"type": "vein", "zone": zone, "ore": ore, "deep_ore": deep_ore, "star": star,
            "title": f"A rich {ore.replace(' Ore', '').lower()} vein",
            "text": "The rock is laced with ore. How do you work it?", "options": options}


def _resolve_vein(node, key, player):
    ore, zone = node["ore"], node["zone"]
    found = []

    def add(name, qty):
        player.add_resource(name, qty)
        found.append(f"{qty}× {name}")

    if key == "safe":
        add(ore, random.randint(3, 4))
        xp = 30 + 5 * zone
    elif key == "deep":
        xp = 60 + 10 * zone
        if random.random() < CAVE_IN_CHANCE:
            add(ore, random.randint(1, 2))
            player.gain_skill_xp("gathering", "Mining", xp // 2)
            return [("trap_pct", CAVE_IN_DAMAGE_PCT, "The tunnel caves in!"),
                    ("resource", 0, f"You dig out {', '.join(found)} (+{xp // 2} Mining XP)")]
        add(ore, random.randint(6, 8))
        if node.get("deep_ore") and random.random() < 0.4:
            add(node["deep_ore"], random.randint(1, 2))
        if node.get("star") and random.random() < 0.08:
            add(STARMETAL, 1)
    elif key == "prospect":
        add(ore, random.randint(1, 2))
        if random.random() < 0.6:
            add(GEMS[1] if random.random() < 1 / 6 else GEMS[0], 1)
        if node.get("star") and random.random() < 0.12:
            add(STARMETAL, 1)
        xp = 45 + 5 * zone
    else:
        return [("nothing", 0, "")]
    player.gain_skill_xp("gathering", "Mining", xp)
    return [("resource", 0, f"You work the vein: {', '.join(found)} (+{xp} Mining XP)")]


NODE_RESOLVERS = {"vein": _resolve_vein}


# ── Blacksmith: forging quality ────────────────────────────────────────────────
# Crafted quality *is* item rarity (no second quality system). A uniform roll plus a
# shift picks the tier; the shift comes from skill margin over the recipe, additives
# and the Masterwork perk. Legendary is only possible with Starmetal.
QUALITY_BANDS = [("Common", 0.40), ("Uncommon", 0.75), ("Rare", 1.05), ("Epic", 1.30)]  # upper bounds
MARGIN_SHIFT, MARGIN_CAP = 0.02, 10   # +2% per Smithing level above the recipe, up to 10 levels
ADDITIVES = {  # name: (quality shift, Smithing level needed)
    "Rough Gem":    (0.10, 10),
    "Flawless Gem": (0.20, 10),
    STARMETAL:      (0.30, 20),
}
MASTERWORK_SHIFT = 0.10


def craft_shift(player, skill, recipe, additive=None):
    """Quality-roll shift at a workshop (Smithing forge or Fletching bench)."""
    from crafting import MASTERWORK_SKILLS
    margin = max(0, min(MARGIN_CAP, skill_level(player, skill) - recipe["req"]))
    shift = margin * MARGIN_SHIFT
    if additive:
        shift += WORKSHOP_ADDITIVES[skill][additive][0]
    if MASTERWORK_SKILLS.get(player.trade_profession) == skill:
        shift += MASTERWORK_SHIFT
    return shift


def forge_shift(player, recipe, additive=None):
    return craft_shift(player, "Smithing", recipe, additive)


def quality_odds(shift, legendary_possible=False):
    """Exact tier probabilities for roll ~ U[0,1) + shift."""
    bands = QUALITY_BANDS if legendary_possible else QUALITY_BANDS[:3] + [("Epic", float("inf"))]
    odds, lo = {}, float("-inf")
    for name, hi in bands:
        a, b = max(0.0, lo - shift), min(1.0, hi - shift)
        odds[name] = max(0.0, b - a)
        lo = hi
    if legendary_possible:
        odds["Legendary"] = max(0.0, 1.0 - max(0.0, QUALITY_BANDS[-1][1] - shift))
    return {k: round(v, 4) for k, v in odds.items() if v > 0}


def roll_quality(shift, legendary_possible=False):
    r = random.random() + shift
    for name, hi in QUALITY_BANDS:
        if r < hi:
            return name
    return "Legendary" if legendary_possible else "Epic"


def usable_additives(player, skill="Smithing"):
    return [a for a, (_, lv) in WORKSHOP_ADDITIVES[skill].items()
            if skill_level(player, skill) >= lv and player.resources.get(a, 0) > 0]


def can_craft_at_bench(player, skill, recipe):
    return (skill_level(player, skill) >= recipe["req"]
            and all(player.resources.get(r, 0) >= q for r, q in recipe["inputs"].items()))


def can_forge(player, recipe):
    return can_craft_at_bench(player, "Smithing", recipe)


def forge(player, recipe, slot, additive=None):
    """Spend the recipe's bars (+ additive) and forge. Returns (ok, message, item)."""
    return bench_craft(player, "Smithing", recipe, slot, additive)


# ── Blacksmith: tempering ──────────────────────────────────────────────────────
TEMPER_LEVEL = 15


def temper_options(player, item):
    """Tempers available for this item right now, with their cost: [(name, text, gold, bar)]."""
    from items import METALS, TEMPERS, TEMPER_TEXT
    if (not item or not item.crafted or item.temper or item.material not in METALS
            or not has_milestone(player, "Smithing", TEMPER_LEVEL)):
        return []
    tier = list(METALS).index(item.material) + 1
    bar = f"{item.material} Bar"
    return [(name, TEMPER_TEXT[name], 40 * tier, bar)
            for name, (slot, _, _) in TEMPERS.items() if slot == item.item_type]


def temper(player, item, name):
    opts = {n: (g, bar) for n, _, g, bar in temper_options(player, item)}
    if name not in opts:
        return False, "That can't be tempered."
    gold, bar = opts[name]
    if player.gold < gold or player.resources.get(bar, 0) < 1:
        return False, f"Tempering costs {gold}g and 1× {bar}."
    player.gold -= gold
    player.remove_resource(bar, 1)
    old_hp = item.stats.get("hp", 0)
    item.apply_temper(name)
    if item in player.equipment.values():
        player._grow_pools(item.stats.get("hp", 0) - old_hp, 0)
    return True, f"Tempered {item.name}: {name}."


# ── Alchemist: ingredients, experiments, journal ───────────────────────────────
# Every ingredient has a main and a secondary property. Herbalism reveals them
# (5: main, 15: secondary); monster reagents always show their main property.
# Mixing two ingredients whose MAIN properties form a recipe's pair discovers it.
# One main + the other's SECONDARY makes a weak, unstable version and a hint.
INGREDIENTS = {
    "Guam Leaf":      ("Vitality",     "Restoration"),
    "Marrentill":     ("Purification", "Vitality"),
    "Tarromin":       ("Strength",     "Fortification"),
    "Harralander":    ("Fortification", "Purification"),
    "Ranarr Weed":    ("Restoration",  "Clarity"),
    "Irit Leaf":      ("Clarity",      "Arcane"),
    "Kwuarm":         ("Power",        "Strength"),
    "Snapdragon":     ("Renewal",      "Restoration"),
    "Lantadyme":      ("Arcane",       "Clarity"),
    "Torstol":        ("Potency",      "Power"),
    # monster reagents (combat drops) and the legendary bloom
    "Vampire Fang":   ("Lifeblood",    "Power"),
    "Dragon Scale":   ("Draconic",     "Fortification"),
    "Shadow Essence": ("Void",         "Arcane"),
    "Starbloom":      ("Mythic",       "Renewal"),
}
MONSTER_REAGENTS = {"Vampire Fang": ["Vampire"], "Dragon Scale": ["Wyvern", "Ancient Dragon"],
                    "Shadow Essence": ["Shadow Assassin", "Void Stalker"]}
REAGENT_DROP_CHANCE = 0.30

# Discoverable recipes: frozenset of two MAIN properties -> brew spec (existing consumable effects).
ALCHEMY_RECIPES = {
    frozenset({"Vitality", "Restoration"}):     {"name": "Healing Draught",       "effect": "heal_pct",      "value": 40},
    frozenset({"Strength", "Power"}):           {"name": "Draught of Might",      "effect": "temp_buff_str", "value": 18, "duration": 4},
    frozenset({"Fortification", "Vitality"}):   {"name": "Ironskin Tonic",        "effect": "temp_buff_vit", "value": 15, "duration": 4},
    frozenset({"Clarity", "Restoration"}):      {"name": "Clarity Draught",       "effect": "heal_mp_pct",   "value": 50},
    frozenset({"Purification", "Renewal"}):     {"name": "Panacea",               "effect": "cure_heal",     "value": 25},
    frozenset({"Arcane", "Potency"}):           {"name": "Elixir of the Arcane",  "effect": "temp_buff_all", "value": 10, "duration": 5},
    frozenset({"Lifeblood", "Restoration"}):    {"name": "Crimson Draught",       "effect": "heal_overheal", "value": 70},
    frozenset({"Draconic", "Fortification"}):   {"name": "Dragonblood Elixir",    "effect": "temp_buff_all", "value": 15, "duration": 6},
    frozenset({"Void", "Arcane"}):              {"name": "Void Tonic",            "effect": "heal_mp_pct",   "value": 100},
    frozenset({"Mythic", "Restoration"}):       {"name": "Phoenix Draught",       "effect": "revive",        "value": 1},
}
UNSTABLE_POTENCY = 0.5
POTENT_BREW_BONUS = 1.25   # Herblore 15

TRADE_MILESTONES.setdefault("Herbalism", {}).update({
    5:  ("Herb Lore", "See each herb's main property at the alchemy bench."),
    10: ("Rare Patches", "Special herb patches can appear while foraging: harvest quickly or carefully."),
    15: ("Keen Eye", "See each herb's secondary property — the key to unstable mixes."),
    20: ("Mythic Bloom", "Careful harvests can uncover Starbloom, a legendary reagent."),
})
TRADE_MILESTONES["Herblore"].update({
    10: ("Reagent Lore", "Alchemists can find monster remains on the trail: alchemical reagents."),
    15: ("Potent Brews", "Recipes from your journal brew 25% stronger."),
})


def journal(player):
    return player.alchemy_journal


def known_properties(player, ingredient):
    """(main, secondary) with '?' for what this player hasn't learned to see yet."""
    main, sec = INGREDIENTS[ingredient]
    reagent = ingredient in MONSTER_REAGENTS or ingredient == "Starbloom"
    show_main = reagent or skill_level(player, "Herbalism") >= 5
    show_sec = skill_level(player, "Herbalism") >= 15
    return (main if show_main else "?"), (sec if show_sec else "?")


def owned_ingredients(player):
    return [n for n in INGREDIENTS if player.resources.get(n, 0) > 0]


def _brew_item(spec, potency=1.0, unstable=False):
    from items import Item
    value = max(1, int(round(spec["value"] * potency))) if spec["effect"] != "revive" else 1
    name = spec["name"] + (" (unstable)" if unstable else "")
    item = Item(name, "consumable", "Common", 30 if not unstable else 10, effect=spec["effect"],
                effect_value=value, effect_duration=spec.get("duration", 0))
    item.category = "potion"
    return item


def experiment(player, a, b):
    """Mix one each of ingredients a and b. Returns (kind, message, item_or_None).
    kind: 'discovery' | 'known' | 'unstable' | 'fail'."""
    if a == b or a not in INGREDIENTS or b not in INGREDIENTS:
        return "invalid", "Choose two different ingredients.", None
    if player.resources.get(a, 0) < 1 or player.resources.get(b, 0) < 1:
        return "invalid", "You don't have those ingredients.", None
    player.remove_resource(a, 1)
    player.remove_resource(b, 1)
    (ma, sa), (mb, sb) = INGREDIENTS[a], INGREDIENTS[b]
    j = journal(player)
    spec = ALCHEMY_RECIPES.get(frozenset({ma, mb}))
    if spec and ma != mb:
        new = spec["name"] not in j["recipes"]
        j["recipes"][spec["name"]] = (a, b)
        item = _brew_item(spec)
        player.add_item(item)
        player.gain_skill_xp("crafting", "Herblore", 60 if new else 25)
        return ("discovery" if new else "known"), (
            f"✨ NEW RECIPE: {spec['name']}! Written into your journal." if new else f"You brew {spec['name']}."), item
    for main, other_sec, partner in ((ma, sb, b), (mb, sa, a)):
        spec = ALCHEMY_RECIPES.get(frozenset({main, other_sec}))
        if spec and main != other_sec:
            missing = other_sec
            j["hints"][spec["name"]] = f"{main} + {missing} → {spec['name']}? ({partner} only carries {missing} faintly)"
            item = _brew_item(spec, UNSTABLE_POTENCY, unstable=True)
            player.add_item(item)
            player.gain_skill_xp("crafting", "Herblore", 20)
            return "unstable", (f"The mixture fizzes — an unstable {spec['name']}. "
                                f"Something with {missing} as its main property would make it whole."), item
    player.gain_skill_xp("crafting", "Herblore", 10)
    if random.random() < 0.3:
        player.hp = max(1, player.hp - max(1, player.max_hp // 20))
        return "fail", "The mixture spits acrid fumes in your face. (−5% HP)", None
    return "fail", "Nothing useful comes of it. The properties don't combine.", None


def brew_known(player, name):
    """One-tap brew of a journal recipe with the same two ingredients."""
    from crafting import DOUBLE_CRAFT_SKILLS, DOUBLE_CRAFT_CHANCE
    pair = journal(player)["recipes"].get(name)
    if not pair:
        return False, "You haven't discovered that recipe.", None
    a, b = pair
    if player.resources.get(a, 0) < 1 or player.resources.get(b, 0) < 1:
        return False, f"Needs 1× {a} and 1× {b}.", None
    player.remove_resource(a, 1)
    player.remove_resource(b, 1)
    spec = next(s for s in ALCHEMY_RECIPES.values() if s["name"] == name)
    potency = POTENT_BREW_BONUS if has_milestone(player, "Herblore", 15) else 1.0
    copies = 2 if DOUBLE_CRAFT_SKILLS.get(player.trade_profession) == "Herblore" and random.random() < DOUBLE_CRAFT_CHANCE else 1
    for _ in range(copies):
        item = _brew_item(spec, potency)
        player.add_item(item)
    player.gain_skill_xp("crafting", "Herblore", 25)
    return True, f"You brew {name}{' ×2!' if copies == 2 else ''}.", item


def reagent_drop(enemy_name):
    """A monster reagent dropped by this enemy (or None)."""
    for reagent, sources in MONSTER_REAGENTS.items():
        if any(src in enemy_name for src in sources) and random.random() < REAGENT_DROP_CHANCE:
            return reagent
    return None


# Rare herb patches (Herbalism 10+)
PATCH_CHANCE = 0.15
STING_CHANCE = 0.20


def _zone_herbs(player, zone):
    from crafting import ZONE_RESOURCES
    lv = skill_level(player, "Herbalism")
    return [n for n, _, req in ZONE_RESOURCES.get(zone, {}).get("Herbalism", []) if lv >= req]


def make_patch_node(player, zone):
    herbs = _zone_herbs(player, zone)
    if not herbs or not has_milestone(player, "Herbalism", 10):
        return None
    nxt = _zone_res(min(zone + 1, 5), "Herbalism")
    bloom = has_milestone(player, "Herbalism", 20)
    careful = f"1–2 herbs, 50% chance of {nxt[0]}" + (", rare Starbloom" if bloom else "") \
        + f" · {int(STING_CHANCE * 100)}% chance of a poisonous sting (−10% HP)"
    return {"type": "patch", "zone": zone, "herbs": herbs, "rare": nxt[0], "bloom": bloom,
            "title": "A lush herb patch", "text": "Rare plants grow among the common ones.",
            "options": [{"key": "quick", "label": "🌿 Harvest quickly", "detail": "3–4 common herbs · no risk"},
                        {"key": "careful", "label": "🔍 Harvest carefully", "detail": careful},
                        {"key": "leave", "label": "↩ Leave it", "detail": ""}]}


def _resolve_patch(node, key, player):
    found = []

    def add(name, qty):
        player.add_resource(name, qty)
        found.append(f"{qty}× {name}")
    events = []
    if key == "quick":
        for _ in range(random.randint(3, 4)):
            add(random.choice(node["herbs"]), 1)
        xp = 30 + 5 * node["zone"]
    elif key == "careful":
        if random.random() < STING_CHANCE:
            events.append(("trap_pct", 10, "A thorned leaf stings you!"))
        add(random.choice(node["herbs"]), random.randint(1, 2))
        if random.random() < 0.5:
            add(node["rare"], 1)
        if node.get("bloom") and random.random() < 0.10:
            add("Starbloom", 1)
        xp = 50 + 8 * node["zone"]
    else:
        return [("nothing", 0, "")]
    player.gain_skill_xp("gathering", "Herbalism", xp)
    return events + [("resource", 0, f"You harvest {', '.join(found)} (+{xp} Herbalism XP)")]


NODE_RESOLVERS["patch"] = _resolve_patch

PROFESSION_EVENTS["Alchemist"].append(
    {"id": "remains", "skill": "Herblore", "level": 10, "icon": "🦴",
     "title": "Monster remains", "detail": "Harvest alchemical reagents from a carcass"})


def zone_reagents(zone):
    """Reagents whose source monsters can spawn in this zone (spawn_enemy uses zone <= current),
    so trail remains never hand out a reagent before its monster belongs in the progression."""
    from enemies import ENEMY_TEMPLATES
    names = [t["name"] for t in ENEMY_TEMPLATES if t["zone"] <= zone]
    return [r for r, sources in MONSTER_REAGENTS.items()
            if any(src in n for src in sources for n in names)]


def _resolve_remains(player, zone):
    found = zone_reagents(zone)
    if not found:   # only offered where reagents exist; this guards old pending paths
        return [("nothing", 0, "The remains are too far gone to harvest anything useful.")]
    reagent = random.choice(found)
    player.add_resource(reagent, 1)
    return [("resource", 0, f"You carefully harvest 1× {reagent} from the remains.")]


# ── Fisher: hard bites, trophies, meals ────────────────────────────────────────
BITE_CHANCE = 0.15
TEMPERAMENTS = {
    # trait: (cue shown to everyone, {response: success chance})
    "aggressive": ("The line jerks violently from side to side!",  {"tire": 0.9, "steady": 0.5, "reel": 0.15}),
    "heavy":      ("Something heavy drags the line straight down.", {"steady": 0.9, "reel": 0.5, "tire": 0.15}),
    "elusive":    ("The line goes slack — then darts away.",        {"reel": 0.9, "tire": 0.5, "steady": 0.15}),
}
RESPONSES = {"reel": "🎣 Reel aggressively", "tire": "⏳ Let it tire", "steady": "🪢 Keep steady tension"}
TROPHY_FISH = {1: "Large Trout", 2: "Trophy Salmon", 3: "Ancient Golden Trout", 4: "Voidfin",
               5: "Emberscale Leviathan"}
LEGENDARY_FISH = "Ashvale River King"
LEGENDARY_FISH_ZONE = 1   # the river by the Starter Village: Fishing 20 is a reason to go home
TROPHY_CHANCE, LEGENDARY_CHANCE = 0.35, 0.10

TRADE_MILESTONES.setdefault("Fishing", {}).update({
    5:  ("Hard Bites", "Strong fish can take the line while fishing: read the cue and choose how to fight it."),
    10: ("Read the Water", "See a hooked fish's temperament outright, and hook rarer fish from deeper waters."),
    15: ("Trophy Fish", "A well-played catch can land a trophy fish for your catch log and a feast."),
    20: ("Legendary Catches", "The Ashvale River King can take your line — but only in the river by the Starter Village (zone 1)."),
})
TRADE_MILESTONES["Cooking"].update({
    10: ("Trophy Feasts", "Cook trophy fish into feasts: all stats up for many fights."),
    15: ("Slow Cooking", "Meals you eat last 2 more fights."),
})


def _zone_fish(player, zone):
    from crafting import ZONE_RESOURCES
    lv = skill_level(player, "Fishing")
    return [n for n, _, req in ZONE_RESOURCES.get(zone, {}).get("Fishing", []) if lv >= req]


def make_bite_node(player, zone):
    fish = _zone_fish(player, zone)
    if not fish or not has_milestone(player, "Fishing", 5):
        return None
    trait = random.choice(list(TEMPERAMENTS))
    if has_milestone(player, "Fishing", 10) and zone < 5 and random.random() < 0.4:
        fish = _zone_res(zone + 1, "Fishing")[:1]   # a rarer fish from deeper water
    cue, _ = TEMPERAMENTS[trait]
    text = cue + (f" It's {trait}." if has_milestone(player, "Fishing", 10) else "")
    return {"type": "bite", "zone": zone, "fish": fish[0], "trait": trait,
            "trophy": has_milestone(player, "Fishing", 15), "legendary": has_milestone(player, "Fishing", 20) and zone == LEGENDARY_FISH_ZONE,
            "title": "Something big is on the line!", "text": text,
            "options": [{"key": k, "label": label, "detail": ""} for k, label in RESPONSES.items()]
                       + [{"key": "leave", "label": "✂ Cut the line", "detail": ""}]}


def _resolve_bite(node, key, player):
    _, odds = TEMPERAMENTS[node["trait"]]
    zone, fish = node["zone"], node["fish"]
    if random.random() >= odds[key]:
        player.gain_skill_xp("gathering", "Fishing", 15)
        return [("nothing", 0, f"The line snaps — it was {node['trait']}, and it got away. (+15 Fishing XP)")]
    qty = random.randint(2, 3)
    player.add_resource(fish, qty)
    xp = 50 + 10 * zone
    caught = [f"{qty}× {fish}"]
    best = odds[key] == max(odds.values())
    events = []
    if best and node.get("legendary") and zone == LEGENDARY_FISH_ZONE and random.random() < LEGENDARY_CHANCE:
        events += _land_trophy(player, LEGENDARY_FISH)
        caught.append(LEGENDARY_FISH)
    elif best and node.get("trophy") and random.random() < TROPHY_CHANCE:
        events += _land_trophy(player, TROPHY_FISH[zone])
        caught.append(TROPHY_FISH[zone])
    player.gain_skill_xp("gathering", "Fishing", xp)
    return [("resource", 0, f"You land it: {', '.join(caught)} (+{xp} Fishing XP)")] + events


def _land_trophy(player, name):
    player.add_resource(name, 1)
    first = name not in player.trophies
    player.trophies[name] = player.trophies.get(name, 0) + 1
    if first:
        player.gain_skill_xp("gathering", "Fishing", 150)
        return [("resource", 0, f"🏆 NEW TROPHY: {name}! Recorded in your catch log. (+150 Fishing XP)")]
    return [("resource", 0, f"🏆 Another {name} for the log ({player.trophies[name]} caught).")]


NODE_RESOLVERS["bite"] = _resolve_bite

# Meals: eaten outside combat, one at a time, last several fights (decremented in combat.end_combat).
#   stats: flat stat bonuses (str/dex/int/vit/lck/crit), resist: chance to shrug off a debuff
MEALS = {
    "Hearty Fish Stew":   {"stats": {"vit": 8},  "fights": 4},
    "Spiced Swordfish":   {"stats": {"crit": 8}, "fights": 4},
    "Dragonfire Chowder": {"stats": {"vit": 6},  "fights": 4, "resist": 0.5},
    "Trophy Feast":       {"stats": {"str": 6, "dex": 6, "int": 6, "vit": 6}, "fights": 6},
    "River King Feast":   {"stats": {"str": 10, "dex": 10, "int": 10, "vit": 10}, "fights": 8, "resist": 0.3},
}
SLOW_COOKING_FIGHTS = 2


def meal_text(name):
    m = MEALS[name]
    parts = [f"+{v}{'%' if k == 'crit' else ''} {k.upper()}" for k, v in m["stats"].items()]
    if m.get("resist"):
        parts.append(f"{int(m['resist'] * 100)}% debuff resist")
    return ", ".join(parts) + f" for {m['fights']} fights"


def eat_meal(player, item):
    m = MEALS[item.meal]
    fights = m["fights"] + (SLOW_COOKING_FIGHTS if has_milestone(player, "Cooking", 15) else 0)
    replaced = player.meal["name"] if player.meal else None
    player.meal = {"name": item.meal, "stats": dict(m["stats"]), "resist": m.get("resist", 0), "fights": fights}
    return f"You eat the {item.name}: {meal_text(item.meal).rsplit(' for ', 1)[0]} for {fights} fights." + (
        f" (Replaces {replaced}.)" if replaced else "")


# ── Fletcher: wood, trees, the fletching bench, field tools ────────────────────
HEARTWOOD, ANCIENT_HEARTWOOD = "Heartwood", "Ancient Heartwood"
TREE_CHANCE = 0.15
BRANCH_CHANCE = 0.20
WORKSHOP_ADDITIVES = {
    "Smithing":  ADDITIVES,
    "Fletching": {HEARTWOOD: (0.15, 10), ANCIENT_HEARTWOOD: (0.30, 20)},
}
LEGENDARY_ADDITIVE = {"Smithing": STARMETAL, "Fletching": ANCIENT_HEARTWOOD}
TRAP_DAMAGE_PCT = 0.15
CAMP_KIT_HEAL = 60            # % HP/MP when making camp with a kit (normal camp: world.REST_HEAL)
UTILITY_TEXT = {
    "arm_trap":     "use outside combat to set it: your next fight starts with the enemy snared (−15% HP, chilled). Not bosses.",
    "camp_kit":     "carried, not used: your next trail camp heals 60% and keeps half your trail depth.",
    "smoke_escape": "use in combat: a guaranteed escape (not from the final battle).",
}

TRADE_MILESTONES.setdefault("Woodcutting", {}).update({
    5:  ("Grain Sense", "See each wood's trait at the fletching bench; Fletchers can follow animal tracks on the trail."),
    10: ("Heartwood", "Special trees can appear while chopping: fell them fast or cut out their heartwood."),
    15: ("Rare Groves", "Special trees can be the rarer wood of the next zone."),
    20: ("Ancient Trees", "Heartwood cuts can yield Ancient Heartwood, a legendary fletching material."),
})
TRADE_MILESTONES["Fletching"].update({
    10: ("Heartwood Inlay", "Inlay Heartwood into a weapon to raise its quality odds."),
    15: ("Snare Mastery", "Your Hunting Traps also make the snared enemy bleed."),
    20: ("Ancient Bowyer", "Craft with Ancient Heartwood: the only way to make Legendary fletched weapons."),
})


def wood_trait(player, wood):
    from items import WOODS
    return WOODS[wood][2] if has_milestone(player, "Woodcutting", 5) else "?"


def _zone_logs(player, zone):
    from crafting import ZONE_RESOURCES
    lv = skill_level(player, "Woodcutting")
    logs = [(req, -i, n) for i, (n, _, req) in enumerate(ZONE_RESOURCES.get(zone, {}).get("Woodcutting", [])) if lv >= req]
    return max(logs)[2] if logs else None


def make_tree_node(player, zone):
    logs = _zone_logs(player, zone)
    if not logs or not has_milestone(player, "Woodcutting", 10):
        return None
    if has_milestone(player, "Woodcutting", 15) and zone < 5 and random.random() < 0.4:
        logs = _zone_res(zone + 1, "Woodcutting")[0]
    ancient = has_milestone(player, "Woodcutting", 20)
    return {"type": "tree", "zone": zone, "logs": logs, "ancient": ancient,
            "title": f"A towering {logs.replace(' Logs', '').lower()} tree",
            "text": "Old and straight-grained. Its heart would make fine bow-wood.",
            "options": [{"key": "fell", "label": "🪓 Fell it quickly", "detail": f"4–5 {logs} · no risk"},
                        {"key": "heart", "label": "🌳 Cut out the heartwood",
                         "detail": f"1–2 {logs} + Heartwood" + (" (rare Ancient Heartwood)" if ancient else "")
                                   + f" · {int(BRANCH_CHANCE * 100)}% chance a branch falls (−10% HP)"},
                        {"key": "leave", "label": "↩ Leave it", "detail": ""}]}


def _resolve_tree(node, key, player):
    found, events = [], []

    def add(name, qty):
        player.add_resource(name, qty)
        found.append(f"{qty}× {name}")
    if key == "fell":
        add(node["logs"], random.randint(4, 5))
        xp = 30 + 5 * node["zone"]
    elif key == "heart":
        if random.random() < BRANCH_CHANCE:
            events.append(("trap_pct", 10, "A dead branch comes crashing down!"))
        add(node["logs"], random.randint(1, 2))
        add(HEARTWOOD, 1)
        if node.get("ancient") and random.random() < 0.10:
            add(ANCIENT_HEARTWOOD, 1)
        xp = 50 + 8 * node["zone"]
    else:
        return [("nothing", 0, "")]
    player.gain_skill_xp("gathering", "Woodcutting", xp)
    return events + [("resource", 0, f"You take {', '.join(found)} (+{xp} Woodcutting XP)")]


NODE_RESOLVERS["tree"] = _resolve_tree
DISCOVERY_NODES["fallen_tree"] = ("make_tree_node", "One tree here still stands — and it's a fine one.")

PROFESSION_EVENTS["Fletcher"].append(
    {"id": "tracks", "skill": "Woodcutting", "level": 5, "icon": "🐾",
     "title": "Animal tracks", "detail": "Set an ambush: your next fight starts with the enemy snared"})


def bench_craft(player, skill, recipe, choice, additive=None):
    """Craft at a workshop: Smithing (choice = 'weapon'|'armor') or Fletching (choice = profile)."""
    from crafting import TRADE_PROFESSIONS
    from items import fletch_item, forge_item
    if skill_level(player, skill) < recipe["req"]:
        return False, f"Requires {skill} {recipe['req']}.", None
    if additive and additive not in usable_additives(player, skill):
        return False, f"You can't use {additive} yet.", None
    if not can_craft_at_bench(player, skill, recipe):
        return False, "Missing materials.", None
    for res, qty in recipe["inputs"].items():
        player.remove_resource(res, qty)
    if additive:
        player.remove_resource(additive, 1)
    rarity = roll_quality(craft_shift(player, skill, recipe, additive),
                          legendary_possible=additive == LEGENDARY_ADDITIVE[skill])
    if skill == "Smithing":
        item = forge_item(choice, recipe["metal"], rarity, player.player_class)
    else:
        item = fletch_item(choice, recipe["wood"], recipe["kind"], rarity, player.player_class)
    player.add_item(item)
    bonus = skill in TRADE_PROFESSIONS.get(player.trade_profession, {}).get("bonus_skills", [])
    xp = int(recipe["xp"] * (1.5 if bonus else 1))
    player.gain_skill_xp("crafting", skill, xp)
    verb = "forge" if skill == "Smithing" else "craft"
    return True, f"You {verb} a [{rarity}] {item.name}! (+{xp} {skill} XP)", item


def fletch(player, recipe, profile, additive=None):
    return bench_craft(player, "Fletching", recipe, profile, additive)


def spring_trap(player, enemy):
    """Apply an armed Hunting Trap at the start of a fight. Returns a log line or None."""
    if not player.armed_trap or enemy.is_boss:
        return None
    player.armed_trap = False
    enemy.hp = max(1, enemy.hp - int(enemy.max_hp * TRAP_DAMAGE_PCT))
    enemy.statuses["Chilled"] = 3
    line = f"Your hunting trap snaps shut on the {enemy.name}! (−{int(TRAP_DAMAGE_PCT * 100)}% HP, slowed)"
    if has_milestone(player, "Fletching", 15):
        enemy.dot, enemy.dot_dmg, enemy.dot_name = max(enemy.dot, 3), max(enemy.dot_dmg, max(1, enemy.max_hp // 25)), "Bleed"
        line += f" It bleeds for {enemy.dot_dmg}/turn."
    return line
