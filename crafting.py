import random
import math
from items import generate_weapon, generate_armor, Item

# ── Zone resource tables ──────────────────────────────────────────────────────
# Format: zone_id → skill → [(resource_name, weight, level_req)]
ZONE_RESOURCES = {
    1: {
        "Mining":     [("Copper Ore", 2, 1), ("Tin Ore", 2, 1)],
        "Woodcutting":[("Normal Logs", 2, 1)],
        "Fishing":    [("Raw Shrimp", 2, 1), ("Raw Sardine", 1, 1)],
        "Herbalism":  [("Guam Leaf", 2, 1), ("Marrentill", 1, 2)],
    },
    2: {
        "Mining":     [("Iron Ore", 2, 4), ("Coal", 2, 4)],
        "Woodcutting":[("Oak Logs", 2, 5), ("Normal Logs", 1, 1)],
        "Fishing":    [("Raw Trout", 2, 5), ("Raw Salmon", 1, 7)],
        "Herbalism":  [("Tarromin", 2, 5), ("Harralander", 1, 6)],
    },
    3: {
        "Mining":     [("Gold Ore", 2, 8), ("Mithril Ore", 1, 10)],
        "Woodcutting":[("Willow Logs", 2, 7), ("Maple Logs", 1, 9)],
        "Fishing":    [("Raw Lobster", 2, 10), ("Raw Swordfish", 1, 12)],
        "Herbalism":  [("Ranarr Weed", 2, 10), ("Irit Leaf", 1, 11)],
    },
    4: {
        "Mining":     [("Adamantite Ore", 2, 14)],
        "Woodcutting":[("Yew Logs", 2, 13)],
        "Fishing":    [("Raw Monkfish", 2, 12), ("Raw Shark", 1, 14)],
        "Herbalism":  [("Kwuarm", 2, 14), ("Snapdragon", 1, 16)],
    },
    5: {
        "Mining":     [("Dragon Metal", 2, 18)],
        "Woodcutting":[("Elder Logs", 2, 18)],
        "Fishing":    [("Raw Anglerfish", 2, 16), ("Raw Dark Crab", 1, 18)],
        "Herbalism":  [("Torstol", 1, 19), ("Lantadyme", 2, 18)],
    },
}

