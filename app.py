import os
import uuid
import random
import pickle
from flask import Flask, session, request, redirect, url_for, render_template

from player import Player, PROFESSIONS
from enemies import spawn_enemy
from quests import QuestLog, generate_quest
from items import generate_shop_stock, generate_weapon, generate_armor, generate_consumable
from world import explore_step, travel_to_zone, ZONES, ZONE_LEVEL_REQ, get_zone
from crafting import (TRADE_PROFESSIONS, CRAFTING_RECIPES, ZONE_RESOURCES,
                      GATHERING_SKILLS, CRAFTING_SKILLS, SKILL_ICONS,
                      GATHER_BUTTON_LABELS, gather_resource, craft_item, calc_skill_level)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', b'shattered-realm-secret-2024')
app.jinja_env.globals['enumerate'] = enumerate
app.jinja_env.globals['len'] = len

SAVE_DIR = '/tmp/rpg_saves'
os.makedirs(SAVE_DIR, exist_ok=True)

SEAL_MESSAGES = {
    1: "✦ The FIRST SEAL cracks. A darkness stirs beyond the horizon...",
    2: "✦ The SECOND SEAL shatters. Ancient powers begin to wake...",
    3: "✦ The THIRD SEAL breaks. The veil between worlds grows thin...",
    4: "✦ The FOURTH SEAL collapses. Reality itself begins to fracture...",
    5: "✦ THE FINAL SEAL IS BROKEN! The Chaos Dragon Lord awakens! You are the realm's last hope!",
}

ENEMY_SPRITES = {
    "Goblin":           "👺",
    "Skeleton":         "💀",
    "Forest Wolf":      "🐺",
    "Bandit":           "🗡️",
    "Orc Warrior":      "👹",
    "Dark Mage":        "🧙",
    "Stone Golem":      "🗿",
    "Vampire":          "🧛",
    "Wyvern":           "🐲",
    "Shadow Assassin":  "🕷️",
    "Lich":             "💀",
    "Ancient Dragon":   "🐉",
    "Chaos Elemental":  "⚡",
    "Undead Titan":     "🦴",
    "Void Stalker":     "👁️",
    "Goblin King":      "👑",
    "Undead Warlord":   "☠️",
    "Arcane Lich King": "🧿",
    "Chaos Dragon Lord":"🔥",
}


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
        'player_class_pending': '',
        'quest_log': None,
        'zone': 1,
        'messages': [],
        'combat_enemy': None,
        'combat_turn': 0,
        'combat_log': [],
        'shop_stock': None,
        'board_quests': None,
        'narrative_stage': 0,
        'triggered_events': set(),
        'craft_skill': 'Smithing',
    }


def add_msg(state, kind, text):
    state['messages'].append({'kind': kind, 'text': text})


def clear_msgs(state):
    state['messages'] = []


def check_profession_unlock(state, player, fallback_screen):
    """If player hit level 5 without a profession, redirect to choice screen."""
    if player.level >= 5 and not player.profession:
        state['pending_screen'] = fallback_screen
        state['screen'] = 'profession_choice'
        return True
    return False


# ── Combat logic ──────────────────────────────────────────────────────────────

