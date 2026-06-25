#!/usr/bin/env python3
"""
Chronicles of the Shattered Realm
A text-based RPG with random quests, loot, leveling, abilities, and turn-based combat.
"""
import random
import time
import sys

from player  import Player
from enemies import spawn_enemy
from combat  import run_combat
from quests  import QuestLog
from items   import generate_shop_stock
from world   import explore_step, travel_to_zone, ZONES, ZONE_LEVEL_REQ, get_zone
from ui      import (clear, header, divider, title_screen, press_enter,
                     menu, show_inventory, show_skills, show_quests, show_abilities,
                     BOLD, RED, GRN, YLW, BLU, MAG, CYN, DIM, RST)

# ── Constants ──────────────────────────────────────────────────────────────────
SHOP_REFRESH_STEPS = 15
REST_HP_PCT        = 0.6
REST_COST_PER_10HP = 3


# ── Helpers ────────────────────────────────────────────────────────────────────
def _input(prompt):
    return input(f"{prompt}").strip()


def _yn(prompt):
    return _input(f"{prompt} [y/n] ").lower().startswith("y")


def _wait(t=0.5):
    time.sleep(t)


def _announce(msg, color=GRN):
    print(f"\n  {color}{msg}{RST}")
    _wait(0.5)


# ── Character Creation ─────────────────────────────────────────────────────────
def create_character():
    clear()
    header("CREATE YOUR HERO")
    print(f"""
  {BOLD}In the Shattered Realm, darkness grows.
  Ancient evils stir. Villages burn.
  Only a true hero can restore the balance.{RST}
""")
    name = ""
    while not name:
        name = _input(f"  Enter your hero's name: ").strip()
        if not name:
            print("  Name cannot be empty.")

    print(f"\n  {BOLD}Choose your class:{RST}")
    class_info = {
        "Warrior": f"{RED}High HP & STR{RST}. Melee combat specialist. Tough and relentless.",
        "Mage":    f"{BLU}High INT & MP{RST}. Master of destructive spells. Fragile but devastating.",
        "Rogue":   f"{MAG}High DEX & LCK{RST}. Swift assassin. Crits, poisons, and stealth.",
    }
    classes = list(class_info.keys())
    for i, (cls, desc) in enumerate(class_info.items(), 1):
        print(f"\n  [{i}] {BOLD}{cls}{RST}\n      {desc}")

    idx = menu("Select class", classes, prompt="Class > ")
    player_class = classes[idx]

    clear()
    header("HERO CREATED")
    print(f"\n  {GRN}Welcome, {BOLD}{name}{RST}{GRN} the {player_class}!{RST}")
    print(f"\n  Your adventure begins in the humble village of Ashvale.")
    print(f"  Danger lurks beyond every shadow...")
    press_enter()
    return Player(name, player_class)


# ── Shop ──────────────────────────────────────────────────────────────────────
def visit_shop(player, level):
    stock = generate_shop_stock(level)
    while True:
        clear()
        header("MERCHANT'S SHOP")
        print(f"\n  Your gold: {YLW}{player.gold}g{RST}\n")
        for i, item in enumerate(stock, 1):
            affordable = GRN if player.gold >= item.value else RED
            print(f"  [{i}] {item}  — {affordable}{item.value}g{RST}")
        divider()
        print(f"  [0] Leave shop")
        raw = _input("\n  Buy item (number) > ")
        if raw == "0" or raw.lower() == "q":
            break
        if raw.isdigit() and 1 <= int(raw) <= len(stock):
            item = stock[int(raw) - 1]
            if player.gold < item.value:
                _announce("Not enough gold!", RED)
            else:
                player.gold -= item.value
                player.add_item(item)
                stock.remove(item)
                _announce(f"Purchased {item.name}!")
        else:
            print("  Invalid choice.")


