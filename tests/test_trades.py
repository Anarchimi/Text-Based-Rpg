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
TESTED_MILESTONES = {("Smithing", 5), ("Herblore", 5), ("Cooking", 5), ("Fletching", 5),
                     ("Mining", 5), ("Mining", 10), ("Mining", 15), ("Mining", 20),
                     ("Smithing", 10), ("Smithing", 15), ("Smithing", 20),
                     ("Herbalism", 5), ("Herbalism", 10), ("Herbalism", 15), ("Herbalism", 20),
                     ("Herblore", 10), ("Herblore", 15)}


def trader(trade, cls='Warrior', level=8, **skills):
    p = Player('T', cls)
    p.level = level
    p.trade_profession = trade
    for name, lv in skills.items():
        table = p.gathering_skills if name in p.gathering_skills else p.crafting_skills
        table[name] = {'level': lv, 'xp': 50 * lv * (lv - 1)}  # XP must match, or the next gain recomputes it
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
    basic, gated = PROFESSION_EVENTS[trade][:2]
    novice = trader(trade)
    ids = {e['id'] for e in available_trade_events(novice, 2)}
    assert ids == {basic['id']}, 'the level-gated discovery needs its crafting skill at 5'
    adept = trader(trade, **{gated['skill']: gated['level']})
    assert {basic['id'], gated['id']} <= {e['id'] for e in available_trade_events(adept, 2)}
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
        items = [v for kind, v, _ in events if kind in ('item', 'node')]
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


# ── Phase 2: Blacksmith ────────────────────────────────────────────────────────

import trades as T
from crafting import CRAFTING_RECIPES, craft_item
from items import METALS, Item, forge_item


class FixedRandom:
    """Deterministic stand-in for trades.random: random() returns queued values, randint the low end."""
    def __init__(self, *values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0) if self.values else 0.99

    def randint(self, a, b):
        return a

    def choice(self, seq):
        return seq[0]


def smith(**skills):
    return trader('Blacksmith', **skills)


def test_veins_need_ore_sense():
    assert T.make_vein_node(smith(Mining=4), 2) is None
    node = T.make_vein_node(smith(Mining=5), 2)
    assert node and {o['key'] for o in node['options']} == {'safe', 'deep', 'leave'}


@pytest.mark.parametrize('zone,ore', [(1, 'Copper Ore'), (2, 'Iron Ore'), (3, 'Mithril Ore'), (5, 'Dragon Metal')])
def test_veins_are_the_zones_main_ore(zone, ore):
    assert T.make_vein_node(smith(Mining=20), zone)['ore'] == ore


def test_prospecting_appears_at_mining_10():
    keys = {o['key'] for o in T.make_vein_node(smith(Mining=10), 2)['options']}
    assert 'prospect' in keys


def test_vein_choices_trade_risk_for_reward(monkeypatch):
    def run(key, *rolls, **skills):
        p = smith(**skills)
        node = T.make_vein_node(p, 2)
        monkeypatch.setattr(T, 'random', FixedRandom(*rolls))
        events = T.resolve_node(node, key, p)
        return p, events
    safe, _ = run('safe', Mining=5)
    deep_ok, _ = run('deep', 0.9, 0.99, Mining=5)          # no cave-in
    deep_bad, ev = run('deep', 0.1, Mining=5)               # cave-in
    assert sum(deep_ok.resources.values()) > sum(safe.resources.values()) > sum(deep_bad.resources.values())
    assert ev[0][0] == 'trap_pct', 'a cave-in hurts'
    prospect, _ = run('prospect', 0.1, 0.9, Mining=10)       # gem roll succeeds, not flawless
    assert prospect.resources.get('Rough Gem') == 1 and sum(prospect.resources.values()) < sum(safe.resources.values())


def test_deep_veins_strike_next_zone_ore_at_15(monkeypatch):
    p = smith(Mining=15)
    node = T.make_vein_node(p, 2)
    assert node['deep_ore'] == 'Gold Ore' and 'Gold Ore' in node['options'][1]['detail']
    monkeypatch.setattr(T, 'random', FixedRandom(0.9, 0.1, 0.99))
    T.resolve_node(node, 'deep', p)
    assert p.resources.get('Gold Ore')
    assert T.make_vein_node(smith(Mining=14), 2)['deep_ore'] is None


