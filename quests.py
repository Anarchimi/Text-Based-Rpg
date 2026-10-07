import random
from enemies import get_zone_enemies
from world import ZONES

QUEST_TYPES = ["kill", "collect", "explore", "bounty"]

# Collect quests: each trophy drops (COLLECT_DROP_CHANCE) from specific enemies.
COLLECT_ITEMS = {
    "Goblin Ear":          ["Goblin"],
    "Wolf Pelt":           ["Forest Wolf"],
    "Bones of the Fallen": ["Skeleton", "Undead Titan"],
    "Cursed Idol":         ["Bandit", "Orc Warrior"],
    "Ancient Rune":        ["Dark Mage", "Lich"],
    "Enchanted Crystal":   ["Stone Golem", "Chaos Elemental"],
    "Vampire Fang":        ["Vampire"],
    "Dragon Scale":        ["Wyvern", "Ancient Dragon"],
    "Shadow Essence":      ["Shadow Assassin", "Void Stalker"],
}
COLLECT_DROP_CHANCE = 0.5
EXPLORE_STEPS = (4, 7)       # scouting quests: explore the zone this many times
BOUNTY_LEADER_CHANCE = 0.35  # chance a matching encounter is the bounty's Leader

QUEST_GIVERS = [
    "The Village Elder", "A Mysterious Stranger", "The Blacksmith",
    "A Desperate Merchant", "The Guild Master", "A Frightened Farmer",
    "The Royal Courier", "A Wandering Knight", "The Innkeeper",
    "A Hooded Figure",
]

KILL_VERBS    = ["eliminate", "slay", "hunt down", "destroy", "put an end to"]
COLLECT_VERBS = ["gather", "retrieve", "bring back", "collect", "obtain"]


class Quest:
    def __init__(self, quest_id, quest_type, title, description, objective,
                 target_name, target_count, reward_gold, reward_xp, reward_item=None, zone=1):
        self.quest_id     = quest_id
        self.quest_type   = quest_type
        self.title        = title
        self.description  = description
        self.objective    = objective
        self.target_name  = target_name
        self.target_count = target_count
        self.current      = 0
        self.reward_gold  = reward_gold
        self.reward_xp    = reward_xp
        self.reward_item  = reward_item
        self.zone         = zone
        self.completed    = False
        self.active       = False

    @property
    def progress_str(self):
        return f"{self.current}/{self.target_count}"

    def is_complete(self):
        return self.current >= self.target_count

    def update(self, event_type, name=None):
        """Advance on a game event: ('kill', enemy name) or ('explore', zone name)."""
        if self.completed or not name:
            return False
        if self.quest_type == "kill" and event_type == "kill":
            hit = self.target_name.lower() in name.lower()
        elif self.quest_type == "collect" and event_type == "kill":
            hit = (any(src.lower() in name.lower() for src in COLLECT_ITEMS.get(self.target_name, []))
                   and random.random() < COLLECT_DROP_CHANCE)
        elif self.quest_type == "explore" and event_type == "explore":
            hit = name == self.target_name
        elif self.quest_type == "bounty" and event_type == "kill":
            hit = name.lower() == f"{self.target_name} Leader".lower()
        else:
            hit = False
        if hit:
            self.current += 1
        return hit


_quest_id_counter = 0

def _next_id():
    global _quest_id_counter
    _quest_id_counter += 1
    return _quest_id_counter


def generate_quest(zone=1, level=1):
    quest_type = random.choice(QUEST_TYPES)
    giver      = random.choice(QUEST_GIVERS)
    diff_mult  = 1 + (level - 1) * 0.15

    if quest_type == "kill":
        enemies   = get_zone_enemies(zone) or ["Goblin"]
        target    = random.choice(enemies)
        count     = random.randint(3, 8)
        verb      = random.choice(KILL_VERBS)
        title     = f"{verb.capitalize()} the {target}s"
        desc      = f"{giver} asks you to {verb} {count} {target}s terrorizing the area."
        objective = f"{verb.capitalize()} {count} {target}s"
        gold      = int((count * 15 + zone * 10) * diff_mult)
        xp        = int((count * 20 + zone * 15) * diff_mult)
        return Quest(_next_id(), "kill", title, desc, objective, target, count, gold, xp, zone=zone)

    elif quest_type == "collect":
        zone_enemies = set(get_zone_enemies(zone))
        options   = [it for it, srcs in COLLECT_ITEMS.items() if zone_enemies & set(srcs)] or ["Goblin Ear"]
        item      = random.choice(options)
        sources   = [e for e in COLLECT_ITEMS[item] if e in zone_enemies] or COLLECT_ITEMS[item]
        count     = random.randint(2, 5)
        verb      = random.choice(COLLECT_VERBS)
        title     = f"{verb.capitalize()} {item}s"
        desc      = f"{giver} needs {count} {item}s. They drop from {' and '.join(e + 's' for e in sources)}."
        objective = f"{verb.capitalize()} {count} {item}s"
        gold      = int((count * 20 + zone * 12) * diff_mult)
        xp        = int((count * 18 + zone * 12) * diff_mult)
        return Quest(_next_id(), "collect", title, desc, objective, item, count, gold, xp, zone=zone)

    elif quest_type == "explore":
        zone_name = ZONES[zone]["name"]
        steps     = random.randint(*EXPLORE_STEPS)
        title     = f"Scout the {zone_name}"
        desc      = f"{giver} wants a report on the {zone_name}. Explore it {steps} times and survive."
        objective = f"Explore the {zone_name} ({steps}×)"
        gold      = int((40 + zone * 15) * diff_mult)
        xp        = int((50 + zone * 20) * diff_mult)
        return Quest(_next_id(), "explore", title, desc, objective, zone_name, steps, gold, xp, zone=zone)

    else:  # bounty
        enemies   = get_zone_enemies(zone) or ["Goblin"]
        target    = random.choice(enemies)
        title     = f"Bounty: {target} Leader"
        desc      = (f"{giver} has posted a bounty on a {target} Leader — tougher than the rest. "
                     f"Keep exploring here; it hunts with the pack.")
        objective = f"Defeat the {target} Leader"
        gold      = int((60 + zone * 20) * diff_mult)
        xp        = int((80 + zone * 25) * diff_mult)
        return Quest(_next_id(), "bounty", title, desc, objective, target, 1, gold, xp, zone=zone)


class QuestLog:
    def __init__(self):
        self.quests    = []
        self.completed = []
        self.max_active = 4

    def active_quests(self):
        return [q for q in self.quests if q.active and not q.completed]

    def available_quests(self):
        return [q for q in self.quests if not q.active and not q.completed]

    def add_quest(self, quest):
        self.quests.append(quest)

    def accept_quest(self, quest):
        if len(self.active_quests()) >= self.max_active:
            return False, f"You can only have {self.max_active} active quests."
        quest.active = True
        return True, f"Quest accepted: {quest.title}"

    def check_event(self, event_type, name=None):
        completed_now = []
        for q in self.active_quests():
            updated = q.update(event_type, name)
            if updated and q.is_complete():
                completed_now.append(q)
        return completed_now

    def finish_quest(self, quest):
        quest.completed = True
        quest.active    = False
        self.completed.append(quest)
        self.quests.remove(quest)

    def refresh_board(self, zone=1, level=1, count=4):
        available = self.available_quests()
        while len(available) < count:
            q = generate_quest(zone=zone, level=level)
            self.add_quest(q)
            available.append(q)
        return available[:count]
