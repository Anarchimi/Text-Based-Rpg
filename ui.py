"""Terminal UI helpers."""
import os
import time

BOLD = "\033[1m"
RED  = "\033[31m"
GRN  = "\033[32m"
YLW  = "\033[33m"
BLU  = "\033[34m"
MAG  = "\033[35m"
CYN  = "\033[36m"
DIM  = "\033[90m"
RST  = "\033[0m"


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def divider(char="─", width=52, color=DIM):
    print(f"{color}{char * width}{RST}")


def header(text, color=CYN):
    divider("═", color=color)
    padding = max(0, (52 - len(text) - 4) // 2)
    print(f"{color}{BOLD}{' ' * padding}⚔  {text}  ⚔{RST}")
    divider("═", color=color)


def title_screen():
    clear()
    lines = [
        "",
        "  ██████╗ ██████╗  ██████╗     ██████╗  ██████╗ ",
        "  ██╔══██╗██╔══██╗██╔════╝     ██╔══██╗██╔════╝ ",
        "  ██████╔╝██████╔╝██║  ███╗    ██████╔╝██║  ███╗",
        "  ██╔══██╗██╔═══╝ ██║   ██║    ██╔══██╗██║   ██║",
        "  ██║  ██║██║     ╚██████╔╝    ██║  ██║╚██████╔╝",
        "  ╚═╝  ╚═╝╚═╝      ╚═════╝     ╚═╝  ╚═╝ ╚═════╝ ",
        "",
        f"  {YLW}Chronicles of the Shattered Realm{RST}",
        "",
        f"  {DIM}A text-based RPG adventure{RST}",
        "",
    ]
    for line in lines:
        print(f"{CYN}{line}{RST}")
    divider("═")


def press_enter(msg="Press ENTER to continue..."):
    input(f"\n{DIM}  {msg}{RST}")


def print_boxed(lines, color=DIM):
    width = max(len(l) for l in lines) + 4
    print(f"{color}┌{'─' * width}┐{RST}")
    for line in lines:
        pad = width - len(line) - 2
        print(f"{color}│ {RST}{line}{' ' * pad} {color}│{RST}")
    print(f"{color}└{'─' * width}┘{RST}")


def menu(title_text, options, prompt="> ", color=CYN):
    """Display a numbered menu and return the chosen index (0-based)."""
    divider()
    print(f"{BOLD}{color}{title_text}{RST}")
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    while True:
        raw = input(f"\n{prompt}").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        if raw.lower() in ("q", "quit", "0"):
            return -1
        print("  Invalid choice.")


def show_inventory(player):
    clear()
    header("INVENTORY")
    weap = player.equipment.get("weapon")
    arm  = player.equipment.get("armor")
    print(f"\n  {BOLD}Equipped:{RST}")
    print(f"    Weapon: {weap if weap else DIM+'None'+RST}")
    print(f"    Armor:  {arm  if arm  else DIM+'None'+RST}")
    print(f"\n  {BOLD}Bag ({len(player.inventory)} items):{RST}  [Gold: {YLW}{player.gold}g{RST}]")
    if not player.inventory:
        print(f"    {DIM}Empty.{RST}")
    else:
        for i, item in enumerate(player.inventory, 1):
            print(f"    [{i:2}] {item}")

    divider()
    print(f"  [E] Equip item   [U] Use consumable   [S] Sell item   [0] Back")
    return input("\n> ").strip().lower()


def show_skills(player):
    clear()
    header("SKILL TREE")
    print(f"\n  Skill Points: {YLW}{player.skill_points}{RST}")
    print(f"\n  {BOLD}Learned:{RST}")
    if not player.skills_learned:
        print(f"    {DIM}None{RST}")
    for s in player.skills_learned:
        print(f"    {GRN}✓{RST} {s['name']:<22} — {s['desc']}")
    print(f"\n  {BOLD}Available:{RST}")
    avail = player.available_skills()
    if not avail:
        print(f"    {DIM}All skills learned!{RST}")
    for i, s in enumerate(avail, 1):
        cost_col = GRN if player.skill_points >= s["cost"] else RED
        print(f"    [{i}] {s['name']:<22} — {s['desc']}  {cost_col}[{s['cost']} SP]{RST}")
    divider()
    if avail:
        raw = input("Learn skill (number) or 0 to go back > ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(avail):
            ok, msg = player.learn_skill(avail[int(raw) - 1])
            print(f"  {GRN if ok else RED}{msg}{RST}")
            time.sleep(0.8)
            return show_skills(player)


def show_quests(player, quest_log):
    clear()
    header("QUEST LOG")
    active = quest_log.active_quests()
    if not active:
        print(f"\n  {DIM}No active quests. Visit the Quest Board!{RST}")
    for q in active:
        print(f"\n  {q.display()}")
    divider()
    print(f"  Completed quests: {GRN}{len(quest_log.completed)}{RST}")
    press_enter()


def show_abilities(player):
    clear()
    header("ABILITIES")
    abilities = player.get_abilities()
    if not abilities:
        print(f"\n  {DIM}No abilities yet. Level up!{RST}")
    for a in abilities:
        mp_col = GRN if player.mp >= a.mp_cost else RED
        print(f"\n  {MAG}{BOLD}{a.name}{RST}  {mp_col}[MP: {a.mp_cost}]{RST}")
        print(f"    {a.description}")
        print(f"    Type: {a.ability_type}  |  Base Power: {a.value}  |  Req Level: {a.level_req}")
    divider()
    press_enter()
