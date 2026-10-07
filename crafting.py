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
#              "forge" / "fletch" → open the workshop (trades.forge / trades.fletch): choose slot or profile + additive
#              "utility" → Fletcher tools (Hunting Trap, Camping Kit, Smoke Arrow), category "utility"
#              "meal" → multi-fight meals (trades.MEALS)
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
        {"name":"Bronze Gear",     "inputs":{"Bronze Bar":2},                  "output_type":"forge", "metal":"Bronze",   "req":2,  "xp":35},
        {"name":"Iron Gear",       "inputs":{"Iron Bar":2},                    "output_type":"forge", "metal":"Iron",   "req":6,  "xp":60},
        {"name":"Steel Gear",      "inputs":{"Steel Bar":2},                   "output_type":"forge", "metal":"Steel",   "req":9,  "xp":80},
        {"name":"Mithril Gear",    "inputs":{"Mithril Bar":2},                 "output_type":"forge", "metal":"Mithril",   "req":12, "xp":100},
        {"name":"Adamantite Gear", "inputs":{"Adamantite Bar":2},              "output_type":"forge", "metal":"Adamantite",   "req":15, "xp":125},
        {"name":"Dragon Gear",     "inputs":{"Dragon Bar":2},                  "output_type":"forge", "metal":"Dragon",   "req":19, "xp":150},
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
        {"name":"Cooked Monkfish",  "inputs":{"Raw Monkfish":1},  "output_type":"consumable","effect":"heal_pct","effect_value":45,"output_name":"Cooked Monkfish",  "req":13,"xp":60},
        {"name":"Cooked Anglerfish","inputs":{"Raw Anglerfish":1},"output_type":"consumable","effect":"heal_pct","effect_value":90,"output_name":"Cooked Anglerfish","req":18,"xp":100},
        {"name":"Hearty Fish Stew",  "inputs":{"Raw Trout":2,"Raw Salmon":1},       "output_type":"meal","output_name":"Hearty Fish Stew",  "req":7, "xp":70},
        {"name":"Spiced Swordfish",  "inputs":{"Raw Swordfish":1,"Raw Lobster":1},  "output_type":"meal","output_name":"Spiced Swordfish",  "req":12,"xp":90},
        {"name":"Dragonfire Chowder","inputs":{"Raw Dark Crab":1,"Raw Anglerfish":1},"output_type":"meal","output_name":"Dragonfire Chowder","req":18,"xp":120},
        {"name":"Trophy Feast (Trout)",  "inputs":{"Large Trout":1},         "output_type":"meal","output_name":"Trophy Feast","req":10,"xp":100},
        {"name":"Trophy Feast (Salmon)", "inputs":{"Trophy Salmon":1},       "output_type":"meal","output_name":"Trophy Feast","req":10,"xp":100},
        {"name":"Trophy Feast (Golden)", "inputs":{"Ancient Golden Trout":1},"output_type":"meal","output_name":"Trophy Feast","req":10,"xp":100},
        {"name":"Trophy Feast (Voidfin)","inputs":{"Voidfin":1},             "output_type":"meal","output_name":"Trophy Feast","req":10,"xp":100},
        {"name":"River King Feast",      "inputs":{"Ashvale River King":1},  "output_type":"meal","output_name":"River King Feast","req":10,"xp":200},
        {"name":"Dark Crab Meat",   "inputs":{"Raw Dark Crab":1}, "output_type":"consumable","effect":"heal_overheal","effect_value":80,"output_name":"Dark Crab Meat","req":19,"xp":100},
    ],
    "Fletching": [
        {"name":"Wooden Staff",   "inputs":{"Normal Logs":2}, "output_type":"fletch","wood":"Normal","kind":"Staff",   "req":1, "xp":30},
        {"name":"Oak Shortbow",   "inputs":{"Oak Logs":2},    "output_type":"fletch","wood":"Oak",   "kind":"Shortbow","req":5, "xp":45},
        {"name":"Willow Bow",     "inputs":{"Willow Logs":2}, "output_type":"fletch","wood":"Willow","kind":"Bow",     "req":9, "xp":60},
        {"name":"Maple Longbow",  "inputs":{"Maple Logs":2},  "output_type":"fletch","wood":"Maple", "kind":"Longbow", "req":12,"xp":80},
        {"name":"Yew Longbow",    "inputs":{"Yew Logs":2},    "output_type":"fletch","wood":"Yew",   "kind":"Longbow", "req":16,"xp":100},
        {"name":"Elder Bow",      "inputs":{"Elder Logs":2},  "output_type":"fletch","wood":"Elder", "kind":"Bow",     "req":19,"xp":130},
        {"name":"Hunting Trap",   "inputs":{"Normal Logs":2},                   "output_type":"utility","utility":"arm_trap",     "output_name":"Hunting Trap", "req":4, "xp":35},
        {"name":"Camping Kit",    "inputs":{"Oak Logs":2,"Willow Logs":1},      "output_type":"utility","utility":"camp_kit",     "output_name":"Camping Kit",  "req":10,"xp":70},
        {"name":"Smoke Arrow",    "inputs":{"Maple Logs":1},                    "output_type":"utility","utility":"smoke_escape", "output_name":"Smoke Arrow",  "req":12,"xp":60},
    ],
}