def test_starmetal_only_at_mining_20(monkeypatch):
    for lv, expected in ((19, None), (20, 1)):
        p = smith(Mining=lv)
        node = T.make_vein_node(p, 2)
        monkeypatch.setattr(T, 'random', FixedRandom(0.1, 0.9, 0.01))  # gem, not flawless, star roll passes
        T.resolve_node(node, 'prospect', p)
        assert p.resources.get('Starmetal') == expected


def test_mining_taps_can_open_a_vein_node(monkeypatch):
    import app as game_app
    monkeypatch.setattr(T, 'VEIN_CHANCE', 1.0)
    st = game_app.fresh_state()
    from quests import QuestLog
    st.update(player=smith(Mining=5), quest_log=QuestLog(), screen='gather', zone=2)
    with game_app.app.test_request_context('/action', method='POST', data={'action': 'gather_Mining'}):
        from flask import session
        session['sid'] = '00000000-0000-4000-8000-000000000002'
        game_app.save_state(st)
        game_app.action()
        st = game_app.get_state()
    assert st['screen'] == 'node' and st['pending_node']['type'] == 'vein' and st['node_return'] == 'gather'


def test_blacksmith_trail_vein_returns_to_the_trail(monkeypatch):
    import app as game_app
    from quests import QuestLog
    p = smith(Mining=5)
    monkeypatch.setattr(game_app, 'generate_explore_options',
                        lambda *a, **k: [{'kind': 'trade', 'event': 'ore_vein', 'trade': 'Blacksmith'}])
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='explore', zone=2)
    game_app.ensure_explore_options(st)
    game_app.take_explore_path(st, p, st['explore_options'][0])
    assert st['screen'] == 'node' and st['node_return'] == 'explore'


# Forging

def _recipe(metal):
    return next(r for r in CRAFTING_RECIPES['Smithing'] if r.get('metal') == metal)


def test_forge_recipes_cannot_be_crafted_generically():
    p = smith(Smithing=20)
    p.resources = {'Iron Bar': 2}
    idx = CRAFTING_RECIPES['Smithing'].index(_recipe('Iron'))
    ok, _, _ = craft_item(p, 'Smithing', idx)
    assert not ok and p.resources['Iron Bar'] == 2


@pytest.mark.parametrize('slot', ['weapon', 'armor'])
def test_forged_gear_is_real_named_equipment(slot):
    item = forge_item(slot, 'Mithril', 'Rare', 'Rogue')
    assert item.crafted and item.material == 'Mithril' and item.item_type == slot
    assert item.name == ('Mithril Dagger' if slot == 'weapon' else 'Mithril Plate')
    assert item.stats['spd'] >= METALS['Mithril'][2][slot]['spd'], 'metal trait applied'
    assert ('atk' if slot == 'weapon' else 'def') in item.stats


def test_quality_odds_are_exact_and_need_investment():
    base = T.quality_odds(0)
    assert abs(sum(base.values()) - 1) < 1e-6 and 'Epic' not in base and 'Legendary' not in base
    invested = T.quality_odds(0.4)
    assert invested.get('Epic', 0) > 0 and 'Common' not in invested
    assert 'Legendary' not in invested and T.quality_odds(0.4, legendary_possible=True)['Legendary'] > 0


def test_forging_uses_the_roll_and_spends_materials(monkeypatch):
    p = smith(Smithing=9)
    p.resources = {'Steel Bar': 2}
    monkeypatch.setattr(T, 'random', FixedRandom(0.99))   # top of the roll
    ok, msg, item = T.forge(p, _recipe('Steel'), 'weapon')
    assert ok and item.rarity == 'Epic' and p.resources.get('Steel Bar', 0) == 0 and item in p.inventory
    assert not T.forge(p, _recipe('Steel'), 'weapon')[0], 'no bars left'


