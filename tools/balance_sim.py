"""Balance simulator: a scripted bot fights real combat code many times.

    python tools/balance_sim.py              # full report
    python tools/balance_sim.py --fights 200 # more samples

The bot plays sensibly but not perfectly: it heals when low, cures DoTs, braces for
telegraphed attacks, opens with its class buff against bosses and otherwise uses
its strongest affordable damage ability. Win rates are therefore a lower bound on
what a careful human achieves.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from combat import do_combat_turn, end_combat                      # noqa: E402
from enemies import BOSS_TEMPLATES, mitigate, spawn_enemy, spawn_final_boss  # noqa: E402
from items import Item, generate_armor, generate_weapon             # noqa: E402
from player import XP_TABLE, Player                                 # noqa: E402
from world import ZONE_LEVEL_REQ                                    # noqa: E402

MAX_LEVEL = len(XP_TABLE) - 1
DEFAULT_PROF = {"Warrior": "Knight", "Mage": "Sorcerer", "Rogue": "Assassin"}
OPENER = {"Warrior": "Battle Cry", "Mage": "Mana Shield", "Rogue": "Poison Blade"}


def build_player(cls, level, rarity="Rare", profession=None, potions=3, antidotes=1):
    p = Player("Sim", cls)
    level = min(level, MAX_LEVEL)
    while p.level < level:
        p.gain_xp(p.xp_next)
    if level >= 5:
        p.choose_profession(profession or DEFAULT_PROF[cls])
    # Spend skill points cheapest-first, like most players would.
    progressed = True
    while progressed:
        progressed = False
        for sk in sorted(p.available_skills(), key=lambda s: s["cost"]):
            if p.learn_skill(sk)[0]:
                progressed = True
        for sk in sorted(p.available_prof_skills(), key=lambda s: s["cost"]):
            if p.learn_prof_skill(sk)[0]:
                progressed = True
    for it in (generate_weapon(cls, level, rarity), generate_armor(level, rarity)):
        p.add_item(it)
        p.equip(it)
    for _ in range(potions):
        p.add_item(Item("Greater Health Potion", "consumable", "Common", 100,
                        effect="heal_pct", effect_value=50))
    for _ in range(antidotes):
        p.add_item(Item("Antidote", "consumable", "Common", 10, effect="cure"))
    p.hp, p.mp = p.max_hp, p.max_mp
    return p


def _consumable_index(p, effect):
    cons = [i for i in p.inventory if i.item_type == "consumable"]
    for idx, it in enumerate(cons):
        if it.effect == effect:
            return idx
    return None


def choose_action(p, e, turn):
    abilities = p.get_abilities()
    names = [a.name for a in abilities]

    def ability(name):
        i = names.index(name)
        return ("ability", i, None) if p.mp >= abilities[i].mp_cost else None

    if e.charging:
        for name in ("Shield Bash", "Smoke Bomb", "Evasion"):
            if name in names and ability(name):
                return ability(name)
        return ("defend", None, None)
    big_hit = mitigate(e.effective_atk * 1.7, p.defense)
    if p.hp < max(p.max_hp * 0.3, min(big_hit * 1.4, p.max_hp * 0.6)):
        idx = _consumable_index(p, "heal_pct")
        if idx is not None:
            return ("item", None, idx)
    dots = [d for d in p.debuffs.values() if d.get("dmg")]
    if dots and p.hp < p.max_hp * 0.6:
        idx = _consumable_index(p, "cure")
        if idx is not None:
            return ("item", None, idx)
    opener = OPENER[p.player_class]
    opener_up = e.dot > 0 if opener == "Poison Blade" else opener in p.buffs
    if e.is_boss and opener in names and not opener_up and ability(opener):
        return ability(opener)
    if (e.is_boss and "Evasion" in names and "Evasion" not in p.buffs
            and p.hp < p.max_hp * 0.7 and ability("Evasion")):
        return ability("Evasion")
    return best_damage(p, e, abilities)


def expected_damage(p, e, a):
    """Rough expected damage of using ability `a` (None = basic attack)."""
    if a is None:
        crit = min(1.0, 0.05 + p.dex / 200)
        return p.attack * (1 + 0.8 * crit)
    dmg = p.ability_power * a.mult * (1 + 0.5 * (0.37 if a.name == "Shadow Step" else 0.12))
    if a.name == "Death Mark":
        dmg *= 4 if p.profession == "Assassin" else 3
    if a.name == "Execute" and e.hp < e.max_hp * 0.3:
        dmg *= 2
    return dmg


def best_damage(p, e, abilities):
    best, best_ev = ("attack", None, None), expected_damage(p, e, None)
    for i, a in enumerate(abilities):
        if a.ability_type == "damage" and p.mp >= a.mp_cost:
            ev = expected_damage(p, e, a)
            if ev > best_ev:
                best, best_ev = ("ability", i, None), ev
    return best


def fight(p, e, max_turns=60):
    state = {"player": p, "combat_enemy": e, "combat_log": [], "combat_turn": 1}
    for turn in range(max_turns):
        action, ab, item = choose_action(p, e, turn)
        result = do_combat_turn(state, action, ab, item)
        if result in ("victory", "defeat", "revived"):
            end_combat(p)
            return result == "victory", turn + 1, p.hp / p.max_hp
        state["combat_log"].clear()
    end_combat(p)
    return False, max_turns, p.hp / p.max_hp  # timeout counts as a loss


def scenario(cls, level, make_enemy, n, **kw):
    wins, turns, hp_left = 0, [], []
    for i in range(n):
        random.seed(i * 7919 + level)
        p = build_player(cls, level, **kw)
        won, t, hp = fight(p, make_enemy())
        wins += won
        turns.append(t)
        if won:
            hp_left.append(hp)
    avg_hp = sum(hp_left) / len(hp_left) if hp_left else 0
    return wins / n, sum(turns) / n, avg_hp


def report(n):
    classes = ["Warrior", "Mage", "Rogue"]
    print(f"{'scenario':42} " + "  ".join(f"{c:>20}" for c in classes))
    print(f"{'':42} " + "  ".join(f"{'win%  turns  hp-left':>20}" for _ in classes))

    def row(label, level, make_enemy, **kw):
        cells = []
        for cls in classes:
            w, t, h = scenario(cls, level, make_enemy, n, **kw)
            cells.append(f"{w*100:4.0f}%  {t:5.1f}  {h*100:6.0f}%")
        print(f"{label:42} " + "  ".join(f"{c:>20}" for c in cells))

    for zone, lvl in ZONE_LEVEL_REQ.items():
        row(f"zone {zone} mob   @ lvl {lvl}", lvl, lambda z=zone, l=lvl: spawn_enemy(z, l), potions=0, antidotes=0)
    for b in BOSS_TEMPLATES:
        lvl = min(ZONE_LEVEL_REQ[b["zone"]] + 2, MAX_LEVEL)
        row(f"{b['name'][:22]:22} @ lvl {lvl}", lvl,
            lambda z=b["zone"], l=lvl: spawn_enemy(z, l, force_boss=True))
    row("Chaos Dragon Lord      @ lvl 19 Rare", 19, lambda: spawn_final_boss(19), potions=5)
    row("Chaos Dragon Lord      @ lvl 19 Epic", 19, lambda: spawn_final_boss(19), rarity="Epic", potions=5)
    row("Chaos Dragon Lord NG+1 @ lvl 19 Legend", 19, lambda: spawn_final_boss(19, ng=1), rarity="Legendary", potions=5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fights", type=int, default=60)
    report(ap.parse_args().fights)