# ── Inventory Management ───────────────────────────────────────────────────────
def manage_inventory(player):
    while True:
        choice = show_inventory(player)
        if choice == "0":
            break
        elif choice == "e":
            equippable = [i for i in player.inventory if i.item_type in ("weapon", "armor")]
            if not equippable:
                _announce("Nothing to equip.", RED)
                continue
            clear()
            header("EQUIP ITEM")
            for i, item in enumerate(equippable, 1):
                print(f"  [{i}] {item}")
            raw = _input("\nEquip which item (0=cancel)? ")
            if raw.isdigit() and 1 <= int(raw) <= len(equippable):
                ok, msg = player.equip(equippable[int(raw) - 1])
                _announce(msg, GRN if ok else RED)
        elif choice == "u":
            consumables = [i for i in player.inventory if i.item_type == "consumable"]
            if not consumables:
                _announce("No consumables.", RED)
                continue
            clear()
            header("USE ITEM")
            for i, item in enumerate(consumables, 1):
                print(f"  [{i}] {item}")
            raw = _input("\nUse which item (0=cancel)? ")
            if raw.isdigit() and 1 <= int(raw) <= len(consumables):
                ok, msg = player.use_consumable(consumables[int(raw) - 1])
                _announce(msg, GRN if ok else RED)
        elif choice == "s":
            if not player.inventory:
                _announce("Nothing to sell.", RED)
                continue
            clear()
            header("SELL ITEM")
            for i, item in enumerate(player.inventory, 1):
                sell_price = item.value // 2
                print(f"  [{i}] {item}  → Sell for {sell_price}g")
            raw = _input("\nSell which item (0=cancel)? ")
            if raw.isdigit() and 1 <= int(raw) <= len(player.inventory):
                item = player.inventory[int(raw) - 1]
                sell_price = item.value // 2
                player.inventory.remove(item)
                player.gold += sell_price
                _announce(f"Sold {item.name} for {sell_price}g!")


# ── Quest Board ────────────────────────────────────────────────────────────────
def visit_quest_board(player, quest_log, zone):
    while True:
        clear()
        header("QUEST BOARD")
        print(f"\n  Active quests: {len(quest_log.active_quests())}/{quest_log.max_active}")
        available = quest_log.refresh_board(zone=zone, level=player.level, count=4)
        print(f"\n  {BOLD}Available Quests:{RST}")
        for i, q in enumerate(available, 1):
            print(f"\n  [{i}] {q.display()}")
        divider()
        print("  [A#] Accept quest (e.g. A1)   [V] View active   [0] Back")
        raw = _input("\n> ").strip().lower()
        if raw == "0":
            break
        elif raw == "v":
            show_quests(player, quest_log)
        elif raw.startswith("a") and raw[1:].isdigit():
            idx = int(raw[1:]) - 1
            if 0 <= idx < len(available):
                ok, msg = quest_log.accept_quest(available[idx])
                _announce(msg, GRN if ok else RED)
            else:
                _announce("Invalid quest number.", RED)


