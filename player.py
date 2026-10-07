import random
from abilities import get_available_abilities

XP_TABLE = [0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200,
            4000, 5000, 6200, 7600, 9200, 11000, 13200, 15800, 18800, 22200]

STATS_VERSION = 2     # bump with a migration in Player.__setstate__ when stat rules change


def skill_stats(skill):
    """{stat: amount} a skill grants. Old saves stored a single "stat"/"bonus" pair."""
    return skill.get("stats") or {skill["stat"]: skill["bonus"]}


SPELL_INT_MULT = 1.0  # Mage spell power = INT × this + weapon ATK

CLASS_BASES = {
    "Warrior": {"hp": 120, "mp": 40,  "str": 14, "dex": 8,  "int": 6,  "vit": 12, "lck": 5},
    "Mage":    {"hp": 70,  "mp": 100, "str": 6,  "dex": 8,  "int": 16, "vit": 6,  "lck": 7},
    "Rogue":   {"hp": 90,  "mp": 60,  "str": 9,  "dex": 16, "int": 8,  "vit": 8,  "lck": 10},
}

CLASS_GROWTH = {
    "Warrior": {"hp": 16, "mp": 4,  "str": 2.5, "dex": 1,   "int": 0.5, "vit": 2,   "lck": 0.3},
    "Mage":    {"hp": 11, "mp": 14, "str": 0.5, "dex": 1,   "int": 3,   "vit": 0.8, "lck": 0.5},
    "Rogue":   {"hp": 14, "mp": 10, "str": 1.2, "dex": 2.8, "int": 1,   "vit": 1,   "lck": 0.8},
}

SKILL_TREE = {
    "Warrior": [
        {"name": "Iron Skin",        "desc": "+15 Max HP",           "stats": {"max_hp": 15},  "cost": 1},
        {"name": "Power Strike",     "desc": "+3 STR",               "stats": {"str": 3},   "cost": 1},
        {"name": "Fortitude",        "desc": "+8 Max HP, +2 VIT",    "stats": {"max_hp": 8, "vit": 2},   "cost": 2},
        {"name": "Veteran's Edge",   "desc": "+5 STR, +3 VIT",       "stats": {"str": 5, "vit": 3},   "cost": 2},
        {"name": "Titan's Grip",     "desc": "+10 STR",              "stats": {"str": 10},  "cost": 3},
        {"name": "Indomitable",      "desc": "+50 Max HP",           "stats": {"max_hp": 50},  "cost": 3},
    ],
    "Mage": [
        {"name": "Mana Tap",         "desc": "+20 Max MP",           "stats": {"max_mp": 20},  "cost": 1},
        {"name": "Arcane Mind",      "desc": "+3 INT",               "stats": {"int": 3},   "cost": 1},
        {"name": "Spell Mastery",    "desc": "+8 INT",               "stats": {"int": 8},   "cost": 2},
        {"name": "Ley Lines",        "desc": "+40 Max MP",           "stats": {"max_mp": 40},  "cost": 2},
        {"name": "Archmage Focus",   "desc": "+15 INT",              "stats": {"int": 15},  "cost": 3},
        {"name": "Infinite Reservoir","desc": "+80 Max MP",          "stats": {"max_mp": 80},  "cost": 3},
    ],
    "Rogue": [
        {"name": "Keen Eye",         "desc": "+3 DEX, +2 LCK",       "stats": {"dex": 3, "lck": 2},   "cost": 1},
        {"name": "Shadow Veil",      "desc": "+5 DEX",               "stats": {"dex": 5},   "cost": 1},
        {"name": "Treasure Hunter",  "desc": "+5 LCK",               "stats": {"lck": 5},   "cost": 2},
        {"name": "Assassin's Mark",  "desc": "+8 DEX",               "stats": {"dex": 8},   "cost": 2},
        {"name": "Ghost Walk",       "desc": "+10 DEX, +5 LCK",      "stats": {"dex": 10, "lck": 5},  "cost": 3},
        {"name": "Master of Shadows","desc": "+20 DEX",              "stats": {"dex": 20},  "cost": 3},
    ],
}

