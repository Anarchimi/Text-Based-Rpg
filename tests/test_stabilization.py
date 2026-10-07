"""Regression tests for the stabilization pass (Inn economics, Arcane Flow, multi-hit deaths, Bastion text)."""
import random

import pytest

import combat
from enemies import ENEMY_ABILITIES
from items import Item
from conftest import combat_state, make_enemy, make_player
from test_professions import pro

LOG = lambda k, t: None


# ── 2. Arcane Flow must not give zero-cost abilities an MP cost ────────────────

def _arcane(p):
    ring = Item('Ring', 'accessory', 'Legendary', 1, {})
    ring.legendary = 'Arcane Flow'
    p.add_item(ring)
    p.equip(ring)
    return p


def test_arcane_flow_keeps_zero_cost_abilities_free():
    p = _arcane(pro('Warrior', 'Berserker'))
    frenzy = next(a for a in p.get_abilities() if a.name == 'Blood Frenzy')
    assert frenzy.mp_cost == 0 and combat.ability_cost(p, frenzy) == 0
    p.mp = 0
    e = make_enemy()
    e.stunned = True
    idx = [a.name for a in p.get_abilities()].index('Blood Frenzy')
    combat.do_combat_turn(combat_state(p, e), 'ability', ability_idx=idx)
    assert 'Blood Frenzy' in p.buffs, 'castable with 0 MP'


def test_arcane_flow_still_discounts_mp_abilities():
    p = _arcane(pro('Warrior', 'Berserker'))
    slash = next(a for a in p.get_abilities() if a.name == 'Slash')
    assert 0 < combat.ability_cost(p, slash) < slash.mp_cost


# ── 3. A multi-hit attacker killed mid-sequence stops hitting ──────────────────

MULTI_HIT = sorted(n for n, spec in ENEMY_ABILITIES.items() if spec.get('hits', 1) > 1)


@pytest.mark.parametrize('name', MULTI_HIT)
@pytest.mark.parametrize('retaliation', ['Riposte', 'Thorns'])
def test_retaliation_kill_stops_a_multi_hit_attack(name, retaliation):
    p = make_player('Warrior', profession='Knight')
    if retaliation == 'Riposte':
        p.buffs['Riposte'] = 3
    else:
        ring = Item('Ring', 'accessory', 'Legendary', 1, {})
        ring.legendary = 'Thorns'
        p.add_item(ring)
        p.equip(ring)
    e = make_enemy()
    e.atk = 100
    e.hp = 1  # dies to the first retaliation
    log = []
    random.seed(0)
    combat._enemy_ability(p, e, name, ENEMY_ABILITIES[name], lambda k, t: log.append(t), False)
    assert not e.is_alive()
    hp_lost_lines = [t for t in log if t.startswith('-') and t.endswith('HP')]
    assert p.max_hp - p.hp == int(hp_lost_lines[0][1:-3]), 'only the first hit landed'
    retaliations = [t for t in log if t.startswith(('Riposte', 'Thorns'))]
    assert len(retaliations) == 1, f'{name}: attacker kept hitting after dying: {log}'


def test_retaliation_kill_mid_multi_hit_ends_the_fight_as_a_victory():
    p = make_player('Warrior', profession='Knight')
    p.buffs['Riposte'] = 3
    e = make_enemy()
    e.abilities = ['Bat Swarm']
    e.hp = 1
    from combat import ENEMY_ABILITY_CHANCE
    combat.ENEMY_ABILITY_CHANCE = 1.0
    try:
        random.seed(0)
        result = combat.do_combat_turn(combat_state(p, e), 'defend')
    finally:
        combat.ENEMY_ABILITY_CHANCE = ENEMY_ABILITY_CHANCE
    assert result == 'victory'


# ── 4. Defend text matches the actual mitigation ──────────────────────────────

@pytest.mark.parametrize('perk,text', [(False, '50%'), (True, '75%')])
def test_defend_log_states_the_real_reduction(perk, text):
    p = pro('Warrior', 'Knight', perk=perk)
    e = make_enemy()
    e.stunned = True
    st = combat_state(p, e)
    combat.do_combat_turn(st, 'defend')
    guard = next(l['text'] for l in st['combat_log'] if 'raise your guard' in l['text'])
    assert text in guard and ('half damage' not in guard if perk else True)


# ── 1. Inn: naps restore half of what's missing; repeated naps can't undercut Full Rest ──

import app as game_app


def _hurt(level, hp_frac=0.1, mp_frac=0.1):
    p = make_player('Warrior', level=level)
    p.max_hp, p.max_mp = 400 + level * 20, 100 + level * 10
    p.hp, p.mp = int(p.max_hp * hp_frac), int(p.max_mp * mp_frac)
    return p


def test_nap_restores_half_of_the_missing_amount():
    p = _hurt(10)
    missing_hp, missing_mp = p.max_hp - p.hp, p.max_mp - p.mp
    hp, mp = game_app.nap_restore(p)
    assert hp == -(-missing_hp // 2) and mp == -(-missing_mp // 2)


@pytest.mark.parametrize('level', [1, 5, 10, 15, 19])
@pytest.mark.parametrize('hurt', [0.05, 0.3, 0.6])
def test_repeated_naps_never_beat_full_rest(level, hurt):
    p = _hurt(level, hurt, hurt)
    full_price = game_app.inn_prices(p)[0]
    spent, naps = 0, 0
    while not game_app.fully_rested(p):
        spent += game_app.inn_prices(p)[1]
        hp, mp = game_app.nap_restore(p)
        p.hp += hp
        p.mp += mp
        naps += 1
        assert naps < 50, 'naps must converge to full'
    assert spent > full_price, f'{naps} naps cost {spent}g < full rest {full_price}g'


@pytest.mark.parametrize('level', [1, 10, 19])
def test_one_nap_is_cheaper_than_full_rest(level):
    full, nap = game_app.inn_prices(_hurt(level))
    assert nap < full


def test_fully_rested_inn_offers_no_paid_rest():
    import os, pickle
    from quests import QuestLog
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    st = game_app.fresh_state()
    p = make_player('Warrior')
    p.gold = 500
    st.update(player=p, quest_log=QuestLog(), screen='inn')
    pickle.dump(st, open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'wb'))
    page = client.get('/').get_data(as_text=True)
    assert 'fully rested' in page
    assert 'value="full_rest"' not in page and 'value="nap"' not in page
    client.post('/action', data={'action': 'nap'})  # a crafted POST still can't charge
    assert pickle.load(open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'rb'))['player'].gold == 500
