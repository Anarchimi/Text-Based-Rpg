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
                     ("Herblore", 10), ("Herblore", 15),
                     ("Fishing", 5), ("Fishing", 10), ("Fishing", 15), ("Fishing", 20),
                     ("Cooking", 10), ("Cooking", 15),
                     ("Woodcutting", 5), ("Woodcutting", 10), ("Woodcutting", 15), ("Woodcutting", 20),
                     ("Fletching", 10), ("Fletching", 15), ("Fletching", 20)}


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
        zone = next(z for z in range(2, 6) if ev in available_trade_events(p, z))   # where it's offered
        random.seed(1)
        events = resolve_trade_event(ev['id'], p, zone, 0)
        gained_resources = sum(p.resources.values())
        items = [v for kind, v, _ in events if kind in ('item', 'node')]
        assert gained_resources > 0 or items or p.armed_trap, f'{ev["id"]} gave nothing'
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


# ── Phase 4: Fisher ────────────────────────────────────────────────────────────

import combat
from trades import MEALS, TEMPERAMENTS


def fisher(**skills):
    return trader('Fisher', **skills)


def bite(p, zone=2, trait='heavy', fish=None):
    node = T.make_bite_node(p, zone)
    node['trait'] = trait
    if fish:
        node['fish'] = fish
    return node


def test_hard_bites_need_fishing_5_and_only_name_the_temperament_at_10():
    assert T.make_bite_node(fisher(Fishing=4), 2) is None
    for lv, named in ((5, False), (10, True)):
        for _ in range(20):
            node = T.make_bite_node(fisher(Fishing=lv), 2)
            assert TEMPERAMENTS[node['trait']][0] in node['text']
            assert (f"It's {node['trait']}" in node['text']) == named


@pytest.mark.parametrize('trait', list(TEMPERAMENTS))
def test_the_response_matters(trait, monkeypatch):
    odds = TEMPERAMENTS[trait][1]
    best = max(odds, key=odds.get)
    worst = min(odds, key=odds.get)
    for key, roll, landed in ((best, 0.8, True), (worst, 0.2, False)):
        p = fisher(Fishing=5)
        monkeypatch.setattr(T, 'random', FixedRandom(roll))
        events = T.resolve_node(bite(p, trait=trait), key, p)
        assert (sum(p.resources.values()) > 0) == landed, (trait, key)
        if not landed:
            assert 'got away' in events[0][2]


def test_rare_fish_from_deeper_water_at_fishing_10(monkeypatch):
    monkeypatch.setattr(T, 'random', FixedRandom(0.1))  # rare-fish roll passes (choice() takes the first trait)
    assert T.make_bite_node(fisher(Fishing=10), 2)['fish'] == 'Raw Lobster'
    monkeypatch.setattr(T, 'random', FixedRandom(0.1))
    assert T.make_bite_node(fisher(Fishing=9), 2)['fish'] in ('Raw Trout', 'Raw Salmon')


def test_trophies_need_fishing_15_and_the_best_response(monkeypatch):
    def play(lv, key):
        p = fisher(Fishing=lv)
        node = bite(p, trait='heavy')
        monkeypatch.setattr(T, 'random', FixedRandom(0.1, 0.1, 0.1))  # catch, (legendary no at <20), trophy yes
        T.resolve_node(node, key, p)
        return p
    p = play(15, 'steady')
    assert p.resources.get('Trophy Salmon') == 1 and p.trophies == {'Trophy Salmon': 1}
    assert not play(14, 'steady').trophies
    assert not play(15, 'reel').trophies, 'a merely adequate fight never lands a trophy'


def test_first_trophy_pays_a_one_time_reward():
    p = fisher(Fishing=15)
    first = T._land_trophy(p, 'Voidfin')
    second = T._land_trophy(p, 'Voidfin')
    assert 'NEW TROPHY' in first[0][2] and 'NEW TROPHY' not in second[0][2] and p.trophies['Voidfin'] == 2