def test_gem_inlay_needs_smithing_10_and_raises_odds():
    p = smith(Smithing=9)
    p.resources = {'Rough Gem': 1}
    assert T.usable_additives(p) == []
    p.crafting_skills['Smithing']['level'] = 10
    assert T.usable_additives(p) == ['Rough Gem']
    r = _recipe('Steel')
    assert T.forge_shift(p, r, 'Rough Gem') > T.forge_shift(p, r)


def test_starforging_is_the_only_legendary_path(monkeypatch):
    p = smith(Smithing=20)
    p.resources = {'Steel Bar': 4, 'Rough Gem': 1, 'Starmetal': 1}
    assert 'Starmetal' in T.usable_additives(p)
    monkeypatch.setattr(T, 'random', FixedRandom(0.99))
    ok, msg, gem_item = T.forge(p, _recipe('Steel'), 'armor', 'Rough Gem')
    assert ok, msg
    monkeypatch.setattr(T, 'random', FixedRandom(0.99))
    _, _, star_item = T.forge(p, _recipe('Steel'), 'armor', 'Starmetal')
    assert gem_item.rarity == 'Epic' and star_item.rarity == 'Legendary' and star_item.legendary
    assert 'Starmetal' not in T.usable_additives(smith(Smithing=19, ))


def test_workshop_screen_flow():
    import app as game_app, os, pickle
    from quests import QuestLog
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    p = smith(Smithing=9)
    p.resources = {'Steel Bar': 2}
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='craft', craft_skill='Smithing')
    path = os.path.join(game_app.SAVE_DIR, f'{sid}.pkl')
    pickle.dump(st, open(path, 'wb'))
    idx = CRAFTING_RECIPES['Smithing'].index(_recipe('Steel'))
    page = client.post('/action', data={'action': f'forge_{idx}'}, follow_redirects=True).get_data(as_text=True)
    odds = T.quality_odds(T.forge_shift(p, _recipe('Steel')))
    assert 'The Forge' in page and 'Quality odds' in page and f"Common {round(odds['Common'] * 100)}%" in page
    client.post('/action', data={'action': 'ws_slot_armor'})
    page = client.post('/action', data={'action': 'ws_forge'}, follow_redirects=True).get_data(as_text=True)
    assert 'Steel Plate' in page
    inv = pickle.load(open(path, 'rb'))['player'].inventory
    assert any(i.crafted and i.kind == 'Plate' for i in inv)


# Tempering

def test_tempering_needs_smithing_15_crafted_gear_and_is_once_only():
    item = forge_item('armor', 'Steel', 'Rare')
    loot = Item('Loot Plate', 'armor', 'Rare', 10, {'def': 40})
    p = smith(Smithing=14)
    p.gold, p.resources = 1000, {'Steel Bar': 3}
    assert T.temper_options(p, item) == []
    p.crafting_skills['Smithing']['level'] = 15
    assert {n for n, *_ in T.temper_options(p, item)} == {'Reinforce', 'Heavy Plating'}
    assert T.temper_options(p, loot) == [], 'loot cannot be tempered'
    before = dict(item.stats)
    ok, _ = T.temper(p, item, 'Heavy Plating')
    assert ok and item.stats['def'] > before['def'] and item.stats.get('spd', 0) < before.get('spd', 0)
    assert T.temper_options(p, item) == [] and not T.temper(p, item, 'Reinforce')[0]


def test_tempering_and_upgrades_stack_once_without_looping():
    p = smith(Smithing=15)
    p.gold, p.resources = 100000, {'Steel Bar': 5, 'Bronze Bar': 2, 'Iron Bar': 2}
    sword = forge_item('weapon', 'Steel', 'Rare', 'Warrior')
    p.add_item(sword)
    p.equip(sword)
    p.upgrade_equipped('weapon')
    upgraded = sword.stats['atk']
    T.temper(p, sword, 'Hone')
    assert sword.stats['atk'] > upgraded and sword.upgrade == 1
    p.upgrade_equipped('weapon')
    assert sword.upgrade == 2 and sword.temper == 'Hone'


# ── Phase 3: Alchemist ─────────────────────────────────────────────────────────