# ── Crafting recipes ──────────────────────────────────────────────────────────
# output_type: "resource" → adds to player.resources
#              "weapon" / "armor" → generates item at level_param
#              "consumable" → creates Item directly with effect/effect_value/effect_duration
CRAFTING_RECIPES = {
    "Smithing": [
        {"name":"Bronze Bar",        "inputs":{"Copper Ore":1,"Tin Ore":1},      "output_type":"resource","output_name":"Bronze Bar",     "req":1,  "xp":25},
        {"name":"Iron Bar",          "inputs":{"Iron Ore":2,"Coal":1},           "output_type":"resource","output_name":"Iron Bar",        "req":5,  "xp":40},
        {"name":"Steel Bar",         "inputs":{"Iron Ore":1,"Coal":2},           "output_type":"resource","output_name":"Steel Bar",       "req":8,  "xp":55},
        {"name":"Mithril Bar",       "inputs":{"Mithril Ore":1,"Coal":2},        "output_type":"resource","output_name":"Mithril Bar",     "req":11, "xp":75},
        {"name":"Adamantite Bar",    "inputs":{"Adamantite Ore":1,"Coal":3},     "output_type":"resource","output_name":"Adamantite Bar",  "req":14, "xp":95},
        {"name":"Dragon Bar",        "inputs":{"Dragon Metal":2,"Coal":4},       "output_type":"resource","output_name":"Dragon Bar",      "req":18, "xp":120},
        {"name":"Bronze Weapon",     "inputs":{"Bronze Bar":2},                  "output_type":"weapon",  "level_param":3,                "req":2,  "xp":35},
        {"name":"Iron Weapon",       "inputs":{"Iron Bar":2},                    "output_type":"weapon",  "level_param":6,                "req":6,  "xp":60},
        {"name":"Steel Weapon",      "inputs":{"Steel Bar":2},                   "output_type":"weapon",  "level_param":9,                "req":9,  "xp":80},
        {"name":"Mithril Weapon",    "inputs":{"Mithril Bar":2},                 "output_type":"weapon",  "level_param":13,               "req":12, "xp":100},
        {"name":"Adamantite Weapon", "inputs":{"Adamantite Bar":2},              "output_type":"weapon",  "level_param":17,               "req":15, "xp":125},
        {"name":"Dragon Weapon",     "inputs":{"Dragon Bar":2},                  "output_type":"weapon",  "level_param":21,               "req":19, "xp":150},
    ],
    "Herblore": [
        {"name":"Attack Potion",  "inputs":{"Guam Leaf":1},                 "output_type":"consumable","effect":"temp_buff_str","effect_value":8, "effect_duration":3,"output_name":"Attack Potion",  "req":1, "xp":30},
        {"name":"Antidote",       "inputs":{"Marrentill":1},                "output_type":"consumable","effect":"cure",          "effect_value":0, "effect_duration":0,"output_name":"Antidote",       "req":2, "xp":25},
        {"name":"Strength Potion","inputs":{"Tarromin":1,"Harralander":1},  "output_type":"consumable","effect":"temp_buff_str","effect_value":15,"effect_duration":3,"output_name":"Strength Potion","req":5, "xp":45},
        {"name":"Defense Potion", "inputs":{"Harralander":1},               "output_type":"consumable","effect":"temp_buff_vit","effect_value":10,"effect_duration":3,"output_name":"Defense Potion", "req":5, "xp":40},
        {"name":"Super Restore",  "inputs":{"Ranarr Weed":1,"Irit Leaf":1},"output_type":"consumable","effect":"heal_pct",     "effect_value":30,"effect_duration":0,"output_name":"Super Restore",  "req":10,"xp":65},
        {"name":"Combat Potion",  "inputs":{"Kwuarm":2},                   "output_type":"consumable","effect":"temp_buff_all","effect_value":5, "effect_duration":5,"output_name":"Combat Potion",  "req":14,"xp":85},
        {"name":"Overload",       "inputs":{"Torstol":1,"Lantadyme":1},    "output_type":"consumable","effect":"temp_buff_all","effect_value":12,"effect_duration":7,"output_name":"Overload",        "req":18,"xp":130},
    ],
    "Cooking": [
        {"name":"Cooked Shrimp",    "inputs":{"Raw Shrimp":1},    "output_type":"consumable","effect":"heal_pct","effect_value":10,"output_name":"Cooked Shrimp",    "req":1, "xp":15},
        {"name":"Cooked Sardine",   "inputs":{"Raw Sardine":1},   "output_type":"consumable","effect":"heal_pct","effect_value":15,"output_name":"Cooked Sardine",   "req":2, "xp":20},
        {"name":"Cooked Trout",     "inputs":{"Raw Trout":1},     "output_type":"consumable","effect":"heal_pct","effect_value":25,"output_name":"Cooked Trout",     "req":7, "xp":35},
        {"name":"Cooked Salmon",    "inputs":{"Raw Salmon":1},    "output_type":"consumable","effect":"heal_pct","effect_value":30,"output_name":"Cooked Salmon",    "req":9, "xp":40},
        {"name":"Cooked Lobster",   "inputs":{"Raw Lobster":1},   "output_type":"consumable","effect":"heal_pct","effect_value":40,"output_name":"Cooked Lobster",   "req":12,"xp":55},
        {"name":"Cooked Swordfish", "inputs":{"Raw Swordfish":1}, "output_type":"consumable","effect":"heal_pct","effect_value":50,"output_name":"Cooked Swordfish", "req":14,"xp":65},
        {"name":"Cooked Shark",     "inputs":{"Raw Shark":1},     "output_type":"consumable","effect":"heal_pct","effect_value":65,"output_name":"Cooked Shark",     "req":16,"xp":80},
        {"name":"Cooked Anglerfish","inputs":{"Raw Anglerfish":1},"output_type":"consumable","effect":"heal_pct","effect_value":90,"output_name":"Cooked Anglerfish","req":18,"xp":100},
        {"name":"Dark Crab Meat",   "inputs":{"Raw Dark Crab":1}, "output_type":"consumable","effect":"heal_overheal","effect_value":80,"output_name":"Dark Crab Meat","req":19,"xp":100},
    ],
    "Fletching": [
        {"name":"Wooden Staff",   "inputs":{"Normal Logs":2}, "output_type":"weapon","level_param":2, "req":1, "xp":30},
        {"name":"Oak Shortbow",   "inputs":{"Oak Logs":2},    "output_type":"weapon","level_param":5, "req":5, "xp":45},
        {"name":"Willow Bow",     "inputs":{"Willow Logs":2}, "output_type":"weapon","level_param":8, "req":9, "xp":60},
        {"name":"Maple Longbow",  "inputs":{"Maple Logs":2},  "output_type":"weapon","level_param":12,"req":12,"xp":80},
        {"name":"Yew Longbow",    "inputs":{"Yew Logs":2},    "output_type":"weapon","level_param":16,"req":16,"xp":100},
        {"name":"Elder Bow",      "inputs":{"Elder Logs":2},  "output_type":"weapon","level_param":21,"req":19,"xp":130},
    ],
}

