"""Skills, gear and other progression must do exactly what their text says."""
import re

import pytest

from items import Item
from player import PROFESSIONS, SKILL_TREE, Player

TOKENS = {'Max HP': 'max_hp', 'Max MP': 'max_mp', 'HP': 'max_hp', 'MP': 'max_mp',
          'STR': 'str', 'DEX': 'dex', 'INT': 'int', 'VIT': 'vit', 'LCK': 'lck'}


def described(desc):
    out = {}
    for n, name in re.findall(r'\+(\d+) (Max HP|Max MP|HP|MP|STR|DEX|INT|VIT|LCK)', desc):
        out[TOKENS[name]] = out.get(TOKENS[name], 0) + int(n)
    return out


def snapshot(p):
    return {s: getattr(p, s) for s in ('max_hp', 'max_mp', 'str', 'dex', 'int', 'vit', 'lck')}


ALL_SKILLS = ([(cls, None, sk) for cls, tree in SKILL_TREE.items() for sk in tree]
              + [(cls, prof, sk) for cls, profs in PROFESSIONS.items()
                 for prof, data in profs.items() for sk in data['skills']])


@pytest.mark.parametrize('cls,prof,skill', ALL_SKILLS, ids=lambda x: x['name'] if isinstance(x, dict) else str(x))
def test_every_skill_grants_exactly_its_description(cls, prof, skill):
    p = Player('T', cls)
    p.skill_points = 99
    if prof:
        p.choose_profession(prof)
    before = snapshot(p)
    learn = p.learn_prof_skill if prof else p.learn_skill
    assert learn(skill)[0]
    after = snapshot(p)
    gained = {k: after[k] - before[k] for k in after if after[k] != before[k]}
    assert gained == described(skill['desc']), f"{skill['name']}: text says {skill['desc']!r}, got {gained}"


def test_armor_hp_counts_while_equipped():
    p = Player('T', 'Warrior')
    base = p.max_hp
    armor = Item('Test Plate', 'armor', 'Rare', 10, {'def': 5, 'hp': 30})
    plain = Item('Test Vest', 'armor', 'Rare', 10, {'def': 5})
    p.add_item(armor)
    p.equip(armor)
    assert p.max_hp == base + 30
    p.add_item(plain)
    p.equip(plain)
    assert p.max_hp == base and p.hp <= p.max_hp


def test_old_saves_are_migrated_to_v2_stats():
    """Recreate a pre-v2 player (double-counted STR, missing second stats) and reload it."""
    import pickle
    p = Player('T', 'Warrior')
    base_str, base_vit, max_hp = p.base_str, p.base_vit, p.max_hp
    # What the old learn_skill did for "Veteran's Edge" (+5 STR, +3 VIT) and "Fortitude" (+8 HP, +2 VIT):
    p.skills_learned = [{'name': "Veteran's Edge", 'stat': 'str', 'bonus': 5, 'cost': 2},
                        {'name': 'Fortitude', 'stat': 'max_hp', 'bonus': 8, 'cost': 2}]
    p.base_str += 5
    p.max_hp += 8
    armor = Item('Old Plate', 'armor', 'Rare', 10, {'def': 5, 'hp': 20})
    p.equipment['armor'] = armor
    del p._stats_version

    q = pickle.loads(pickle.dumps(p))
    assert q.str == base_str + 5, 'STR skill must count once, not twice'
    assert q.vit == base_vit + 3 + 2, 'second stats are now granted'
    assert q.max_hp == max_hp + 8 + 20, 'armor HP is now applied'
    assert pickle.loads(pickle.dumps(q)).max_hp == q.max_hp, 'migration runs only once'


# ── Quests ─────────────────────────────────────────────────────────────────────

import random as _random

import quests
from quests import COLLECT_ITEMS, Quest, QuestLog, generate_quest
from world import ZONES


def _quests_of(qtype, zone, n=200):
    _random.seed(0)
    out = [q for q in (generate_quest(zone=zone, level=5) for _ in range(n)) if q.quest_type == qtype]
    assert out, f'no {qtype} quests generated'
    return out


@pytest.mark.parametrize('zone', range(1, 6))
def test_explore_quests_complete_by_exploring_their_zone(zone):
    for q in _quests_of('explore', zone):
        assert q.target_name == ZONES[zone]['name']
        for _ in range(q.target_count):
            q.update('explore', ZONES[zone]['name'])
        assert q.is_complete()


@pytest.mark.parametrize('zone', range(1, 6))
def test_collect_quests_drop_only_from_their_listed_enemies(zone, monkeypatch):
    monkeypatch.setattr(quests, 'COLLECT_DROP_CHANCE', 1.0)
    for q in _quests_of('collect', zone):
        sources = COLLECT_ITEMS[q.target_name]
        assert any(s in q.description for s in sources), 'description must say where it drops'
        q.update('kill', 'Some Unrelated Monster')
        assert q.current == 0
        for _ in range(q.target_count):
            q.update('kill', sources[0])
        assert q.is_complete()


def test_bounty_needs_the_leader_not_any_member():
    for q in _quests_of('bounty', 2):
        q.update('kill', q.target_name)
        assert q.current == 0
        q.update('kill', f'{q.target_name} Leader')
        assert q.is_complete()