def test_river_king_only_at_fishing_20(monkeypatch):
    for lv, expected in ((19, None), (20, 1)):
        p = fisher(Fishing=lv)
        node = bite(p, zone=T.LEGENDARY_FISH_ZONE, trait='heavy')   # build before fixing the rolls
        monkeypatch.setattr(T, 'random', FixedRandom(0.1, 0.05))
        T.resolve_node(node, 'steady', p)
        assert p.resources.get('Ashvale River King') == expected


@pytest.mark.parametrize('trade,event,skill,level,node_type', [
    ('Blacksmith', 'ore_vein', 'Mining', 5, 'vein'),
    ('Alchemist', 'herb_patch', 'Herbalism', 10, 'patch'),
    ('Fisher', 'hidden_pool', 'Fishing', 5, 'bite'),
])
def test_basic_trail_discoveries_become_nodes_at_their_milestone(trade, event, skill, level, node_type):
    below = resolve_trade_event(event, trader(trade, **{skill: level - 1}), 2, 0)
    assert below[0][0] == 'resource', 'before the milestone: a plain haul'
    at = resolve_trade_event(event, trader(trade, **{skill: level}), 2, 0)
    assert at[0][0] == 'node' and at[0][1]['type'] == node_type


def _cook_meal(p, recipe_name, inputs):
    p.resources.update(inputs)
    idx = next(i for i, r in enumerate(CRAFTING_RECIPES['Cooking']) if r['name'] == recipe_name)
    ok, msg, item = craft_item(p, 'Cooking', idx)
    assert ok, msg
    return item


def test_meals_buff_for_several_fights_and_are_eaten_outside_combat():
    p = fisher(Cooking=12)
    stew = _cook_meal(p, 'Hearty Fish Stew', {'Raw Trout': 2, 'Raw Salmon': 1})
    assert stew.category == 'meal' and stew not in p.combat_consumables()
    vit = p.vit
    ok, msg = p.use_consumable(stew)
    assert ok and p.vit == vit + 8 and p.meal['fights'] == MEALS['Hearty Fish Stew']['fights']
    for _ in range(MEALS['Hearty Fish Stew']['fights']):
        combat.end_combat(p)
    assert p.meal is None and p.vit == vit


def test_spiced_swordfish_adds_crit():
    p = fisher(Cooking=12)
    item = _cook_meal(p, 'Spiced Swordfish', {'Raw Swordfish': 1, 'Raw Lobster': 1})
    base = p.crit_bonus
    p.use_consumable(item)
    assert p.crit_bonus == pytest.approx(base + 0.08)


def test_dragonfire_chowder_resists_debuffs(monkeypatch):
    from conftest import make_enemy
    p = fisher(Cooking=18)
    p.use_consumable(_cook_meal(p, 'Dragonfire Chowder', {'Raw Dark Crab': 1, 'Raw Anglerfish': 1}))
    e = make_enemy()
    monkeypatch.setattr(combat.random, 'random', lambda: 0.1)
    combat._enemy_ability(p, e, 'Poison Blade', combat.ability_spec('Poison Blade'), lambda k, t: None, False)
    assert 'Poisoned' not in p.debuffs


def test_trophy_feast_needs_cooking_10_and_slow_cooking_extends_meals():
    p = fisher(Cooking=9)
    p.resources['Trophy Salmon'] = 1
    idx = next(i for i, r in enumerate(CRAFTING_RECIPES['Cooking']) if r['name'] == 'Trophy Feast (Salmon)')
    assert not craft_item(p, 'Cooking', idx)[0]
    for lv, extra in ((10, 0), (15, T.SLOW_COOKING_FIGHTS)):
        q = fisher(Cooking=lv)
        feast = _cook_meal(q, 'Trophy Feast (Salmon)', {'Trophy Salmon': 1})
        q.use_consumable(feast)
        assert q.meal['fights'] == MEALS['Trophy Feast']['fights'] + extra


