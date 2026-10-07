"""Gear: slots, bonus stats, rarity, luck, legendary effects and the item UI."""
import random

import pytest

import combat
from items import (AFFIX_COUNT, GEAR_SLOTS, LEGENDARY_EFFECTS, RARITIES, Item, generate_accessory,
                   generate_armor, generate_loot, generate_weapon)
from player import Player
from conftest import combat_state, make_enemy, make_player

GENERATORS = {
    'weapon':    lambda r, cls=None: generate_weapon(cls, 10, r),
    'armor':     lambda r, cls=None: generate_armor(10, r, cls),
    'accessory': lambda r, cls=None: generate_accessory(10, r, cls),
}
BASE = {'weapon': 1, 'armor': 1, 'accessory': 0}  # atk / def / none


@pytest.mark.parametrize('slot', GEAR_SLOTS)
@pytest.mark.parametrize('rarity', RARITIES)
def test_bonus_stat_count_follows_rarity(slot, rarity):
    random.seed(1)
    item = GENERATORS[slot](rarity)
    extra = 1 if slot == 'accessory' else 0
    assert len(item.stats) == BASE[slot] + AFFIX_COUNT[rarity] + extra
    assert (item.legendary is not None) == (rarity == 'Legendary')


def test_bonus_stats_lean_toward_the_class_main_stat():
    random.seed(2)
    mage_int = sum('int' in generate_weapon('Mage', 10, 'Uncommon').stats for _ in range(300))
    mage_str = sum('str' in generate_weapon('Mage', 10, 'Uncommon').stats for _ in range(300))
    assert mage_int > 2 * mage_str


def test_luck_raises_loot_rarity():
    def avg_rarity(luck):
        random.seed(3)
        gear = [i for _ in range(600) for i in generate_loot(10, luck, 1) if i.item_type != 'consumable']
        return sum(RARITIES.index(i.rarity) for i in gear) / len(gear)
    assert avg_rarity(60) > avg_rarity(0) + 0.3


def test_equipped_bonus_stats_count_and_unequipping_removes_them():
    p = Player('T', 'Warrior')
    base = {s: getattr(p, s) for s in ('str', 'dex', 'int', 'vit', 'lck', 'max_hp', 'max_mp', 'speed')}
    ring = Item('Test Ring', 'accessory', 'Epic', 10,
                {'str': 5, 'dex': 4, 'int': 3, 'vit': 2, 'lck': 1, 'hp': 30, 'mp': 20, 'spd': 6, 'crit': 5})
    p.add_item(ring)
    p.equip(ring)
    assert p.str == base['str'] + 5 and p.dex == base['dex'] + 4 and p.int == base['int'] + 3
    assert p.vit == base['vit'] + 2 and p.lck == base['lck'] + 1
    assert p.max_hp == base['max_hp'] + 30 and p.max_mp == base['max_mp'] + 20
    assert p.speed >= base['speed'] + 6 and p.crit_bonus == 0.05
    plain = Item('Plain Ring', 'accessory', 'Common', 1, {})
    p.add_item(plain)
    p.equip(plain)
    assert {s: getattr(p, s) for s in base} == base


def test_old_saves_get_an_accessory_slot():
    import pickle
    p = Player('T', 'Rogue')
    del p.equipment['accessory']
    q = pickle.loads(pickle.dumps(p))
    assert q.equipment['accessory'] is None
    assert q.gear_stat('str') == 0


# ── Legendary effects: each must change combat ─────────────────────────────────

def _with(effect, cls='Warrior'):
    p = make_player(cls)
    item = Item('L', 'accessory', 'Legendary', 1, {})
    item.legendary = effect
    p.add_item(item)
    p.equip(item)
    return p


def test_every_legendary_effect_has_a_test():
    tested = {'Vampiric', 'Thorns', 'Executioner', 'Arcane Flow', 'Bulwark', 'Second Wind'}
    assert set(LEGENDARY_EFFECTS) == tested


