"""Trade profession gameplay: milestones, trail discoveries (phase 1)."""
import pickle
import random

import pytest

import trades
import world
from player import Player
from trades import (PROFESSION_EVENTS, TRADE_MILESTONES, available_trade_events, has_milestone,
                    milestones_between, resolve_trade_event)

# Every milestone listed must be backed by a test below. Add to this set with the test.
TESTED_MILESTONES = {("Smithing", 5), ("Herblore", 5), ("Cooking", 5), ("Fletching", 5)}


def trader(trade, cls='Warrior', level=8, **skills):
    p = Player('T', cls)
    p.level = level
    p.trade_profession = trade
    for name, lv in skills.items():
        table = p.gathering_skills if name in p.gathering_skills else p.crafting_skills
        table[name]['level'] = lv
    p.resources = {}
    return p


def test_every_listed_milestone_is_tested():
    listed = {(skill, lv) for skill, table in TRADE_MILESTONES.items() for lv in table}
    assert listed <= TESTED_MILESTONES, f'milestones without a test: {listed - TESTED_MILESTONES}'


# ── Milestone announcements ────────────────────────────────────────────────────

def test_crossing_a_milestone_is_announced_once():
    p = trader('Blacksmith')
    p.crafting_skills['Smithing'] = {'level': 4, 'xp': 50 * 4 * 3}   # cumulative XP for level 4
    p.gain_skill_xp('crafting', 'Smithing', 400)                       # → level 5
    msgs = p.pop_unlocks()
    assert len(msgs) == 1 and 'Smithing 5' in msgs[0] and 'Battlefield Salvage' in msgs[0]
    assert p.pop_unlocks() == []


def test_milestones_between_lists_only_crossed_levels():
    assert [m[0] for m in milestones_between('Smithing', 1, 4)] == []
    assert [m[0] for m in milestones_between('Smithing', 4, 6)] == [5]
    assert [m[0] for m in milestones_between('Smithing', 5, 9)] == []


# ── Trail discoveries ──────────────────────────────────────────────────────────

@pytest.mark.parametrize('trade', list(PROFESSION_EVENTS))
def test_discoveries_need_the_profession_and_the_skill_level(trade):
    basic, gated = PROFESSION_EVENTS[trade]
    novice = trader(trade)
    ids = {e['id'] for e in available_trade_events(novice, 2)}
    assert ids == {basic['id']}, 'the level-gated discovery needs its crafting skill at 5'
    adept = trader(trade, **{gated['skill']: gated['level']})
    assert {e['id'] for e in available_trade_events(adept, 2)} == {basic['id'], gated['id']}
    assert has_milestone(adept, gated['skill'], gated['level'])
    assert available_trade_events(trader(None), 2) == []
    other = next(t for t in PROFESSION_EVENTS if t != trade)
    assert not {e['id'] for e in available_trade_events(trader(other), 2)} & {basic['id'], gated['id']}


def test_trade_paths_only_offered_to_professions():
    def kinds(trade):
        p = trader(trade)
        seen = set()
        for seed in range(80):
            random.seed(seed)
            seen |= {o['kind'] for o in world.generate_explore_options(p, 2, set(), 0)}
        return seen
    assert 'trade' in kinds('Fisher') and 'trade' not in kinds(None)


@pytest.mark.parametrize('trade', list(PROFESSION_EVENTS))
def test_every_discovery_resolves_to_real_rewards(trade):
    for ev in PROFESSION_EVENTS[trade]:
        p = trader(trade, **{ev['skill']: 20})
        random.seed(1)
        events = resolve_trade_event(ev['id'], p, 2, 0)
        gained_resources = sum(p.resources.values())
        items = [v for kind, v, _ in events if kind == 'item']
        assert gained_resources > 0 or items, f'{ev["id"]} gave nothing'
        title, detail = world.describe_option({'kind': 'trade', 'event': ev['id'], 'trade': trade}, 2)
        assert ev['title'] in title and trade in detail


def test_basic_discovery_grants_gathering_xp_and_zone_resources():
    p = trader('Blacksmith')
    xp = p.gathering_skills['Mining']['xp']
    random.seed(0)
    resolve_trade_event('ore_vein', p, 2, 0)
    assert p.gathering_skills['Mining']['xp'] > xp
    assert set(p.resources) <= {'Iron Ore', 'Coal'} and 3 <= sum(p.resources.values()) <= 5


def test_choosing_a_discovery_on_the_trail_applies_it(monkeypatch):
    import app as game_app
    from conftest import make_player
    from quests import QuestLog
    p = make_player('Rogue', level=8)
    p.trade_profession, p.resources = 'Fletcher', {}
    monkeypatch.setattr(game_app, 'generate_explore_options',
                        lambda *a, **k: [{'kind': 'trade', 'event': 'fallen_tree', 'trade': 'Fletcher'}])
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='explore', zone=2)
    game_app.ensure_explore_options(st)
    assert 'Fallen tree' in st['explore_options'][0]['title']
    game_app.take_explore_path(st, p, st['explore_options'][0])
    assert set(p.resources) <= {'Oak Logs', 'Normal Logs'} and sum(p.resources.values()) >= 3


def test_old_players_load_without_trade_fields():
    p = Player('T', 'Mage')
    del p.unlock_log, p.trade_specialization
    q = pickle.loads(pickle.dumps(p))
    assert q.pop_unlocks() == [] and q.trade_specialization is None
