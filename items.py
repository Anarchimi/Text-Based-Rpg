import random

RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

RARITY_WEIGHTS = [55, 25, 12, 6, 2]

WEAPON_PREFIXES = ["Iron", "Steel", "Shadow", "Flame", "Frost", "Thunder", "Ancient", "Cursed", "Blessed", "Void"]
WEAPON_NAMES = {
    "Warrior": ["Sword", "Axe", "Mace", "Greatsword", "Warhammer", "Spear"],
    "Mage":    ["Staff", "Wand", "Tome", "Crystal", "Orb", "Scepter"],
    "Rogue":   ["Dagger", "Blade", "Shiv", "Kris", "Stiletto", "Crossbow"],
}
ARMOR_PREFIXES = ["Leather", "Chain", "Plate", "Shadow", "Runic", "Ancient", "Blessed", "Void", "Ember", "Frost"]
ARMOR_NAMES    = ["Chestplate", "Helmet", "Gauntlets", "Boots", "Pauldrons", "Greaves"]
CONSUMABLE_NAMES = [
    ("Health Potion",         "heal_pct",    25),
    ("Greater Health Potion", "heal_pct",    50),
    ("Mana Potion",           "heal_mp_pct", 30),
    ("Greater Mana Potion",   "heal_mp_pct", 60),
    ("Elixir of Power",       "buff_str",    5),
    ("Elixir of Wisdom",      "buff_int",    5),
    ("Antidote",              "cure",        0),
    ("Phoenix Feather",       "revive",      1),
]


# Gear upgrades (+1 … +5) at the forge: gold plus smithed bars, +12% base stats per level.
UPGRADE_MAX = 5
UPGRADE_STAT_GAIN = 0.12
UPGRADE_BARS = {1: "Bronze Bar", 2: "Iron Bar", 3: "Steel Bar", 4: "Mithril Bar", 5: "Adamantite Bar"}
UPGRADE_BAR_QTY = 2


def upgrade_cost(item, player=None):
    """(gold, bar name, bar qty) for the next upgrade, or None at max. Blacksmiths pay less."""
    n = item.upgrade + 1
    if item.item_type not in GEAR_SLOTS or n > UPGRADE_MAX:
        return None
    gold, qty = 60 * n * n, UPGRADE_BAR_QTY
    if player is not None and getattr(player, "trade_profession", None) == "Blacksmith":
        gold, qty = int(gold * 0.7), max(1, qty - 1)
    return gold, UPGRADE_BARS[n], qty


class Item:
    # Class-level defaults so items pickled before upgrades existed still load.
    upgrade = 0
    base_stats = None
    base_name = None
    legendary = None   # key of LEGENDARY_EFFECTS
    category = None    # "food" for cooked consumables (Fisher perk), else potion/other

    def __init__(self, name, item_type, rarity, value, stats=None, effect=None, effect_value=0, effect_duration=0):
        self.name = name
        self.item_type = item_type   # "weapon", "armor", "consumable"
        self.rarity = rarity
        self.value = value           # gold sell value
        self.stats = stats or {}     # {"atk": 5, "def": 3, ...}
        self.effect = effect         # for consumables
        self.effect_value = effect_value
        self.effect_duration = effect_duration  # turns for temp buffs

    def apply_upgrade(self):
        if self.base_stats is None:
            self.base_stats, self.base_name = dict(self.stats), self.name
        self.upgrade += 1
        mult = 1 + UPGRADE_STAT_GAIN * self.upgrade
        self.stats = {k: max(v + self.upgrade, int(round(v * mult))) for k, v in self.base_stats.items()}
        self.name = f"{self.base_name} +{self.upgrade}"
        self.value = int(self.value * 1.25)

    def stat_string(self):
        if not self.stats:
            return ""
        parts = [f"+{v} {k.upper()}" for k, v in self.stats.items()]
        return " | ".join(parts)

    def __str__(self):
        base = f"[{self.rarity}] {self.name}"
        stats = self.stat_string()
        return f"{base}" + (f" ({stats})" if stats else "") + f" [Worth: {self.value}g]"


