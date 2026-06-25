import random
from items import generate_loot

ENEMY_TEMPLATES = [
    # (name, hp_base, hp_scale, atk_base, atk_scale, def_base, def_scale, xp_base, gold_base, zone_min, abilities)
    {"name": "Goblin",        "hp": 30,  "hp_s": 4,  "atk": 8,  "atk_s": 1.2, "def": 2,  "def_s": 0.3, "xp": 30,  "gold": 8,  "zone": 1, "tier": 1,
     "abilities": ["Scratch", "Flee Attempt"]},
    {"name": "Skeleton",      "hp": 40,  "hp_s": 5,  "atk": 10, "atk_s": 1.5, "def": 4,  "def_s": 0.5, "xp": 40,  "gold": 10, "zone": 1, "tier": 1,
     "abilities": ["Bone Crush"]},
    {"name": "Forest Wolf",   "hp": 50,  "hp_s": 6,  "atk": 12, "atk_s": 1.8, "def": 3,  "def_s": 0.4, "xp": 45,  "gold": 6,  "zone": 1, "tier": 1,
     "abilities": ["Bite", "Howl"]},
    {"name": "Bandit",        "hp": 55,  "hp_s": 7,  "atk": 14, "atk_s": 2.0, "def": 5,  "def_s": 0.6, "xp": 55,  "gold": 20, "zone": 1, "tier": 1,
     "abilities": ["Slash", "Cheap Shot"]},
    {"name": "Orc Warrior",   "hp": 80,  "hp_s": 9,  "atk": 16, "atk_s": 2.2, "def": 7,  "def_s": 0.8, "xp": 80,  "gold": 18, "zone": 2, "tier": 2,
     "abilities": ["Heavy Blow", "War Cry"]},
    {"name": "Dark Mage",     "hp": 60,  "hp_s": 6,  "atk": 20, "atk_s": 2.8, "def": 4,  "def_s": 0.4, "xp": 90,  "gold": 25, "zone": 2, "tier": 2,
     "abilities": ["Dark Bolt", "Drain Life"]},
    {"name": "Stone Golem",   "hp": 120, "hp_s": 12, "atk": 18, "atk_s": 2.0, "def": 15, "def_s": 1.2, "xp": 110, "gold": 22, "zone": 2, "tier": 2,
     "abilities": ["Ground Slam", "Rock Throw"]},
    {"name": "Vampire",       "hp": 90,  "hp_s": 10, "atk": 22, "atk_s": 3.0, "def": 8,  "def_s": 0.9, "xp": 130, "gold": 40, "zone": 3, "tier": 3,
     "abilities": ["Blood Drain", "Hypnosis", "Bat Swarm"]},
    {"name": "Wyvern",        "hp": 140, "hp_s": 15, "atk": 26, "atk_s": 3.5, "def": 10, "def_s": 1.0, "xp": 160, "gold": 35, "zone": 3, "tier": 3,
     "abilities": ["Tail Swipe", "Fire Breath"]},
    {"name": "Shadow Assassin","hp": 85, "hp_s": 8,  "atk": 30, "atk_s": 4.0, "def": 6,  "def_s": 0.5, "xp": 150, "gold": 50, "zone": 3, "tier": 3,
     "abilities": ["Shadow Strike", "Vanish", "Poison Blade"]},
    {"name": "Lich",          "hp": 160, "hp_s": 18, "atk": 35, "atk_s": 5.0, "def": 12, "def_s": 1.5, "xp": 250, "gold": 80, "zone": 4, "tier": 4,
     "abilities": ["Soul Rend", "Undead Army", "Death Coil"]},
    {"name": "Ancient Dragon","hp": 300, "hp_s": 25, "atk": 45, "atk_s": 6.0, "def": 20, "def_s": 2.0, "xp": 400, "gold": 150,"zone": 5, "tier": 5,
     "abilities": ["Dragon Breath", "Tail Crush", "Roar", "Wing Buffet"]},
]

