"""Every ability and profession passive must actually change combat.

These guard against the "described but never implemented" bugs that shipped
for the Assassin passive and the Battle Cry / Mana Shield / Evasion buffs.
"""
import random
import re

import pytest

import app as game_app
from abilities import CLASS_ABILITIES
from player import PROFESSIONS
from conftest import ability_index, combat_state, make_enemy, make_player

BUFFS = [(cls, a.name) for cls, abilities in CLASS_ABILITIES.items()
         for a in abilities if a.ability_type == 'buff']


def _enemy_phase_outcome(player, seed):
    """Run one turn where the player does nothing, so only the enemy acts."""
    enemy = make_enemy()
    enemy.atk = 200  # well above player defense so damage is never the 1-dmg floor
    random.seed(seed)
    game_app.do_combat_turn(combat_state(player, enemy), 'item', item_idx=None)
    return player.hp, player.mp


@pytest.mark.parametrize('cls,name', BUFFS)
def test_every_buff_changes_something(cls, name):
    differs = False
    for seed in range(20):
        plain = make_player(cls)
        buffed = make_player(cls)
        buffed.buffs[name] = 3
        if (plain.attack, plain.defense) != (buffed.attack, buffed.defense):
            differs = True
            break
        if _enemy_phase_outcome(plain, seed) != _enemy_phase_outcome(buffed, seed):
            differs = True
            break
    assert differs, f'{cls} buff {name!r} has no effect on stats or incoming damage'


def test_battle_cry_raises_attack_20pct():
    p = make_player('Warrior')
    base = p.attack
    p.buffs['Battle Cry'] = 3
    assert p.attack == int(base * 1.2)


def test_evasion_dodges_one_hit_then_expires():
    p = make_player('Rogue')
    p.buffs['Evasion'] = 3
    log = []
    clog = lambda k, t: log.append(t)
    assert game_app.hit_player(p, 50, clog) == 0
    assert 'Evasion' not in p.buffs
    assert game_app.hit_player(p, 50, clog) == 50


def test_mana_shield_moves_half_the_damage_to_mp():
    p = make_player('Mage')
    p.buffs['Mana Shield'] = 3
    hp, mp = p.hp, p.mp
    lost = game_app.hit_player(p, 50, lambda k, t: None)
    assert lost == 25 and p.hp == hp - 25 and p.mp == mp - 25


def test_mana_shield_without_mp_absorbs_nothing():
    p = make_player('Mage')
    p.buffs['Mana Shield'] = 3
    p.mp = 0
    assert game_app.hit_player(p, 50, lambda k, t: None) == 50


def test_shield_bash_can_stun(monkeypatch):
    p = make_player('Warrior')
    e = make_enemy()
    bash = next(a for a in p.get_abilities() if a.name == 'Shield Bash')
    monkeypatch.setattr(bash, 'status_chance', 1.0)
    st = combat_state(p, e)
    random.seed(0)
    idx = ability_index(p, 'Shield Bash')
    game_app.do_combat_turn(st, 'ability', ability_idx=idx)
    assert any('stunned' in l['text'] for l in st['combat_log'])


# ── Profession passives ────────────────────────────────────────────────────────

def _ability_damage(cls, profession, ability, hp_frac=1.0, seed=1):
    p = make_player(cls, profession=profession)
    e = make_enemy(hp_frac)
    before = e.hp
    random.seed(seed)
    st = combat_state(p, e)
    game_app.do_combat_turn(st, 'ability', ability_idx=ability_index(p, ability))
    return before - e.hp - _dot_damage(st)


def _dot_damage(st):
    total = 0
    for l in st['combat_log']:
        m = re.match(r'(?:Poison|Burn) deals (\d+)', l['text'])
        if m:
            total += int(m.group(1))
    return total


def test_sorcerer_boosts_spell_damage():
    assert _ability_damage('Mage', 'Sorcerer', 'Meteor') > _ability_damage('Mage', None, 'Meteor')


def test_necromancer_boosts_damage_on_wounded_enemy():
    assert (_ability_damage('Mage', 'Necromancer', 'Meteor', hp_frac=0.4)
            > _ability_damage('Mage', None, 'Meteor', hp_frac=0.4))


def test_berserker_rage_when_low_hp():
    def dmg(prof):
        p = make_player('Warrior', profession=prof)
        p.hp = int(p.max_hp * 0.2)
        e = make_enemy()
        random.seed(3)
        game_app.do_combat_turn(combat_state(p, e), 'ability', ability_idx=ability_index(p, 'Slash'))
        return e.max_hp - e.hp
    assert dmg('Berserker') > dmg(None)


def test_assassin_death_mark_multiplier():
    plain = _ability_damage('Rogue', None, 'Death Mark')
    assassin = _ability_damage('Rogue', 'Assassin', 'Death Mark')
    wounded = _ability_damage('Rogue', 'Assassin', 'Death Mark', hp_frac=0.3)
    assert plain < assassin < wounded


def test_trickster_poison_lasts_longer():
    def dot(prof):
        p = make_player('Rogue', profession=prof)
        e = make_enemy()
        random.seed(2)
        game_app.do_combat_turn(combat_state(p, e), 'ability', ability_idx=ability_index(p, 'Poison Blade'))
        return e.dot
    assert dot('Trickster') > dot(None)


def test_elementalist_can_burn():
    burned = False
    for seed in range(40):
        p = make_player('Mage', profession='Elementalist')
        e = make_enemy()
        random.seed(seed)
        game_app.do_combat_turn(combat_state(p, e), 'ability', ability_idx=ability_index(p, 'Fireball'))
        burned = burned or e.dot > 0
    assert burned


def test_ranger_flee_always_succeeds():
    for seed in range(10):
        p = make_player('Rogue', profession='Ranger')
        e = make_enemy()
        e.atk = 10_000  # makes normal flee impossible
        random.seed(seed)
        assert game_app.do_combat_turn(combat_state(p, e), 'flee') == 'fled'


def test_ranger_first_strike():
    def dmg(prof):
        p = make_player('Rogue', profession=prof)
        e = make_enemy()
        random.seed(4)
        game_app.do_combat_turn(combat_state(p, e), 'attack')
        return e.max_hp - e.hp
    assert dmg('Ranger') > dmg(None)


@pytest.mark.parametrize('prof,stat', [('Knight', 'defense'), ('Champion', 'attack'),
                                       ('Champion', 'defense')])
def test_stat_passives(prof, stat):
    def player(profession):
        p = make_player('Warrior', profession=profession)
        p.base_str = p.base_vit = 100  # big enough that a 10% bonus survives int()
        return p
    assert getattr(player(prof), stat) > getattr(player(None), stat)


def test_every_profession_is_covered():
    covered = {'Sorcerer', 'Necromancer', 'Berserker', 'Assassin', 'Trickster',
               'Elementalist', 'Ranger', 'Knight', 'Champion'}
    all_profs = {name for profs in PROFESSIONS.values() for name in profs}
    assert all_profs == covered, f'new profession(s) without a passive test: {all_profs - covered}'
