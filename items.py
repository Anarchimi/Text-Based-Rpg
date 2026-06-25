import random

RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
RARITY_COLORS = {
    "Common":    "",
    "Uncommon":  "\033[32m",
    "Rare":      "\033[34m",
    "Epic":      "\033[35m",
    "Legendary": "\033[33m",
}
RESET = "\033[0m"

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
    ("Health Potion",    "heal_hp",   30),
    ("Greater Health Potion", "heal_hp", 70),
    ("Mana Potion",      "heal_mp",   20),
    ("Greater Mana Potion",  "heal_mp", 50),
    ("Elixir of Power",  "buff_str",  5),
    ("Elixir of Wisdom", "buff_int",  5),
    ("Antidote",         "cure",      0),
    ("Phoenix Feather",  "revive",    1),
]


class Item:
    def __init__(self, name, item_type, rarity, value, stats=None, effect=None, effect_value=0):
        self.name = name
        self.item_type = item_type   # "weapon", "armor", "consumable"
        self.rarity = rarity
        self.value = value           # gold sell value
        self.stats = stats or {}     # {"atk": 5, "def": 3, ...}
        self.effect = effect         # for consumables
        self.effect_value = effect_value

    def colored_name(self):
        color = RARITY_COLORS.get(self.rarity, "")
        return f"{color}[{self.rarity}] {self.name}{RESET}"

    def stat_string(self):
        if not self.stats:
            return ""
        parts = [f"+{v} {k.upper()}" for k, v in self.stats.items()]
        return " | ".join(parts)

    def __str__(self):
        base = self.colored_name()
        stats = self.stat_string()
        return f"{base}" + (f" ({stats})" if stats else "") + f" [Worth: {self.value}g]"


def roll_rarity(bonus=0):
    weights = RARITY_WEIGHTS[:]
    if bonus > 0:
        weights[0] = max(10, weights[0] - bonus * 5)
        weights[-1] += bonus * 2
    idx = random.choices(range(len(RARITIES)), weights=weights, k=1)[0]
    return RARITIES[idx]


def rarity_multiplier(rarity):
    return [1.0, 1.4, 2.0, 3.0, 5.0][RARITIES.index(rarity)]


def generate_weapon(player_class=None, level=1, rarity=None):
    if rarity is None:
        rarity = roll_rarity(level // 5)
    mult = rarity_multiplier(rarity)
    classes = list(WEAPON_NAMES.keys())
    cls = player_class if player_class in WEAPON_NAMES else random.choice(classes)
    prefix = random.choice(WEAPON_PREFIXES)
    wname  = random.choice(WEAPON_NAMES[cls])
    name   = f"{prefix} {wname}"
    base_atk = int((5 + level * 2) * mult)
    stats = {"atk": base_atk}
    if random.random() < 0.3:
        stats["spd"] = random.randint(1, int(3 * mult))
    value = int(base_atk * 3 * mult)
    return Item(name, "weapon", rarity, value, stats)


def generate_armor(level=1, rarity=None):
    if rarity is None:
        rarity = roll_rarity(level // 5)
    mult = rarity_multiplier(rarity)
    prefix = random.choice(ARMOR_PREFIXES)
    aname  = random.choice(ARMOR_NAMES)
    name   = f"{prefix} {aname}"
    base_def = int((3 + level) * mult)
    stats = {"def": base_def}
    if random.random() < 0.3:
        stats["hp"] = random.randint(5, int(15 * mult))
    value = int(base_def * 5 * mult)
    return Item(name, "armor", rarity, value, stats)


def generate_consumable():
    c = random.choice(CONSUMABLE_NAMES)
    name, effect, eff_val = c
    value = max(5, eff_val * 2)
    return Item(name, "consumable", "Common", value, effect=effect, effect_value=eff_val)


def generate_loot(level=1, luck=0, count=None):
    if count is None:
        count = random.randint(0, 3)
    items = []
    for _ in range(count):
        roll = random.random() + luck * 0.05
        if roll < 0.4:
            items.append(generate_consumable())
        elif roll < 0.7:
            items.append(generate_weapon(level=level))
        else:
            items.append(generate_armor(level=level))
    return items


SHOP_STOCK_SIZE = 6

def generate_shop_stock(level=1):
    stock = []
    for _ in range(2):
        stock.append(generate_weapon(level=level))
    for _ in range(2):
        stock.append(generate_armor(level=level))
    for _ in range(SHOP_STOCK_SIZE - 4):
        stock.append(generate_consumable())
    return stock
