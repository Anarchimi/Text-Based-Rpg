import random

ZONES = {
    1: {"name": "Starter Village & Surroundings", "desc": "Peaceful farmlands with lurking danger.",            "enc_chance": 0.35, "boss_chance": 0.04},
    2: {"name": "Dark Forest",                    "desc": "Ancient trees hide terrible creatures.",             "enc_chance": 0.45, "boss_chance": 0.06},
    3: {"name": "Cursed Ruins",                   "desc": "Remnants of a fallen civilization, now haunted.",    "enc_chance": 0.55, "boss_chance": 0.08},
    4: {"name": "Shadow Realm",                   "desc": "A plane of darkness and unimaginable power.",        "enc_chance": 0.65, "boss_chance": 0.10},
    5: {"name": "Dragon's Peak",                  "desc": "The lair of the most powerful beings in existence.", "enc_chance": 0.75, "boss_chance": 0.12},
}

ZONE_LEVEL_REQ = {1: 1, 2: 5, 3: 10, 4: 15, 5: 18}

# Level-scaled events: lambdas take (lvl) param
FLAVOUR_EVENTS = [
    ("You find a hidden cache of gold!",    "gold",       lambda lvl: random.randint(10 + lvl*5,  40 + lvl*15)),
    ("You discover a health spring!",       "heal_pct",   lambda lvl: random.randint(15, 30)),
    ("A mana font restores your power!",    "heal_mp_pct",lambda lvl: random.randint(20, 40)),
    ("You find a skill scroll!",            "xp",         lambda lvl: random.randint(30 + lvl*10, 80 + lvl*30)),
    ("You rest under a great tree.",        "rest",       lambda lvl: 0),
    ("You find nothing but silence.",       "nothing",    lambda lvl: 0),
]

TRAP_EVENTS = [
    ("A hidden trap triggers! You take damage.",         "trap_pct", lambda: random.randint(5, 15)),
    ("You step into quicksand and barely escape!",       "trap_pct", lambda: random.randint(5, 12)),
    ("Falling rocks strike you from above!",             "trap_pct", lambda: random.randint(8, 20)),
    ("Poison darts fly from the wall!",                  "trap_pct", lambda: random.randint(6, 18)),
]

# One-time named events per zone: (event_id, message, event_type, value)
NAMED_EVENTS = {
    1: [
        ("n1_prophecy", "A dying soldier clutches your arm. 'Five seals bind the ancient evil... five champions must fall to break them.' He breathes his last.", "narrative", 0),
        ("n1_altar",    "You discover a mossy stone altar humming with divine energy. The light washes over you, sealing your wounds.", "heal_pct", 25),
    ],
    2: [
        ("n2_scout",    "A fallen scout's satchel holds tactical notes. You absorb the knowledge.", "xp", 60),
        ("n2_warning",  "Cave walls bear claw marks three feet deep. Whatever made these dwarfs you. You press on anyway.", "narrative", 0),
    ],
    3: [
        ("n3_ruin_gold", "A crumbling vault yields forgotten treasure.", "gold", 80),
        ("n3_lich_eye",  "A disembodied eye watches you pass. You feel ancient malice probing your mind. It blinks, then vanishes.", "narrative", 0),
    ],
    4: [
        ("n4_void",      "The air ripples. For a moment you see your own death — a vast shadow consuming the realm. Then it passes.", "narrative", 0),
        ("n4_relic",     "A fragment of a shattered seal pulses with stored power. You absorb it.", "xp", 120),
    ],
    5: [
        ("n5_dragon",    "'I HAVE WAITED AN ETERNITY FOR THIS,' a voice booms across the void. The ground shakes beneath your feet.", "narrative", 0),
        ("n5_prophecy",  "You remember the prophecy: five seals, five trials, one champion. This is the final threshold. You were born for this.", "narrative", 0),
    ],
}


LAIR_STEPS = 12  # explore a zone this many times to find its boss's lair (then challenge it at will)


def get_zone(zone_id):
    return ZONES.get(zone_id, ZONES[1])


def can_enter_zone(player_level, zone_id):
    return player_level >= ZONE_LEVEL_REQ.get(zone_id, 99)


