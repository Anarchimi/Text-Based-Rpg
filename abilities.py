import random

class Ability:
    def __init__(self, name, mp_cost, description, ability_type, value, level_req=1, target="enemy"):
        self.name = name
        self.mp_cost = mp_cost
        self.description = description
        self.ability_type = ability_type  # "damage", "heal", "buff", "debuff", "dot"
        self.value = value                # base value (damage/heal amount)
        self.level_req = level_req
        self.target = target              # "enemy", "self"

    def calculate_effect(self, user_stats):
        stat_bonus = 0
        if self.ability_type == "damage":
            stat_bonus = user_stats.get("int", 0) // 4 + user_stats.get("str", 0) // 6
            return self.value + stat_bonus + random.randint(-2, 4)
        elif self.ability_type == "heal":
            stat_bonus = user_stats.get("int", 0) // 3
            return self.value + stat_bonus + random.randint(0, 5)
        elif self.ability_type == "dot":
            return self.value + user_stats.get("int", 0) // 5
        return self.value

# ── Warrior Abilities ────────────────────────────────────────────────────────
WARRIOR_ABILITIES = [
    Ability("Slash",        6,  "A powerful sword strike",                       "damage", 18, 1),
    Ability("Shield Bash",  8,  "Stuns with a shield blow (bonus damage)",        "damage", 22, 3),
    Ability("Battle Cry",   10, "Boosts ATK temporarily (+20% for 3 turns)",      "buff",   20, 5,  "self"),
    Ability("Whirlwind",    15, "Strike all enemies (AoE) with spinning blade",   "damage", 30, 7),
    Ability("Berserk",      20, "Double attack power, halve defense for 2 turns", "buff",   40, 10, "self"),
    Ability("Execute",      25, "Massive strike, 2x damage on low-HP enemies",    "damage", 50, 14),
]

# ── Mage Abilities ────────────────────────────────────────────────────────────
MAGE_ABILITIES = [
    Ability("Fireball",     8,  "Launch a burning fireball at the enemy",         "damage", 22, 1),
    Ability("Ice Lance",    6,  "Freezing spear that may slow the enemy",         "damage", 18, 3),
    Ability("Arcane Surge", 12, "Unleash raw arcane energy",                      "damage", 32, 5),
    Ability("Mana Shield",  15, "Convert MP into a protective barrier",           "buff",   30, 7,  "self"),
    Ability("Chain Lightning",20,"Lightning jumps between targets for bonus dmg", "damage", 40, 10),
    Ability("Meteor",       30, "Call down a meteor for devastating damage",      "damage", 65, 14),
]

# ── Rogue Abilities ────────────────────────────────────────────────────────────
ROGUE_ABILITIES = [
    Ability("Backstab",     6,  "Strike a vital point for extra damage",          "damage", 20, 1),
    Ability("Poison Blade", 8,  "Coat blade in poison (3-turn DoT)",              "dot",    8,  3),
    Ability("Evasion",      10, "Dodge the next incoming attack",                 "buff",   25, 5,  "self"),
    Ability("Shadow Step",  12, "Teleport behind enemy for massive crit strike",  "damage", 38, 7),
    Ability("Smoke Bomb",   15, "Reduce enemy accuracy, reposition",              "debuff", 20, 10),
    Ability("Death Mark",   25, "Mark enemy for death; 3x damage next strike",   "damage", 55, 14),
]

CLASS_ABILITIES = {
    "Warrior": WARRIOR_ABILITIES,
    "Mage":    MAGE_ABILITIES,
    "Rogue":   ROGUE_ABILITIES,
}

def get_available_abilities(player_class, level):
    abilities = CLASS_ABILITIES.get(player_class, [])
    return [a for a in abilities if a.level_req <= level]
