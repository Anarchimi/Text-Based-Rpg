import random
import time
from abilities import Ability

BOLD  = "\033[1m"
RED   = "\033[31m"
GRN   = "\033[32m"
YLW   = "\033[33m"
BLU   = "\033[34m"
MAG   = "\033[35m"
CYN   = "\033[36m"
RST   = "\033[0m"


def _pause(t=0.4):
    time.sleep(t)


def _divider(char="─", width=50):
    print(f"\033[90m{char * width}{RST}")


def _header(title):
    _divider("═")
    print(f"{BOLD}{CYN}  ⚔  {title}  ⚔{RST}")
    _divider("═")


def _show_combat_status(player, enemy):
    print(f"\n{BOLD}{player.name}{RST}  {player.status_bar()}")
    buffs = ", ".join(f"{k}({v}t)" for k, v in player.buffs.items())
    if buffs:
        print(f"  Buffs: {GRN}{buffs}{RST}")
    if player.dot > 0:
        print(f"  {RED}POISONED{RST}: {player.dot_dmg} dmg, {player.dot} turns left")
    print(f"\n{BOLD}{RED}{enemy.name}{RST}  {enemy.hp_bar()}")
    if enemy.stunned:
        print(f"  {YLW}[STUNNED]{RST}")
    if enemy.dot > 0:
        print(f"  {GRN}[POISONED]{RST}: {enemy.dot_dmg} dmg, {enemy.dot} turns left")
    print()