# ── Exploring: choose one of three paths ───────────────────────────────────────
# Each Explore press offers EXPLORE_CHOICES paths with their risk shown. Every path
# taken goes one step deeper down the trail (max MAX_DEPTH); depth raises enemy
# level, gold, loot rarity and trap odds. Resting (camp, Inn) resets it.
EXPLORE_CHOICES = 3
MAX_DEPTH = 10
DEPTH_LEVELS_PER = 3      # +1 enemy level per this many depth
DEPTH_GOLD = 0.10         # +10% gold per depth
DEPTH_LUCK = 3            # +3 loot luck per depth
TREASURE_TRAP_BASE = 20   # % trap chance on treasure, +2 per depth
REST_HEAL = 0.30          # camp restores 30% HP and MP

TREASURE_SPOTS = ["an overturned cart", "a collapsed tent", "a moss-covered chest", "a hollow tree",
                  "a fallen adventurer's pack", "a cracked urn", "a half-buried strongbox"]


def depth_effects(depth):
    """Human-readable summary of what the current depth does."""
    return {"enemy_levels": depth // DEPTH_LEVELS_PER, "gold_pct": int(depth * DEPTH_GOLD * 100),
            "luck": depth * DEPTH_LUCK, "trap_pct": TREASURE_TRAP_BASE + 2 * depth}


def generate_explore_options(player, zone_id, triggered_events, depth, ng=0):
    """Three distinct paths: always one fight, plus two others weighted by situation."""
    from enemies import spawn_enemy   # world is imported by quests; keep import local
    zone = ZONES.get(zone_id, ZONES[1])
    level = player.level + depth // DEPTH_LEVELS_PER
    force_boss = random.random() < zone["boss_chance"]
    enemy = spawn_enemy(zone=zone_id, level=level, force_boss=force_boss, ng=ng)
    options = [{"kind": "fight", "enemy": enemy}]

    pool = {"treasure": 3, "forage": 2, "shrine": 2, "mystery": 2}
    if player.hp < player.max_hp * 0.7 or player.mp < player.max_mp * 0.5:
        pool["rest"] = 3
    if any(eid not in triggered_events for eid, *_ in NAMED_EVENTS.get(zone_id, [])):
        pool["story"] = 4
    if not _forage_skills(player, zone_id):
        pool.pop("forage")
    while len(options) < EXPLORE_CHOICES and pool:
        kind = random.choices(list(pool), weights=list(pool.values()))[0]
        del pool[kind]
        opt = {"kind": kind}
        if kind == "treasure":
            opt["spot"] = random.choice(TREASURE_SPOTS)
            opt["trap_pct"] = depth_effects(depth)["trap_pct"]
        elif kind == "forage":
            opt["skill"] = random.choice(_forage_skills(player, zone_id))
        options.append(opt)
    random.shuffle(options)
    return options


def _forage_skills(player, zone_id):
    from crafting import ZONE_RESOURCES
    res = ZONE_RESOURCES.get(zone_id, {})
    return [sk for sk, table in res.items()
            if any(player.gathering_skills.get(sk, {"level": 1})["level"] >= req for _, _, req in table)]


def describe_option(opt, zone_id, player_level=None):
    """(icon + title, detail line) shown on the explore screen."""
    kind = opt["kind"]
    if kind == "fight":
        e = opt["enemy"]
        tag = " · BOSS" if e.is_boss else (" · Bounty target!" if e.name.endswith(" Leader") else "")
        if player_level is not None and e.level >= player_level + 2:
            tag += " · ⚠ above your level"
        verb = "Face" if e.is_boss else "Track"
        return f"{'💀' if e.is_boss else '⚔'} {verb} the {e.name}", f"Lv {e.level} · {e.max_hp} HP{tag}"
    if kind == "treasure":
        return f"💰 Search {opt['spot']}", f"Gold, maybe gear · {opt['trap_pct']}% trap risk"
    if kind == "forage":
        from crafting import ZONE_RESOURCES
        names = ", ".join(n for n, _, _ in ZONE_RESOURCES[zone_id][opt["skill"]])
        return f"🌿 Forage ({opt['skill']})", f"{names} · +{opt['skill']} XP"
    if kind == "shrine":
        return "⛩ Pray at a weathered shrine", "A blessing… or a curse"
    if kind == "mystery":
        return "❓ Follow the strange lights", "Anything could happen"
    if kind == "rest":
        return "🔥 Make camp", f"+{int(REST_HEAL * 100)}% HP & MP · resets trail depth"
    if kind == "story":
        return "✦ Something stirs nearby", "An important moment in the story"
    return kind, ""


