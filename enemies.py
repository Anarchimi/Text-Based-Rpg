import random
from items import generate_loot

# Defense reduces damage by a percentage: DEF_K defense halves incoming damage.
# (Flat subtraction made early bosses harmless and late bosses unkillable.)
DEF_K = 100


# Balance knobs — tune with `python tools/balance_sim.py`.
MOB_HP_MULT     = 2.6   # regular enemies' HP multiplier
MOB_HP_GROWTH   = 1.1   # × template hp_s per level
MOB_ATK_GROWTH  = 0.9   # × template atk_s per level
MOB_DEF_GROWTH  = 1.0   # × template def_s per level
BOSS_HP_GROWTH  = 0.13  # boss stat = base × (1 + growth × (level - 1))
BOSS_ATK_GROWTH = 0.08
BOSS_DEF_GROWTH = 0.06
NG_PLUS_POWER   = 0.45  # each New Game+ cycle: enemy HP/ATK/DEF × (1 + this × cycle)


def mitigate(dmg, defense):
    return max(1, int(dmg * DEF_K / (DEF_K + max(0, defense))))

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
    {"name": "Ancient Dragon",  "hp": 220, "hp_s": 20, "atk": 40, "atk_s": 5.5, "def": 18, "def_s": 1.8, "xp": 400, "gold": 150,"zone": 5, "tier": 5,
     "abilities": ["Dragon Breath", "Tail Crush", "Roar", "Wing Buffet"]},
    {"name": "Chaos Elemental", "hp": 170, "hp_s": 17, "atk": 44, "atk_s": 6.0, "def": 14, "def_s": 1.4, "xp": 380, "gold": 130,"zone": 5, "tier": 5,
     "abilities": ["Chaos Burst", "Void Rift", "Elemental Storm"]},
    {"name": "Undead Titan",    "hp": 260, "hp_s": 22, "atk": 38, "atk_s": 5.0, "def": 22, "def_s": 2.2, "xp": 420, "gold": 160,"zone": 5, "tier": 5,
     "abilities": ["Titan Slam", "Bone Crush", "Death Wail"]},
    {"name": "Void Stalker",    "hp": 190, "hp_s": 18, "atk": 48, "atk_s": 6.5, "def": 12, "def_s": 1.2, "xp": 450, "gold": 175,"zone": 5, "tier": 5,
     "abilities": ["Phase Strike", "Void Step", "Reality Tear", "Soul Devour"]},
]

# Each zone boss guards one of the Five Seals (seal = zone). Breaking all five
# lets the player confront FINAL_BOSS on Dragon's Peak.
BOSS_TEMPLATES = [
    {"name": "Goblin King",       "zone": 1, "hp": 200,  "atk": 20, "def": 8,  "xp": 300,  "gold": 100,
     "abilities": ["Rage", "Minion Summon", "Heavy Slash"],
     "phase2": "The Goblin King hurls his crown aside. 'ENOUGH!'"},
    {"name": "Undead Warlord",    "zone": 2, "hp": 350,  "atk": 35, "def": 15, "xp": 600,  "gold": 200,
     "abilities": ["Death Strike", "Soul Drain", "Bone Shield"],
     "phase2": "Bones knit back together. The Warlord's eyes burn brighter."},
    {"name": "Arcane Lich King",  "zone": 3, "hp": 500,  "atk": 50, "def": 20, "xp": 1000, "gold": 350,
     "abilities": ["Arcane Explosion", "Time Warp", "Meteor Strike"],
     "phase2": "The Lich King's phylactery cracks — raw magic pours out."},
    {"name": "Shadow Sovereign",  "zone": 4, "hp": 600,  "atk": 58, "def": 22, "xp": 1400, "gold": 450,
     "abilities": ["Umbral Lance", "Eclipse", "Night Veil", "Soul Siphon"],
     "phase2": "The Sovereign's shadow tears free and fights beside it."},
    {"name": "Ignaroth the Elder Wyrm", "zone": 5, "hp": 640, "atk": 60, "def": 24, "xp": 1800, "gold": 550,
     "abilities": ["Inferno", "Crushing Talon", "Ancient Roar", "Wing Gale"],
     "phase2": "Ignaroth roars. Molten scales fall away, revealing white-hot flesh."},
]