def test_vampiric_heals_on_hit():
    p = _with('Vampiric')
    p.hp = p.max_hp // 2
    hp = p.hp
    combat._player_attack(p, make_enemy(), lambda k, t: None)
    assert p.hp > hp


def test_thorns_reflects_damage():
    p, e = _with('Thorns'), make_enemy()
    hp = e.hp
    combat.hit_player(p, 100, lambda k, t: None, attacker=e)
    assert e.hp == hp - 20


def test_executioner_hits_harder_on_wounded_enemies():
    def dmg(effect):
        p = _with(effect) if effect else make_player('Warrior')
        e = make_enemy(hp_frac=0.2)
        before = e.hp
        random.seed(5)
        combat._player_attack(p, e, lambda k, t: None)
        return before - e.hp
    assert dmg('Executioner') > dmg(None)


def test_arcane_flow_discounts_abilities():
    p = _with('Arcane Flow', 'Mage')
    meteor = next(a for a in p.get_abilities() if a.name == 'Meteor')
    assert combat.ability_cost(p, meteor) < meteor.mp_cost
    p.mp = 1000
    combat._player_ability(p, make_enemy(), meteor, lambda k, t: None)
    assert p.mp == 1000 - combat.ability_cost(p, meteor)


def test_bulwark_heals_when_defending():
    p = _with('Bulwark')
    p.hp = p.max_hp // 2
    e = make_enemy()
    e.stunned = True  # keep the enemy from hitting back
    hp = p.hp
    combat.do_combat_turn(combat_state(p, e), 'defend')
    assert p.hp > hp


def test_second_wind_saves_once_per_fight():
    p = _with('Second Wind')
    e = make_enemy()
    e.atk = 10 ** 7
    st = combat_state(p, e)
    random.seed(0)
    assert combat.do_combat_turn(st, 'item', item_idx=None) == 'continue' and p.hp == 1
    assert combat.do_combat_turn(st, 'item', item_idx=None) == 'defeat'
    combat.end_combat(p)
    assert not p.second_wind_used


# ── UI ─────────────────────────────────────────────────────────────────────────

def test_selling_gear_sells_that_item(tmp_path):
    """The sell button used to assume consumables come first in the inventory."""
    import pickle, os
    import app as game_app
    from quests import QuestLog
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    p = make_player('Warrior')
    sword = Item('Sword To Sell', 'weapon', 'Common', 50, {'atk': 5})
    potion = Item('Health Potion', 'consumable', 'Common', 10, effect='heal_pct', effect_value=25)
    p.inventory = [sword, potion]  # gear before consumable
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='inventory')
    pickle.dump(st, open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'wb'))
    page = client.get('/').get_data(as_text=True)
    import re
    sell = re.search(r'Sword To Sell.*?value="(sell_\d+)"', page, re.S).group(1)
    client.post('/action', data={'action': sell})
    st = pickle.load(open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'rb'))
    assert [i.name for i in st['player'].inventory] == ['Health Potion']


def test_inventory_shows_comparison_and_legendary_text():
    import pickle, os
    import app as game_app
    from quests import QuestLog
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    p = make_player('Warrior')
    p.equipment['weapon'] = Item('Old Sword', 'weapon', 'Common', 5, {'atk': 10})
    new = Item('New Sword', 'weapon', 'Legendary', 5, {'atk': 25, 'str': 4})
    new.legendary = 'Vampiric'
    p.inventory = [new]
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='inventory')
    pickle.dump(st, open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'wb'))
    page = client.get('/').get_data(as_text=True)
    assert '+15 ATK' in page and '+4 STR' in page and 'gains Vampiric' in page
    assert LEGENDARY_EFFECTS['Vampiric'][1] in page


def test_permanent_and_revive_consumables_are_not_pocket_change():
    from items import CONSUMABLE_NAMES, generate_consumable
    random.seed(0)
    seen = {}
    for _ in range(400):
        c = generate_consumable()
        seen[c.effect] = c.value
    assert seen['buff_str'] >= 300 and seen['buff_int'] >= 300 and seen['revive'] >= 200
