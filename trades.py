"""Trade profession gameplay: skill milestones and profession discoveries on the trail.

Trade skills (Mining, Smithing, Herbalism, ...) are levelled 1–20 by everyone; the
trade profession only speeds two of them up (+50% XP, see crafting.TRADE_PROFESSIONS).
Milestones are keyed to those existing skill levels — there is no separate mastery bar.

Rule: TRADE_MILESTONES lists only unlocks that are implemented. Each entry names its
behaviour and has a test (tests/test_trades.py checks coverage).
"""
import random

MILESTONE_LEVELS = (5, 10, 15, 20)

# skill -> {level: (title, what it unlocks)}
TRADE_MILESTONES = {
    "Smithing":  {5: ("Battlefield Salvage", "Blacksmiths can find old battlefields on the trail: metal bars and salvaged gear.")},
    "Herblore":  {5: ("Abandoned Apothecary", "Alchemists can find ruined apothecaries on the trail: potions and rare herbs.")},
    "Cooking":   {5: ("Smokehouse Ruins", "Fishers can find old smokehouses on the trail: preserved food.")},
    "Fletching": {5: ("Hunter's Cache", "Fletchers can find hunters' caches on the trail: seasoned timber and a hunting weapon.")},
}


def skill_level(player, skill):
    for table in (player.gathering_skills, player.crafting_skills):
        if skill in table:
            return table[skill]["level"]
    return 0


def has_milestone(player, skill, level):
    return level in TRADE_MILESTONES.get(skill, {}) and skill_level(player, skill) >= level


def milestones_between(skill, old_level, new_level):
    """Milestones crossed when `skill` went from old_level to new_level."""
    return [(lv, *TRADE_MILESTONES[skill][lv]) for lv in sorted(TRADE_MILESTONES.get(skill, {}))
            if old_level < lv <= new_level]


def next_milestone(player, skill):
    lv = skill_level(player, skill)
    for m in sorted(TRADE_MILESTONES.get(skill, {})):
        if m > lv:
            return (m, *TRADE_MILESTONES[skill][m])
    return None


# ── Profession discoveries on the trail ────────────────────────────────────────
# Offered as an extra explore path kind ("trade") only to players with the trade
# profession, and only once its skill requirement is met.

def _zone_res(zone, skill):
    from crafting import ZONE_RESOURCES
    return [name for name, _, _ in ZONE_RESOURCES.get(zone, ZONE_RESOURCES[1]).get(skill, [])]


# The level-1 discovery of each trade: its gathering skill yields a bigger haul.
BASIC_DISCOVERY_SKILL = {"ore_vein": "Mining", "herb_patch": "Herbalism",
                         "hidden_pool": "Fishing", "fallen_tree": "Woodcutting"}

ZONE_BAR = {1: "Bronze Bar", 2: "Iron Bar", 3: "Steel Bar", 4: "Mithril Bar", 5: "Adamantite Bar"}

PROFESSION_EVENTS = {
    "Blacksmith": [
        {"id": "ore_vein", "skill": "Mining", "level": 1, "icon": "⛏",
         "title": "Exposed ore vein", "detail": "Ore lies bare in the rock · 3–5 ore"},
        {"id": "salvage", "skill": "Smithing", "level": 5, "icon": "⚔",
         "title": "Old battlefield", "detail": "Salvage metal bars, maybe gear"},
    ],
    "Alchemist": [
        {"id": "herb_patch", "skill": "Herbalism", "level": 1, "icon": "🌿",
         "title": "Wild herb patch", "detail": "Untouched herbs · 3–5 herbs"},
        {"id": "apothecary", "skill": "Herblore", "level": 5, "icon": "⚗",
         "title": "Abandoned apothecary", "detail": "Dusty shelves · potions and rare herbs"},
    ],
    "Fisher": [
        {"id": "hidden_pool", "skill": "Fishing", "level": 1, "icon": "🎣",
         "title": "Hidden pool", "detail": "Fish teem in still water · 3–5 fish"},
        {"id": "smokehouse", "skill": "Cooking", "level": 5, "icon": "🍖",
         "title": "Smokehouse ruins", "detail": "Preserved food left behind"},
    ],
    "Fletcher": [
        {"id": "fallen_tree", "skill": "Woodcutting", "level": 1, "icon": "🪵",
         "title": "Fallen tree", "detail": "Storm-felled timber · 3–5 logs"},
        {"id": "hunter_cache", "skill": "Fletching", "level": 5, "icon": "🏹",
         "title": "Hunter's cache", "detail": "Seasoned timber, maybe a weapon"},
    ],
}