def resolve_option(opt, player, zone_id, triggered_events, depth):
    """Outcome of a chosen path as (event_type, value, message) tuples for app.py.

    Extra event types beyond the classic explore events: 'item' (value: Item),
    'resource' (value: message only, already applied), 'encounter' (value: Enemy),
    'reset_depth'."""
    from items import generate_loot
    kind = opt["kind"]
    lvl = player.level
    gold_mult = 1 + depth * DEPTH_GOLD
    luck = int(player.lck) + depth * DEPTH_LUCK
    if kind == "fight":
        return [("encounter", opt["enemy"], "You close in on your quarry.")]
    if kind == "treasure":
        if random.randint(1, 100) <= opt["trap_pct"]:
            msg, _, fn = random.choice(TRAP_EVENTS)
            return [("trap_pct", fn(), f"It was rigged! {msg}")]
        events = [("gold", int(random.randint(10 + lvl * 5, 40 + lvl * 15) * gold_mult),
                   f"You search {opt['spot']}.")]
        if random.random() < 0.35:
            gear = [i for i in generate_loot(lvl, luck, 3, player.player_class) if i.item_type != "consumable"]
            if gear:
                events.append(("item", gear[0], "Tucked inside:"))
        return events
    if kind == "forage":
        from crafting import gather_resource
        got = gather_resource(player, zone_id, opt["skill"])
        if not got:
            return [("nothing", 0, "You find nothing worth taking.")]
        res, qty, xp, up = got
        return [("resource", 0, f"You gather {qty}× {res} (+{xp} {opt['skill']} XP)"
                                + (f" ★ {opt['skill']} leveled up!" if up else ""))]
    if kind == "shrine":
        roll = random.random()
        if roll < 0.30:
            return [("heal_pct", 100, "Warm light washes over you."), ("heal_mp_pct", 100, "")]
        if roll < 0.60:
            return [("xp", random.randint(40 + lvl * 15, 90 + lvl * 35), "Visions of old battles fill your mind.")]
        if roll < 0.80:
            return [("gold", int(random.randint(20 + lvl * 8, 60 + lvl * 20) * gold_mult), "Offerings glint at the shrine's base.")]
        return [("trap_pct", random.randint(10, 20), "The shrine is profane. A curse saps your strength!")]
    if kind == "mystery":
        roll = random.random()
        if roll < 0.25:
            from enemies import spawn_enemy
            enemy = spawn_enemy(zone=zone_id, level=lvl + depth // DEPTH_LEVELS_PER + 1)
            return [("encounter", enemy, f"The lights were a lure — an ambush by a {enemy.name}!")]
        if roll < 0.45:
            gear = [i for i in generate_loot(lvl, luck + 10, 4, player.player_class) if i.item_type != "consumable"]
            if gear:
                return [("item", gear[0], "The lights fade over a forgotten grave. Something gleams in the dirt:")]
        if roll < 0.65:
            msg, ev, fn = random.choice(FLAVOUR_EVENTS[:4])
            return [(ev, fn(lvl), msg)]
        if roll < 0.85:
            msg, _, fn = random.choice(TRAP_EVENTS)
            return [("trap_pct", fn(), msg)]
        return [("nothing", 0, "The lights vanish. You're left alone in the dark.")]
    if kind == "rest":
        return [("heal_pct", int(REST_HEAL * 100), "You make camp and rest."),
                ("heal_mp_pct", int(REST_HEAL * 100), ""), ("reset_depth", 0, "")]
    if kind == "story":
        for eid, msg, etype, val in NAMED_EVENTS.get(zone_id, []):
            if eid not in triggered_events:
                triggered_events.add(eid)
                return [(etype, val, msg)]
        return [("nothing", 0, "Whatever it was, it's gone.")]
    return [("nothing", 0, "")]


def travel_to_zone(player, new_zone_id):
    if not can_enter_zone(player.level, new_zone_id):
        req = ZONE_LEVEL_REQ.get(new_zone_id, 99)
        return False, f"You need to be Level {req} to enter {ZONES[new_zone_id]['name']}."
    z = ZONES.get(new_zone_id)
    if not z:
        return False, "Unknown zone."
    return True, f"You travel to {z['name']}.\n  {z['desc']}"
