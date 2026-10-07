"""Exploring: choose one of three paths; trail depth trades safety for rewards."""
import os
import pickle
import random

import pytest

import app as game_app
import world
from quests import QuestLog
from world import (EXPLORE_CHOICES, MAX_DEPTH, NAMED_EVENTS, depth_effects, describe_option,
                   generate_explore_options, resolve_option)
from conftest import make_player

KINDS = ['fight', 'treasure', 'forage', 'shrine', 'mystery', 'rest', 'story']


def _player(cls='Warrior', level=8):
    p = make_player(cls, level=level)
    p.max_hp = p.hp = 500
    return p


@pytest.mark.parametrize('zone', range(1, 6))
def test_paths_are_distinct_and_always_include_a_fight(zone):
    for seed in range(30):
        random.seed(seed)
        opts = generate_explore_options(_player(), zone, set(), depth=0)
        kinds = [o['kind'] for o in opts]
        assert len(opts) == EXPLORE_CHOICES and len(set(kinds)) == len(kinds)
        assert 'fight' in kinds


def test_every_path_kind_shows_text_and_resolves():
    random.seed(1)
    p = _player()
    from enemies import spawn_enemy
    samples = {
        'fight': {'kind': 'fight', 'enemy': spawn_enemy(2, 8)},
        'treasure': {'kind': 'treasure', 'spot': 'a chest', 'trap_pct': 20},
        'forage': {'kind': 'forage', 'skill': 'Mining'},
        'shrine': {'kind': 'shrine'}, 'mystery': {'kind': 'mystery'},
        'rest': {'kind': 'rest'}, 'story': {'kind': 'story'},
    }
    assert set(samples) == set(KINDS)
    for kind, opt in samples.items():
        title, detail = describe_option(opt, 1)
        assert title and detail, kind
        events = resolve_option(opt, p, 1, set(), depth=0)
        assert events and all(len(e) == 3 for e in events), kind


def test_rest_only_offered_when_hurt():
    def kinds(hurt):
        p = _player()
        if hurt:
            p.hp = 100
        seen = set()
        for seed in range(60):
            random.seed(seed)
            seen |= {o['kind'] for o in generate_explore_options(p, 1, set(NAMED_EVENTS[1][i][0] for i in range(2)), 0)}
        return seen
    assert 'rest' not in kinds(False) and 'rest' in kinds(True)


def test_depth_makes_enemies_tougher_and_traps_likelier():
    def fight_level(depth):
        random.seed(3)
        opts = generate_explore_options(_player(level=8), 2, set(), depth)
        return next(o for o in opts if o['kind'] == 'fight')['enemy'].level
    assert fight_level(9) >= fight_level(0) + 2
    assert depth_effects(10)['trap_pct'] > depth_effects(0)['trap_pct']


def test_treasure_trap_risk_matches_what_is_shown():
    p = _player()
    trapped = 0
    for seed in range(400):
        random.seed(seed)
        events = resolve_option({'kind': 'treasure', 'spot': 'x', 'trap_pct': 30}, p, 1, set(), 0)
        trapped += events[0][0] == 'trap_pct'
    assert 0.22 < trapped / 400 < 0.38


def test_story_path_fires_each_named_event_once():
    seen = set()
    p = _player()
    for _ in range(len(NAMED_EVENTS[1]) + 1):
        resolve_option({'kind': 'story'}, p, 1, seen, 0)
    assert seen == {eid for eid, *_ in NAMED_EVENTS[1]}


# ── Through the web app ────────────────────────────────────────────────────────

def _client_with(state):
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    path = os.path.join(game_app.SAVE_DIR, f'{sid}.pkl')
    pickle.dump(state, open(path, 'wb'))
    return client, path


def _state(**kw):
    st = game_app.fresh_state()
    hero = _player()
    hero.profession = 'Knight'
    st.update(player=hero, quest_log=QuestLog(), screen='hub', zone=1, **kw)
    return st


def test_paths_do_not_reroll_by_backing_out():
    client, path = _client_with(_state())
    client.post('/action', data={'action': 'explore'})
    first = [o['title'] for o in pickle.load(open(path, 'rb'))['explore_options']]
    client.post('/action', data={'action': 'back'})
    client.post('/action', data={'action': 'explore'})
    assert [o['title'] for o in pickle.load(open(path, 'rb'))['explore_options']] == first


def test_taking_paths_deepens_the_trail_and_resting_resets_it(monkeypatch):
    monkeypatch.setattr(game_app, 'generate_explore_options',
                        lambda *a, **k: [{'kind': 'shrine'}, {'kind': 'rest'}, {'kind': 'mystery'}])
    monkeypatch.setattr(game_app, 'resolve_option',
                        lambda opt, *a: [('heal_pct', 30, 'rest'), ('reset_depth', 0, '')] if opt['kind'] == 'rest'
                        else [('nothing', 0, 'quiet')])
    client, path = _client_with(_state())
    client.post('/action', data={'action': 'explore'})
    for _ in range(3):
        client.post('/action', data={'action': 'choose_0'})
    assert pickle.load(open(path, 'rb'))['depth'] == 3
    page = client.get('/').get_data(as_text=True)
    assert 'Trail depth 3/' in page
    client.post('/action', data={'action': 'choose_1'})  # make camp
    assert pickle.load(open(path, 'rb'))['depth'] == 0


def test_inn_and_travel_reset_depth():
    for leave in ({'action': 'inn'}, {'action': 'world_map'}):
        client, path = _client_with(_state(depth=6))
        client.post('/action', data=leave)
        follow = {'action': 'nap'} if leave['action'] == 'inn' else {'action': 'travel_1'}
        client.post('/action', data=follow)
        assert pickle.load(open(path, 'rb'))['depth'] == 0, leave


def test_winning_a_trail_fight_returns_to_the_trail_with_deeper_loot(monkeypatch):
    from enemies import spawn_enemy
    enemy = spawn_enemy(1, 1)
    enemy.hp = 1
    seen_luck = []
    real = enemy.loot_drop
    def spy(level, lck=0, player_class=None):
        seen_luck.append(lck)
        return real(level, lck, player_class)
    enemy.loot_drop = spy
    monkeypatch.setattr(game_app, 'generate_explore_options',
                        lambda *a, **k: [{'kind': 'fight', 'enemy': enemy}])
    st = _state(depth=5)
    game_app.ensure_explore_options(st)
    st['screen'] = 'explore'
    game_app.take_explore_path(st, st['player'], st['explore_options'][0])
    assert st['screen'] == 'combat' and st['return_to'] == 'explore'
    game_app.finish_combat_victory(st)
    assert seen_luck and seen_luck[0] >= int(st['player'].lck) + 5 * world.DEPTH_LUCK
    del enemy.loot_drop  # the spy can't be pickled when the save is written below
    st['screen'] = 'combat_result'
    with game_app.app.test_request_context('/action', method='POST', data={'action': 'continue'}):
        from flask import session
        session['sid'] = '00000000-0000-4000-8000-000000000001'
        game_app.save_state(st)
        game_app.action()
        st = game_app.get_state()
    assert st['screen'] == 'explore' and st['explore_options']


def test_fight_preview_warns_about_stronger_enemies():
    from enemies import spawn_enemy
    tough = spawn_enemy(2, 12)
    tough.level = 12
    assert '⚠' in describe_option({'kind': 'fight', 'enemy': tough}, 2, player_level=8)[1]
    assert '⚠' not in describe_option({'kind': 'fight', 'enemy': tough}, 2, player_level=12)[1]
