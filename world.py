import random

ZONES = {
    1: {"name": "Starter Village & Surroundings", "desc": "Peaceful farmlands with lurking danger.",            "enc_chance": 0.35, "boss_chance": 0.04},
    2: {"name": "Dark Forest",                    "desc": "Ancient trees hide terrible creatures.",             "enc_chance": 0.45, "boss_chance": 0.06},
    3: {"name": "Cursed Ruins",                   "desc": "Remnants of a fallen civilization, now haunted.",    "enc_chance": 0.55, "boss_chance": 0.08},
    4: {"name": "Shadow Realm",                   "desc": "A plane of darkness and unimaginable power.",        "enc_chance": 0.65, "boss_chance": 0.10},
    5: {"name": "Dragon's Peak",                  "desc": "The lair of the most powerful beings in existence.", "enc_chance": 0.75, "boss_chance": 0.12},
}

ZONE_LEVEL_REQ = {1: 1, 2: 5, 3: 10, 4: 15, 5: 18}

EXPLORE_EVENTS = [
    "You venture deeper into the {zone}.",
    "You follow a worn path through {zone}.",
    "The air grows heavy as you explore {zone}.",
    "Strange sounds echo around you in {zone}.",
    "Ancient runes line the walls as you explore {zone}.",
    "The wind whispers warnings as you traverse {zone}.",
    "You stumble upon an old campfire — someone was here recently.",
    "A signpost marks the way forward through {zone}.",
]

FLAVOUR_EVENTS = [
    ("You find a hidden cache of gold!", "gold",   lambda: random.randint(10, 40)),
    ("You discover a health spring!",    "heal_hp",lambda: random.randint(20, 50)),
    ("A mana font restores your power!", "heal_mp",lambda: random.randint(15, 35)),
    ("You find a skill scroll!",         "xp",     lambda: random.randint(30, 80)),
    ("You rest under a great tree.",     "rest",   lambda: 0),
    ("You find nothing but silence.",    "nothing",lambda: 0),
]

TRAP_EVENTS = [
    ("A hidden trap triggers! You take damage.", "trap", lambda lvl: random.randint(5, 10 + lvl * 2)),
    ("You step into quicksand and barely escape!", "trap", lambda lvl: random.randint(3, 8 + lvl)),
    ("Falling rocks strike you!",                 "trap", lambda lvl: random.randint(8, 15 + lvl * 2)),
]


def get_zone(zone_id):
    return ZONES.get(zone_id, ZONES[1])


def can_enter_zone(player_level, zone_id):
    return player_level >= ZONE_LEVEL_REQ.get(zone_id, 99)


def explore_step(player, zone_id=1):
    """Returns a list of (event_type, value, message) tuples."""
    zone      = ZONES.get(zone_id, ZONES[1])
    zone_name = zone["name"]
    player.steps += 1

    events = []

    # Narrative flavour
    msg = random.choice(EXPLORE_EVENTS).format(zone=zone_name)
    events.append(("narrative", 0, msg))

    roll = random.random()

    # Random positive event (20% chance)
    if roll < 0.20:
        ev_name, ev_type, ev_fn = random.choice(FLAVOUR_EVENTS)
        val = ev_fn()
        events.append((ev_type, val, ev_name))

    # Trap (10% chance)
    elif roll < 0.30:
        trap_msg, _, trap_fn = random.choice(TRAP_EVENTS)
        val = trap_fn(player.level)
        events.append(("trap", val, trap_msg))

    # Encounter
    elif roll < 0.30 + zone["enc_chance"]:
        force_boss = random.random() < zone["boss_chance"]
        events.append(("encounter", zone_id, "⚠  A monster blocks your path!" if not force_boss else "💀  BOSS ENCOUNTER!"))

    else:
        events.append(("nothing", 0, "You walk in peace for a while."))

    return events


def travel_to_zone(player, new_zone_id):
    if not can_enter_zone(player.level, new_zone_id):
        req = ZONE_LEVEL_REQ.get(new_zone_id, 99)
        return False, f"You need to be Level {req} to enter {ZONES[new_zone_id]['name']}."
    z = ZONES.get(new_zone_id)
    if not z:
        return False, "Unknown zone."
    return True, f"You travel to {z['name']}.\n  {z['desc']}"