def roll_rarity(bonus=0):
    weights = RARITY_WEIGHTS[:]
    if bonus > 0:
        weights[0] = max(10, weights[0] - bonus * 5)
        weights[-1] += bonus * 2
    idx = random.choices(range(len(RARITIES)), weights=weights, k=1)[0]
    return RARITIES[idx]


def loot_rarity_bonus(level, luck=0):
    """Higher level and luck shift rarity rolls upward (LCK used to do nothing here)."""
    return level // 5 + max(0, luck) // 10


def rarity_multiplier(rarity):
    return [1.0, 1.4, 2.0, 3.0, 5.0][RARITIES.index(rarity)]


# ── Gear: slots, bonus stats ("affixes"), legendary effects ────────────────────
GEAR_SLOTS = ("weapon", "armor", "accessory")
AFFIX_COUNT = {"Common": 0, "Uncommon": 1, "Rare": 2, "Epic": 3, "Legendary": 3}
# Which bonus stats can roll on each slot (weights).
AFFIX_POOL = {
    "weapon":    {"str": 3, "dex": 3, "int": 3, "crit": 3, "spd": 2, "lck": 1},
    "armor":     {"vit": 3, "hp": 3, "str": 2, "dex": 2, "int": 2, "mp": 2},
    "accessory": {"str": 2, "dex": 2, "int": 2, "vit": 2, "lck": 2, "hp": 2, "mp": 2, "crit": 2, "spd": 1},
}
CLASS_MAIN_STAT = {"Warrior": "str", "Mage": "int", "Rogue": "dex"}
STAT_LABELS = {"atk": "ATK", "def": "DEF", "spd": "SPD", "hp": "HP", "mp": "MP", "str": "STR", "dex": "DEX",
               "int": "INT", "vit": "VIT", "lck": "LCK", "crit": "% CRIT"}

# Legendary items carry one of these. Each is implemented where its name is
# checked (combat.py / Player) and has a test proving it changes combat.
LEGENDARY_EFFECTS = {
    "Vampiric":    ("of Hunger",    "Heal 10% of the damage you deal."),
    "Thorns":      ("of Thorns",    "Attackers take 20% of the damage they deal you."),
    "Executioner": ("of the Headsman", "+25% damage to enemies below 35% HP."),
    "Arcane Flow": ("of the Wellspring", "Abilities cost 25% less MP."),
    "Bulwark":     ("of the Bastion", "Defending also restores 10% of max HP."),
    "Second Wind": ("of the Phoenix", "Once per fight, survive a lethal blow with 1 HP."),
}

ACCESSORY_PREFIXES = ["Silver", "Gold", "Bone", "Jade", "Obsidian", "Moonlit", "Runed", "Ember", "Frost", "Void"]
ACCESSORY_NAMES    = ["Ring", "Amulet", "Charm", "Talisman", "Pendant", "Signet"]


def _affix_value(stat, level, rarity):
    r = 1 + 0.25 * RARITIES.index(rarity)
    base = {
        "str": 2 + level * 0.6, "dex": 2 + level * 0.6, "int": 2 + level * 0.6,
        "vit": 2 + level * 0.5, "lck": 2 + level * 0.4,
        "hp": 8 + level * 4, "mp": 5 + level * 3,
        "spd": 1 + level * 0.25, "crit": 2 + level * 0.15,
    }[stat]
    return max(1, int(base * r * random.uniform(0.7, 1.15)))


def roll_affixes(slot, level, rarity, player_class=None, count=None):
    """Distinct bonus stats for an item; the class's main stat is 3× as likely."""
    pool = dict(AFFIX_POOL[slot])
    main = CLASS_MAIN_STAT.get(player_class)
    if main in pool:
        pool[main] *= 3
    n = AFFIX_COUNT[rarity] if count is None else count
    out = {}
    while pool and len(out) < n:
        stat = random.choices(list(pool), weights=list(pool.values()))[0]
        del pool[stat]
        out[stat] = _affix_value(stat, level, rarity)
    return out


