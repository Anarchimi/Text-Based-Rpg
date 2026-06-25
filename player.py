import random
from abilities import get_available_abilities

XP_TABLE = [0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200,
            4000, 5000, 6200, 7600, 9200, 11000, 13200, 15800, 18800, 22200]

CLASS_BASES = {
    "Warrior": {"hp": 120, "mp": 40,  "str": 14, "dex": 8,  "int": 6,  "vit": 12, "lck": 5},
    "Mage":    {"hp": 70,  "mp": 100, "str": 6,  "dex": 8,  "int": 16, "vit": 6,  "lck": 7},
    "Rogue":   {"hp": 90,  "mp": 60,  "str": 9,  "dex": 16, "int": 8,  "vit": 8,  "lck": 10},
}

CLASS_GROWTH = {
    "Warrior": {"hp": 16, "mp": 4,  "str": 2.5, "dex": 1,   "int": 0.5, "vit": 2,   "lck": 0.3},
    "Mage":    {"hp": 8,  "mp": 14, "str": 0.5, "dex": 1,   "int": 3,   "vit": 0.8, "lck": 0.5},
    "Rogue":   {"hp": 10, "mp": 7,  "str": 1.2, "dex": 2.8, "int": 1,   "vit": 1,   "lck": 0.8},
}

SKILL_TREE = {
    "Warrior": [
        {"name": "Iron Skin",        "desc": "+15 Max HP",           "stat": "max_hp",  "bonus": 15,  "cost": 1},
        {"name": "Power Strike",     "desc": "+3 STR",               "stat": "str",     "bonus": 3,   "cost": 1},
        {"name": "Fortitude",        "desc": "+8 Max HP, +2 VIT",    "stat": "max_hp",  "bonus": 8,   "cost": 2},
        {"name": "Veteran's Edge",   "desc": "+5 STR, +3 VIT",       "stat": "str",     "bonus": 5,   "cost": 2},
        {"name": "Titan's Grip",     "desc": "+10 STR",              "stat": "str",     "bonus": 10,  "cost": 3},
        {"name": "Indomitable",      "desc": "+50 Max HP",           "stat": "max_hp",  "bonus": 50,  "cost": 3},
    ],
    "Mage": [
        {"name": "Mana Tap",         "desc": "+20 Max MP",           "stat": "max_mp",  "bonus": 20,  "cost": 1},
        {"name": "Arcane Mind",      "desc": "+3 INT",               "stat": "int",     "bonus": 3,   "cost": 1},
        {"name": "Spell Mastery",    "desc": "+8 INT",               "stat": "int",     "bonus": 8,   "cost": 2},
        {"name": "Ley Lines",        "desc": "+40 Max MP",           "stat": "max_mp",  "bonus": 40,  "cost": 2},
        {"name": "Archmage Focus",   "desc": "+15 INT",              "stat": "int",     "bonus": 15,  "cost": 3},
        {"name": "Infinite Reservoir","desc": "+80 Max MP",          "stat": "max_mp",  "bonus": 80,  "cost": 3},
    ],
    "Rogue": [
        {"name": "Keen Eye",         "desc": "+3 DEX, +2 LCK",       "stat": "dex",     "bonus": 3,   "cost": 1},
        {"name": "Shadow Veil",      "desc": "+5 DEX",               "stat": "dex",     "bonus": 5,   "cost": 1},
        {"name": "Treasure Hunter",  "desc": "+5 LCK",               "stat": "lck",     "bonus": 5,   "cost": 2},
        {"name": "Assassin's Mark",  "desc": "+8 DEX",               "stat": "dex",     "bonus": 8,   "cost": 2},
        {"name": "Ghost Walk",       "desc": "+10 DEX, +5 LCK",      "stat": "dex",     "bonus": 10,  "cost": 3},
        {"name": "Master of Shadows","desc": "+20 DEX",              "stat": "dex",     "bonus": 20,  "cost": 3},
    ],
}