def test_meals_are_not_offered_in_combat_ui():
    import app as game_app, os
    from quests import QuestLog
    from enemies import spawn_enemy
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    p = fisher(Cooking=12)
    _cook_meal(p, 'Hearty Fish Stew', {'Raw Trout': 2, 'Raw Salmon': 1})
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='combat', combat_enemy=spawn_enemy(1, 1), combat_turn=1)
    pickle.dump(st, open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'wb'))
    page = client.get('/').get_data(as_text=True)
    assert 'Hearty Fish Stew' not in page


def test_old_saves_have_no_meal_or_trophies():
    p = Player('T', 'Rogue')
    del p.meal, p.trophies
    q = pickle.loads(pickle.dumps(p))
    assert q.meal is None and q.trophies == {} and q.meal_stat('vit') == 0


# ── Phase 5: Fletcher ──────────────────────────────────────────────────────────

from items import PROFILES, WOODS, fletch_item
from enemies import spawn_enemy


def fletcher(**skills):
    return trader('Fletcher', cls='Rogue', **skills)


def _frecipe(name):
    return next(r for r in CRAFTING_RECIPES['Fletching'] if r['name'] == name)


def test_fletched_weapons_are_no_longer_renamed_generic_weapons():
    bow = fletch_item('Power', 'Yew', 'Longbow', 'Rare', 'Rogue')
    assert bow.crafted and bow.material == 'Yew' and bow.kind == 'Longbow' and bow.profile == 'Power'
    assert bow.name == 'Yew Longbow' and not bow.name.startswith('Crafted')
    assert fletch_item('Power', 'Yew', 'Longbow', 'Rare', 'Mage').kind == 'Staff'
    p = fletcher(Fletching=20)
    p.resources = {'Oak Logs': 2}
    assert not craft_item(p, 'Fletching', CRAFTING_RECIPES['Fletching'].index(_frecipe('Oak Shortbow')))[0], \
        'generic crafting refuses fletched gear'


def test_profiles_trade_damage_for_speed_or_crit(monkeypatch):
    import items
    monkeypatch.setattr(items, 'roll_affixes', lambda *a, **k: {})  # isolate the profile
    power, speed, precision = (fletch_item(p, 'Willow', 'Bow', 'Rare', 'Rogue') for p in ('Power', 'Speed', 'Precision'))
    assert power.stats['atk'] > precision.stats['atk'] > speed.stats['atk']
    assert speed.stats['spd'] > precision.stats['spd'] > power.stats['spd']
    assert precision.stats.get('crit', 0) > power.stats.get('crit', 0)


@pytest.mark.parametrize('wood,stat', [('Oak', 'hp'), ('Willow', 'spd'), ('Maple', 'crit'), ('Elder', 'dex')])
def test_wood_traits_shape_the_weapon(wood, stat, monkeypatch):
    import items
    monkeypatch.setattr(items, 'roll_affixes', lambda *a, **k: {})
    assert fletch_item('Precision', wood, 'Bow', 'Common', 'Rogue').stats.get(stat, 0) > \
        fletch_item('Precision', 'Normal', 'Bow', 'Common', 'Rogue').stats.get(stat, 0)


def test_yew_is_powerful(monkeypatch):
    import items
    monkeypatch.setattr(items, 'roll_affixes', lambda *a, **k: {})
    yew = fletch_item('Precision', 'Yew', 'Bow', 'Common')
    base = (5 + WOODS['Yew'][0] * 2)
    assert yew.stats['atk'] == int(base * 1.1)


def test_grain_sense_reveals_wood_traits():
    assert T.wood_trait(fletcher(Woodcutting=4), 'Yew') == '?'
    assert T.wood_trait(fletcher(Woodcutting=5), 'Yew') == 'powerful'


def test_trees_need_woodcutting_10_and_heartwood_trades_risk(monkeypatch):
    assert T.make_tree_node(fletcher(Woodcutting=9), 2) is None
    p = fletcher(Woodcutting=10)
    monkeypatch.setattr(T, 'random', FixedRandom(0.9))
    node = T.make_tree_node(p, 2)
    assert node['logs'] == 'Oak Logs' and {o['key'] for o in node['options']} == {'fell', 'heart', 'leave'}
    monkeypatch.setattr(T, 'random', FixedRandom(0.1))     # branch falls
    events = T.resolve_node(node, 'heart', p)
    assert events[0][0] == 'trap_pct' and p.resources.get('Heartwood') == 1
    q = fletcher(Woodcutting=10)
    monkeypatch.setattr(T, 'random', FixedRandom())
    T.resolve_node(node, 'fell', q)
    assert q.resources.get('Oak Logs', 0) >= 4 and 'Heartwood' not in q.resources


