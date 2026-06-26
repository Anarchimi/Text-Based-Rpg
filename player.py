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

PROFESSIONS = {
    "Warrior": {
        "Knight": {
            "passive": "+25% DEF. Your presence is unbreakable.",
            "stat_bonus": {"max_hp": 40, "base_vit": 4},
            "skills": [
                {"name": "Iron Wall",    "desc": "+8 VIT",             "stat": "vit",    "bonus": 8,  "cost": 1},
                {"name": "Stalwart",     "desc": "+30 Max HP, +5 VIT", "stat": "max_hp", "bonus": 30, "cost": 2},
                {"name": "Unbreakable",  "desc": "+80 Max HP",         "stat": "max_hp", "bonus": 80, "cost": 3},
            ],
        },
        "Berserker": {
            "passive": "+50% ATK when HP below 30%.",
            "stat_bonus": {"base_str": 6, "max_hp": -20},
            "skills": [
                {"name": "Bloodlust",    "desc": "+8 STR",  "stat": "str", "bonus": 8,  "cost": 1},
                {"name": "Frenzy",       "desc": "+15 STR", "stat": "str", "bonus": 15, "cost": 2},
                {"name": "War Incarnate","desc": "+25 STR", "stat": "str", "bonus": 25, "cost": 3},
            ],
        },
        "Champion": {
            "passive": "+10% ATK and DEF at all times.",
            "stat_bonus": {"base_str": 3, "base_vit": 3, "max_hp": 20},
            "skills": [
                {"name": "Valor",        "desc": "+6 STR, +4 VIT", "stat": "str", "bonus": 6,  "cost": 1},
                {"name": "Victor's Edge","desc": "+12 STR",         "stat": "str", "bonus": 12, "cost": 2},
                {"name": "Grand Legacy", "desc": "+20 STR, +10 VIT","stat": "str", "bonus": 20, "cost": 3},
            ],
        },
    },
    "Mage": {
        "Sorcerer": {
            "passive": "+30% spell damage on all damage abilities.",
            "stat_bonus": {"base_int": 8, "max_mp": 30},
            "skills": [
                {"name": "Overcharge",    "desc": "+8 INT",          "stat": "int", "bonus": 8,  "cost": 1},
                {"name": "Arcane Surge",  "desc": "+15 INT, +20 MP", "stat": "int", "bonus": 15, "cost": 2},
                {"name": "Transcendence", "desc": "+25 INT",          "stat": "int", "bonus": 25, "cost": 3},
            ],
        },
        "Elementalist": {
            "passive": "30% chance to Burn (DoT) enemies on any ability hit.",
            "stat_bonus": {"base_int": 4, "max_mp": 50},
            "skills": [
                {"name": "Attunement",     "desc": "+6 INT, +20 MP",  "stat": "int", "bonus": 6,  "cost": 1},
                {"name": "Volatile Magic", "desc": "+12 INT, +30 MP", "stat": "int", "bonus": 12, "cost": 2},
                {"name": "Avatar",         "desc": "+20 INT, +50 MP", "stat": "int", "bonus": 20, "cost": 3},
            ],
        },
        "Necromancer": {
            "passive": "+20% damage vs enemies below 50% HP.",
            "stat_bonus": {"base_int": 5, "max_hp": 15, "max_mp": 20},
            "skills": [
                {"name": "Soul Tap",    "desc": "+6 INT, +25 MP",  "stat": "int", "bonus": 6,  "cost": 1},
                {"name": "Life Drain",  "desc": "+12 INT, +30 HP", "stat": "int", "bonus": 12, "cost": 2},
                {"name": "Lich Form",   "desc": "+20 INT, +60 HP", "stat": "int", "bonus": 20, "cost": 3},
            ],
        },
    },
    "Rogue": {
        "Assassin": {
            "passive": "Execute triggers at 40% HP. Death Mark deals 3× damage.",
            "stat_bonus": {"base_dex": 5, "base_lck": 3},
            "skills": [
                {"name": "Blade Mastery", "desc": "+8 DEX",           "stat": "dex", "bonus": 8,  "cost": 1},
                {"name": "Predator",      "desc": "+12 DEX, +5 LCK",  "stat": "dex", "bonus": 12, "cost": 2},
                {"name": "Shadow Lord",   "desc": "+20 DEX, +10 LCK", "stat": "dex", "bonus": 20, "cost": 3},
            ],
        },
        "Ranger": {
            "passive": "Flee always succeeds. +20% ATK on first strike each combat.",
            "stat_bonus": {"base_dex": 6, "base_lck": 4},
            "skills": [
                {"name": "Eagle Eye",   "desc": "+6 DEX, +5 LCK",  "stat": "dex", "bonus": 6,  "cost": 1},
                {"name": "Hunter",      "desc": "+12 DEX, +5 LCK", "stat": "dex", "bonus": 12, "cost": 2},
                {"name": "Wind Runner", "desc": "+20 DEX, +10 LCK","stat": "dex", "bonus": 20, "cost": 3},
            ],
        },
        "Trickster": {
            "passive": "Poison lasts +2 extra turns and deals +50% DoT damage.",
            "stat_bonus": {"base_dex": 3, "base_int": 4, "base_lck": 3},
            "skills": [
                {"name": "Venom Craft",   "desc": "+6 DEX, +4 INT",  "stat": "dex", "bonus": 6,  "cost": 1},
                {"name": "Toxic Mastery", "desc": "+10 DEX, +6 INT", "stat": "dex", "bonus": 10, "cost": 2},
                {"name": "Poison Adept",  "desc": "+15 DEX, +10 INT","stat": "dex", "bonus": 15, "cost": 3},
            ],
        },
    },
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

        self.buffs   = {}
        self.debuffs = {}
        self.dot     = 0
        self.dot_dmg = 0

        self.temp_buffs = []  # [{"stat":"str","amount":8,"turns":3}, ...]

        # Combat professions
        self.profession         = None
        self.prof_skills_learned = []
        self.first_strike_used  = False  # for Ranger passive

        # Trade / gathering professions
        self.trade_profession = None
        self.gathering_skills = {s: {"level": 1, "xp": 0}
                                  for s in ["Mining", "Woodcutting", "Fishing", "Herbalism"]}
        self.crafting_skills  = {s: {"level": 1, "xp": 0}
                                  for s in ["Smithing", "Fletching", "Cooking", "Herblore"]}
        self.resources = {}

        self.kills    = 0
        self.quests_completed = 0
        self.steps    = 0

    # ── Derived Stats ──────────────────────────────────────────────────────────
    @property
    def str(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "str")
        prof_bonus = sum(s["bonus"] for s in self.prof_skills_learned if s["stat"] == "str")
        eq_bonus = self.equipment["weapon"].stats.get("str", 0) if self.equipment["weapon"] else 0
        temp = sum(b["amount"] for b in self.temp_buffs if b["stat"] in ("str", "all"))
        return self.base_str + bonus + prof_bonus + eq_bonus + temp

    @property
    def dex(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "dex")
        prof_bonus = sum(s["bonus"] for s in self.prof_skills_learned if s["stat"] == "dex")
        return self.base_dex + bonus + prof_bonus

    @property
    def int(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "int")
        prof_bonus = sum(s["bonus"] for s in self.prof_skills_learned if s["stat"] == "int")
        return self.base_int + bonus + prof_bonus

    @property
    def vit(self):
        prof_bonus = sum(s["bonus"] for s in self.prof_skills_learned if s["stat"] == "vit")
        temp = sum(b["amount"] for b in self.temp_buffs if b["stat"] in ("vit", "all"))
        return self.base_vit + prof_bonus + temp

    @property
    def lck(self):
        bonus = sum(s["bonus"] for s in self.skills_learned if s["stat"] == "lck")
        prof_bonus = sum(s["bonus"] for s in self.prof_skills_learned if s["stat"] == "lck")
        return self.base_lck + bonus + prof_bonus

    @property
    def attack(self):
        base = self.str + self.dex // 3
        weap = self.equipment["weapon"].stats.get("atk", 0) if self.equipment["weapon"] else 0
        berserk = 2 if "Berserk" in self.buffs else 1
        champion_bonus = int((base + weap) * 0.10) if self.profession == "Champion" else 0
        return int((base + weap + champion_bonus) * berserk)

    @property
    def defense(self):
        base = int(self.base_vit * 0.8)
        arm  = self.equipment["armor"].stats.get("def", 0) if self.equipment["armor"] else 0
        vit_temp = sum(b["amount"] for b in self.temp_buffs if b["stat"] in ("vit", "all"))
        prof_vit = sum(s["bonus"] for s in self.prof_skills_learned if s["stat"] == "vit")
        base += int((vit_temp + prof_vit) * 0.8)
        knight_bonus = int((base + arm) * 0.25) if self.profession == "Knight" else 0
        champion_bonus = int((base + arm) * 0.10) if self.profession == "Champion" else 0
        berserk_pen = (base + arm) // 2 if "Berserk" in self.buffs else 0
        return max(0, base + arm + knight_bonus + champion_bonus - berserk_pen)

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
        self.max_hp = int(self.max_hp)
        self.hp = self.max_hp  # heal to full on level up
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
        stat = skill["stat"]
        bonus = skill["bonus"]
        if stat == "max_hp":
            self.max_hp += bonus
            self.hp = min(self.hp + bonus, self.max_hp)
        elif stat == "max_mp":
            self.max_mp += bonus
            self.mp = min(self.mp + bonus, self.max_mp)
        elif stat == "str":
            self.base_str += bonus
        elif stat == "dex":
            self.base_dex += bonus
        elif stat == "int":
            self.base_int += bonus
        elif stat == "vit":
            self.base_vit += bonus
        elif stat == "lck":
            self.base_lck += bonus
        return True, f"Learned {skill['name']}!"

    # ── Combat Professions ─────────────────────────────────────────────────────
    def choose_profession(self, prof_name):
        profs = PROFESSIONS.get(self.player_class, {})
        if prof_name not in profs:
            return False, "Invalid profession."
        if self.profession:
            return False, "Already chosen a profession."
        p = profs[prof_name]
        self.profession = prof_name
        for stat, val in p["stat_bonus"].items():
            if stat == "max_hp":
                self.max_hp += val
                self.hp = min(self.hp + max(0, val), self.max_hp)
            elif stat == "max_mp":
                self.max_mp += val
                self.mp = min(self.mp + max(0, val), self.max_mp)
            elif stat == "base_str":
                self.base_str += val
            elif stat == "base_dex":
                self.base_dex += val
            elif stat == "base_int":
                self.base_int += val
            elif stat == "base_vit":
                self.base_vit += val
            elif stat == "base_lck":
                self.base_lck += val
        return True, f"You are now a {prof_name}! {p['passive']}"

    def available_prof_skills(self):
        if not self.profession:
            return []
        profs = PROFESSIONS.get(self.player_class, {})
        p = profs.get(self.profession, {})
        learned_names = {s["name"] for s in self.prof_skills_learned}
        return [s for s in p.get("skills", []) if s["name"] not in learned_names]

    def learn_prof_skill(self, skill):
        if self.skill_points < skill["cost"]:
            return False, "Not enough skill points."
        self.skill_points -= skill["cost"]
        self.prof_skills_learned.append(skill)
        stat = skill["stat"]
        bonus = skill["bonus"]
        if stat == "max_hp":
            self.max_hp += bonus
            self.hp = min(self.hp + bonus, self.max_hp)
        elif stat == "max_mp":
            self.max_mp += bonus
            self.mp = min(self.mp + bonus, self.max_mp)
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
        eff = item.effect
        val = item.effect_value
        dur = getattr(item, 'effect_duration', 0)

        if eff == "heal_pct":
            amt = int(self.max_hp * val / 100)
            healed = min(amt, self.max_hp - self.hp)
            self.hp += healed
            msg = f"Restored {healed} HP ({val}% of max)."
        elif eff == "heal_mp_pct":
            amt = int(self.max_mp * val / 100)
            restored = min(amt, self.max_mp - self.mp)
            self.mp += restored
            msg = f"Restored {restored} MP ({val}% of max)."
        elif eff == "heal_hp":
            healed = min(val, self.max_hp - self.hp)
            self.hp += healed
            msg = f"Restored {healed} HP."
        elif eff == "heal_mp":
            restored = min(val, self.max_mp - self.mp)
            self.mp += restored
            msg = f"Restored {restored} MP."
        elif eff == "heal_overheal":
            base_heal = int(self.max_hp * val / 100)
            overheal_cap = int(self.max_hp * 1.1)
            self.hp = min(self.hp + base_heal, overheal_cap)
            msg = f"Restored HP! Can exceed max HP briefly."
        elif eff == "temp_buff_str":
            self.temp_buffs.append({"stat": "str", "amount": val, "turns": dur})
            msg = f"STR +{val} for {dur} turns!"
        elif eff == "temp_buff_vit":
            self.temp_buffs.append({"stat": "vit", "amount": val, "turns": dur})
            msg = f"VIT/DEF +{val} for {dur} turns!"
        elif eff == "temp_buff_all":
            self.temp_buffs.append({"stat": "all", "amount": val, "turns": dur})
            msg = f"All stats +{val} for {dur} turns!"
        elif eff == "buff_str":
            self.base_str += val
            msg = f"STR permanently increased by {val}!"
        elif eff == "buff_int":
            self.base_int += val
            msg = f"INT permanently increased by {val}!"
        elif eff == "cure":
            self.dot = 0
            self.dot_dmg = 0
            self.debuffs.clear()
            msg = "Cured all status effects!"
        elif eff == "revive":
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
        # Tick temp buffs
        still_active = []
        for b in self.temp_buffs:
            b = dict(b)
            b["turns"] -= 1
            if b["turns"] > 0:
                still_active.append(b)
            else:
                expired.append(f"{b['stat']}_buff")
        self.temp_buffs = still_active
        return expired

    # ── Gathering / Crafting skills ────────────────────────────────────────────
    def add_resource(self, name, qty=1):
        self.resources[name] = self.resources.get(name, 0) + qty

    def remove_resource(self, name, qty=1):
        current = self.resources.get(name, 0)
        if current < qty:
            raise ValueError(f"Not enough {name} (have {current}, need {qty})")
        self.resources[name] = current - qty
        if self.resources[name] == 0:
            del self.resources[name]

    def gain_skill_xp(self, skill_type, skill_name, xp):
        """Add XP to gathering or crafting skill. Returns (new_level, leveled_up)."""
        if skill_type == "gathering":
            skills = self.gathering_skills
        else:
            skills = self.crafting_skills
        if skill_name not in skills:
            return 1, False
        skill = skills[skill_name]
        skill["xp"] += xp
        total_xp = skill["xp"]
        level, accumulated = 1, 0
        while level < 20:
            needed = level * 100
            if total_xp >= accumulated + needed:
                accumulated += needed
                level += 1
            else:
                break
        old_level = skill["level"]
        skill["level"] = level
        return level, level > old_level

    # ── Display ────────────────────────────────────────────────────────────────
    def status_bar(self):
        hp_pct = self.hp / self.max_hp
        mp_pct = self.mp / self.max_mp
        hp_col = "\033[32m" if hp_pct > 0.5 else ("\033[33m" if hp_pct > 0.25 else "\033[31m")
        rst    = "\033[0m"
        return (f"{hp_col}HP: {self.hp}/{self.max_hp}{rst}  "
                f"\033[34mMP: {self.mp}/{self.max_mp}{rst}  "
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
        if self.profession:
            lines.append(f"  Profession: {self.profession}")
        weap = self.equipment["weapon"]
        arm  = self.equipment["armor"]
        lines.append(f"  Weapon: {weap.name if weap else 'None'}")
        lines.append(f"  Armor:  {arm.name  if arm  else 'None'}")
        if self.skills_learned:
            lines.append(f"  Skills: {', '.join(s['name'] for s in self.skills_learned)}")
        if self.buffs:
            lines.append(f"  Buffs:  {', '.join(f'{k}({v}t)' for k,v in self.buffs.items())}")
        if self.temp_buffs:
            lines.append("  Temp:   " + ', '.join(b['stat']+'+'+str(b['amount'])+'('+str(b['turns'])+'t)' for b in self.temp_buffs))
        if self.dot > 0:
            lines.append(f"  POISONED: {self.dot_dmg} dmg for {self.dot} more turns")
        return "\n".join(lines)