def do_combat_turn(state, action, ability_idx=None, item_idx=None):
    player = state['player']
    enemy  = state['combat_enemy']
    log    = state['combat_log']

    def clog(kind, text):
        log.append({'kind': kind, 'text': text})

    if action == 'attack':
        bonus = random.randint(-2, 4)
        crit  = random.random() < (0.05 + player.dex / 200)
        dmg   = int((player.attack + bonus) * (1.8 if crit else 1.0))

        # Ranger first-strike passive
        if player.profession == 'Ranger' and not player.first_strike_used:
            dmg = int(dmg * 1.2)
            player.first_strike_used = True
            clog('buff', 'Ranger first-strike bonus! +20% ATK')

        # Berserker passive
        if player.profession == 'Berserker' and player.hp < player.max_hp * 0.3:
            dmg = int(dmg * 1.5)
            clog('buff', 'BERSERK RAGE! +50% ATK!')

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
                dmg  = int(effect * (1.5 if crit else 1.0))

                # Sorcerer passive
                if player.profession == 'Sorcerer':
                    dmg = int(dmg * 1.3)

                # Necromancer passive
                if player.profession == 'Necromancer' and enemy.hp < enemy.max_hp * 0.5:
                    dmg = int(dmg * 1.2)

                # Berserker passive
                if player.profession == 'Berserker' and player.hp < player.max_hp * 0.3:
                    dmg = int(dmg * 1.5)
                    clog('buff', 'BERSERK RAGE! +50% ATK!')

                # Execute thresholds
                execute_threshold = 0.40 if player.profession == 'Assassin' else 0.30
                if picked.name == 'Execute' and enemy.hp < enemy.max_hp * execute_threshold:
                    dmg = int(dmg * 2)
                    clog('crit', 'EXECUTE! 2× DAMAGE!')
                if picked.name == 'Death Mark':
                    mult = 3 if player.profession != 'Assassin' else 3
                    dmg = int(dmg * mult)
                    clog('crit', f'DEATH MARK! {mult}× DAMAGE!')

                actual = enemy.take_damage(dmg)
                if crit:
                    clog('crit', '★ CRITICAL!')
                clog('player', f'{picked.name}: {actual} damage!')

                # Elementalist Burn passive
                if player.profession == 'Elementalist' and random.random() < 0.30:
                    enemy.dot = max(enemy.dot, 4)
                    enemy.dot_dmg = max(enemy.dot_dmg, 5)
                    clog('poison', 'BURN applied! Enemy is on fire!')

            elif picked.ability_type == 'heal':
                healed = min(effect, player.max_hp - player.hp)
                player.hp += healed
                clog('heal', f'{picked.name}: Restored {healed} HP!')
            elif picked.ability_type == 'buff':
                player.buffs[picked.name] = 3
                clog('buff', f'{picked.name} activated for 3 turns!')
            elif picked.ability_type == 'dot':
                turns = 3
                if player.profession == 'Trickster':
                    turns = 5  # +2 extra turns
                enemy.dot = turns
                dot_dmg = effect
                if player.profession == 'Trickster':
                    dot_dmg = int(dot_dmg * 1.5)
                enemy.dot_dmg = dot_dmg
                clog('poison', f'Poisoned {enemy.name} for {dot_dmg} dmg/turn x{turns} turns!')
            elif picked.ability_type == 'debuff':
                enemy.stunned = True
                clog('stun', f'{enemy.name} is stunned next turn!')

    elif action == 'item' and item_idx is not None:
        consumables = [i for i in player.inventory if i.item_type == 'consumable']
        if 0 <= item_idx < len(consumables):
            ok, text = player.use_consumable(consumables[item_idx])
            clog('heal' if ok else 'danger', text)

    elif action == 'flee':
        if player.profession == 'Ranger':
            clog('warning', 'Ranger instincts guide you to safety!')
            return 'fled'
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
        if not b.endswith('_buff'):
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
    player    = state['player']
    enemy     = state['combat_enemy']
    quest_log = state['quest_log']
    log       = state['combat_log']

    items, gold = enemy.loot_drop(player.level, int(player.lck))
    player.gold += gold
    player.kills += 1
    player.first_strike_used = False  # reset Ranger passive

    log.append({'kind': 'victory', 'text': f'VICTORY! Defeated the {enemy.name}!'})
    log.append({'kind': 'xp',      'text': f'+{enemy.xp} XP   +{gold} gold'})

    for item in items:
        log.append({'kind': 'loot', 'text': f'Loot: {item.name} [{item.rarity}]'})
        player.add_item(item)

    for q in quest_log.check_event('kill', enemy.name):
        log.append({'kind': 'quest', 'text': f'Quest progress: {q.title}'})

    levels = player.gain_xp(enemy.xp)
    for lvl in levels:
        log.append({'kind': 'levelup', 'text': f'★ LEVEL UP! Now Level {lvl}! +2 Skill Points'})

    # Narrative arc — Five Seals
    if enemy.is_boss and state['zone'] > state.get('narrative_stage', 0):
        state['narrative_stage'] = state['zone']
        seal_msg = SEAL_MESSAGES.get(state['zone'], '')
        if seal_msg:
            log.append({'kind': 'lore', 'text': seal_msg})

    quest_log.check_event('explore', get_zone(state['zone'])['name'])
    for q in list(quest_log.active_quests()):
        if q.is_complete():
            quest_log.finish_quest(q)
            player.gold += q.reward_gold
            player.gain_xp(q.reward_xp)
            player.quests_completed += 1
            log.append({'kind': 'quest', 'text': f'Quest complete: {q.title}! +{q.reward_gold}g +{q.reward_xp} XP'})

    state['combat_enemy'] = None

    if check_profession_unlock(state, player, 'combat_result'):
        return
    state['screen'] = 'combat_result'


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    state = get_state()
    if state is None:
        state = fresh_state()
        save_state(state)
    return render_template('game.html', state=state, zones=ZONES,
                           zone_reqs=ZONE_LEVEL_REQ,
                           professions=PROFESSIONS,
                           trade_professions=TRADE_PROFESSIONS,
                           crafting_recipes=CRAFTING_RECIPES,
                           zone_resources=ZONE_RESOURCES,
                           skill_icons=SKILL_ICONS,
                           gather_button_labels=GATHER_BUTTON_LABELS,
                           gathering_skills=GATHERING_SKILLS,
                           crafting_skills_list=CRAFTING_SKILLS,
                           enemy_sprites=ENEMY_SPRITES)