BOSS_TEMPLATES = [
    {"name": "Goblin King",       "zone": 1, "hp": 200,  "atk": 20, "def": 8,  "xp": 300,  "gold": 100,
     "abilities": ["Rage", "Minion Summon", "Heavy Slash"]},
    {"name": "Undead Warlord",    "zone": 2, "hp": 350,  "atk": 35, "def": 15, "xp": 600,  "gold": 200,
     "abilities": ["Death Strike", "Soul Drain", "Bone Shield"]},
    {"name": "Arcane Lich King",  "zone": 3, "hp": 500,  "atk": 50, "def": 20, "xp": 1000, "gold": 350,
     "abilities": ["Arcane Explosion", "Time Warp", "Meteor Strike"]},
    {"name": "Chaos Dragon Lord", "zone": 4, "hp": 800,  "atk": 70, "def": 30, "xp": 2000, "gold": 600,
     "abilities": ["Chaos Breath", "World Ender", "Eternal Flame", "Void Crush"]},
]


class Enemy:
    def __init__(self, template, level=1, is_boss=False):
        self.name      = template["name"]
        self.is_boss   = is_boss
        self.level     = level
        self.abilities = template["abilities"][:]

        scale = level - 1
        if is_boss:
            self.max_hp = template["hp"] + scale * 20
            self.atk    = template["atk"] + scale * 4
            self.def_   = template["def"] + scale * 2
            self.xp     = template["xp"] + scale * 50
            self.gold   = template["gold"] + scale * 20
        else:
            self.max_hp = int(template["hp"] + template["hp_s"] * scale)
            self.atk    = int(template["atk"] + template["atk_s"] * scale)
            self.def_   = int(template["def"] + template["def_s"] * scale)
            self.xp     = int(template["xp"] + scale * 8)
            self.gold   = int(template["gold"] + scale * 3)

        self.hp       = self.max_hp
        self.debuffs  = {}
        self.dot      = 0
        self.dot_dmg  = 0
        self.stunned  = False

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, dmg):
        reduced = max(1, dmg - self.def_)
        self.hp = max(0, self.hp - reduced)
        return reduced

    def attack_player(self, player_def):
        base = self.atk + random.randint(-3, 5)
        if self.stunned:
            self.stunned = False
            return 0, True   # (dmg, was_stunned)
        crit = random.random() < 0.1
        dmg  = int(base * (1.5 if crit else 1.0))
        reduced = max(1, dmg - player_def)
        return reduced, False

    def use_ability(self):
        if not self.abilities:
            return None, 0
        ability = random.choice(self.abilities)
        bonus = random.randint(5, 20)
        return ability, bonus

    def tick_dot(self):
        if self.dot > 0:
            self.hp = max(0, self.hp - self.dot_dmg)
            self.dot -= 1
            return self.dot_dmg
        return 0

    def hp_bar(self, width=20):
        pct  = self.hp / self.max_hp
        fill = int(width * pct)
        col  = "\033[32m" if pct > 0.5 else ("\033[33m" if pct > 0.25 else "\033[31m")
        rst  = "\033[0m"
        return f"{col}[{'█'*fill}{'░'*(width-fill)}]{rst} {self.hp}/{self.max_hp}"

    def loot_drop(self, player_level, player_lck=0):
        items = generate_loot(level=player_level, luck=player_lck,
                              count=random.randint(0, 2 + (1 if self.is_boss else 0)))
        gold  = self.gold + random.randint(-self.gold // 4, self.gold // 4)
        return items, max(1, gold)


def spawn_enemy(zone=1, level=1, force_boss=False):
    if force_boss:
        candidates = [t for t in BOSS_TEMPLATES if t["zone"] <= zone]
        t = max(candidates, key=lambda x: x["zone"]) if candidates else BOSS_TEMPLATES[0]
        return Enemy(t, level=level, is_boss=True)

    candidates = [t for t in ENEMY_TEMPLATES if t["zone"] <= zone]
    if not candidates:
        candidates = [ENEMY_TEMPLATES[0]]
    tier_weights = [2 ** t["tier"] for t in candidates]
    t = random.choices(candidates, weights=tier_weights, k=1)[0]
    return Enemy(t, level=max(1, level + random.randint(-1, 2)))


def get_zone_enemies(zone):
    return [t["name"] for t in ENEMY_TEMPLATES if t["zone"] == zone]