from itertools import combinations
from trades import ALCHEMY_RECIPES, INGREDIENTS


def alch(**skills):
    return trader('Alchemist', **skills)


def stock(p, *names, qty=3):
    for n in names:
        p.resources[n] = qty
    return p


def test_property_reveal_follows_herbalism():
    assert T.known_properties(alch(Herbalism=1), 'Guam Leaf') == ('?', '?')
    assert T.known_properties(alch(Herbalism=5), 'Guam Leaf') == ('Vitality', '?')
    assert T.known_properties(alch(Herbalism=15), 'Guam Leaf') == ('Vitality', 'Restoration')
    assert T.known_properties(alch(Herbalism=1), 'Vampire Fang')[0] == 'Lifeblood', 'reagents show their main property'


def test_every_recipe_is_discoverable_from_real_ingredients():
    mains = {}
    for name, (m, _) in INGREDIENTS.items():
        mains.setdefault(m, []).append(name)
    for pair, spec in ALCHEMY_RECIPES.items():
        a, b = sorted(pair)
        assert mains.get(a) and mains.get(b), f"{spec['name']} needs an ingredient with main property {a}/{b}"


def test_most_combinations_teach_something():
    """Avoid a combinatorial system where nearly every mix is garbage."""
    useful = total = 0
    for a, b in combinations(INGREDIENTS, 2):
        (ma, sa), (mb, sb) = INGREDIENTS[a], INGREDIENTS[b]
        total += 1
        useful += any(frozenset(x) in ALCHEMY_RECIPES and len(set(x)) == 2
                      for x in ((ma, mb), (ma, sb), (mb, sa)))
    assert useful / total > 0.2, f'only {useful}/{total} mixes do anything'


def test_discovery_persists_in_the_journal_through_save_load():
    p = stock(alch(), 'Guam Leaf', 'Ranarr Weed')
    kind, msg, item = T.experiment(p, 'Guam Leaf', 'Ranarr Weed')
    assert kind == 'discovery' and 'Healing Draught' in msg and item.effect == 'heal_pct'
    assert p.resources['Guam Leaf'] == 2 and p.resources['Ranarr Weed'] == 2
    q = pickle.loads(pickle.dumps(p))
    assert q.alchemy_journal['recipes']['Healing Draught'] == ('Guam Leaf', 'Ranarr Weed')
    assert T.experiment(q, 'Ranarr Weed', 'Guam Leaf')[0] == 'known', 'rediscovering is not new'


def test_unstable_mix_is_weaker_and_leaves_a_hint():
    p = stock(alch(), 'Guam Leaf', 'Snapdragon')   # Vitality + (Snapdragon secondary: Restoration)
    kind, msg, item = T.experiment(p, 'Guam Leaf', 'Snapdragon')
    assert kind == 'unstable' and 'Healing Draught' in item.name and item.effect_value == 20
    assert 'Healing Draught' in p.alchemy_journal['hints'] and 'Restoration' in msg


def test_failed_mix_consumes_ingredients(monkeypatch):
    monkeypatch.setattr(T, 'random', FixedRandom(0.9))  # no fumes
    p = stock(alch(), 'Tarromin', 'Marrentill')
    kind, _, item = T.experiment(p, 'Tarromin', 'Marrentill')
    assert kind == 'fail' and item is None and p.resources['Tarromin'] == 2


def test_brewing_a_known_recipe_is_one_tap():
    p = stock(alch(), 'Guam Leaf', 'Ranarr Weed')
    assert not T.brew_known(p, 'Healing Draught')[0], 'must be discovered first'
    T.experiment(p, 'Guam Leaf', 'Ranarr Weed')
    ok, _, item = T.brew_known(p, 'Healing Draught')
    assert ok and item.effect_value == 40


def test_potent_brews_at_herblore_15():
    p = stock(alch(Herblore=15), 'Guam Leaf', 'Ranarr Weed')
    T.experiment(p, 'Guam Leaf', 'Ranarr Weed')
    _, _, item = T.brew_known(p, 'Healing Draught')
    assert item.effect_value == 50