@app.route('/action', methods=['POST'])
def action():
    state = get_state()
    if state is None:
        state = fresh_state()

    act    = request.form.get('action', '')
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
            state['player_class_pending'] = act
            state['screen'] = 'trade_prof_choice'

    elif screen == 'trade_prof_choice':
        if act in TRADE_PROFESSIONS:
            cls  = state.get('player_class_pending', 'Warrior')
            name = state.get('player_name', 'Hero')
            player = Player(name, cls)
            w = generate_weapon(player_class=cls, level=1, rarity='Common')
            a = generate_armor(level=1, rarity='Common')
            p = generate_consumable()
            player.add_item(w)
            player.add_item(a)
            player.add_item(p)
            player.equip(w)
            player.equip(a)
            player.trade_profession = act
            tp = TRADE_PROFESSIONS[act]
            for res, qty in tp['start_resources'].items():
                player.add_resource(res, qty)
            quest_log = QuestLog()
            for _ in range(3):
                quest_log.add_quest(generate_quest(zone=1, level=1))
            state['player']     = player
            state['quest_log']  = quest_log
            state['zone']       = 1
            state['messages']   = [{'kind': 'success',
                                     'text': f'Welcome, {name} the {cls}! Trade: {tp["icon"]} {act}. Your adventure begins!'}]
            state['screen'] = 'hub'

    elif screen == 'profession_choice':
        player = state['player']
        profs  = PROFESSIONS.get(player.player_class, {})
        if act in profs:
            ok, text = player.choose_profession(act)
            if ok:
                add_msg(state, 'success', text)
                pending = state.pop('pending_screen', 'hub')
                state['screen'] = pending
            else:
                add_msg(state, 'danger', text)
                state['screen'] = state.pop('pending_screen', 'hub')

    elif screen == 'hub':
        player    = state['player']
        quest_log = state['quest_log']
        clear_msgs(state)

        if act == 'explore':
            triggered = state.setdefault('triggered_events', set())
            events = explore_step(player, state['zone'], triggered)
            for ev_type, val, ev_msg in events:
                if ev_type == 'narrative':
                    if ev_msg:
                        add_msg(state, 'info', ev_msg)
                elif ev_type == 'gold':
                    player.gold += val
                    add_msg(state, 'gold', f'{ev_msg} +{val} gold!')
                elif ev_type == 'heal_pct':
                    amt = int(player.max_hp * val / 100)
                    healed = min(amt, player.max_hp - player.hp)
                    player.hp += healed
                    add_msg(state, 'heal', f'{ev_msg} +{healed} HP!')
                elif ev_type == 'heal_mp_pct':
                    amt = int(player.max_mp * val / 100)
                    restored = min(amt, player.max_mp - player.mp)
                    player.mp += restored
                    add_msg(state, 'heal', f'{ev_msg} +{restored} MP!')
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
                elif ev_type == 'trap_pct':
                    dmg = max(1, int(player.max_hp * val / 100))
                    player.hp = max(1, player.hp - dmg)
                    add_msg(state, 'danger', f'{ev_msg} -{dmg} HP! ({val}% of max HP)')
                elif ev_type == 'trap':
                    player.hp = max(1, player.hp - val)
                    add_msg(state, 'danger', f'{ev_msg} -{val} HP!')
                elif ev_type == 'encounter':
                    force_boss = ev_msg.startswith('💀')
                    add_msg(state, 'warning', ev_msg)
                    enemy = spawn_enemy(zone=state['zone'], level=player.level, force_boss=force_boss)
                    enemy_name_for_log = f"A {enemy.name}" if not enemy.is_boss else f"BOSS: {enemy.name}"
                    state['combat_enemy'] = enemy
                    state['combat_turn']  = 1
                    state['combat_log']   = [{'kind': 'info', 'text': f'{enemy_name_for_log} (Level ~{enemy.level}) appears!'}]
                    player.first_strike_used = False
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
                check_profession_unlock(state, player, 'hub')

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
        elif act == 'gather':
            state['screen'] = 'gather'
        elif act == 'craft':
            state['screen'] = 'craft'
        elif act == 'quit':
            state = fresh_state()

    elif screen == 'combat':
        ability_idx = None
        item_idx    = None
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
        stock  = state.get('shop_stock') or []
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
        player    = state['player']
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
        board     = state.get('board_quests') or []
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
        elif act.startswith('learn_prof_'):
            try:
                idx = int(act.split('_')[2])
            except (IndexError, ValueError):
                idx = -1
            avail = player.available_prof_skills()
            if 0 <= idx < len(avail):
                ok, text = player.learn_prof_skill(avail[idx])
                add_msg(state, 'success' if ok else 'danger', text)

    elif screen in ('abilities', 'stats'):
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)

    elif screen == 'gather':
        player = state['player']
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act.startswith('gather_'):
            skill_name = act.split('_', 1)[1]  # e.g. "gather_Mining" → "Mining"
            result = gather_resource(player, state['zone'], skill_name)
            if result is None:
                add_msg(state, 'warning', f'Your {skill_name} level is too low to gather here. Level up first!')
            else:
                res_name, qty, xp, leveled_up = result
                add_msg(state, 'success', f'Gathered {qty}× {res_name}! (+{xp} {skill_name} XP)')
                if leveled_up:
                    new_lv = player.gathering_skills[skill_name]['level']
                    add_msg(state, 'levelup', f'★ {skill_name} leveled up! Now level {new_lv}!')

    elif screen == 'craft':
        player = state['player']
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act.startswith('tab_'):
            state['craft_skill'] = act.split('_', 1)[1]
        elif act.startswith('craft_'):
            parts = act.split('_', 2)
            if len(parts) == 3:
                skill_name = parts[1]
                try:
                    recipe_idx = int(parts[2])
                except ValueError:
                    recipe_idx = -1
                ok, text, _ = craft_item(player, skill_name, recipe_idx,
                                          player_class=player.player_class)
                add_msg(state, 'success' if ok else 'danger', text)

    elif screen == 'game_over':
        if act == 'restart':
            state = fresh_state()

    save_state(state)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