def test_rare_groves_and_ancient_trees(monkeypatch):
    monkeypatch.setattr(T, 'random', FixedRandom(0.1))
    assert T.make_tree_node(fletcher(Woodcutting=15), 2)['logs'] == 'Willow Logs'
    monkeypatch.setattr(T, 'random', FixedRandom(0.1))
    assert T.make_tree_node(fletcher(Woodcutting=14), 2)['logs'] == 'Oak Logs'
    for lv, expected in ((19, None), (20, 1)):
        p = fletcher(Woodcutting=lv)
        monkeypatch.setattr(T, 'random', FixedRandom(0.9))
        node = T.make_tree_node(p, 2)
        monkeypatch.setattr(T, 'random', FixedRandom(0.9, 0.01))   # no branch, ancient roll passes
        T.resolve_node(node, 'heart', p)
        assert p.resources.get('Ancient Heartwood') == expected


def test_heartwood_inlay_and_ancient_bowyer():
    p = fletcher(Fletching=9)
    p.resources = {'Heartwood': 1, 'Ancient Heartwood': 1}
    assert T.usable_additives(p, 'Fletching') == []
    p = fletcher(Fletching=10)
    p.resources = {'Heartwood': 1, 'Ancient Heartwood': 1}
    assert T.usable_additives(p, 'Fletching') == ['Heartwood']
    p = fletcher(Fletching=20)
    p.resources = {'Willow Logs': 2, 'Ancient Heartwood': 1}
    T.random_backup = T.random
    T.random = FixedRandom(0.99)
    try:
        ok, msg, item = T.fletch(p, _frecipe('Willow Bow'), 'Speed', 'Ancient Heartwood')
    finally:
        T.random = T.random_backup
    assert ok and item.rarity == 'Legendary' and item.profile == 'Speed'


def test_hunting_trap_snares_the_next_non_boss_fight():
    p = fletcher(Fletching=4)
    p.resources = {'Normal Logs': 2}
    ok, _, trap = craft_item(p, 'Fletching', CRAFTING_RECIPES['Fletching'].index(_frecipe('Hunting Trap')))
    assert ok and trap.category == 'utility' and trap not in p.combat_consumables()
    assert p.use_consumable(trap)[0] and p.armed_trap
    boss = spawn_enemy(2, 8, force_boss=True)
    assert T.spring_trap(p, boss) is None and p.armed_trap, 'bosses are too big to snare'
    e = spawn_enemy(2, 8)
    line = T.spring_trap(p, e)
    assert line and e.hp < e.max_hp and 'Chilled' in e.statuses and not p.armed_trap and e.dot == 0


def test_snare_mastery_adds_bleed():
    p = fletcher(Fletching=15)
    p.armed_trap = True
    e = spawn_enemy(2, 8)
    T.spring_trap(p, e)
    assert e.dot > 0 and e.dot_name == 'Bleed'


def test_trap_springs_when_a_trail_fight_starts(monkeypatch):
    import app as game_app
    from quests import QuestLog
    p = fletcher()
    p.armed_trap = True
    e = spawn_enemy(1, 1)
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog())
    game_app.start_combat(st, e, 'A goblin appears!', return_to='explore')
    assert e.hp < e.max_hp and any('trap' in l['text'] for l in st['combat_log'])


def test_animal_tracks_set_a_free_ambush():
    assert 'tracks' not in {e['id'] for e in available_trade_events(fletcher(Woodcutting=4), 2)}
    p = fletcher(Woodcutting=5)
    assert 'tracks' in {e['id'] for e in available_trade_events(p, 2)}
    resolve_trade_event('tracks', p, 2, 0)
    assert p.armed_trap


