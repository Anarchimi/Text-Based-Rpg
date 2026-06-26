import random
from enemies import get_zone_enemies

QUEST_TYPES = ["kill", "collect", "explore", "bounty"]

COLLECT_ITEMS = [
    "Goblin Ear", "Wolf Pelt", "Dragon Scale", "Ancient Rune",
    "Enchanted Crystal", "Shadow Essence", "Bones of the Fallen",
    "Cursed Idol", "Moonstone", "Vampire Fang",
]

QUEST_GIVERS = [
    "The Village Elder", "A Mysterious Stranger", "The Blacksmith",
    "A Desperate Merchant", "The Guild Master", "A Frightened Farmer",
    "The Royal Courier", "A Wandering Knight", "The Innkeeper",
    "A Hooded Figure",
]

KILL_VERBS    = ["eliminate", "slay", "hunt down", "destroy", "put an end to"]
COLLECT_VERBS = ["gather", "retrieve", "bring back", "collect", "obtain"]
EXPLORE_LOCS  = [
    "the Abandoned Mine", "the Dark Forest", "the Cursed Ruins",
    "the Ancient Temple", "the Forgotten Graveyard", "the Misty Swamp",
    "the Volcanic Caves", "the Frozen Peaks", "the Sunken City",
    "the Shadow Realm",
]


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
        if self.completed:
            return False
        if self.quest_type == "kill" and event_type == "kill":
            if name and (name.lower() in self.target_name.lower() or self.target_name.lower() in name.lower()):
                self.current += 1
                return True
        elif self.quest_type == "collect" and event_type == "kill":
            if random.random() < 0.33:
                self.current += 1
                return True
        elif self.quest_type == "explore" and event_type == "explore":
            if name == self.target_name:
                self.current += 1
                return True
        elif self.quest_type == "bounty" and event_type == "kill":
            if name and self.target_name.lower() in name.lower():
                self.current += 1
                return True
        return False

    def display(self):
        star   = "\033[33m★\033[0m" if self.active else " "
        done   = " \033[32m[COMPLETE]\033[0m" if self.is_complete() else ""
        return (f"{star} [{self.quest_type.upper()}] {self.title}{done}\n"
                f"    {self.description}\n"
                f"    Progress: {self.progress_str}  "
                f"Reward: {self.reward_xp} XP + {self.reward_gold}g"
                + (f" + Item" if self.reward_item else ""))


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
        item      = random.choice(COLLECT_ITEMS)
        count     = random.randint(2, 5)
        verb      = random.choice(COLLECT_VERBS)
        title     = f"{verb.capitalize()} {item}s"
        desc      = f"{giver} needs you to {verb} {count} {item}s from the wilderness."
        objective = f"{verb.capitalize()} {count} {item}s"
        gold      = int((count * 20 + zone * 12) * diff_mult)
        xp        = int((count * 18 + zone * 12) * diff_mult)
        return Quest(_next_id(), "collect", title, desc, objective, item, count, gold, xp, zone=zone)

    elif quest_type == "explore":
        location  = random.choice(EXPLORE_LOCS)
        title     = f"Explore {location}"
        desc      = f"{giver} wants information about {location}. Venture there and survive."
        objective = f"Reach {location}"
        gold      = int((40 + zone * 15) * diff_mult)
        xp        = int((50 + zone * 20) * diff_mult)
        return Quest(_next_id(), "explore", title, desc, objective, location, 1, gold, xp, zone=zone)

    else:  # bounty
        enemies   = get_zone_enemies(zone) or ["Goblin"]
        target    = random.choice(enemies)
        title     = f"Bounty: {target} Leader"
        desc      = f"{giver} has posted a bounty. Bring down a powerful {target}."
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
