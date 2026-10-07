"""Combat professions: every signature ability and every capstone perk must change combat."""
import random

import pytest

import combat
from abilities import PROFESSION_ABILITIES
from player import PROFESSIONS
from conftest import combat_state, make_enemy, make_player

ALL_PROFS = [(cls, prof) for cls, profs in PROFESSIONS.items() for prof in profs]
LOG = lambda k, t: None


def pro(cls, prof, perk=False, level=20):
    p = make_player(cls, level=level, profession=prof)
    if perk:
        p.prof_skills_learned = list(PROFESSIONS[cls][prof]['skills'])
    return p


def use(p, e, name, seed=0):
    idx = [a.name for a in p.get_abilities()].index(name)
    random.seed(seed)
    st = combat_state(p, e)
    combat.do_combat_turn(st, 'ability', ability_idx=idx)
    return st


@pytest.mark.parametrize('cls,prof', ALL_PROFS)
def test_every_profession_has_a_signature_and_a_perk(cls, prof):
    assert prof in PROFESSION_ABILITIES
    assert PROFESSION_ABILITIES[prof].name in [a.name for a in pro(cls, prof).get_abilities()]
    perks = [sk.get('perk') for sk in PROFESSIONS[cls][prof]['skills'] if sk.get('perk')]
    assert len(perks) == 1, 'the cost-3 skill carries exactly one perk'
    assert perks[0] in SIGNATURE_AND_PERK_TESTS


# ── Signature abilities ────────────────────────────────────────────────────────

def test_riposte_counters_when_hit():
    p, e = pro('Warrior', 'Knight'), make_enemy()
    p.buffs['Riposte'] = 3
    hp = e.hp
    combat.hit_player(p, 50, LOG, attacker=e)
    assert e.hp < hp


def test_blood_frenzy_costs_hp_and_boosts_and_heals():
    p, e = pro('Warrior', 'Berserker'), make_enemy()
    hp = p.hp
    e.stunned = True
    use(p, e, 'Blood Frenzy')
    assert 'Blood Frenzy' in p.buffs and p.hp == hp - int(p.max_hp * 0.10)
    def hit(frenzy):
        q = pro('Warrior', 'Berserker')
        if frenzy:
            q.buffs['Blood Frenzy'] = 3
        q.hp = q.max_hp // 2
        x = make_enemy()
        random.seed(4)
        combat._player_attack(q, x, LOG)
        return x.max_hp - x.hp, q.hp
    (plain_dmg, plain_hp), (frenzy_dmg, frenzy_hp) = hit(False), hit(True)
    assert frenzy_dmg > plain_dmg and frenzy_hp > plain_hp


def test_rallying_strike_heals():
    p, e = pro('Warrior', 'Champion'), make_enemy()
    p.hp = p.max_hp // 2
    e.stunned = True
    hp = p.hp
    use(p, e, 'Rallying Strike')
    assert p.hp > hp and e.hp < e.max_hp


def test_arcane_overload_outhits_meteor():
    def dmg(name):
        p, e = pro('Mage', 'Sorcerer'), make_enemy()
        e.stunned = True
        use(p, e, name, seed=2)
        return e.max_hp - e.hp
    assert dmg('Arcane Overload') > dmg('Meteor')


def test_convergence_doubles_on_burning_or_chilled():
    def dmg(status):
        p, e = pro('Mage', 'Elementalist'), make_enemy()
        e.stunned = True
        if status == 'chilled':
            e.statuses['Chilled'] = 3
        before = e.hp
        st = use(p, e, 'Convergence', seed=7)
        return any('CONVERGENCE' in l['text'] for l in st['combat_log'])
    assert dmg('chilled') and not dmg(None)


def test_soul_harvest_heals_from_damage():
    p, e = pro('Mage', 'Necromancer'), make_enemy()
    p.hp = p.max_hp // 3
    e.stunned = True
    hp = p.hp
    use(p, e, 'Soul Harvest')
    assert p.hp > hp


def test_shadowstrike_always_crits_on_wounded_targets():
    for seed in range(10):
        p, e = pro('Rogue', 'Assassin'), make_enemy(hp_frac=0.3)
        e.stunned = True
        st = use(p, e, 'Shadowstrike', seed=seed)
        assert any('CRITICAL' in l['text'] for l in st['combat_log'])


def test_volley_fires_three_arrows():
    p, e = pro('Rogue', 'Ranger'), make_enemy()
    e.stunned = True
    st = use(p, e, 'Volley')
    assert sum(l['text'].startswith('Volley:') for l in st['combat_log']) == 3


