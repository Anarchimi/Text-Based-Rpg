import random


class Ability:
    """A player combat ability.

    Damage abilities deal `mult` × the caster's power (Player.ability_power: ATK
    for Warriors/Rogues, spell power for Mages). `status` is applied to the enemy
    on hit with `status_chance`. Buffs store `value` for display only; their
    effects are implemented where the buff name is checked (see CLAUDE.md).
    """

    def __init__(self, name, mp_cost, description, ability_type, value, level_req=1,
                 target="enemy", mult=1.0, status=None, status_chance=0.0):
        self.name = name
        self.mp_cost = mp_cost
        self.description = description
        self.ability_type = ability_type  # "damage", "heal", "buff", "debuff", "dot"
        self.value = value
        self.level_req = level_req
        self.target = target              # "enemy", "self"
        self.mult = mult
        self.status = status              # enemy status applied on hit, e.g. "Stunned"
        self.status_chance = status_chance

    def calculate_effect(self, power):
        if self.ability_type == "damage":
            return int(power * self.mult) + random.randint(-2, 4)
        if self.ability_type == "dot":
            return max(1, int(power * self.mult))
        if self.ability_type == "heal":
            return int(power * self.mult) + random.randint(0, 5)
        return self.value


# ── Warrior Abilities ────────────────────────────────────────────────────────
WARRIOR_ABILITIES = [
    Ability("Slash",        6,  "A powerful sword strike (1.4× ATK)",                "damage", 18, 1,  mult=1.4),
    Ability("Shield Bash",  8,  "1.2× ATK with a 35% chance to stun",                "damage", 22, 3,  mult=1.2,
            status="Stunned", status_chance=0.35),
    Ability("Battle Cry",   10, "Boosts ATK temporarily (+20% for 3 turns)",         "buff",   20, 5,  "self"),
    Ability("Whirlwind",    15, "Spinning blade strike (2× ATK)",                    "damage", 30, 7,  mult=2.0),
    Ability("Berserk",      20, "Double attack power, halve defense for 3 turns",    "buff",   40, 10, "self"),
    Ability("Execute",      25, "2.2× ATK, doubled on enemies below 30% HP",         "damage", 50, 14, mult=2.2),
]

# ── Mage Abilities ────────────────────────────────────────────────────────────
MAGE_ABILITIES = [
    Ability("Fireball",     8,  "1.4× spell power, 30% chance to burn",              "damage", 22, 1,  mult=1.4,
            status="Burning", status_chance=0.30),
    Ability("Ice Lance",    6,  "1.2× spell power and chills (enemy ATK -25%)",      "damage", 18, 3,  mult=1.2,
            status="Chilled", status_chance=1.0),
    Ability("Arcane Surge", 12, "Unleash raw arcane energy (1.8× spell power)",      "damage", 32, 5,  mult=1.8),
    Ability("Mana Shield",  15, "Half of incoming damage drains MP, not HP",         "buff",   30, 7,  "self"),
    Ability("Chain Lightning",20,"Crackling bolt (2.2× spell power)",                "damage", 40, 10, mult=2.2),
    Ability("Meteor",       30, "Devastating impact (2.9× spell power)",             "damage", 65, 14, mult=2.9),
]

# ── Rogue Abilities ────────────────────────────────────────────────────────────
ROGUE_ABILITIES = [
    Ability("Backstab",     6,  "Strike a vital point (1.5× ATK)",                   "damage", 20, 1,  mult=1.5),
    Ability("Poison Blade", 8,  "Poison: 0.35× ATK per turn for 3 turns",            "dot",    8,  3,  mult=0.35),
    Ability("Evasion",      10, "Dodge the next incoming attack",                    "buff",   25, 5,  "self"),
    Ability("Shadow Step",  12, "Strike from the shadows (1.9× ATK, +25% crit)",     "damage", 38, 7,  mult=1.9),
    Ability("Smoke Bomb",   15, "Blind the enemy: it loses its next turn",           "debuff", 20, 10),
    Ability("Death Mark",   25, "1.1× ATK, then tripled",                            "damage", 55, 14, mult=1.1),
]

CLASS_ABILITIES = {
    "Warrior": WARRIOR_ABILITIES,
    "Mage":    MAGE_ABILITIES,
    "Rogue":   ROGUE_ABILITIES,
}


def get_available_abilities(player_class, level):
    abilities = CLASS_ABILITIES.get(player_class, [])
    return [a for a in abilities if a.level_req <= level]