def _finish_gear(item, slot, level, rarity, player_class, affix_count=None):
    for stat, val in roll_affixes(slot, level, rarity, player_class, affix_count).items():
        item.stats[stat] = item.stats.get(stat, 0) + val
    if rarity == "Legendary":
        item.legendary = random.choice(list(LEGENDARY_EFFECTS))
        item.name = f"{item.name} {LEGENDARY_EFFECTS[item.legendary][0]}"
    item.value = int(item.value * (1 + 0.15 * len(item.stats)))
    return item


def generate_weapon(player_class=None, level=1, rarity=None, luck=0):
    if rarity is None:
        rarity = roll_rarity(loot_rarity_bonus(level, luck))
    mult = rarity_multiplier(rarity)
    cls = player_class if player_class in WEAPON_NAMES else random.choice(list(WEAPON_NAMES))
    name = f"{random.choice(WEAPON_PREFIXES)} {random.choice(WEAPON_NAMES[cls])}"
    base_atk = int((5 + level * 2) * mult)
    item = Item(name, "weapon", rarity, int(base_atk * 3 * mult), {"atk": base_atk})
    return _finish_gear(item, "weapon", level, rarity, player_class)


def generate_armor(level=1, rarity=None, player_class=None, luck=0):
    if rarity is None:
        rarity = roll_rarity(loot_rarity_bonus(level, luck))
    mult = rarity_multiplier(rarity)
    name = f"{random.choice(ARMOR_PREFIXES)} {random.choice(ARMOR_NAMES)}"
    base_def = int((4 + level * 2) * mult)
    item = Item(name, "armor", rarity, int(base_def * 5 * mult), {"def": base_def})
    return _finish_gear(item, "armor", level, rarity, player_class)


def generate_accessory(level=1, rarity=None, player_class=None, luck=0):
    """Accessories have no base stat — only bonus stats (one more than other gear)."""
    if rarity is None:
        rarity = roll_rarity(loot_rarity_bonus(level, luck))
    name = f"{random.choice(ACCESSORY_PREFIXES)} {random.choice(ACCESSORY_NAMES)}"
    item = Item(name, "accessory", rarity, int((20 + level * 6) * rarity_multiplier(rarity)), {})
    return _finish_gear(item, "accessory", level, rarity, player_class, AFFIX_COUNT[rarity] + 1)


# Prices for consumables whose effect value isn't a sensible price
# (permanent stats and auto-revive used to cost 10g and 5g).
CONSUMABLE_PRICES = {"buff_str": 400, "buff_int": 400, "revive": 250, "cure": 15}


def generate_consumable():
    c = random.choice(CONSUMABLE_NAMES)
    name, effect, eff_val = c
    value = CONSUMABLE_PRICES.get(effect, max(5, eff_val * 2))
    return Item(name, "consumable", "Common", value, effect=effect, effect_value=eff_val)


def generate_loot(level=1, luck=0, count=None, player_class=None):
    if count is None:
        count = random.randint(0, 3)
    items = []
    for _ in range(count):
        roll = random.random()
        if roll < 0.4:
            items.append(generate_consumable())
        elif roll < 0.65:
            items.append(generate_weapon(player_class, level, luck=luck))
        elif roll < 0.88:
            items.append(generate_armor(level, player_class=player_class, luck=luck))
        else:
            items.append(generate_accessory(level, player_class=player_class, luck=luck))
    return items


SHOP_STOCK_SIZE = 6

def generate_shop_stock(level=1, player_class=None):
    stock = [generate_weapon(player_class, level), generate_weapon(player_class, level),
             generate_armor(level, player_class=player_class), generate_armor(level, player_class=player_class),
             generate_accessory(level, player_class=player_class)]
    while len(stock) < SHOP_STOCK_SIZE + 1:
        stock.append(generate_consumable())
    return stock
