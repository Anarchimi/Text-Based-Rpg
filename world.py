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


def get_zone(zone_id):
    return ZONES.get(zone_id, ZONES[1])


def can_enter_zone(player_level, zone_id):
    return player_level >= ZONE_LEVEL_REQ.get(zone_id, 99)


def explore_step(player, zone_id=1, triggered_events=None):
    """Returns a list of (event_type, value, message) tuples."""
    if triggered_events is None:
        triggered_events = set()

    zone      = ZONES.get(zone_id, ZONES[1])
    zone_name = zone["name"]
    player.steps += 1

    events = []

    # Named one-time events (25% chance if any untriggered)
    zone_named = NAMED_EVENTS.get(zone_id, [])
    untriggered = [(eid, msg, etype, val) for eid, msg, etype, val in zone_named
                   if eid not in triggered_events]
    if untriggered and random.random() < 0.25:
        eid, msg, etype, val = random.choice(untriggered)
        triggered_events.add(eid)
        events.append((etype, val, msg))
        return events

    # Regular narrative flavour
    msg = random.choice(EXPLORE_EVENTS).format(zone=zone_name)
    events.append(("narrative", 0, msg))

    roll = random.random()

    # Random positive event (20% chance)
    if roll < 0.20:
        ev_name, ev_type, ev_fn = random.choice(FLAVOUR_EVENTS)
        val = ev_fn(player.level)
        events.append((ev_type, val, ev_name))

    # Trap (10% chance)
    elif roll < 0.30:
        trap_msg, _, trap_fn = random.choice(TRAP_EVENTS)
        val = trap_fn()
        events.append(("trap_pct", val, trap_msg))

    # Encounter
    elif roll < 0.30 + zone["enc_chance"]:
        force_boss = random.random() < zone["boss_chance"]
        events.append(("encounter", zone_id,
                        "⚠  A monster blocks your path!" if not force_boss else "💀  BOSS ENCOUNTER!"))

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