def available_trade_events(player, zone):
    """Discoveries this player can be offered here (profession + skill level + zone resources)."""
    out = []
    for ev in PROFESSION_EVENTS.get(player.trade_profession, []):
        if skill_level(player, ev["skill"]) < ev["level"]:
            continue
        gather_skill = BASIC_DISCOVERY_SKILL.get(ev["id"])
        if gather_skill and not _zone_res(zone, gather_skill):
            continue
        out.append(ev)
    return out


def describe_trade_event(event_id, trade):
    ev = next(e for e in PROFESSION_EVENTS[trade] if e["id"] == event_id)
    return f"{ev['icon']} {ev['title']}", f"{trade} discovery · {ev['detail']}"


def _grant(player, name, qty):
    player.add_resource(name, qty)
    return f"{qty}× {name}"


def resolve_trade_event(event_id, player, zone, depth):
    """Outcome tuples in the explore event format (see world.resolve_option)."""
    from items import Item, generate_armor, generate_weapon
    lvl = player.level
    if event_id in BASIC_DISCOVERY_SKILL:
        skill = BASIC_DISCOVERY_SKILL[event_id]
        got = [_grant(player, random.choice(_zone_res(zone, skill)), 1) for _ in range(random.randint(3, 5))]
        player.gain_skill_xp("gathering", skill, 20 + 5 * zone)
        return [("resource", 0, f"You harvest the find: {', '.join(got)} (+{20 + 5 * zone} {skill} XP)")]
    if event_id == "salvage":
        msg = f"You pick through the wreckage: {_grant(player, ZONE_BAR[zone], random.randint(1, 3))}"
        events = [("resource", 0, msg)]
        if random.random() < 0.4:
            gear = random.choice([generate_weapon(player.player_class, lvl), generate_armor(lvl, player_class=player.player_class)])
            events.append(("item", gear, "Half-buried in the mud:"))
        return events
    if event_id == "apothecary":
        herbs = _zone_res(zone, "Herbalism")
        events = [("resource", 0, f"Among the shelves: {_grant(player, herbs[-1], random.randint(2, 3))}")]
        potion = Item("Greater Health Potion", "consumable", "Common", 100, effect="heal_pct", effect_value=50)
        events.append(("item", potion, "A sealed flask survived:"))
        return events
    if event_id == "smokehouse":
        fish = _zone_res(zone, "Fishing")[0]
        cooked = "Cooked " + fish.replace("Raw ", "")
        food = Item(cooked, "consumable", "Common", 20, effect="heal_pct", effect_value=15 + 5 * zone)
        food.category = "food"
        return [("item", food, "Hanging in the smoke, still good:"),
                ("resource", 0, f"And in a barrel: {_grant(player, fish, 2)}")]
    if event_id == "hunter_cache":
        logs = _zone_res(zone, "Woodcutting")
        events = [("resource", 0, f"Seasoned timber: {_grant(player, logs[-1], random.randint(2, 4))}")]
        if random.random() < 0.35:
            events.append(("item", generate_weapon(player.player_class, lvl), "A hunter's spare weapon:"))
        return events
    return [("nothing", 0, "Whatever was here is gone.")]
