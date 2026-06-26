import os
import uuid
import random
import pickle
from flask import Flask, session, request, redirect, url_for, render_template

from player import Player
from enemies import spawn_enemy
from quests import QuestLog, generate_quest
from items import generate_shop_stock, generate_weapon, generate_armor, generate_consumable
from world import explore_step, travel_to_zone, ZONES, ZONE_LEVEL_REQ, get_zone

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', b'shattered-realm-secret-2024')
app.jinja_env.globals['enumerate'] = enumerate

SAVE_DIR = '/tmp/rpg_saves'
os.makedirs(SAVE_DIR, exist_ok=True)


# ── State management ──────────────────────────────────────────────────────────

def get_state():
    sid = session.get('sid')
    if not sid:
        return None
    try:
        with open(f'{SAVE_DIR}/{sid}.pkl', 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None


def save_state(state):
    sid = session.get('sid')
    if not sid:
        sid = str(uuid.uuid4())
        session['sid'] = sid
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(f'{SAVE_DIR}/{sid}.pkl', 'wb') as f:
        pickle.dump(state, f)


def fresh_state():
    return {
        'screen': 'title',
        'player': None,
        'player_name': '',
        'quest_log': None,
        'zone': 1,
        'messages': [],
        'combat_enemy': None,
        'combat_turn': 0,
        'combat_log': [],
        'shop_stock': None,
        'board_quests': None,
    }


def add_msg(state, kind, text):
    state['messages'].append({'kind': kind, 'text': text})


def clear_msgs(state):
    state['messages'] = []


# ── Combat logic ──────────────────────────────────────────────────────────────

def do_combat_turn(state, action, ability_idx=None, item_idx=None):
    player = state['player']
    enemy = state['combat_enemy']
    log = state['combat_log']

    def clog(kind, text):
        log.append({'kind': kind, 'text': text})

    if action == 'attack':
        bonus = random.randint(-2, 4)
        crit = random.random() < (0.05 + player.dex / 200)
        dmg = int((player.attack + bonus) * (1.8 if crit else 1.0))
        actual = enemy.take_damage(dmg)
        if crit:
            clog('crit', '★ CRITICAL HIT!')
        clog('player', f'{player.name} attacks for {actual} damage.')

    elif action == 'ability' and ability_idx is not None:
        abilities = player.get_abilities()
        if 0 <= ability_idx < len(abilities):
            picked = abilities[ability_idx]
            if player.mp < picked.mp_cost:
                clog('danger', 'Not enough MP!')
                return 'continue'
            player.mp -= picked.mp_cost
            stats = {'str': int(player.str), 'dex': int(player.dex), 'int': int(player.int)}
            effect = picked.calculate_effect(stats)
            if picked.ability_type == 'damage':
                crit = random.random() < 0.12
                dmg = int(effect * (1.5 if crit else 1.0))
                if picked.name == 'Execute' and enemy.hp < enemy.max_hp * 0.3:
                    dmg = int(dmg * 2)
                    clog('crit', 'EXECUTE! 2x DAMAGE!')
                if picked.name == 'Death Mark':
                    dmg = int(dmg * 3)
                    clog('crit', 'DEATH MARK! 3x DAMAGE!')
                actual = enemy.take_damage(dmg)
                if crit:
                    clog('crit', '★ CRITICAL!')
                clog('player', f'{picked.name}: {actual} damage!')
            elif picked.ability_type == 'heal':
                healed = min(effect, player.max_hp - player.hp)
                player.hp += healed
                clog('heal', f'{picked.name}: Restored {healed} HP!')
            elif picked.ability_type == 'buff':
                player.buffs[picked.name] = 3
                clog('buff', f'{picked.name} activated for 3 turns!')
            elif picked.ability_type == 'dot':
                enemy.dot = 3
                enemy.dot_dmg = effect
                clog('poison', f'Poisoned {enemy.name} for {effect} dmg/turn!')
            elif picked.ability_type == 'debuff':
                enemy.stunned = True
                clog('stun', f'{enemy.name} is stunned next turn!')

    elif action == 'item' and item_idx is not None:
        consumables = [i for i in player.inventory if i.item_type == 'consumable']
        if 0 <= item_idx < len(consumables):
            ok, text = player.use_consumable(consumables[item_idx])
            clog('heal' if ok else 'danger', text)

    elif action == 'flee':
        flee_chance = 30 + int(player.dex) + int(player.speed * 1.5)
        if random.randint(1, 100) < flee_chance - enemy.atk:
            clog('warning', 'You fled from the battle!')
            return 'fled'
        clog('danger', "Couldn't flee! The enemy blocks your escape!")

    if not enemy.is_alive():
        return 'victory'

    dot_dmg = enemy.tick_dot()
    if dot_dmg:
        clog('poison', f'Poison deals {dot_dmg} to {enemy.name}. ({enemy.hp} HP left)')
        if not enemy.is_alive():
            return 'victory'

    use_ability = random.random() < 0.3 and enemy.abilities
    if use_ability:
        ability_name, bonus = enemy.use_ability()
        if enemy.stunned:
            clog('warning', f'{enemy.name} is stunned and cannot act!')
            enemy.stunned = False
        else:
            sdmg = max(1, int(enemy.atk * 1.3 + bonus) - player.defense)
            player.hp = max(0, player.hp - sdmg)
            clog('enemy', f'{enemy.name} uses {ability_name}! -{sdmg} HP')
    else:
        if enemy.stunned:
            clog('warning', f'{enemy.name} is stunned and misses!')
            enemy.stunned = False
        else:
            dmg, was_stunned = enemy.attack_player(player.defense)
            if was_stunned:
                clog('warning', f'{enemy.name} was stunned and missed!')
            else:
                player.hp = max(0, player.hp - dmg)
                clog('enemy', f'{enemy.name} attacks: -{dmg} HP')

    expired = player.tick_buffs()
    if player.dot > 0:
        clog('danger', f'You are poisoned! -{player.dot_dmg} HP')
    for b in expired:
        clog('warning', f'{b} wore off.')

    if player.hp <= 0:
        if player.has_revive():
            clog('warning', 'Defeated... but a Phoenix Feather saves you!')
            player.consume_revive()
            return 'revived'
        return 'defeat'

    state['combat_turn'] += 1
    return 'continue'


def finish_combat_victory(state):
    player = state['player']
    enemy = state['combat_enemy']
    quest_log = state['quest_log']
    log = state['combat_log']

    items, gold = enemy.loot_drop(player.level, int(player.lck))
    player.gold += gold
    player.kills += 1

    log.append({'kind': 'victory', 'text': f'VICTORY! Defeated the {enemy.name}!'})
    log.append({'kind': 'xp', 'text': f'+{enemy.xp} XP   +{gold} gold'})

    for item in items:
        log.append({'kind': 'loot', 'text': f'Loot: {item.name} [{item.rarity}]'})
        player.add_item(item)

    for q in quest_log.check_event('kill', enemy.name):
        log.append({'kind': 'quest', 'text': f'Quest progress: {q.title}'})

    levels = player.gain_xp(enemy.xp)
    for lvl in levels:
        log.append({'kind': 'levelup', 'text': f'★ LEVEL UP! Now Level {lvl}! +2 Skill Points'})

    quest_log.check_event('explore', get_zone(state['zone'])['name'])
    for q in list(quest_log.active_quests()):
        if q.is_complete():
            quest_log.finish_quest(q)
            player.gold += q.reward_gold
            player.gain_xp(q.reward_xp)
            player.quests_completed += 1
            log.append({'kind': 'quest', 'text': f'Quest complete: {q.title}! +{q.reward_gold}g +{q.reward_xp} XP'})

    state['combat_enemy'] = None
    state['screen'] = 'combat_result'


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    state = get_state()
    if state is None:
        state = fresh_state()
        save_state(state)
    return render_template('game.html', state=state, zones=ZONES, zone_reqs=ZONE_LEVEL_REQ)


@app.route('/action', methods=['POST'])
def action():
    state = get_state()
    if state is None:
        state = fresh_state()

    act = request.form.get('action', '')
    screen = state['screen']

    if screen == 'title':
        if act == 'new_game':
            clear_msgs(state)
            state['screen'] = 'char_name'

    elif screen == 'char_name':
        name = request.form.get('name', '').strip()
        if name:
            state['player_name'] = name
            state['screen'] = 'char_class'

    elif screen == 'char_class':
        if act in ('Warrior', 'Mage', 'Rogue'):
            name = state.get('player_name', 'Hero')
            player = Player(name, act)
            w = generate_weapon(player_class=act, level=1, rarity='Common')
            a = generate_armor(level=1, rarity='Common')
            p = generate_consumable()
            player.add_item(w)
            player.add_item(a)
            player.add_item(p)
            player.equip(w)
            player.equip(a)
            quest_log = QuestLog()
            for _ in range(3):
                quest_log.add_quest(generate_quest(zone=1, level=1))
            state['player'] = player
            state['quest_log'] = quest_log
            state['zone'] = 1
            state['messages'] = [{'kind': 'success', 'text': f'Welcome, {name} the {act}! Your adventure begins in Ashvale.'}]
            state['screen'] = 'hub'

    elif screen == 'hub':
        player = state['player']
        quest_log = state['quest_log']
        clear_msgs(state)

        if act == 'explore':
            events = explore_step(player, state['zone'])
            for ev_type, val, ev_msg in events:
                if ev_type == 'narrative':
                    add_msg(state, 'info', ev_msg)
                elif ev_type == 'gold':
                    player.gold += val
                    add_msg(state, 'gold', f'{ev_msg} +{val} gold!')
                elif ev_type == 'heal_hp':
                    healed = min(val, player.max_hp - player.hp)
                    player.hp += healed
                    add_msg(state, 'heal', f'{ev_msg} +{healed} HP!')
                elif ev_type == 'heal_mp':
                    restored = min(val, player.max_mp - player.mp)
                    player.mp += restored
                    add_msg(state, 'heal', f'{ev_msg} +{restored} MP!')
                elif ev_type == 'xp':
                    levels = player.gain_xp(val)
                    add_msg(state, 'xp', f'{ev_msg} +{val} XP!')
                    for lvl in levels:
                        add_msg(state, 'levelup', f'★ LEVEL UP! Now Level {lvl}!')
                elif ev_type == 'rest':
                    hp_gain = player.max_hp // 10
                    player.hp = min(player.max_hp, player.hp + hp_gain)
                    add_msg(state, 'heal', f'{ev_msg} +{hp_gain} HP')
                elif ev_type == 'trap':
                    player.hp = max(1, player.hp - val)
                    add_msg(state, 'danger', f'{ev_msg} -{val} HP!')
                elif ev_type == 'encounter':
                    force_boss = ev_msg.startswith('💀')
                    add_msg(state, 'warning', ev_msg)
                    enemy = spawn_enemy(zone=state['zone'], level=player.level, force_boss=force_boss)
                    state['combat_enemy'] = enemy
                    state['combat_turn'] = 1
                    state['combat_log'] = [{'kind': 'info', 'text': f'A {enemy.name} (Level ~{enemy.level}) appears!'}]
                    state['screen'] = 'combat'
                    break
                elif ev_type == 'nothing':
                    add_msg(state, 'dim', ev_msg)
            if state['screen'] == 'hub':
                quest_log.check_event('explore', get_zone(state['zone'])['name'])
                for q in list(quest_log.active_quests()):
                    if q.is_complete():
                        quest_log.finish_quest(q)
                        player.gold += q.reward_gold
                        player.gain_xp(q.reward_xp)
                        player.quests_completed += 1
                        add_msg(state, 'quest', f'Quest complete: {q.title}! +{q.reward_gold}g +{q.reward_xp} XP')

        elif act == 'shop':
            state['shop_stock'] = generate_shop_stock(player.level)
            state['screen'] = 'shop'
        elif act == 'inn':
            state['screen'] = 'inn'
        elif act == 'quest_board':
            state['board_quests'] = quest_log.refresh_board(zone=state['zone'], level=player.level, count=4)
            state['screen'] = 'quest_board'
        elif act == 'world_map':
            state['screen'] = 'world_map'
        elif act == 'inventory':
            state['screen'] = 'inventory'
        elif act == 'skills':
            state['screen'] = 'skills'
        elif act == 'abilities':
            state['screen'] = 'abilities'
        elif act == 'stats':
            state['screen'] = 'stats'
        elif act == 'quit':
            state = fresh_state()

    elif screen == 'combat':
        ability_idx = None
        item_idx = None
        if act.startswith('ability_'):
            try:
                ability_idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                pass
            act = 'ability'
        elif act.startswith('item_'):
            try:
                item_idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                pass
            act = 'item'

        result = do_combat_turn(state, act, ability_idx, item_idx)

        if result == 'victory':
            finish_combat_victory(state)
        elif result == 'defeat':
            state['screen'] = 'game_over'
            state['combat_enemy'] = None
        elif result == 'fled':
            state['combat_enemy'] = None
            state['screen'] = 'hub'
            add_msg(state, 'warning', 'You fled from the battle!')
        elif result == 'revived':
            state['combat_enemy'] = None
            state['screen'] = 'hub'
            add_msg(state, 'warning', 'You were revived by a Phoenix Feather!')

    elif screen == 'combat_result':
        if act == 'continue':
            state['screen'] = 'hub'
            state['combat_log'] = []

    elif screen == 'shop':
        player = state['player']
        stock = state.get('shop_stock') or []
        if act == 'back':
            state['screen'] = 'hub'
            state['shop_stock'] = None
        elif act.startswith('buy_'):
            try:
                idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                idx = -1
            if 0 <= idx < len(stock):
                item = stock[idx]
                if player.gold >= item.value:
                    player.gold -= item.value
                    player.add_item(item)
                    stock.pop(idx)
                    state['shop_stock'] = stock
                    add_msg(state, 'success', f'Purchased {item.name}!')
                else:
                    add_msg(state, 'danger', 'Not enough gold!')

    elif screen == 'inn':
        player = state['player']
        hp_missing = player.max_hp - player.hp
        cost = (hp_missing // 10) * 3 + 5
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act == 'full_rest':
            if player.gold >= cost:
                player.gold -= cost
                player.hp = player.max_hp
                player.mp = player.max_mp
                player.dot = 0
                add_msg(state, 'success', 'You rest well. HP and MP fully restored!')
            else:
                add_msg(state, 'danger', 'Not enough gold!')
        elif act == 'nap':
            player.hp = min(player.max_hp, player.hp + player.max_hp // 2)
            player.mp = min(player.max_mp, player.mp + player.max_mp // 2)
            player.dot = 0
            add_msg(state, 'success', 'You take a short nap. HP/MP partially restored.')

    elif screen == 'quest_board':
        quest_log = state['quest_log']
        board = state.get('board_quests') or []
        if act == 'back':
            state['screen'] = 'hub'
            state['board_quests'] = None
            clear_msgs(state)
        elif act.startswith('accept_'):
            try:
                idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                idx = -1
            if 0 <= idx < len(board):
                ok, text = quest_log.accept_quest(board[idx])
                add_msg(state, 'success' if ok else 'danger', text)

    elif screen == 'world_map':
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act.startswith('travel_'):
            try:
                zone_id = int(act.split('_')[1])
            except (IndexError, ValueError):
                zone_id = -1
            ok, text = travel_to_zone(state['player'], zone_id)
            if ok:
                state['zone'] = zone_id
                state['screen'] = 'hub'
            add_msg(state, 'success' if ok else 'danger', text)

    elif screen == 'inventory':
        player = state['player']
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act.startswith('equip_'):
            try:
                idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                idx = -1
            equippable = [i for i in player.inventory if i.item_type in ('weapon', 'armor')]
            if 0 <= idx < len(equippable):
                ok, text = player.equip(equippable[idx])
                add_msg(state, 'success' if ok else 'danger', text)
        elif act.startswith('use_'):
            try:
                idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                idx = -1
            consumables = [i for i in player.inventory if i.item_type == 'consumable']
            if 0 <= idx < len(consumables):
                ok, text = player.use_consumable(consumables[idx])
                add_msg(state, 'success' if ok else 'danger', text)
        elif act.startswith('sell_'):
            try:
                idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                idx = -1
            if 0 <= idx < len(player.inventory):
                item = player.inventory[idx]
                sell_price = item.value // 2
                player.inventory.remove(item)
                player.gold += sell_price
                add_msg(state, 'gold', f'Sold {item.name} for {sell_price}g!')

    elif screen == 'skills':
        player = state['player']
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act.startswith('learn_'):
            try:
                idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                idx = -1
            avail = player.available_skills()
            if 0 <= idx < len(avail):
                ok, text = player.learn_skill(avail[idx])
                add_msg(state, 'success' if ok else 'danger', text)

    elif screen in ('abilities', 'stats'):
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)

    elif screen == 'game_over':
        if act == 'restart':
            state = fresh_state()

    save_state(state)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