def test_bounty_leaders_spawn_while_the_bounty_is_active(monkeypatch):
    import app as game_app
    from conftest import make_player
    from enemies import ENEMY_TEMPLATES, Enemy
    monkeypatch.setattr(game_app, 'BOUNTY_LEADER_CHANCE', 1.0)
    log = QuestLog()
    q = Quest(1, 'bounty', 'b', 'd', 'o', 'Goblin', 1, 10, 10)
    log.add_quest(q)
    log.accept_quest(q)
    monkeypatch.setattr(game_app, 'generate_explore_options',
                        lambda *a, **k: [{'kind': 'fight', 'enemy': Enemy(ENEMY_TEMPLATES[0], 1)}])
    st = game_app.fresh_state()
    st.update(player=make_player('Warrior'), quest_log=log, screen='hub')
    game_app.ensure_explore_options(st)
    enemy = st['explore_options'][0]['enemy']
    assert enemy.name == 'Goblin Leader' and enemy.template_name == 'Goblin'
    assert 'Bounty target' in st['explore_options'][0]['detail']


# ── Flee ───────────────────────────────────────────────────────────────────────

def test_flee_depends_on_speed_not_enemy_attack():
    from combat import flee_chance
    from conftest import make_enemy, make_player
    slow, fast = make_player('Warrior'), make_player('Rogue')
    fast.base_dex = 200
    weak, brutal = make_enemy(), make_enemy()
    brutal.atk = 10_000
    assert flee_chance(fast, weak) > flee_chance(slow, weak)
    assert flee_chance(slow, brutal) == flee_chance(slow, weak), 'enemy ATK must not block fleeing'
    assert flee_chance(slow, brutal) >= 0.10


# ── Boss lairs ─────────────────────────────────────────────────────────────────

def test_exploring_finds_the_boss_lair_then_it_can_be_challenged(monkeypatch):
    import app as game_app
    from conftest import make_player
    from world import LAIR_STEPS
    monkeypatch.setattr(game_app, 'generate_explore_options',
                        lambda *a, **k: [{'kind': 'shrine'}, {'kind': 'shrine'}, {'kind': 'shrine'}])
    monkeypatch.setattr(game_app, 'resolve_option', lambda *a: [('nothing', 0, 'quiet')])
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    import pickle, os
    st = game_app.fresh_state()
    hero = make_player('Warrior')
    hero.profession = 'Knight'
    st.update(player=hero, quest_log=QuestLog(), screen='hub', zone=2)
    pickle.dump(st, open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'wb'))
    client.post('/action', data={'action': 'explore'})
    for _ in range(LAIR_STEPS - 1):
        client.post('/action', data={'action': 'choose_0'})
    page = client.post('/action', data={'action': 'back'}, follow_redirects=True).get_data(as_text=True)
    assert 'Challenge Undead Warlord' not in page
    client.post('/action', data={'action': 'explore'})
    page = client.post('/action', data={'action': 'choose_0'}, follow_redirects=True).get_data(as_text=True)
    assert "found the lair of Undead Warlord" in page
    page = client.post('/action', data={'action': 'back'}, follow_redirects=True).get_data(as_text=True)
    assert 'Challenge Undead Warlord' in page
    page = client.post('/action', data={'action': 'challenge_boss'}, follow_redirects=True).get_data(as_text=True)
    assert 'Undead Warlord' in page and 'Defend' in page  # in combat with the zone boss


# ── Gear upgrades ──────────────────────────────────────────────────────────────

def test_upgrading_costs_gold_and_bars_and_raises_stats():
    from items import UPGRADE_MAX, upgrade_cost
    p = Player('T', 'Warrior')
    armor = Item('Plate', 'armor', 'Rare', 100, {'def': 20, 'hp': 10})
    p.add_item(armor)
    p.equip(armor)
    assert not p.upgrade_equipped('armor')[0], 'no gold, no bars'
    p.gold = 100_000
    p.resources = {b: 99 for b in ('Bronze Bar', 'Iron Bar', 'Steel Bar', 'Mithril Bar', 'Adamantite Bar')}
    hp, gold = p.max_hp, p.gold
    defs = [armor.stats['def']]
    for n in range(1, UPGRADE_MAX + 1):
        cost = upgrade_cost(armor)
        ok, _ = p.upgrade_equipped('armor')
        assert ok and armor.upgrade == n and armor.name == f'Plate +{n}'
        defs.append(armor.stats['def'])
    assert defs == sorted(defs) and defs[-1] > defs[0] * 1.5
    assert p.max_hp > hp, 'armor HP upgrades raise max HP'
    assert p.gold < gold and p.resources['Adamantite Bar'] == 97
    assert upgrade_cost(armor) is None and not p.upgrade_equipped('armor')[0]


def test_unequipping_upgraded_armor_removes_its_hp():
    p = Player('T', 'Warrior')
    base = p.max_hp
    armor = Item('Plate', 'armor', 'Rare', 100, {'def': 20, 'hp': 10})
    p.add_item(armor)
    p.equip(armor)
    p.gold, p.resources = 10_000, {'Bronze Bar': 2}
    p.upgrade_equipped('armor')
    other = Item('Rags', 'armor', 'Common', 1, {'def': 1})
    p.add_item(other)
    p.equip(other)
    assert p.max_hp == base