def test_camping_kit_improves_one_camp_and_keeps_half_the_depth():
    import world
    p = fletcher()
    p.add_item(Item('Camping Kit', 'consumable', 'Common', 25, effect='camp_kit'))
    assert not p.use_consumable(p.inventory[-1])[0], 'used automatically, not from the bag'
    events = world.resolve_option({'kind': 'rest'}, p, 2, set(), depth=8)
    assert ('heal_pct', T.CAMP_KIT_HEAL, ) == events[0][:2] and ('set_depth', 4) == events[-1][:2]
    assert not any(i.effect == 'camp_kit' for i in p.inventory), 'one camp per kit'
    plain = world.resolve_option({'kind': 'rest'}, p, 2, set(), depth=8)
    assert plain[-1][0] == 'reset_depth'


def test_smoke_arrow_escapes_but_not_the_final_battle():
    from enemies import spawn_final_boss
    for enemy, expected in ((spawn_enemy(2, 8, force_boss=True), 'fled'), (spawn_final_boss(19), 'continue')):
        p = fletcher()
        p.max_hp = p.hp = 10_000
        arrow = Item('Smoke Arrow', 'consumable', 'Common', 25, effect='smoke_escape')
        arrow.category = 'utility'
        p.add_item(arrow)
        idx = p.combat_consumables().index(arrow)
        st = {'player': p, 'combat_enemy': enemy, 'combat_log': [], 'combat_turn': 1}
        assert combat.do_combat_turn(st, 'item', item_idx=idx) == expected
        assert (arrow in p.inventory) == (expected == 'continue')


def test_fletching_bench_flow_through_the_web():
    import app as game_app, os
    from quests import QuestLog
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    p = fletcher(Fletching=9, Woodcutting=5)
    p.resources = {'Willow Logs': 2}
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='craft', craft_skill='Fletching')
    path = os.path.join(game_app.SAVE_DIR, f'{sid}.pkl')
    pickle.dump(st, open(path, 'wb'))
    idx = CRAFTING_RECIPES['Fletching'].index(_frecipe('Willow Bow'))
    page = client.post('/action', data={'action': f'forge_{idx}'}, follow_redirects=True).get_data(as_text=True)
    assert 'Fletching Bench' in page and 'flexible' in page and 'Precision' in page
    client.post('/action', data={'action': 'ws_profile_Precision'})
    client.post('/action', data={'action': 'ws_forge'})
    inv = pickle.load(open(path, 'rb'))['player'].inventory
    assert any(i.profile == 'Precision' and i.material == 'Willow' for i in inv)


# ── Phase 6: an old save loads and every new trade screen renders ──────────────

def test_pre_trade_save_loads_and_all_trade_screens_render():
    import app as game_app, os
    from quests import QuestLog
    p = trader('Blacksmith', Mining=12, Smithing=12, Herblore=5, Herbalism=5)
    p.resources = {'Guam Leaf': 2, 'Ranarr Weed': 2, 'Iron Bar': 2}
    for attr in ('unlock_log', 'trade_specialization', 'alchemy_journal', 'trophies', 'meal', 'armed_trap'):
        delattr(p, attr)
    st = game_app.fresh_state()
    st.update(player=p, quest_log=QuestLog(), screen='hub', zone=2)
    for key in ('pending_node', 'node_return', 'workshop', 'alchemy_pick'):
        del st[key]
    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    pickle.dump(st, open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'wb'))

    def go(action, expect):
        resp = client.post('/action', data={'action': action}, follow_redirects=True)
        assert resp.status_code == 200 and expect in resp.get_data(as_text=True), action
    go('gather', 'Next · Lv')
    go('back', 'Explore')
    go('craft', 'Craft')
    go('tab_Herblore', 'Alchemy bench')
    go('alchemy', 'Alchemy Bench')
    go('back', 'Craft')
    go('tab_Smithing', 'Forge…')
    idx = CRAFTING_RECIPES['Smithing'].index(_recipe('Iron'))
    go(f'forge_{idx}', 'Quality odds')
    go('back', 'Craft')
    go('back', 'Explore')
    go('inventory', 'Inventory')
    go('back', 'Explore')
    go('explore', 'Choose your path')