def test_monster_reagent_recipes_and_panacea():
    p = stock(alch(), 'Vampire Fang', 'Ranarr Weed', 'Marrentill', 'Snapdragon')
    assert T.experiment(p, 'Vampire Fang', 'Ranarr Weed')[2].name == 'Crimson Draught'
    _, _, panacea = T.experiment(p, 'Marrentill', 'Snapdragon')
    p.debuffs['Poisoned'] = {'turns': 3, 'dmg': 5}
    p.hp = 10
    p.add_item(panacea)
    p.use_consumable(panacea)
    assert not p.debuffs and p.hp > 10


def test_phoenix_draught_is_a_working_revive():
    p = stock(alch(), 'Starbloom', 'Ranarr Weed')
    _, _, item = T.experiment(p, 'Starbloom', 'Ranarr Weed')
    assert item.effect == 'revive' and p.has_revive()


def test_reagents_drop_only_from_their_monsters(monkeypatch):
    monkeypatch.setattr(T, 'random', FixedRandom(0.0, 0.0, 0.0))
    assert T.reagent_drop('Vampire') == 'Vampire Fang'
    assert T.reagent_drop('Goblin') is None
    assert T.reagent_drop('Void Stalker Leader') == 'Shadow Essence'


def test_herb_patches_need_herbalism_10_and_careful_trades_risk(monkeypatch):
    assert T.make_patch_node(alch(Herbalism=9), 2) is None
    p = alch(Herbalism=10)
    node = T.make_patch_node(p, 2)
    assert {o['key'] for o in node['options']} == {'quick', 'careful', 'leave'}
    monkeypatch.setattr(T, 'random', FixedRandom(0.1, 0.1))     # stung, rare herb found
    events = T.resolve_node(node, 'careful', p)
    assert events[0][0] == 'trap_pct' and p.resources.get(node['rare']) == 1
    monkeypatch.setattr(T, 'random', FixedRandom())
    q = alch(Herbalism=10)
    T.resolve_node(node, 'quick', q)
    assert sum(q.resources.values()) >= 3 and node['rare'] not in q.resources


def test_starbloom_only_with_mythic_bloom(monkeypatch):
    for lv, expected in ((19, None), (20, 1)):
        p = alch(Herbalism=lv)
        node = T.make_patch_node(p, 2)
        monkeypatch.setattr(T, 'random', FixedRandom(0.9, 0.9, 0.01))  # no sting, no rare, bloom roll passes
        T.resolve_node(node, 'careful', p)
        assert p.resources.get('Starbloom') == expected


def test_reagent_lore_unlocks_monster_remains():
    ids = lambda p: {e['id'] for e in available_trade_events(p, 3)}
    assert 'remains' not in ids(alch(Herblore=9)) and 'remains' in ids(alch(Herblore=10))
    p = alch(Herblore=10)
    resolve_trade_event('remains', p, 3, 0)
    assert set(p.resources) <= set(T.MONSTER_REAGENTS) and sum(p.resources.values()) == 1


def test_alchemy_bench_flow_through_the_web():
    import app as game_app, os
    from quests import QuestLog
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    p = stock(alch(Herbalism=5), 'Guam Leaf', 'Ranarr Weed')
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='craft', craft_skill='Herblore')
    path = os.path.join(game_app.SAVE_DIR, f'{sid}.pkl')
    pickle.dump(st, open(path, 'wb'))
    page = client.post('/action', data={'action': 'alchemy'}, follow_redirects=True).get_data(as_text=True)
    assert 'Alchemy Bench' in page and 'Vitality' in page
    client.post('/action', data={'action': 'alc_pick_Guam Leaf'})
    client.post('/action', data={'action': 'alc_pick_Ranarr Weed'})
    page = client.post('/action', data={'action': 'alc_mix'}, follow_redirects=True).get_data(as_text=True)
    assert 'NEW RECIPE: Healing Draught' in page and 'value="alc_brew_Healing Draught"' in page
    assert 'Healing Draught' in pickle.load(open(path, 'rb'))['player'].alchemy_journal['recipes']
