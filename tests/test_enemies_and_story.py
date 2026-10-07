"""Enemy abilities, status effects, boss phases, the Five Seals, the ending and NG+."""
import os
import random
import sys

import pytest

import app as game_app
import combat
from enemies import (BOSS_TEMPLATES, ENEMY_ABILITIES, ENEMY_TEMPLATES, FINAL_BOSS,
                     ability_spec, spawn_enemy, spawn_final_boss)
from conftest import combat_state, make_enemy, make_player

ALL_ENEMIES = ENEMY_TEMPLATES + BOSS_TEMPLATES + [FINAL_BOSS]


def _log():
    out = []
    return out, lambda kind, text: out.append(text)


def _use(name, player=None, enemy=None, defending=False, seed=0):
    player = player or make_player('Warrior')
    enemy = enemy or make_enemy()
    enemy.atk = 100
    log, clog = _log()
    random.seed(seed)
    combat._enemy_ability(player, enemy, name, ability_spec(name), clog, defending)
    return player, enemy, log


# ── Enemy abilities ────────────────────────────────────────────────────────────

def test_every_enemy_ability_has_a_spec():
    names = {a for t in ALL_ENEMIES for a in t['abilities']}
    assert names <= set(ENEMY_ABILITIES), f'abilities with no effect defined: {names - set(ENEMY_ABILITIES)}'


@pytest.mark.parametrize('name', sorted(ENEMY_ABILITIES))
def test_every_enemy_ability_does_something(name):
    """Each ability must change the player or the enemy — no flavour-text-only moves."""
    spec = ability_spec(name)
    if spec['kind'] == 'stun':
        spec = dict(spec, chance=1.0)
        ENEMY_ABILITIES[name], original = spec, ENEMY_ABILITIES[name]
    try:
        p, e, _ = _use(name)
    finally:
        if spec['kind'] == 'stun':
            ENEMY_ABILITIES[name] = original
    changed = p.hp < p.max_hp or p.debuffs or e.statuses
    assert changed, f'{name} had no effect'


def test_drain_heals_the_enemy():
    e = make_enemy()
    e.hp = e.max_hp // 2
    before = e.hp
    _use('Drain Life', enemy=e)
    assert e.hp > before


def test_dot_ticks_and_antidote_cures():
    p, _, _ = _use('Poison Blade')
    assert 'Poisoned' in p.debuffs
    hp = p.hp
    ticks, _ = p.tick_debuffs()
    assert ticks and p.hp < hp
    from items import Item
    antidote = Item('Antidote', 'consumable', 'Common', 10, effect='cure')
    p.add_item(antidote)
    p.use_consumable(antidote)
    assert not p.debuffs


def test_weaken_lowers_attack():
    p = make_player('Warrior')
    atk = p.attack
    _use('Soul Rend', player=p)
    assert p.attack < atk


def test_stun_skips_the_players_turn_and_grants_immunity():
    p = make_player('Warrior')
    p.debuffs['Stunned'] = {'turns': 1, 'dmg': 0}
    e = make_enemy()
    hp = e.hp
    st = combat_state(p, e)
    combat.do_combat_turn(st, 'attack')
    assert e.hp == hp, 'a stunned player must not act'
    assert 'Steadfast' in p.buffs
    ENEMY_ABILITIES['Cheap Shot'], orig = dict(ENEMY_ABILITIES['Cheap Shot'], chance=1.0), ENEMY_ABILITIES['Cheap Shot']
    try:
        _use('Cheap Shot', player=p)
    finally:
        ENEMY_ABILITIES['Cheap Shot'] = orig
    assert 'Stunned' not in p.debuffs, 'Steadfast should block an immediate re-stun'


def test_defend_halves_damage_and_blocks_stuns():
    plain = make_player('Warrior')
    braced = make_player('Warrior')
    log, clog = _log()
    assert combat.hit_player(braced, 100, clog, defending=True) == 50
    assert combat.hit_player(plain, 100, clog) == 100
    ENEMY_ABILITIES['Cheap Shot'], orig = dict(ENEMY_ABILITIES['Cheap Shot'], chance=1.0), ENEMY_ABILITIES['Cheap Shot']
    try:
        p, _, _ = _use('Cheap Shot', defending=True)
    finally:
        ENEMY_ABILITIES['Cheap Shot'] = orig
    assert 'Stunned' not in p.debuffs


def test_enemy_evade_dodges_the_next_hit():
    e = make_enemy()
    e.statuses['Evading'] = 3
    hp = e.hp
    log, clog = _log()
    combat._player_attack(make_player('Warrior'), e, clog)
    assert e.hp == hp and 'Evading' not in e.statuses


def test_shielded_enemy_takes_half_damage():
    a, b = make_enemy(), make_enemy()
    b.statuses['Shielded'] = 2
    assert b.take_damage(100) == a.take_damage(100) // 2


def test_ice_lance_chills():
    p = make_player('Mage')
    e = make_enemy()
    idx = [a.name for a in p.get_abilities()].index('Ice Lance')
    random.seed(0)
    combat.do_combat_turn(combat_state(p, e), 'ability', ability_idx=idx)
    assert 'Chilled' in e.statuses


# ── Telegraphs and boss phases ─────────────────────────────────────────────────

def _charging_boss():
    e = spawn_final_boss(19)
    e.charging = 'World Ender'
    return e


def test_telegraphed_attack_fires_next_turn():
    p = make_player('Warrior')
    e = _charging_boss()
    random.seed(1)
    combat.do_combat_turn(combat_state(p, e), 'item', item_idx=None)
    assert e.charging is None and p.hp < p.max_hp