# ── Cleanup: progression-safe rewards ──────────────────────────────────────────

def test_monster_remains_respect_zone_progression():
    """Remains may only yield reagents whose source monster can already spawn in that zone."""
    from enemies import ENEMY_TEMPLATES
    first_zone = {r: min(t['zone'] for t in ENEMY_TEMPLATES if any(src in t['name'] for src in srcs))
                  for r, srcs in T.MONSTER_REAGENTS.items()}
    for zone in range(1, 6):
        assert set(T.zone_reagents(zone)) == {r for r, z in first_zone.items() if z <= zone}
    assert T.zone_reagents(1) == [] and T.zone_reagents(2) == []

    for zone in (1, 2):
        p = alch(Herblore=20)
        assert 'remains' not in {e['id'] for e in available_trade_events(p, zone)}, \
            'no reagent-bearing monster lives here yet'
        events = resolve_trade_event('remains', p, zone, 0)   # e.g. a path offered by an older build
        assert events[0][0] == 'nothing' and not p.resources
    for zone in (3, 4, 5):
        p = alch(Herblore=10)
        assert 'remains' in {e['id'] for e in available_trade_events(p, zone)}
        for seed in range(30):
            random.seed(seed)
            resolve_trade_event('remains', p, zone, 0)
        assert set(p.resources) <= set(T.zone_reagents(zone))


def test_every_zone_has_its_own_trophy_fish_and_feast():
    assert len(set(T.TROPHY_FISH.values())) == len(T.TROPHY_FISH) == 5
    assert T.LEGENDARY_FISH not in T.TROPHY_FISH.values()
    feasts = {name for r in CRAFTING_RECIPES['Cooking'] if r['output_type'] == 'meal' for name in r['inputs']}
    assert set(T.TROPHY_FISH.values()) | {T.LEGENDARY_FISH} <= feasts


def test_zone_5_lands_its_own_trophy(monkeypatch):
    p = fisher(Fishing=19)
    node = bite(p, zone=5, trait='heavy')
    monkeypatch.setattr(T, 'random', FixedRandom(0.1, 0.1))   # catch, trophy
    T.resolve_node(node, 'steady', p)
    assert p.trophies == {T.TROPHY_FISH[5]: 1} and T.TROPHY_FISH[5] != T.TROPHY_FISH[4]


@pytest.mark.parametrize('zone', [2, 3, 4, 5])
def test_river_king_only_bites_in_its_home_river(monkeypatch, zone):
    p = fisher(Fishing=20)
    node = bite(p, zone=zone, trait='heavy')
    assert not node['legendary']
    node['legendary'] = True   # a node saved by an older build must not land it either
    monkeypatch.setattr(T, 'random', FixedRandom(0.1, 0.01, 0.99))   # catch, legendary roll, no trophy
    T.resolve_node(node, 'steady', p)
    assert T.LEGENDARY_FISH not in p.resources and T.LEGENDARY_FISH not in p.trophies


def test_revive_messages_name_the_actual_item(monkeypatch):
    p = alch()
    draught = Item('Phoenix Draught', 'consumable', 'Rare', 200, effect='revive', effect_value=1)
    p.add_item(draught)
    ok, msg = p.use_consumable(draught)
    assert not ok and 'Phoenix Draught' in msg and 'Feather' not in msg and draught in p.inventory

    e = spawn_enemy(1, 1)
    e.atk = 10 ** 6
    monkeypatch.setattr(combat, 'ENEMY_ABILITY_CHANCE', 0)
    st = {'player': p, 'combat_enemy': e, 'combat_log': [], 'combat_turn': 1}
    for seed in range(20):   # skip any lucky dodge
        random.seed(seed)
        p.hp = 1
        if combat.do_combat_turn(st, 'defend') == 'revived':
            break
    text = ' '.join(l['text'] for l in st['combat_log'])
    assert 'Phoenix Draught saves you' in text and 'Feather' not in text
    assert draught not in p.inventory