# ── Trade professions ─────────────────────────────────────────────────────────
TRADE_PROFESSIONS = {
    "Blacksmith": {
        "desc": "Expert in Mining & Smithing. +50% gathering/crafting XP for those skills. Start with iron ores.",
        "bonus_skills": ["Mining", "Smithing"],
        "start_resources": {"Iron Ore": 5, "Coal": 3},
        "icon": "⚒",
    },
    "Alchemist": {
        "desc": "Master herbalist & brewer. +50% XP for Herbalism & Herblore. Start with herbs.",
        "bonus_skills": ["Herbalism", "Herblore"],
        "start_resources": {"Guam Leaf": 5, "Marrentill": 3},
        "icon": "⚗",
    },
    "Fisher": {
        "desc": "Skilled angler & cook. +50% XP for Fishing & Cooking. Start with fresh fish.",
        "bonus_skills": ["Fishing", "Cooking"],
        "start_resources": {"Raw Trout": 5},
        "icon": "🎣",
    },
    "Ranger": {
        "desc": "Woodsman & fletcher. +50% XP for Woodcutting & Fletching. Start with oak logs.",
        "bonus_skills": ["Woodcutting", "Fletching"],
        "start_resources": {"Oak Logs": 5, "Normal Logs": 3},
        "icon": "🏹",
    },
}

GATHERING_SKILLS = ["Mining", "Woodcutting", "Fishing", "Herbalism"]
CRAFTING_SKILLS  = ["Smithing", "Fletching", "Cooking", "Herblore"]
ALL_SKILLS       = GATHERING_SKILLS + CRAFTING_SKILLS

SKILL_ICONS = {
    "Mining": "⛏", "Woodcutting": "🪵", "Fishing": "🎣", "Herbalism": "🌿",
    "Smithing": "🔨", "Fletching": "🏹", "Cooking": "🍳", "Herblore": "⚗",
}

GATHER_BUTTON_LABELS = {
    "Mining": "⛏ Mine",
    "Woodcutting": "🪵 Chop",
    "Fishing": "🎣 Fish",
    "Herbalism": "🌿 Forage",
}


def xp_for_level(level):
    """XP needed to advance from `level` to level+1."""
    return level * 100


def calc_skill_level(total_xp):
    """Convert accumulated XP to skill level (1–20). O(1) closed-form solution.
    Cumulative XP to reach level n = sum(k*100 for k in 1..n-1) = 50*n*(n-1).
    Solving 50n(n-1) <= xp: n = floor((1 + sqrt(1 + 0.08*xp)) / 2).
    """
    if total_xp <= 0:
        return 1
    n = int((1 + math.sqrt(1 + 0.08 * total_xp)) / 2)
    return min(n, 20)