def test_blinding_powder_makes_the_enemy_miss():
    p, e = pro('Rogue', 'Trickster'), make_enemy()
    e.stunned = True
    use(p, e, 'Blinding Powder')
    assert 'Blinded' in e.statuses
    misses = 0
    for seed in range(200):
        random.seed(seed)
        misses += combat._enemy_hit(pro('Rogue', 'Trickster'), e, 1.0, LOG, False) == 0
    assert 50 < misses < 110  # ~40% of 200


# ── Capstone perks ─────────────────────────────────────────────────────────────

def test_bastion_defend_blocks_more():
    assert combat.hit_player(pro('Warrior', 'Knight', perk=True), 100, LOG, defending=True) == 25
    assert combat.hit_player(pro('Warrior', 'Knight'), 100, LOG, defending=True) == 50


def test_undying_rage_raises_the_rage_threshold():
    assert combat.rage_threshold(pro('Warrior', 'Berserker', perk=True)) == 0.5
    assert combat.rage_threshold(pro('Warrior', 'Berserker')) == 0.3


def test_momentum_builds_and_resets_on_defend():
    p, e = pro('Warrior', 'Champion', perk=True), make_enemy()
    e.stunned = True
    st = combat_state(p, e)
    for _ in range(3):
        e.stunned = True
        combat.do_combat_turn(st, 'attack')
    assert p.momentum == 3
    combat.do_combat_turn(st, 'defend')
    assert p.momentum == 0
    q = pro('Warrior', 'Champion')
    combat.do_combat_turn(combat_state(q, make_enemy()), 'attack')
    assert q.momentum == 0, 'no perk, no momentum'


def test_spellweaver_crits_more():
    def crits(perk):
        n = 0
        for seed in range(150):
            p, e = pro('Mage', 'Sorcerer', perk=perk), make_enemy()
            e.stunned = True
            n += any('CRITICAL' in l['text'] for l in use(p, e, 'Fireball', seed)['combat_log'])
        return n
    assert crits(True) > crits(False) + 10


def test_wildfire_burns_more_often():
    def burns(perk):
        n = 0
        for seed in range(150):
            p, e = pro('Mage', 'Elementalist', perk=perk), make_enemy()
            e.stunned = True
            use(p, e, 'Arcane Surge', seed)
            n += e.dot > 0
        return n
    assert burns(True) > burns(False) + 15


def test_deathless_saves_once_per_fight():
    p, e = pro('Mage', 'Necromancer', perk=True), make_enemy()
    e.stunned = True
    p.hp = int(p.max_hp * 0.2)
    combat.do_combat_turn(combat_state(p, e), 'defend')
    assert p.hp > p.max_hp * 0.4 and p.deathless_used
    combat.end_combat(p)
    assert not p.deathless_used


def test_exploit_weakness_hits_afflicted_enemies_harder():
    def dmg(perk, afflicted):
        p, e = pro('Rogue', 'Assassin', perk=perk), make_enemy()
        if afflicted:
            e.dot, e.dot_dmg = 3, 1
        random.seed(9)
        combat._player_attack(p, e, LOG)
        return e.max_hp - e.hp
    assert dmg(True, True) > dmg(True, False)
    assert dmg(False, True) == dmg(False, False)


def test_hunters_mark_bigger_first_strike_that_bleeds():
    def strike(perk):
        p, e = pro('Rogue', 'Ranger', perk=perk), make_enemy()
        random.seed(5)
        combat._player_attack(p, e, LOG)
        return e.max_hp - e.hp, e.dot
    (d0, bleed0), (d1, bleed1) = strike(False), strike(True)
    assert d1 > d0 and bleed1 > 0 and bleed0 == 0


def test_stacking_venom_stacks_poison():
    p, e = pro('Rogue', 'Trickster', perk=True), make_enemy()
    e.stunned = True
    use(p, e, 'Poison Blade')
    first = e.dot_dmg
    e.stunned = True
    use(p, e, 'Poison Blade')
    assert e.dot_dmg > first
    q, x = pro('Rogue', 'Trickster'), make_enemy()
    x.stunned = True
    use(q, x, 'Poison Blade')
    single = x.dot_dmg
    x.stunned = True
    use(q, x, 'Poison Blade')
    assert x.dot_dmg == single


SIGNATURE_AND_PERK_TESTS = {'Bastion', 'Undying Rage', 'Momentum', 'Spellweaver', 'Wildfire', 'Deathless',
                            'Exploit Weakness', "Hunter's Mark", 'Stacking Venom'}
