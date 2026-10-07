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


# ── Trade professions ──────────────────────────────────────────────────────────

import crafting
from crafting import CRAFTING_RECIPES, TRADE_PROFESSIONS, craft_item
from items import Item, upgrade_cost
from player import Player


def trader(trade, cls='Warrior'):
    p = Player('T', cls)
    p.trade_profession = trade
    p.crafting_skills = {k: {'level': 20, 'xp': 0} for k in p.crafting_skills}
    p.resources = {}
    return p


def _recipe_idx(skill, name):
    return next(i for i, r in enumerate(CRAFTING_RECIPES[skill]) if r['name'] == name)


def test_every_trade_has_two_perks_and_no_name_clash_with_combat_professions():
    combat_names = {prof for profs in PROFESSIONS.values() for prof in profs}
    for name, data in TRADE_PROFESSIONS.items():
        assert len(data['perks']) == 2, name
        assert name not in combat_names, f'{name} is both a trade and a combat profession'


@pytest.mark.parametrize('trade,skill,recipe,inputs', [
    ('Blacksmith', 'Smithing', 'Iron Weapon', {'Iron Bar': 2}),
    ('Fletcher', 'Fletching', 'Oak Shortbow', {'Oak Logs': 2}),
])
def test_masterwork_crafts_rare_gear(trade, skill, recipe, inputs):
    for who, expected in ((trade, 'Rare'), ('Fisher', 'Uncommon')):
        p = trader(who)
        p.resources = dict(inputs)
        ok, _, item = craft_item(p, skill, _recipe_idx(skill, recipe))
        assert ok and item.rarity == expected, who


@pytest.mark.parametrize('trade,skill,recipe,inputs', [
    ('Alchemist', 'Herblore', 'Antidote', {'Marrentill': 1}),
    ('Fisher', 'Cooking', 'Cooked Shrimp', {'Raw Shrimp': 1}),
])
def test_double_craft(trade, skill, recipe, inputs, monkeypatch):
    monkeypatch.setattr(crafting, 'DOUBLE_CRAFT_CHANCE', 1.0)
    for who, expected in ((trade, 2), ('Blacksmith', 1)):
        p = trader(who)
        p.resources = dict(inputs)
        craft_item(p, skill, _recipe_idx(skill, recipe))
        assert len([i for i in p.inventory if i.name == recipe]) == expected, who


def test_forgemaster_upgrades_cheaper():
    sword = Item('S', 'weapon', 'Rare', 10, {'atk': 10})
    smith, other = trader('Blacksmith'), trader('Alchemist')
    g1, bar1, q1 = upgrade_cost(sword, smith)
    g0, bar0, q0 = upgrade_cost(sword, other)
    assert g1 < g0 and q1 < q0 and bar1 == bar0


def _drink(trade, category=None, effect='heal_pct'):
    p = trader(trade)
    p.hp, p.mp = 1, 0
    item = Item('X', 'consumable', 'Common', 5, effect=effect, effect_value=20)
    item.category = category
    p.add_item(item)
    p.use_consumable(item)
    return p.hp, p.mp


def test_alchemist_potions_are_stronger_but_not_food():
    assert _drink('Alchemist')[0] > _drink('Blacksmith')[0]
    assert _drink('Alchemist', 'food')[0] == _drink('Blacksmith', 'food')[0]


def test_fisher_food_heals_more_and_restores_mp():
    hp_f, mp_f = _drink('Fisher', 'food')
    hp_o, mp_o = _drink('Blacksmith', 'food')
    assert hp_f > hp_o and mp_f > 0 and mp_o == 0
    assert _drink('Fisher')[0] == _drink('Blacksmith')[0], 'potions are not food'


def test_cooked_items_are_tagged_food():
    p = trader('Blacksmith')
    p.resources = {'Raw Shrimp': 1}
    _, _, item = craft_item(p, 'Cooking', _recipe_idx('Cooking', 'Cooked Shrimp'))
    assert item.category == 'food'


def test_woodsmans_eye_halves_traps_and_forages_more():
    import world
    from conftest import make_player
    def trap_pct(trade):
        p = make_player('Rogue', level=8)
        p.trade_profession = trade
        for seed in range(40):
            random.seed(seed)
            for o in world.generate_explore_options(p, 2, set(), depth=4):
                if o['kind'] == 'treasure':
                    return o['trap_pct']
    assert trap_pct('Fletcher') == trap_pct('Fisher') // 2
    def forage(trade):
        p = make_player('Rogue', level=8)
        p.trade_profession, p.resources = trade, {}
        random.seed(1)
        world.resolve_option({'kind': 'forage', 'skill': 'Mining'}, p, 1, set(), 0)
        return sum(p.resources.values())
    assert forage('Fletcher') == forage('Fisher') + 1


def test_old_ranger_trade_is_renamed_to_fletcher():
    import pickle
    p = Player('T', 'Rogue')
    p.trade_profession = 'Ranger'
    assert pickle.loads(pickle.dumps(p)).trade_profession == 'Fletcher'