# ── Trade professions ─────────────────────────────────────────────────────────
# Each trade: +50% XP in its two skills, a crafting perk and a perk outside crafting.
# Perk logic: craft_item() here, Player.use_consumable / items.upgrade_cost, world.py trail.
TRADE_PROFESSIONS = {
    "Blacksmith": {
        "desc": "Mining & Smithing expert.",
        "bonus_skills": ["Mining", "Smithing"],
        "perks": ["Masterwork: better forging odds (quality roll +10%).",
                  "Forgemaster: gear upgrades cost 30% less gold and one fewer bar."],
        "start_resources": {"Iron Ore": 5, "Coal": 3},
        "icon": "⚒",
    },
    "Alchemist": {
        "desc": "Herbalism & Herblore master.",
        "bonus_skills": ["Herbalism", "Herblore"],
        "perks": ["Double Brew: 30% chance to brew two potions.",
                  "Potency: potions you drink are 50% stronger."],
        "start_resources": {"Guam Leaf": 5, "Marrentill": 3},
        "icon": "⚗",
    },
    "Fisher": {
        "desc": "Fishing & Cooking specialist.",
        "bonus_skills": ["Fishing", "Cooking"],
        "perks": ["Big Catch: 30% chance to cook two meals.",
                  "Hearty Meals: food heals 50% more and restores MP too."],
        "start_resources": {"Raw Trout": 5},
        "icon": "🎣",
    },
    "Fletcher": {
        "desc": "Woodcutting & Fletching woodsman.",
        "bonus_skills": ["Woodcutting", "Fletching"],
        "perks": ["Masterwork: better fletching odds (quality roll +10%).",
                  "Woodsman's Eye: on the trail, forage paths lead to timber (+1 wood) and treasure traps are half as likely."],
        "start_resources": {"Oak Logs": 5, "Normal Logs": 3},
        "icon": "🏹",
    },
}
MASTERWORK_SKILLS = {"Blacksmith": "Smithing", "Fletcher": "Fletching"}
DOUBLE_CRAFT_SKILLS = {"Alchemist": "Herblore", "Fisher": "Cooking"}
DOUBLE_CRAFT_CHANCE = 0.30

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
    if recipe["output_type"] in ("forge", "fletch"):
        return False, "Gear is made at the workshop — open it from this recipe.", None
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

    if out_type == "utility":
        from trades import UTILITY_TEXT
        item = Item(recipe["output_name"], "consumable", "Common", 25, effect=recipe["utility"])
        item.category = "utility"
        player.add_item(item)
        return True, f"Crafted {item.name}: {UTILITY_TEXT[recipe['utility']]} (+{raw_xp} XP){lv_msg}", item

    if out_type == "meal":
        from trades import MEALS, meal_text
        item = Item(recipe["output_name"], "consumable", "Common", 40, effect="meal")
        item.category, item.meal = "meal", recipe["output_name"]
        player.add_item(item)
        return True, f"Cooked {item.name}: {meal_text(item.meal)}. Eat it before a fight. (+{raw_xp} XP){lv_msg}", item

    if out_type == "consumable":
        eff     = recipe["effect"]
        eff_val = recipe["effect_value"]
        eff_dur = recipe.get("effect_duration", 0)
        value   = max(10, eff_val * 3)
        copies = 2 if DOUBLE_CRAFT_SKILLS.get(tp) == skill_name and random.random() < DOUBLE_CRAFT_CHANCE else 1
        for _ in range(copies):
            item = Item(recipe["output_name"], "consumable", "Common", value,
                        effect=eff, effect_value=eff_val, effect_duration=eff_dur)
            if skill_name == "Cooking":
                item.category = "food"
            player.add_item(item)
        extra = " ×2!" if copies == 2 else ""
        return True, f"Crafted {recipe['output_name']}{extra}! (+{raw_xp} XP){lv_msg}", item

    return False, "Unknown output type.", None