def gather_resource(player, zone_id, skill_name):
    """
    Perform one gather action.
    Returns (resource_name, qty, xp_gained, leveled_up) or None if no eligible resources.
    """
    zone_res  = ZONE_RESOURCES.get(zone_id, ZONE_RESOURCES[1])
    available = zone_res.get(skill_name, [])
    skill_data = getattr(player, 'gathering_skills', {}).get(skill_name, {"level": 1, "xp": 0})
    skill_level = skill_data["level"]

    eligible = [(name, wt) for name, wt, req in available if skill_level >= req]
    if not eligible:
        return None

    names, weights = zip(*eligible)
    resource = random.choices(names, weights=weights, k=1)[0]

    qty = random.randint(1, 2)
    if skill_level >= 10:
        qty = random.randint(1, 3)

    tp = getattr(player, 'trade_profession', None)
    bonus_skills = TRADE_PROFESSIONS.get(tp, {}).get("bonus_skills", []) if tp else []
    if skill_name in bonus_skills and random.random() < 0.5:
        qty += 1

    base_xp = 15 + skill_level * 5
    xp_gained = int(base_xp * 1.5) if skill_name in bonus_skills else base_xp

    _, leveled_up = player.gain_skill_xp("gathering", skill_name, xp_gained)
    player.add_resource(resource, qty)

    return resource, qty, xp_gained, leveled_up


def craft_item(player, skill_name, recipe_idx, player_class=None):
    """
    Attempt to craft a recipe.
    Returns (success: bool, message: str, item_or_None).
    """
    recipes = CRAFTING_RECIPES.get(skill_name, [])
    if not 0 <= recipe_idx < len(recipes):
        return False, "Invalid recipe.", None

    recipe = recipes[recipe_idx]
    skill_data = getattr(player, 'crafting_skills', {}).get(skill_name, {"level": 1, "xp": 0})

    if skill_data["level"] < recipe["req"]:
        return False, f"Requires {skill_name} level {recipe['req']}.", None

    for res_name, qty in recipe["inputs"].items():
        if getattr(player, 'resources', {}).get(res_name, 0) < qty:
            return False, f"Need {qty}× {res_name}.", None

    for res_name, qty in recipe["inputs"].items():
        player.remove_resource(res_name, qty)

    tp = getattr(player, 'trade_profession', None)
    bonus_skills = TRADE_PROFESSIONS.get(tp, {}).get("bonus_skills", []) if tp else []
    raw_xp = int(recipe["xp"] * 1.5) if skill_name in bonus_skills else recipe["xp"]
    _, leveled_up = player.gain_skill_xp("crafting", skill_name, raw_xp)

    lv_msg = f" ★ {skill_name} leveled up!" if leveled_up else ""
    out_type = recipe["output_type"]

    if out_type == "resource":
        player.add_resource(recipe["output_name"], 1)
        return True, f"Crafted {recipe['output_name']}! (+{raw_xp} XP){lv_msg}", None

    if out_type in ("weapon", "armor"):
        pc = player_class or getattr(player, 'player_class', None)
        if out_type == "weapon":
            item = generate_weapon(player_class=pc, level=recipe["level_param"], rarity="Uncommon")
        else:
            item = generate_armor(level=recipe.get("level_param", 5), rarity="Uncommon")
        item.name = f"Crafted {recipe['name']}"
        player.add_item(item)
        return True, f"Crafted {item.name}! (+{raw_xp} XP){lv_msg}", item

    if out_type == "consumable":
        eff     = recipe["effect"]
        eff_val = recipe["effect_value"]
        eff_dur = recipe.get("effect_duration", 0)
        value   = max(10, eff_val * 3)
        item = Item(recipe["output_name"], "consumable", "Common", value,
                    effect=eff, effect_value=eff_val, effect_duration=eff_dur)
        player.add_item(item)
        return True, f"Crafted {recipe['output_name']}! (+{raw_xp} XP){lv_msg}", item

    return False, "Unknown output type.", None