def test_defending_against_a_telegraph_halves_it():
    def damage_taken(action):
        p = make_player('Warrior')
        random.seed(1)
        combat.do_combat_turn(combat_state(p, _charging_boss()), action, item_idx=None)
        return p.max_hp - p.hp
    assert damage_taken('defend') < damage_taken('item') * 0.6


def test_stun_interrupts_a_telegraph():
    p = make_player('Warrior')
    e = _charging_boss()
    e.stunned = True
    combat.do_combat_turn(combat_state(p, e), 'item', item_idx=None)
    assert e.charging is None and p.hp == p.max_hp


def test_boss_enters_phase_two_below_half_hp():
    e = spawn_enemy(1, 5, force_boss=True)
    e.hp = e.max_hp // 2 - 1
    st = combat_state(make_player('Warrior'), e)
    random.seed(0)
    combat.do_combat_turn(st, 'item', item_idx=None)
    assert e.phase == 2
    assert any('second phase' in l['text'] for l in st['combat_log'])


# ── Story: seals, final battle, ending, New Game+ ──────────────────────────────

def test_every_zone_has_its_own_boss():
    assert sorted(b['zone'] for b in BOSS_TEMPLATES) == [1, 2, 3, 4, 5]
    for zone in range(1, 6):
        assert spawn_enemy(zone, 10, force_boss=True).seal == zone
    assert spawn_final_boss(19).is_final


def _victory_state(enemy, zone):
    from quests import QuestLog
    st = game_app.fresh_state()
    st.update(player=make_player('Warrior'), quest_log=QuestLog(), zone=zone,
              combat_enemy=enemy, combat_log=[], screen='combat')
    st['player'].profession = 'Knight'  # skip the level-5 profession prompt
    return st


def test_seals_break_once_each_in_any_order():
    st = _victory_state(spawn_enemy(3, 12, force_boss=True), 3)
    game_app.finish_combat_victory(st)
    assert st['seals'] == {3} and st['narrative_stage'] == 1
    st['combat_enemy'] = spawn_enemy(3, 12, force_boss=True)
    game_app.finish_combat_victory(st)
    assert st['narrative_stage'] == 1, 'killing the same boss twice breaks no extra seal'


def test_final_battle_needs_five_seals_and_dragons_peak():
    st = _victory_state(None, 5)
    st['seals'] = {1, 2, 3, 4}
    assert not game_app.final_battle_available(st)
    st['seals'].add(5)
    assert game_app.final_battle_available(st)
    st['zone'] = 4
    assert not game_app.final_battle_available(st)


def test_killing_the_dragon_lord_shows_the_ending_and_ng_plus_resets():
    st = _victory_state(spawn_final_boss(19), 5)
    st['seals'] = {1, 2, 3, 4, 5}
    game_app.finish_combat_victory(st)
    assert st['screen'] == 'ending' and st['dragon_slain']

    level = st['player'].level
    game_app.start_new_game_plus(st)
    assert st['ng_plus'] == 1 and st['seals'] == set() and not st['dragon_slain']
    assert st['player'].level == level, 'NG+ keeps the character'
    assert st['screen'] == 'hub'


def test_ng_plus_makes_enemies_stronger():
    random.seed(0)
    base = spawn_final_boss(19)
    harder = spawn_final_boss(19, ng=2)
    assert harder.max_hp > base.max_hp and harder.atk > base.atk


def test_old_saves_are_migrated():
    st = game_app.fresh_state()
    for key in ('seals', 'ng_plus', 'dragon_slain'):
        del st[key]
    st['narrative_stage'] = 2
    st = game_app.migrate_state(st)
    assert st['seals'] == {1, 2} and st['ng_plus'] == 0


# ── Balance regression: the endgame must stay beatable ─────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))


@pytest.mark.parametrize('cls', ['Warrior', 'Mage', 'Rogue'])
def test_final_boss_is_beatable_with_good_gear(cls):
    import balance_sim
    win_rate, _, _ = balance_sim.scenario(cls, 19, lambda: spawn_final_boss(19), 30,
                                          rarity='Epic', potions=5)
    assert win_rate >= 0.4, f'{cls} beats the final boss only {win_rate:.0%} of the time'


@pytest.mark.parametrize('cls', ['Warrior', 'Mage', 'Rogue'])
def test_regular_fights_are_not_one_shots(cls):
    import balance_sim
    _, turns, _ = balance_sim.scenario(cls, 1, lambda: spawn_enemy(1, 1), 30, potions=0, antidotes=0)
    assert turns >= 2, f'{cls} kills zone-1 enemies in {turns:.1f} turns'


def test_stun_from_an_enemy_turn_lasts_until_the_players_next_turn(monkeypatch):
    """The stun lands during the enemy phase and must survive the end-of-round tick."""
    p = make_player('Warrior')
    e = make_enemy()
    e.abilities = ['Cheap Shot']
    monkeypatch.setitem(ENEMY_ABILITIES, 'Cheap Shot', dict(ENEMY_ABILITIES['Cheap Shot'], chance=1.0))
    monkeypatch.setattr(combat, 'ENEMY_ABILITY_CHANCE', 1.0)
    st = combat_state(p, e)
    combat.do_combat_turn(st, 'item', item_idx=None)   # enemy stuns us
    assert 'Stunned' in p.debuffs
    hp = e.hp
    combat.do_combat_turn(st, 'attack')                 # our attack is skipped
    assert e.hp == hp