FINAL_BOSS = {"name": "Chaos Dragon Lord", "zone": 5, "hp": 900, "atk": 70, "def": 28, "xp": 3000, "gold": 1000,
              "abilities": ["Chaos Breath", "World Ender", "Eternal Flame", "Void Crush"],
              "phase2": "THE CHAOS DRAGON LORD UNFURLS ITS TRUE FORM. Reality buckles."}

# What each enemy ability actually does. Unlisted names fall back to DEFAULT_ABILITY.
#   kind: hit | drain | dot | stun | weaken | enrage | shield | evade
#   mult: damage as a multiple of the enemy's ATK; hits: number of strikes
#   status/turns/dot: debuff applied to the player (dot = per-turn damage as ×ATK)
#   chance: chance the status lands; charge: telegraphed one turn in advance
DEFAULT_ABILITY = {"kind": "hit", "mult": 1.3}
ENEMY_ABILITIES = {
    # Zone 1
    "Scratch":        {"kind": "hit",    "mult": 1.1},
    "Flee Attempt":   {"kind": "evade",  "text": "darts around, ready to dodge"},
    "Bone Crush":     {"kind": "weaken", "mult": 1.2, "turns": 2},
    "Bite":           {"kind": "dot",    "mult": 1.0, "status": "Bleeding", "turns": 3, "dot": 0.25},
    "Howl":           {"kind": "enrage", "text": "howls, working itself into a frenzy"},
    "Slash":          {"kind": "hit",    "mult": 1.3},
    "Cheap Shot":     {"kind": "stun",   "mult": 0.8, "chance": 0.5},
    # Zone 2
    "Heavy Blow":     {"kind": "hit",    "mult": 1.6},
    "War Cry":        {"kind": "enrage", "text": "lets out a bloodcurdling war cry"},
    "Dark Bolt":      {"kind": "hit",    "mult": 1.5},
    "Drain Life":     {"kind": "drain",  "mult": 1.2},
    "Ground Slam":    {"kind": "stun",   "mult": 1.2, "chance": 0.3},
    "Rock Throw":     {"kind": "hit",    "mult": 1.4},
    # Zone 3
    "Blood Drain":    {"kind": "drain",  "mult": 1.3},
    "Hypnosis":       {"kind": "stun",   "mult": 0.0, "chance": 0.6},
    "Bat Swarm":      {"kind": "hit",    "mult": 0.5, "hits": 3},
    "Tail Swipe":     {"kind": "hit",    "mult": 1.4},
    "Fire Breath":    {"kind": "dot",    "mult": 1.1, "status": "Burning", "turns": 2, "dot": 0.4},
    "Shadow Strike":  {"kind": "hit",    "mult": 1.7},
    "Vanish":         {"kind": "evade",  "text": "melts into the shadows"},
    "Poison Blade":   {"kind": "dot",    "mult": 0.9, "status": "Poisoned", "turns": 4, "dot": 0.25},
    # Zone 4
    "Soul Rend":      {"kind": "weaken", "mult": 1.3, "turns": 3},
    "Undead Army":    {"kind": "hit",    "mult": 0.55, "hits": 3},
    "Death Coil":     {"kind": "drain",  "mult": 1.4},
    # Zone 5
    "Dragon Breath":  {"kind": "dot",    "mult": 1.3, "status": "Burning", "turns": 2, "dot": 0.4},
    "Tail Crush":     {"kind": "hit",    "mult": 1.6},
    "Roar":           {"kind": "weaken", "mult": 0.0, "turns": 3},
    "Wing Buffet":    {"kind": "stun",   "mult": 1.0, "chance": 0.35},
    "Chaos Burst":    {"kind": "hit",    "mult": 1.7},
    "Void Rift":      {"kind": "weaken", "mult": 1.1, "turns": 3},
    "Elemental Storm":{"kind": "dot",    "mult": 0.5, "hits": 3, "status": "Burning", "turns": 2, "dot": 0.3},
    "Titan Slam":     {"kind": "stun",   "mult": 1.7, "chance": 0.25},
    "Death Wail":     {"kind": "weaken", "mult": 0.8, "turns": 3},
    "Phase Strike":   {"kind": "hit",    "mult": 1.6},
    "Void Step":      {"kind": "evade",  "text": "flickers out of phase"},
    "Reality Tear":   {"kind": "dot",    "mult": 1.0, "status": "Bleeding", "turns": 4, "dot": 0.25},
    "Soul Devour":    {"kind": "drain",  "mult": 1.5},
    # Bosses
    "Rage":           {"kind": "enrage", "text": "flies into a rage"},
    "Minion Summon":  {"kind": "hit",    "mult": 0.5, "hits": 3, "text": "summons goblins — they swarm you"},
    "Heavy Slash":    {"kind": "hit",    "mult": 1.6},
    "Death Strike":   {"kind": "hit",    "mult": 2.2, "charge": True},
    "Soul Drain":     {"kind": "drain",  "mult": 1.3},
    "Bone Shield":    {"kind": "shield", "turns": 2, "text": "raises a wall of bone"},
    "Arcane Explosion":{"kind": "hit",   "mult": 1.7},
    "Time Warp":      {"kind": "stun",   "mult": 0.0, "chance": 0.7},
    "Meteor Strike":  {"kind": "dot",    "mult": 2.2, "status": "Burning", "turns": 2, "dot": 0.3, "charge": True},
    "Umbral Lance":   {"kind": "hit",    "mult": 1.8},
    "Eclipse":        {"kind": "weaken", "mult": 0.9, "turns": 3},
    "Night Veil":     {"kind": "evade",  "text": "wraps itself in living darkness"},
    "Soul Siphon":    {"kind": "drain",  "mult": 1.4},
    "Inferno":        {"kind": "dot",    "mult": 1.2, "status": "Burning", "turns": 3, "dot": 0.3},
    "Crushing Talon": {"kind": "dot",    "mult": 1.5, "status": "Bleeding", "turns": 3, "dot": 0.2},
    "Ancient Roar":   {"kind": "weaken", "mult": 0.0, "turns": 3},
    "Wing Gale":      {"kind": "stun",   "mult": 1.0, "chance": 0.35},
    "Chaos Breath":   {"kind": "dot",    "mult": 1.4, "status": "Burning", "turns": 3, "dot": 0.3},
    "World Ender":    {"kind": "hit",    "mult": 3.0, "charge": True},
    "Eternal Flame":  {"kind": "shield", "turns": 2, "text": "is wreathed in eternal flame"},
    "Void Crush":     {"kind": "weaken", "mult": 1.5, "turns": 3},
}