PROFESSIONS = {
    "Warrior": {
        "Knight": {
            "passive": "+25% DEF. Your presence is unbreakable.",
            "stat_bonus": {"max_hp": 40, "base_vit": 4},
            "skills": [
                {"name": "Iron Wall",    "desc": "+8 VIT",             "stats": {"vit": 8},  "cost": 1},
                {"name": "Stalwart",     "desc": "+30 Max HP, +5 VIT", "stats": {"max_hp": 30, "vit": 5}, "cost": 2},
                {"name": "Unbreakable",  "desc": "+80 Max HP",         "stats": {"max_hp": 80}, "cost": 3},
            ],
        },
        "Berserker": {
            "passive": "+50% ATK when HP below 30%.",
            "stat_bonus": {"base_str": 6, "max_hp": -20},
            "skills": [
                {"name": "Bloodlust",    "desc": "+8 STR",  "stats": {"str": 8},  "cost": 1},
                {"name": "Frenzy",       "desc": "+15 STR", "stats": {"str": 15}, "cost": 2},
                {"name": "War Incarnate","desc": "+25 STR", "stats": {"str": 25}, "cost": 3},
            ],
        },
        "Champion": {
            "passive": "+10% ATK and DEF at all times.",
            "stat_bonus": {"base_str": 3, "base_vit": 3, "max_hp": 20},
            "skills": [
                {"name": "Valor",        "desc": "+6 STR, +4 VIT", "stats": {"str": 6, "vit": 4},  "cost": 1},
                {"name": "Victor's Edge","desc": "+12 STR",         "stats": {"str": 12}, "cost": 2},
                {"name": "Grand Legacy", "desc": "+20 STR, +10 VIT","stats": {"str": 20, "vit": 10}, "cost": 3},
            ],
        },
    },
    "Mage": {
        "Sorcerer": {
            "passive": "+30% spell damage on all damage abilities.",
            "stat_bonus": {"base_int": 8, "max_mp": 30},
            "skills": [
                {"name": "Overcharge",    "desc": "+8 INT",          "stats": {"int": 8},  "cost": 1},
                {"name": "Arcane Surge",  "desc": "+15 INT, +20 MP", "stats": {"int": 15, "max_mp": 20}, "cost": 2},
                {"name": "Transcendence", "desc": "+25 INT",          "stats": {"int": 25}, "cost": 3},
            ],
        },
        "Elementalist": {
            "passive": "30% chance to Burn (DoT) enemies on any ability hit.",
            "stat_bonus": {"base_int": 4, "max_mp": 50},
            "skills": [
                {"name": "Attunement",     "desc": "+6 INT, +20 MP",  "stats": {"int": 6, "max_mp": 20},  "cost": 1},
                {"name": "Volatile Magic", "desc": "+12 INT, +30 MP", "stats": {"int": 12, "max_mp": 30}, "cost": 2},
                {"name": "Avatar",         "desc": "+20 INT, +50 MP", "stats": {"int": 20, "max_mp": 50}, "cost": 3},
            ],
        },
        "Necromancer": {
            "passive": "+20% damage vs enemies below 50% HP.",
            "stat_bonus": {"base_int": 5, "max_hp": 15, "max_mp": 20},
            "skills": [
                {"name": "Soul Tap",    "desc": "+6 INT, +25 MP",  "stats": {"int": 6, "max_mp": 25},  "cost": 1},
                {"name": "Life Drain",  "desc": "+12 INT, +30 HP", "stats": {"int": 12, "max_hp": 30}, "cost": 2},
                {"name": "Lich Form",   "desc": "+20 INT, +60 HP", "stats": {"int": 20, "max_hp": 60}, "cost": 3},
            ],
        },
    },
    "Rogue": {
        "Assassin": {
            "passive": "Death Mark deals 4× damage (5× on enemies below 40% HP).",
            "stat_bonus": {"base_dex": 5, "base_lck": 3},
            "skills": [
                {"name": "Blade Mastery", "desc": "+8 DEX",           "stats": {"dex": 8},  "cost": 1},
                {"name": "Predator",      "desc": "+12 DEX, +5 LCK",  "stats": {"dex": 12, "lck": 5}, "cost": 2},
                {"name": "Shadow Lord",   "desc": "+20 DEX, +10 LCK", "stats": {"dex": 20, "lck": 10}, "cost": 3},
            ],
        },
        "Ranger": {
            "passive": "Flee always succeeds. +20% ATK on first strike each combat.",
            "stat_bonus": {"base_dex": 6, "base_lck": 4},
            "skills": [
                {"name": "Eagle Eye",   "desc": "+6 DEX, +5 LCK",  "stats": {"dex": 6, "lck": 5},  "cost": 1},
                {"name": "Hunter",      "desc": "+12 DEX, +5 LCK", "stats": {"dex": 12, "lck": 5}, "cost": 2},
                {"name": "Wind Runner", "desc": "+20 DEX, +10 LCK","stats": {"dex": 20, "lck": 10}, "cost": 3},
            ],
        },
        "Trickster": {
            "passive": "Poison lasts +2 extra turns and deals +50% DoT damage.",
            "stat_bonus": {"base_dex": 3, "base_int": 4, "base_lck": 3},
            "skills": [
                {"name": "Venom Craft",   "desc": "+6 DEX, +4 INT",  "stats": {"dex": 6, "int": 4},  "cost": 1},
                {"name": "Toxic Mastery", "desc": "+10 DEX, +6 INT", "stats": {"dex": 10, "int": 6}, "cost": 2},
                {"name": "Poison Adept",  "desc": "+15 DEX, +10 INT","stats": {"dex": 15, "int": 10}, "cost": 3},
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

        self._stats_version = STATS_VERSION
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
    def skill_bonus(self, stat):
        """Sum of `stat` granted by every learned skill (class tree + profession)."""
        return sum(skill_stats(sk).get(stat, 0)
                   for sk in self.skills_learned + self.prof_skills_learned)

    def _temp(self, stat):
        return sum(b["amount"] for b in self.temp_buffs if b["stat"] in (stat, "all"))

    @property
    def str(self):
        eq_bonus = self.equipment["weapon"].stats.get("str", 0) if self.equipment["weapon"] else 0
        return self.base_str + self.skill_bonus("str") + eq_bonus + self._temp("str")

    @property
    def dex(self):
        return self.base_dex + self.skill_bonus("dex")

    @property
    def int(self):
        return self.base_int + self.skill_bonus("int")

    @property
    def vit(self):
        return self.base_vit + self.skill_bonus("vit") + self._temp("vit")

    @property
    def lck(self):
        return self.base_lck + self.skill_bonus("lck")

    @property
    def attack(self):
        base = self.str + self.dex // 3
        weap = self.equipment["weapon"].stats.get("atk", 0) if self.equipment["weapon"] else 0
        berserk = 2 if "Berserk" in self.buffs else 1
        battle_cry = 1.2 if "Battle Cry" in self.buffs else 1
        weakened = 0.75 if "Weakened" in self.debuffs else 1
        champion_bonus = int((base + weap) * 0.10) if self.profession == "Champion" else 0
        return int((base + weap + champion_bonus) * berserk * battle_cry * weakened)

    @property
    def spell_power(self):
        weap = self.equipment["weapon"].stats.get("atk", 0) if self.equipment["weapon"] else 0
        weakened = 0.75 if "Weakened" in self.debuffs else 1
        return int((self.int * SPELL_INT_MULT + weap) * weakened)

    @property
    def ability_power(self):
        """What damage abilities scale with: spell power for Mages, ATK otherwise."""
        return self.spell_power if self.player_class == "Mage" else self.attack

    @property
    def defense(self):
        base = int(self.vit * 0.8)
        arm  = self.equipment["armor"].stats.get("def", 0) if self.equipment["armor"] else 0
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
        return self._learn(skill, self.skills_learned)

    def _learn(self, skill, learned):
        """Stats are summed from learned skills on access; only max HP/MP are stored."""
        if self.skill_points < skill["cost"]:
            return False, "Not enough skill points."
        self.skill_points -= skill["cost"]
        learned.append(skill)
        stats = skill_stats(skill)
        self._grow_pools(stats.get("max_hp", 0), stats.get("max_mp", 0))
        return True, f"Learned {skill['name']}!"

    def _grow_pools(self, hp, mp):
        if hp:
            self.max_hp += hp
            self.hp = max(1, min(self.hp + hp, self.max_hp))
        if mp:
            self.max_mp += mp
            self.mp = max(0, min(self.mp + mp, self.max_mp))

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
        return self._learn(skill, self.prof_skills_learned)

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
            self._grow_pools(-old.stats.get("hp", 0), 0)
        self.equipment[item.item_type] = item
        self._grow_pools(item.stats.get("hp", 0), 0)
        return True, f"Equipped {item.name}."

    def upgrade_equipped(self, slot):
        """Spend gold + bars to raise the equipped item's upgrade level by one."""
        from items import upgrade_cost
        item = self.equipment.get(slot)
        if not item:
            return False, "Nothing equipped there."
        cost = upgrade_cost(item)
        if cost is None:
            return False, f"{item.name} is already fully upgraded."
        gold, bar, qty = cost
        if self.gold < gold:
            return False, f"Upgrading costs {gold}g (you have {self.gold}g)."
        if self.resources.get(bar, 0) < qty:
            return False, f"Upgrading needs {qty}× {bar} (you have {self.resources.get(bar, 0)}). Smith them at the Craft menu."
        self.gold -= gold
        self.remove_resource(bar, qty)
        old_hp = item.stats.get("hp", 0)
        item.apply_upgrade()
        self._grow_pools(item.stats.get("hp", 0) - old_hp, 0)
        gains = ", ".join(f"{k.upper()} {v}" for k, v in item.stats.items())
        return True, f"The smith reforges it: {item.name} ({gains})."

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

    # ── Debuffs (applied by enemies; see combat.py) ─────────────────────────────
    # self.debuffs: {name: {"turns": n, "dmg": per-turn damage (DoTs only)}}
    DOT_DEBUFFS = ("Poisoned", "Burning", "Bleeding")

    def add_debuff(self, name, turns, dmg=0):
        cur = self.debuffs.get(name)
        if cur:  # re-applying refreshes duration and keeps the stronger tick
            cur["turns"] = max(cur["turns"], turns)
            cur["dmg"] = max(cur.get("dmg", 0), dmg)
        else:
            self.debuffs[name] = {"turns": turns, "dmg": dmg}

    def tick_debuffs(self):
        """Apply DoTs and count down. Returns ([(name, dmg)], [expired names])."""
        ticks, expired = [], []
        for name in list(self.debuffs):
            if name == "Stunned":  # consumed when the player's next turn is skipped
                continue
            d = self.debuffs[name]
            if name in self.DOT_DEBUFFS and d.get("dmg"):
                self.hp = max(0, self.hp - d["dmg"])
                ticks.append((name, d["dmg"]))
            d["turns"] -= 1
            if d["turns"] <= 0:
                del self.debuffs[name]
                expired.append(name)
        return ticks, expired

    def __setstate__(self, d):
        # debuffs used to be an unused {} on old saves; make sure it exists.
        d.setdefault("debuffs", {})
        self.__dict__.update(d)
        if d.get("_stats_version", 1) < STATS_VERSION:
            self._migrate_stats_v2()

    def _migrate_stats_v2(self):
        """Saves before v2: class-tree STR/DEX/INT/VIT/LCK skills were added to base_* AND
        summed again on access (double counted); second stats in descriptions like
        "+8 Max HP, +2 VIT" were never applied; armor HP was ignored."""
        for sk in self.skills_learned:
            if sk.get("stat") in ("str", "dex", "int", "vit", "lck"):
                attr = "base_" + sk["stat"]
                setattr(self, attr, getattr(self, attr) - sk["bonus"])
        current = {sk["name"]: sk for tree in SKILL_TREE.values() for sk in tree}
        for profs in PROFESSIONS.values():
            for prof in profs.values():
                current.update({sk["name"]: sk for sk in prof["skills"]})
        for learned in (self.skills_learned, self.prof_skills_learned):
            for i, sk in enumerate(learned):
                new = current.get(sk["name"])
                if new is None or "stats" in sk:
                    continue
                already = sk["stat"]  # the only stat old code applied to max HP/MP
                stats = skill_stats(new)
                self._grow_pools(stats.get("max_hp", 0) if already != "max_hp" else 0,
                                 stats.get("max_mp", 0) if already != "max_mp" else 0)
                learned[i] = new
        armor = self.equipment.get("armor")
        if armor:
            self._grow_pools(armor.stats.get("hp", 0), 0)
        self._stats_version = STATS_VERSION

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