# ── Rest ───────────────────────────────────────────────────────────────────────
def visit_inn(player):
    clear()
    header("THE RUSTY FLAGON INN")
    hp_missing = player.max_hp - player.hp
    mp_missing = player.max_mp - player.mp
    cost = (hp_missing // 10) * REST_COST_PER_10HP + 5

    print(f"\n  \"Welcome, traveler. Rest your weary bones.\"\n")
    print(f"  Current HP: {player.hp}/{player.max_hp}  ({hp_missing} missing)")
    print(f"  Current MP: {player.mp}/{player.max_mp}  ({mp_missing} missing)")
    print(f"\n  Full rest cost: {YLW}{cost}g{RST}   Your gold: {YLW}{player.gold}g{RST}")
    divider()
    print("  [1] Rest (full restore)   [2] Nap (50% HP/MP, free)   [0] Leave")
    choice = _input("\n> ").strip()

    if choice == "1":
        if player.gold < cost:
            _announce("Not enough gold!", RED)
        else:
            player.gold -= cost
            player.hp    = player.max_hp
            player.mp    = player.max_mp
            player.dot   = 0
            _announce("You rest well. HP and MP fully restored!")
    elif choice == "2":
        player.hp  = min(player.max_hp, player.hp + player.max_hp // 2)
        player.mp  = min(player.max_mp, player.mp + player.max_mp // 2)
        player.dot = 0
        _announce("You take a short nap. HP/MP partially restored.")
    press_enter()


# ── Zone Travel ────────────────────────────────────────────────────────────────
def zone_select(player, current_zone):
    clear()
    header("WORLD MAP")
    print()
    for zid, zdata in ZONES.items():
        req     = ZONE_LEVEL_REQ[zid]
        unlocked = player.level >= req
        marker  = GRN + "★" if zid == current_zone else (GRN + "✓" if unlocked else RED + "✗")
        lock    = "" if unlocked else f"  {DIM}[Req Level {req}]{RST}"
        current_mark = f" {CYN}← YOU ARE HERE{RST}" if zid == current_zone else ""
        print(f"  {marker}{RST} [{zid}] {BOLD}{zdata['name']}{RST}{lock}{current_mark}")
        print(f"       {DIM}{zdata['desc']}{RST}")
        print()
    divider()
    raw = _input("Travel to zone (number) or 0 to cancel > ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(ZONES):
        target = int(raw)
        ok, msg = travel_to_zone(player, target)
        _announce(msg, GRN if ok else RED)
        if ok:
            return target
    return current_zone


# ── Handle Explore Events ─────────────────────────────────────────────────────
def handle_explore_events(player, events, quest_log, zone):
    for ev_type, val, msg in events:
        print(f"\n  {msg}")
        _wait(0.4)

        if ev_type == "gold":
            player.gold += val
            print(f"  {YLW}+{val} gold!{RST}")

        elif ev_type == "heal_hp":
            healed = min(val, player.max_hp - player.hp)
            player.hp += healed
            print(f"  {GRN}+{healed} HP restored!{RST}")

        elif ev_type == "heal_mp":
            restored = min(val, player.max_mp - player.mp)
            player.mp += restored
            print(f"  {BLU}+{restored} MP restored!{RST}")

        elif ev_type == "xp":
            levels = player.gain_xp(val)
            print(f"  {YLW}+{val} XP!{RST}")
            for lvl in levels:
                print(f"\n  {GRN}{BOLD}★ LEVEL UP! Now Level {lvl}! ★{RST}")
                print(f"  +2 Skill Points awarded!")

        elif ev_type == "rest":
            hp_gain = player.max_hp // 10
            player.hp = min(player.max_hp, player.hp + hp_gain)
            print(f"  {GRN}+{hp_gain} HP from resting.{RST}")

        elif ev_type == "trap":
            player.hp = max(1, player.hp - val)
            print(f"  {RED}-{val} HP!{RST}")
            if player.hp <= 1:
                print(f"  {RED}You barely survive...{RST}")

        elif ev_type == "encounter":
            force_boss = (msg.startswith("💀"))
            _wait(0.3)
            enemy = spawn_enemy(zone=zone, level=player.level, force_boss=force_boss)
            result, xp_gain, loot = run_combat(player, enemy, quest_log=quest_log)

            if result == "defeat":
                return "game_over"

            # Quest: explore event
            quest_log.check_event("explore", get_zone(zone)["name"])

    return "ok"


# ── Village Hub ────────────────────────────────────────────────────────────────
def village_hub(player, quest_log, zone):
    while True:
        clear()
        header(f"ASHVALE VILLAGE  — {get_zone(zone)['name']}")
        print(f"\n  {player.status_bar()}")
        print(f"\n  What would you like to do?\n")
        options = [
            "⚔  Explore (venture into the wilds)",
            "📋 Quest Board",
            "🏪 Merchant's Shop",
            "🏨 Inn (rest & recover)",
            "🗺  World Map (change zone)",
            "📦 Inventory",
            "🌟 Skill Tree",
            "✨ Abilities",
            "📊 Character Stats",
            "🚪 Quit Game",
        ]
        for i, opt in enumerate(options, 1):
            print(f"  [{i}] {opt}")
        divider()
        raw = _input("\n> ").strip()

        if not raw.isdigit() or not (1 <= int(raw) <= len(options)):
            continue
        choice = int(raw)

        if choice == 1:
            # Explore
            clear()
            header(f"EXPLORING: {get_zone(zone)['name'].upper()}")
            print(f"\n  {player.status_bar()}\n")
            events = explore_step(player, zone)
            result = handle_explore_events(player, events, quest_log, zone)
            if result == "game_over":
                return "game_over"
            # Check for quest turn-ins
            newly_done = [q for q in quest_log.active_quests() if q.is_complete()]
            for q in newly_done:
                print(f"\n  {YLW}★ Quest '{q.title}' is complete! Return to collect reward!{RST}")
            divider()
            # Auto turn-in completed quests
            for q in list(quest_log.active_quests()):
                if q.is_complete():
                    quest_log.finish_quest(q)
                    player.gold  += q.reward_gold
                    player.gain_xp(q.reward_xp)
                    player.quests_completed += 1
                    print(f"  {GRN}Quest reward: +{q.reward_gold}g, +{q.reward_xp} XP{RST}")
            press_enter("Press ENTER to return to village...")

        elif choice == 2:
            visit_quest_board(player, quest_log, zone)

        elif choice == 3:
            visit_shop(player, player.level)

        elif choice == 4:
            visit_inn(player)

        elif choice == 5:
            zone = zone_select(player, zone)

        elif choice == 6:
            manage_inventory(player)

        elif choice == 7:
            show_skills(player)

        elif choice == 8:
            show_abilities(player)

        elif choice == 9:
            clear()
            header("CHARACTER STATS")
            print()
            print(player.full_stats())
            divider()
            press_enter()

        elif choice == 10:
            if _yn("  Are you sure you want to quit?"):
                return "quit"

    return "quit"


# ── Game Over / Victory ────────────────────────────────────────────────────────
def game_over_screen(player):
    clear()
    header("GAME OVER")
    print(f"""
  {RED}{BOLD}You have fallen in battle...{RST}

  {DIM}The Shattered Realm grows darker without its hero.{RST}

  {BOLD}Final Stats:{RST}
    Name:   {player.name} the {player.player_class}
    Level:  {player.level}
    Kills:  {player.kills}
    Quests: {player.quests_completed}
    Gold:   {player.gold}g
""")
    divider()
    press_enter("Press ENTER to exit...")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    title_screen()
    print(f"\n  {BOLD}[1]{RST} New Game    {BOLD}[2]{RST} Quit\n")
    choice = _input("> ").strip()
    if choice != "1":
        print(f"\n  {DIM}Farewell, traveler.{RST}\n")
        sys.exit(0)

    player     = create_character()
    quest_log  = QuestLog()
    current_zone = 1

    # Give starter gear
    from items import generate_weapon, generate_armor, generate_consumable
    starter_weapon = generate_weapon(player_class=player.player_class, level=1, rarity="Common")
    starter_armor  = generate_armor(level=1, rarity="Common")
    starter_potion = generate_consumable()
    player.add_item(starter_weapon)
    player.add_item(starter_armor)
    player.add_item(starter_potion)
    player.equip(starter_weapon)
    player.equip(starter_armor)

    # Seed quest board
    for _ in range(3):
        from quests import generate_quest
        quest_log.add_quest(generate_quest(zone=1, level=1))

    result = village_hub(player, quest_log, current_zone)

    if result == "game_over":
        game_over_screen(player)
    else:
        clear()
        header("FAREWELL")
        print(f"\n  {GRN}Thanks for playing, {player.name}!{RST}")
        print(f"\n  Final Level: {player.level}   Kills: {player.kills}   "
              f"Quests: {player.quests_completed}   Gold: {player.gold}g\n")


if __name__ == "__main__":
    main()