def ability_spec(name):
    return ENEMY_ABILITIES.get(name, DEFAULT_ABILITY)


class Enemy:
    def __init__(self, template, level=1, is_boss=False):
        self.name      = template["name"]
        self.is_boss   = is_boss
        self.level     = level
        self.abilities = template["abilities"][:]

        scale = level - 1
        if is_boss:
            reward_scale = 1 + scale * 0.12
            self.max_hp = int(template["hp"] * (1 + scale * BOSS_HP_GROWTH))
            self.atk    = int(template["atk"] * (1 + scale * BOSS_ATK_GROWTH))
            self.def_   = int(template["def"] * (1 + scale * BOSS_DEF_GROWTH))
            self.xp     = int(template["xp"] * reward_scale)
            self.gold   = int(template["gold"] * reward_scale)
        else:
            self.max_hp = int((template["hp"] + template["hp_s"] * scale * MOB_HP_GROWTH) * MOB_HP_MULT)
            self.atk    = int(template["atk"] + template["atk_s"] * scale * MOB_ATK_GROWTH)
            self.def_   = int(template["def"] + template["def_s"] * scale * MOB_DEF_GROWTH)
            self.xp     = int(template["xp"] + scale * 15)
            self.gold   = int(template["gold"] + scale * 5)

        self.hp       = self.max_hp
        self.debuffs  = {}
        self.dot      = 0
        self.dot_dmg  = 0
        self.dot_name = "Poison"
        self.stunned  = False
        self.statuses = {}      # {"Chilled"|"Enraged"|"Shielded"|"Evading": turns left}
        self.charging = None    # ability name being telegraphed for next turn
        self.phase    = 1       # bosses enter phase 2 below 50% HP
        self.phase2_text = template.get("phase2")
        self.seal     = template["zone"] if is_boss else None
        self.is_final = False
        self.template_name = self.name   # sprite / quest lookups survive renames like "X Leader"

    def __setstate__(self, d):
        # Saves pickled before these attributes existed.
        d.setdefault("statuses", {})
        d.setdefault("dot_name", "Poison")
        d.setdefault("charging", None)
        d.setdefault("phase", 1)
        d.setdefault("phase2_text", None)
        d.setdefault("seal", None)
        d.setdefault("is_final", False)
        d.setdefault("template_name", d.get("name"))
        self.__dict__.update(d)

    def apply_ng_plus(self, ng):
        """New Game+ cycle `ng` makes everything tougher and more rewarding."""
        if ng <= 0:
            return
        power = 1 + NG_PLUS_POWER * ng
        self.max_hp = self.hp = int(self.max_hp * power)
        self.atk  = int(self.atk * power)
        self.def_ = int(self.def_ * power)
        self.xp   = int(self.xp * (1 + 0.25 * ng))
        self.gold = int(self.gold * (1 + 0.25 * ng))

    def make_leader(self):
        """Bounty target: a named, tougher, richer version of this enemy."""
        self.template_name = self.name
        self.name = f"{self.name} Leader"
        self.max_hp = self.hp = int(self.max_hp * 1.5)
        self.atk  = int(self.atk * 1.25)
        self.def_ = int(self.def_ * 1.2)
        self.xp   = self.xp * 2
        self.gold = self.gold * 2

    @property
    def effective_atk(self):
        atk = self.atk
        if "Enraged" in self.statuses:
            atk *= 1.3
        if "Chilled" in self.statuses:
            atk *= 0.75
        if self.phase == 2:
            atk *= 1.15
        return atk

    def tick_statuses(self):
        expired = []
        for name in list(self.statuses):
            self.statuses[name] -= 1
            if self.statuses[name] <= 0:
                del self.statuses[name]
                expired.append(name)
        return expired

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, dmg):
        """Apply a player hit after defense and Shielded. Returns damage dealt."""
        reduced = mitigate(dmg, self.def_)
        if "Shielded" in self.statuses:
            reduced = max(1, reduced // 2)
        self.hp = max(0, self.hp - reduced)
        return reduced

    def tick_dot(self):
        if self.dot > 0:
            self.hp = max(0, self.hp - self.dot_dmg)
            self.dot -= 1
            return self.dot_dmg
        return 0

    def loot_drop(self, player_level, player_lck=0, player_class=None):
        items = generate_loot(level=player_level, luck=player_lck, player_class=player_class,
                              count=random.randint(0, 2 + (1 if self.is_boss else 0)))
        gold  = self.gold + random.randint(-self.gold // 4, self.gold // 4)
        return items, max(1, gold)


def spawn_enemy(zone=1, level=1, force_boss=False, ng=0):
    if force_boss:
        t = next((b for b in BOSS_TEMPLATES if b["zone"] == zone), BOSS_TEMPLATES[0])
        enemy = Enemy(t, level=level, is_boss=True)
    else:
        candidates = [t for t in ENEMY_TEMPLATES if t["zone"] <= zone]
        if not candidates:
            candidates = [ENEMY_TEMPLATES[0]]
        tier_weights = [2 ** t["tier"] for t in candidates]
        t = random.choices(candidates, weights=tier_weights, k=1)[0]
        enemy = Enemy(t, level=max(1, level + random.randint(-1, 2)))
    enemy.apply_ng_plus(ng)
    return enemy


def spawn_final_boss(level, ng=0):
    enemy = Enemy(FINAL_BOSS, level=level, is_boss=True)
    enemy.seal = None
    enemy.is_final = True
    enemy.apply_ng_plus(ng)
    return enemy


def get_zone_enemies(zone):
    return [t["name"] for t in ENEMY_TEMPLATES if t["zone"] == zone]