def _pick(prompt, options, labels=None):
    if labels is None:
        labels = [str(o) for o in options]
    for i, label in enumerate(labels, 1):
        print(f"  [{i}] {label}")
    while True:
        raw = input(f"\n{prompt} > ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw == "0":
            return None
        print("  Invalid choice.")


def run_combat(player, enemy, quest_log=None):
    _header(f"ENCOUNTER: {enemy.name.upper()}")
    print(f"  A {RED}{BOLD}{enemy.name}{RST} (Level ~{enemy.level}) appears!\n")
    _pause(0.5)

    turn = 0
    flee_chance_base = 30 + player.dex

    while player.hp > 0 and enemy.is_alive():
        turn += 1
        _divider()
        print(f"{YLW}  — Turn {turn} —{RST}")
        _show_combat_status(player, enemy)

        # ── Player's choice ────────────────────────────────────────────────────
        print(f"{BOLD}Actions:{RST}")
        actions = ["Attack", "Abilities", "Items", "Flee"]
        print(f"  [1] Attack   [2] Abilities   [3] Items   [4] Flee")

        while True:
            choice = input("\nAction > ").strip()
            if choice in ("1", "2", "3", "4"):
                break
            print("  Choose 1-4.")

        player_msg = ""

        if choice == "1":
            # Basic attack
            bonus = random.randint(-2, 4)
            crit  = random.random() < (0.05 + player.dex / 200)
            dmg   = int((player.attack + bonus) * (1.8 if crit else 1.0))
            actual = enemy.take_damage(dmg)
            crit_txt = f"  {YLW}★ CRITICAL HIT!{RST}\n" if crit else ""
            player_msg = f"{crit_txt}  {BOLD}{player.name}{RST} attacks for {RED}{actual}{RST} damage."

        elif choice == "2":
            abilities = player.get_abilities()
            if not abilities:
                print("  No abilities available yet.")
                continue
            print(f"\n{BOLD}Abilities:{RST}  (0=Cancel)")
            for i, a in enumerate(abilities, 1):
                mp_col = GRN if player.mp >= a.mp_cost else RED
                print(f"  [{i}] {a.name:<18} {mp_col}MP:{a.mp_cost}{RST}  — {a.description}")
            picked = _pick("Choose ability", abilities,
                           [f"{a.name} (MP:{a.mp_cost})" for a in abilities])
            if picked is None:
                continue
            if player.mp < picked.mp_cost:
                print(f"  {RED}Not enough MP!{RST}")
                _pause(0.6)
                continue

            player.mp -= picked.mp_cost
            stats = {"str": int(player.str), "dex": int(player.dex), "int": int(player.int)}
            effect = picked.calculate_effect(stats)

            if picked.ability_type == "damage":
                crit = random.random() < 0.12
                dmg  = int(effect * (1.5 if crit else 1.0))
                # Execute bonus
                if picked.name == "Execute" and enemy.hp < enemy.max_hp * 0.3:
                    dmg = int(dmg * 2)
                    print(f"  {RED}EXECUTE! 2x DAMAGE!{RST}")
                # Death Mark
                if picked.name == "Death Mark":
                    dmg = int(dmg * 3)
                    print(f"  {MAG}DEATH MARK! 3x DAMAGE!{RST}")
                actual = enemy.take_damage(dmg)
                crit_txt = f"  {YLW}★ CRITICAL!{RST}\n" if crit else ""
                player_msg = f"{crit_txt}  {MAG}{picked.name}{RST}: {RED}{actual}{RST} damage!"

            elif picked.ability_type == "heal":
                healed = min(effect, player.max_hp - player.hp)
                player.hp += healed
                player_msg = f"  {GRN}{picked.name}{RST}: Restored {GRN}{healed}{RST} HP!"

            elif picked.ability_type == "buff":
                turns = 3
                player.buffs[picked.name] = turns
                player_msg = f"  {GRN}{picked.name}{RST} activated for {turns} turns!"

            elif picked.ability_type == "dot":
                enemy.dot     = 3
                enemy.dot_dmg = effect
                player_msg = f"  {GRN}Poisoned {enemy.name}{RST} for {effect} dmg/turn (3 turns)!"

            elif picked.ability_type == "debuff":
                enemy.stunned = True
                player_msg = f"  {YLW}{enemy.name}{RST} is stunned next turn!"

        elif choice == "3":
            consumables = [i for i in player.inventory if i.item_type == "consumable"]
            if not consumables:
                print(f"  {RED}No consumables in inventory!{RST}")
                _pause(0.6)
                continue
            print(f"\n{BOLD}Consumables:{RST}  (0=Cancel)")
            for i, item in enumerate(consumables, 1):
                print(f"  [{i}] {item}")
            picked = _pick("Use item", consumables, [str(i) for i in consumables])
            if picked is None:
                continue
            ok, msg = player.use_consumable(picked)
            player_msg = f"  {GRN}{msg}{RST}"

        elif choice == "4":
            flee_roll = random.randint(1, 100)
            spd_bonus = int(player.speed * 1.5)
            if flee_roll < flee_chance_base + spd_bonus - enemy.atk:
                print(f"\n  {YLW}You fled from the battle!{RST}")
                _pause(0.5)
                return "fled", 0, []
            else:
                player_msg = f"  {RED}Couldn't flee! The enemy blocks your escape!{RST}"

        print(player_msg)
        _pause(0.4)

        if not enemy.is_alive():
            break

        # ── DoT tick on enemy ─────────────────────────────────────────────────
        dot_dmg = enemy.tick_dot()
        if dot_dmg:
            print(f"  {GRN}Poison{RST} deals {dot_dmg} to {enemy.name}. ({enemy.hp} HP left)")
            _pause(0.3)
            if not enemy.is_alive():
                break

        # ── Enemy turn ────────────────────────────────────────────────────────
        _pause(0.3)
        use_ability = random.random() < 0.3 and enemy.abilities
        if use_ability:
            ability_name, bonus = enemy.use_ability()
            if enemy.stunned:
                print(f"  {YLW}{enemy.name} is stunned and can't act!{RST}")
                enemy.stunned = False
            else:
                special_dmg = max(1, int(enemy.atk * 1.3 + bonus) - player.defense)
                player.hp   = max(0, player.hp - special_dmg)
                print(f"  {RED}{enemy.name}{RST} uses {MAG}{ability_name}{RST}! "
                      f"{RED}-{special_dmg} HP{RST}")
        else:
            if enemy.stunned:
                print(f"  {YLW}{enemy.name} is stunned and misses!{RST}")
                enemy.stunned = False
            else:
                dmg, stunned_skip = enemy.attack_player(player.defense)
                if stunned_skip:
                    print(f"  {YLW}{enemy.name} was stunned and missed!{RST}")
                else:
                    player.hp = max(0, player.hp - dmg)
                    print(f"  {RED}{enemy.name}{RST} attacks: {RED}-{dmg} HP{RST}")

        # ── Player DoT tick ───────────────────────────────────────────────────
        expired = player.tick_buffs()
        if player.dot > 0:
            print(f"  {RED}You are poisoned!{RST} -{player.dot_dmg} HP")
        for b in expired:
            print(f"  {YLW}{b} wore off.{RST}")

        _pause(0.3)

    # ── Resolution ────────────────────────────────────────────────────────────
    _divider("═")
    if enemy.is_alive():
        if player.has_revive():
            print(f"\n  {RED}You were defeated...{RST} but a Phoenix Feather saves you!")
            player.consume_revive()
            _pause(0.7)
            return "revived", 0, []
        print(f"\n  {RED}{BOLD}YOU WERE DEFEATED by {enemy.name}!{RST}")
        _pause(0.5)
        return "defeat", 0, []

    # Victory
    items, gold = enemy.loot_drop(player.level, int(player.lck))
    print(f"\n  {GRN}{BOLD}VICTORY!{RST} You defeated the {enemy.name}!")
    print(f"  Earned: {YLW}+{enemy.xp} XP{RST}  {YLW}+{gold}g{RST}")

    if items:
        print(f"\n  {BOLD}Loot dropped:{RST}")
        for item in items:
            print(f"    {item}")

    player.gold  += gold
    player.kills += 1

    # Quest progress
    if quest_log:
        newly_completed = quest_log.check_event("kill", enemy.name)
        for q in newly_completed:
            print(f"\n  {YLW}★ Quest completed: {q.title}!{RST}")

    for item in items:
        player.add_item(item)

    levels_gained = player.gain_xp(enemy.xp)
    for lvl in levels_gained:
        print(f"\n  {GRN}{BOLD}★ LEVEL UP! You are now Level {lvl}! ★{RST}")
        print(f"  Stats increased! +2 Skill Points")

    _pause(0.6)
    return "victory", enemy.xp, items