class Player:
    def __init__(self, name, player_class):
        self.name = name
        self.player_class = player_class
        base = CLASS_BASES[player_class]

        self.level   = 1
        self.xp      = 0
        self.xp_next = XP_TABLE[1]
        self.skill_points = 2

        self.base_str = base["str"]
        self.base_dex = base["dex"]
        self.base_int = base["int"]
        self.base_vit = base["vit"]
        self.base_lck = base["lck"]

        self.max_hp = base["hp"]
        self.max_mp = base["mp"]
        self.hp     = self.max_hp
        self.mp     = self.max_mp

        self.gold      = 50
        self.inventory = []
        self.equipment = {"weapon": None, "armor": None}
        self.skills_learned = []

        self.buffs    = {}   # {"name": turns_remaining}
        self.debuffs  = {}
        self.dot      = 0    # damage over time remaining
        self.dot_dmg  = 0

        self.kills    = 0
        self.quests_completed = 0
        self.steps    = 0

    # ── Derived Stats ──────────────────────────────────────────────────────────
    @property
    def str(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "str")
        eq_bonus = self.equipment["weapon"].stats.get("str", 0) if self.equipment["weapon"] else 0
        return self.base_str + bonus + eq_bonus

    @property
    def dex(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "dex")
        return self.base_dex + bonus

    @property
    def int(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "int")
        return self.base_int + bonus

    @property
    def vit(self):
        return self.base_vit

    @property
    def lck(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "lck")
        return self.base_lck + bonus

    @property
    def attack(self):
        base = self.str + self.dex // 3
        weap = self.equipment["weapon"].stats.get("atk", 0) if self.equipment["weapon"] else 0
        berserk = 2 if "Berserk" in self.buffs else 1
        return (base + weap) * berserk

    @property
    def defense(self):
        base = self.vit // 2
        arm  = self.equipment["armor"].stats.get("def", 0) if self.equipment["armor"] else 0
        berserk_pen = self.defense // 2 if "Berserk" in self.buffs else 0
        return max(0, base + arm - berserk_pen)

    @property
    def speed(self):
        base = self.dex // 2
        weap_spd = self.equipment["weapon"].stats.get("spd", 0) if self.equipment["weapon"] else 0
        return base + weap_spd

    # ── Leveling ──────────────────────────────────────────────────────────────
    def gain_xp(self, amount):
        self.xp += amount
        leveled = []
        while self.level < len(XP_TABLE) - 1 and self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.skill_points += 2
            self.xp_next = XP_TABLE[min(self.level, len(XP_TABLE) - 1)]
            self._apply_growth()
            leveled.append(self.level)
        return leveled

    def _apply_growth(self):
        g = CLASS_GROWTH[self.player_class]
        self.max_hp += int(g["hp"])
        self.max_mp += int(g["mp"])
        self.base_str += g["str"]
        self.base_dex += g["dex"]
        self.base_int += g["int"]
        self.base_vit += g["vit"]
        self.base_lck += g["lck"]
        bonus_hp = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "max_hp")
        self.max_hp = int(self.max_hp)
        self.hp = self.max_hp + bonus_hp
        self.mp = self.max_mp

    # ── Skills ─────────────────────────────────────────────────────────────────
    def available_skills(self):
        learned_names = {s["name"] for s in self.skills_learned}
        return [s for s in SKILL_TREE[self.player_class] if s["name"] not in learned_names]

    def learn_skill(self, skill):
        if self.skill_points < skill["cost"]:
            return False, "Not enough skill points."
        self.skill_points -= skill["cost"]
        self.skills_learned.append(skill)
        if skill["stat"] == "max_hp":
            self.max_hp += skill["bonus"]
            self.hp = min(self.hp + skill["bonus"], self.max_hp)
        elif skill["stat"] == "max_mp":
            self.max_mp += skill["bonus"]
            self.mp = min(self.mp + skill["bonus"], self.max_mp)
        return True, f"Learned {skill['name']}!"

    # ── Abilities ──────────────────────────────────────────────────────────────
    def get_abilities(self):
        return get_available_abilities(self.player_class, self.level)

    # ── Inventory ──────────────────────────────────────────────────────────────
    def add_item(self, item):
        self.inventory.append(item)

    def equip(self, item):
        if item.item_type not in ("weapon", "armor"):
            return False, "Can't equip that."
        self.inventory.remove(item)
        old = self.equipment[item.item_type]
        if old:
            self.inventory.append(old)
        self.equipment[item.item_type] = item
        return True, f"Equipped {item.name}."

    def use_consumable(self, item):
        if item.item_type != "consumable":
            return False, "Not a consumable."
        msg = ""
        if item.effect == "heal_hp":
            healed = min(item.effect_value, self.max_hp - self.hp)
            self.hp += healed
            msg = f"Restored {healed} HP."
        elif item.effect == "heal_mp":
            restored = min(item.effect_value, self.max_mp - self.mp)
            self.mp += restored
            msg = f"Restored {restored} MP."
        elif item.effect == "buff_str":
            self.base_str += item.effect_value
            msg = f"STR increased by {item.effect_value}!"
        elif item.effect == "buff_int":
            self.base_int += item.effect_value
            msg = f"INT increased by {item.effect_value}!"
        elif item.effect == "cure":
            self.dot = 0
            self.dot_dmg = 0
            msg = "Cured all status effects!"
        elif item.effect == "revive":
            msg = "Saved for revive on death."
        self.inventory.remove(item)
        return True, msg

    def has_revive(self):
        return any(i.effect == "revive" for i in self.inventory)

    def consume_revive(self):
        for i in self.inventory:
            if i.effect == "revive":
                self.inventory.remove(i)
                self.hp = self.max_hp // 2
                return True
        return False

    # ── Buff Management ────────────────────────────────────────────────────────
    def tick_buffs(self):
        expired = []
        for b in list(self.buffs):
            self.buffs[b] -= 1
            if self.buffs[b] <= 0:
                expired.append(b)
                del self.buffs[b]
        if self.dot > 0:
            self.hp = max(0, self.hp - self.dot_dmg)
            self.dot -= 1
        return expired

    # ── Display ────────────────────────────────────────────────────────────────
    def status_bar(self):
        hp_pct  = self.hp / self.max_hp
        mp_pct  = self.mp / self.max_mp
        hp_col  = "\033[32m" if hp_pct > 0.5 else ("\033[33m" if hp_pct > 0.25 else "\033[31m")
        mp_col  = "\033[34m"
        rst     = "\033[0m"
        return (f"{hp_col}HP: {self.hp}/{self.max_hp}{rst}  "
                f"{mp_col}MP: {self.mp}/{self.max_mp}{rst}  "
                f"Gold: {self.gold}g  LVL: {self.level}  XP: {self.xp}/{self.xp_next}")

    def full_stats(self):
        lines = [
            f"  Name:  {self.name} the {self.player_class}  (Level {self.level})",
            f"  HP:    {self.hp}/{self.max_hp}    MP: {self.mp}/{self.max_mp}",
            f"  STR:   {self.str:.0f}     DEX: {self.dex:.0f}     INT: {self.int:.0f}",
            f"  VIT:   {self.vit:.0f}     LCK: {self.lck:.0f}",
            f"  ATK:   {self.attack:.0f}     DEF: {self.defense:.0f}     SPD: {self.speed:.0f}",
            f"  Gold:  {self.gold}g    XP: {self.xp}/{self.xp_next}",
            f"  Skill Points: {self.skill_points}",
            f"  Kills: {self.kills}    Quests: {self.quests_completed}",
        ]
        weap = self.equipment["weapon"]
        arm  = self.equipment["armor"]
        lines.append(f"  Weapon: {weap.name if weap else 'None'}")
        lines.append(f"  Armor:  {arm.name  if arm  else 'None'}")
        if self.skills_learned:
            lines.append(f"  Skills: {', '.join(s['name'] for s in self.skills_learned)}")
        if self.buffs:
            lines.append(f"  Buffs:  {', '.join(f'{k}({v}t)' for k,v in self.buffs.items())}")
        if self.dot > 0:
            lines.append(f"  POISONED: {self.dot_dmg} dmg for {self.dot} more turns")
        return "\n".join(lines)
