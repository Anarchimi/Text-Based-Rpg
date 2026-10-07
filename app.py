import os
import re
import sys
import uuid
import random
import pickle
from datetime import timedelta
from flask import Flask, session, request, redirect, url_for, render_template
from flask_compress import Compress

from player import Player, PROFESSIONS
from abilities import PROFESSION_ABILITIES
from enemies import BOSS_TEMPLATES, spawn_enemy, spawn_final_boss
from quests import BOUNTY_LEADER_CHANCE
from combat import ability_cost, defend_reduction, do_combat_turn, end_combat, hit_player  # noqa: F401  (hit_player re-exported for tests)
from quests import QuestLog, generate_quest
from items import (generate_shop_stock, generate_weapon, generate_armor, generate_consumable, upgrade_cost,
                   STAT_LABELS, LEGENDARY_EFFECTS, METAL_TRAIT_TEXT, SMITHED_WEAPON, PROFILES, WOODS)
from world import (travel_to_zone, ZONES, ZONE_LEVEL_REQ, LAIR_STEPS, MAX_DEPTH, DEPTH_GOLD, DEPTH_LUCK,
                   get_zone, generate_explore_options, describe_option, resolve_option, depth_effects)
import trades
from trades import TRADE_MILESTONES, next_milestone
from crafting import (TRADE_PROFESSIONS, CRAFTING_RECIPES, ZONE_RESOURCES,
                      GATHERING_SKILLS, CRAFTING_SKILLS, SKILL_ICONS,
                      GATHER_BUTTON_LABELS, gather_resource, craft_item, calc_skill_level)

app = Flask(__name__)
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    # No hardcoded fallback: a key committed to the repo lets anyone forge session cookies.
    # A per-process random key is safe but logs everyone out on restart, so set SECRET_KEY in production.
    print('WARNING: SECRET_KEY not set; using a random key (sessions reset on restart).', file=sys.stderr)
    _secret = os.urandom(32)
app.secret_key = _secret
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=365)
app.config['COMPRESS_MIMETYPES'] = [
    'text/html', 'text/css', 'application/json', 'application/javascript',
]
app.config['COMPRESS_LEVEL'] = 6
app.config['COMPRESS_MIN_SIZE'] = 500
Compress(app)

app.jinja_env.globals['enumerate'] = enumerate
app.jinja_env.globals['len'] = len
app.jinja_env.globals['upgrade_cost'] = upgrade_cost
app.jinja_env.globals['depth_effects'] = depth_effects
app.jinja_env.globals['max_depth'] = MAX_DEPTH
app.jinja_env.globals['next_milestone'] = next_milestone
app.jinja_env.globals['trade_milestones'] = TRADE_MILESTONES
app.jinja_env.globals['trades'] = trades
app.jinja_env.globals['metal_traits'] = METAL_TRAIT_TEXT
app.jinja_env.globals['smithed_weapon'] = SMITHED_WEAPON
app.jinja_env.globals['profiles'] = PROFILES
app.jinja_env.globals['woods'] = WOODS
app.jinja_env.globals['profession_abilities'] = PROFESSION_ABILITIES
app.jinja_env.globals['ability_cost'] = ability_cost
app.jinja_env.globals['defend_reduction'] = defend_reduction
app.jinja_env.globals['STAT_LABELS'] = STAT_LABELS
app.jinja_env.globals['LEGENDARY_EFFECTS'] = LEGENDARY_EFFECTS

# Saves outlive restarts: default to <repo>/instance/saves, override with RPG_SAVE_DIR
# (point it at a persistent volume in production).
def resolve_save_dir():
    return os.environ.get('RPG_SAVE_DIR') or os.path.join(app.instance_path, 'saves')


SAVE_DIR = resolve_save_dir()
os.makedirs(SAVE_DIR, exist_ok=True)

_PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL

# Keyed by how many seals are broken (not which zone), so any order reads right.
SEAL_MESSAGES = {
    1: "✦ The FIRST SEAL cracks. A darkness stirs beyond the horizon...",
    2: "✦ The SECOND SEAL shatters. Ancient powers begin to wake...",
    3: "✦ The THIRD SEAL breaks. The veil between worlds grows thin...",
    4: "✦ The FOURTH SEAL collapses. Reality itself begins to fracture...",
    5: "✦ THE FINAL SEAL IS BROKEN! The Chaos Dragon Lord awakens on Dragon's Peak. Go — end this.",
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
    "Shadow Sovereign": "🌑",
    "Ignaroth the Elder Wyrm": "🐉",
    "Chaos Dragon Lord":"🔥",
}


# ── State management ──────────────────────────────────────────────────────────

_SID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def _valid_sid(sid):
    """The sid becomes a filename we unpickle, so only accept a canonical UUID."""
    return isinstance(sid, str) and bool(_SID_RE.match(sid))


def get_state():
    sid = session.get('sid')
    if not _valid_sid(sid):
        return None
    try:
        with open(f'{SAVE_DIR}/{sid}.pkl', 'rb') as f:
            return migrate_state(pickle.load(f))
    except Exception:
        return None


def migrate_state(state):
    """Fill in state keys added after a save was written."""
    if 'seals' not in state:
        # Old saves only stored a count; assume the earliest zones' seals were broken.
        state['seals'] = set(range(1, state.get('narrative_stage', 0) + 1))
    for key, default in fresh_state().items():
        state.setdefault(key, default)
    return state


def save_state(state):
    sid = session.get('sid')
    if not _valid_sid(sid):
        sid = str(uuid.uuid4())
        session['sid'] = sid
    os.makedirs(SAVE_DIR, exist_ok=True)
    path = f'{SAVE_DIR}/{sid}.pkl'
    # Write then rename, so a crash mid-write can't leave a truncated save behind.
    tmp = f'{path}.{os.getpid()}.tmp'
    try:
        with open(tmp, 'wb') as f:
            pickle.dump(state, f, protocol=_PICKLE_PROTOCOL)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


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
        'narrative_stage': 0,     # == len(seals); kept for the hub seal bar
        'seals': set(),           # zone ids whose boss has been defeated
        'dragon_slain': False,
        'ng_plus': 0,
        'lair_progress': {},      # zone id -> explore steps taken there (LAIR_STEPS finds the boss)
        'depth': 0,               # trail depth: paths taken since last rest (see world.py)
        'explore_options': None,  # offered paths, kept until one is taken
        'pending_node': None,     # special trade node being decided (trades.py), shown on `node`
        'node_return': 'gather',  # screen to go back to after the node
        'workshop': None,         # {'skill', 'recipe', 'slot', 'additive'} on the `workshop` screen
        'alchemy_pick': [],       # up to two ingredients chosen on the `alchemy` screen
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


# ── Exploring ─────────────────────────────────────────────────────────────────

def nap_restore(player):
    """A nap restores half of what's *missing* (rounded up), so repeated naps never beat
    the Full Rest: each costs at least 40% of the base price but closes only half the gap."""
    return -(-(player.max_hp - player.hp) // 2), -(-(player.max_mp - player.mp) // 2)


def fully_rested(player):
    return player.hp >= player.max_hp and player.mp >= player.max_mp


def inn_prices(player):
    """(full rest, nap) in gold. Scales with level and with how much HP *and* MP is missing."""
    missing = (player.max_hp - player.hp) // 8 + (player.max_mp - player.mp) // 8
    full = 10 + player.level * 6 + missing
    return full, max(5, int(full * 0.4))


app.jinja_env.globals['inn_prices'] = inn_prices
app.jinja_env.globals['fully_rested'] = fully_rested
app.jinja_env.globals['nap_restore'] = nap_restore


def special_node_for(player, zone, skill):
    """Occasionally a routine gather tap turns into a special node (milestone-gated)."""
    if skill == 'Mining' and random.random() < trades.VEIN_CHANCE:
        return trades.make_vein_node(player, zone)
    if skill == 'Herbalism' and random.random() < trades.PATCH_CHANCE:
        return trades.make_patch_node(player, zone)
    if skill == 'Fishing' and random.random() < trades.BITE_CHANCE:
        return trades.make_bite_node(player, zone)
    if skill == 'Woodcutting' and random.random() < trades.TREE_CHANCE:
        return trades.make_tree_node(player, zone)
    return None


def open_node(state, node, return_to):
    state['pending_node'] = node
    state['node_return'] = return_to
    state['screen'] = 'node'


def reset_depth(state):
    """Resting or leaving the zone ends the trail; offered paths re-roll for the new depth."""
    if state.get('depth'):
        state['depth'] = 0
        state['explore_options'] = None


def start_combat(state, enemy, intro, kind='info', return_to='hub'):
    state['combat_enemy'] = enemy
    state['combat_turn'] = 1
    state['combat_log'] = [{'kind': kind, 'text': intro}]
    snare = trades.spring_trap(state['player'], enemy)
    if snare:
        state['combat_log'].append({'kind': 'player', 'text': snare})
    state['return_to'] = return_to
    state['player'].first_strike_used = False
    state['screen'] = 'combat'


def ensure_explore_options(state):
    """Offer paths once; they persist until one is taken (no rerolling by backing out)."""
    if state.get('explore_options'):
        return
    player = state['player']
    options = generate_explore_options(player, state['zone'], state.setdefault('triggered_events', set()),
                                       state.get('depth', 0), ng=state.get('ng_plus', 0))
    for opt in options:
        enemy = opt.get('enemy')
        if (enemy and not enemy.is_boss and random.random() < BOUNTY_LEADER_CHANCE
                and any(q.quest_type == 'bounty' and q.target_name == enemy.name
                        for q in state['quest_log'].active_quests())):
            enemy.make_leader()
    for opt in options:
        opt['title'], opt['detail'] = describe_option(opt, state['zone'], player.level)
    state['explore_options'] = options


def take_explore_path(state, player, opt):
    state['explore_options'] = None
    zone = state['zone']
    lairs = state['lair_progress']
    lairs[zone] = lairs.get(zone, 0) + 1
    if lairs[zone] == LAIR_STEPS:
        add_msg(state, 'lore', f"💀 You've found the lair of {zone_boss_name(zone)}! "
                               f"You can challenge it from the hub whenever you're ready.")
    depth = state.get('depth', 0)
    state['depth'] = min(MAX_DEPTH, depth + 1)
    events = resolve_option(opt, player, zone, state.setdefault('triggered_events', set()), depth)
    apply_explore_events(state, player, events)
    if state['screen'] == 'explore':
        after_explore_step(state, player)
    # else: a fight or a special node opened; the step finishes when that resolves


def after_explore_step(state, player):
    """Quest progress, profession prompt and fresh paths after a non-fight trail step."""
    quest_log = state['quest_log']
    quest_log.check_event('explore', get_zone(state['zone'])['name'])
    complete_finished_quests(state, player, quest_log)
    if not check_profession_unlock(state, player, 'explore'):
        ensure_explore_options(state)


def complete_finished_quests(state, player, quest_log):
    for q in list(quest_log.active_quests()):
        if q.is_complete():
            quest_log.finish_quest(q)
            player.gold += q.reward_gold
            player.gain_xp(q.reward_xp)
            player.quests_completed += 1
            add_msg(state, 'quest', f'Quest complete: {q.title}! +{q.reward_gold}g +{q.reward_xp} XP')


def apply_explore_events(state, player, events):
    """Apply (event_type, value, message) outcomes from world.resolve_option."""
    def say(kind, msg, suffix):
        add_msg(state, kind, f'{msg} {suffix}'.strip())

    for ev_type, val, ev_msg in events:
        if ev_type == 'gold':
            player.gold += val
            say('gold', ev_msg, f'+{val} gold!')
        elif ev_type == 'heal_pct':
            healed = min(int(player.max_hp * val / 100), player.max_hp - player.hp)
            player.hp += healed
            say('heal', ev_msg, f'+{healed} HP!')
        elif ev_type == 'heal_mp_pct':
            restored = min(int(player.max_mp * val / 100), player.max_mp - player.mp)
            player.mp += restored
            say('heal', ev_msg, f'+{restored} MP!')
        elif ev_type == 'xp':
            levels = player.gain_xp(val)
            say('xp', ev_msg, f'+{val} XP!')
            for lvl in levels:
                add_msg(state, 'levelup', f'★ LEVEL UP! Now Level {lvl}!')
        elif ev_type == 'trap_pct':
            dmg = max(1, int(player.max_hp * val / 100))
            player.hp = max(1, player.hp - dmg)
            say('danger', ev_msg, f'-{dmg} HP!')
        elif ev_type == 'item':
            player.add_item(val)
            say('loot', ev_msg, f'[{val.rarity}] {val.name}')
        elif ev_type == 'resource':
            add_msg(state, 'success', ev_msg)
        elif ev_type == 'set_depth':
            state['depth'] = val
            state['explore_options'] = None
            add_msg(state, 'dim', f'Your camp kept you on the trail — depth {val}.')
        elif ev_type == 'reset_depth':
            reset_depth(state)
            add_msg(state, 'dim', 'Rested — the trail depth resets.')
        elif ev_type == 'node':
            add_msg(state, 'info', ev_msg)
            open_node(state, val, return_to=state['screen'])
            return
        elif ev_type == 'encounter':
            add_msg(state, 'warning', ev_msg)
            enemy = val
            label = f'BOSS: {enemy.name}' if enemy.is_boss else f'A {enemy.name}'
            start_combat(state, enemy, f'{label} (Level ~{enemy.level}) appears!', return_to='explore')
            return
        elif ev_msg:
            add_msg(state, 'info' if ev_type == 'narrative' else 'dim', ev_msg)


def zone_boss_name(zone):
    return next(b['name'] for b in BOSS_TEMPLATES if b['zone'] == zone)


def lair_found(state):
    return state.get('lair_progress', {}).get(state['zone'], 0) >= LAIR_STEPS


def final_battle_available(state):
    return (len(state.get('seals', ())) >= 5 and not state.get('dragon_slain')
            and state['zone'] == 5)


def start_new_game_plus(state):
    """Keep the character and gear; restart the story with tougher enemies."""
    player = state['player']
    state['ng_plus'] = state.get('ng_plus', 0) + 1
    state['seals'] = set()
    state['narrative_stage'] = 0
    state['dragon_slain'] = False
    state['triggered_events'] = set()
    state['lair_progress'] = {}
    state['zone'] = 1
    player.hp, player.mp = player.max_hp, player.max_mp
    state['screen'] = 'hub'
    add_msg(state, 'lore', f"NEW GAME+ {state['ng_plus']}: The seals reform. The realm remembers your name — "
                           f"and so does the darkness. Enemies are stronger; their treasure richer.")


def finish_combat_victory(state):
    player    = state['player']
    enemy     = state['combat_enemy']
    quest_log = state['quest_log']
    log       = state['combat_log']

    end_combat(player)
    depth = state.get('depth', 0) if state.get('return_to') == 'explore' else 0
    items, gold = enemy.loot_drop(player.level, int(player.lck) + 10 * state.get('ng_plus', 0) + depth * DEPTH_LUCK,
                                  player_class=player.player_class)
    gold = int(gold * (1 + depth * DEPTH_GOLD))
    player.gold += gold
    player.kills += 1
    player.first_strike_used = False  # reset Ranger passive

    log.append({'kind': 'victory', 'text': f'VICTORY! Defeated the {enemy.name}!'})
    log.append({'kind': 'xp',      'text': f'+{enemy.xp} XP   +{gold} gold'})

    for item in items:
        log.append({'kind': 'loot', 'text': f'Loot: {item.name} [{item.rarity}]'})
        player.add_item(item)

    reagent = trades.reagent_drop(enemy.name)
    if reagent:
        player.add_resource(reagent, 1)
        log.append({'kind': 'loot', 'text': f'Reagent: 1× {reagent}'})

    for q in quest_log.check_event('kill', enemy.name):
        log.append({'kind': 'quest', 'text': f'Quest progress: {q.title}'})

    levels = player.gain_xp(enemy.xp)
    for lvl in levels:
        log.append({'kind': 'levelup', 'text': f'★ LEVEL UP! Now Level {lvl}! +2 Skill Points'})

    # Narrative arc — Five Seals
    seals = state.setdefault('seals', set())
    if enemy.seal and enemy.seal not in seals:
        seals.add(enemy.seal)
        state['narrative_stage'] = len(seals)
        log.append({'kind': 'lore', 'text': SEAL_MESSAGES[len(seals)]})

    quest_log.check_event('explore', get_zone(state['zone'])['name'])
    for q in list(quest_log.active_quests()):
        if q.is_complete():
            quest_log.finish_quest(q)
            player.gold += q.reward_gold
            player.gain_xp(q.reward_xp)
            player.quests_completed += 1
            log.append({'kind': 'quest', 'text': f'Quest complete: {q.title}! +{q.reward_gold}g +{q.reward_xp} XP'})

    state['combat_enemy'] = None

    if enemy.is_final:
        state['dragon_slain'] = True
        state['screen'] = 'ending'
        return
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
                           enemy_sprites=ENEMY_SPRITES,
                           final_ready=bool(state.get('player')) and final_battle_available(state),
                           lair_steps=LAIR_STEPS,
                           zone_boss=zone_boss_name(state.get('zone') or 1))


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
            ensure_explore_options(state)
            state['screen'] = 'explore'

        elif act == 'challenge_boss' and lair_found(state):
            enemy = spawn_enemy(zone=state['zone'], level=player.level, force_boss=True,
                                ng=state.get('ng_plus', 0))
            start_combat(state, enemy, f'You enter the lair. {enemy.name} rises to meet you!', kind='lore')

        elif act == 'final_battle' and final_battle_available(state):
            enemy = spawn_final_boss(player.level, ng=state.get('ng_plus', 0))
            start_combat(state, enemy, "The sky splits open. The Chaos Dragon Lord descends upon Dragon's Peak!",
                         kind='lore')

        elif act == 'shop':
            state['shop_stock'] = generate_shop_stock(player.level, player.player_class)
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
            end_combat(state['player'])
            state['screen'] = 'game_over'
            state['combat_enemy'] = None
        elif result == 'fled':
            end_combat(state['player'])
            state.pop('return_to', None)
            state['combat_enemy'] = None
            state['screen'] = 'hub'
            add_msg(state, 'warning', 'You fled from the battle!')
        elif result == 'revived':
            end_combat(state['player'])
            state.pop('return_to', None)
            state['combat_enemy'] = None
            state['screen'] = 'hub'
            add_msg(state, 'warning', 'You were revived! Your revive item was used up.')

    elif screen == 'explore':
        player = state['player']
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act.startswith('choose_'):
            try:
                idx = int(act.split('_')[1])
            except (IndexError, ValueError):
                idx = -1
            options = state.get('explore_options') or []
            if 0 <= idx < len(options):
                clear_msgs(state)
                take_explore_path(state, player, options[idx])

    elif screen == 'node':
        player = state['player']
        node = state.get('pending_node')
        key = act[5:] if act.startswith('node_') else None
        if node and key in {o['key'] for o in node['options']}:
            clear_msgs(state)
            state['pending_node'] = None
            back = state.get('node_return') or 'hub'
            state['screen'] = back
            apply_explore_events(state, player, trades.resolve_node(node, key, player))
            if state['screen'] == 'explore':
                after_explore_step(state, player)
        elif not node:
            state['screen'] = state.get('node_return') or 'hub'

    elif screen == 'workshop':
        player = state['player']
        ws = state.get('workshop') or {}
        recipes = CRAFTING_RECIPES.get(ws.get('skill'), [])
        recipe = recipes[ws['recipe']] if 0 <= ws.get('recipe', -1) < len(recipes) else None
        if act == 'back' or recipe is None:
            state['screen'] = 'craft'
            clear_msgs(state)
        elif act in ('ws_slot_weapon', 'ws_slot_armor'):
            ws['slot'] = act.rsplit('_', 1)[1]
        elif act.startswith('ws_profile_') and act[len('ws_profile_'):] in PROFILES:
            ws['profile'] = act[len('ws_profile_'):]
        elif act.startswith('ws_add_'):
            add = act[len('ws_add_'):]
            ws['additive'] = add if add in trades.usable_additives(player, ws['skill']) else None
        elif act == 'ws_forge':
            clear_msgs(state)
            choice = ws.get('slot', 'weapon') if ws['skill'] == 'Smithing' else ws.get('profile', 'Power')
            ok, text, _ = trades.bench_craft(player, ws['skill'], recipe, choice, ws.get('additive'))
            add_msg(state, 'success' if ok else 'danger', text)
            if ws.get('additive') not in trades.usable_additives(player, ws['skill']):
                ws['additive'] = None

    elif screen == 'alchemy':
        player = state['player']
        pick = state.setdefault('alchemy_pick', [])
        if act == 'back':
            state['screen'] = 'craft'
            state['alchemy_pick'] = []
            clear_msgs(state)
        elif act.startswith('alc_pick_'):
            name = act[len('alc_pick_'):]
            if name in pick:
                pick.remove(name)
            elif name in trades.owned_ingredients(player) and len(pick) < 2:
                pick.append(name)
        elif act == 'alc_mix' and len(pick) == 2:
            clear_msgs(state)
            kind, text, _ = trades.experiment(player, *pick)
            add_msg(state, {'discovery': 'levelup', 'known': 'success', 'unstable': 'warning'}.get(kind, 'danger'), text)
            state['alchemy_pick'] = [n for n in pick if player.resources.get(n, 0) > 0]
        elif act.startswith('alc_brew_'):
            clear_msgs(state)
            ok, text, _ = trades.brew_known(player, act[len('alc_brew_'):])
            add_msg(state, 'success' if ok else 'danger', text)

    elif screen == 'combat_result':
        if act == 'continue':
            state['screen'] = state.pop('return_to', 'hub')
            state['combat_log'] = []
            if state['screen'] == 'explore':
                ensure_explore_options(state)

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
        player = state['player']
        full_cost, nap_cost = inn_prices(player)
        if act == 'back':
            state['screen'] = 'hub'
            clear_msgs(state)
        elif act in ('full_rest', 'nap'):
            cost = full_cost if act == 'full_rest' else nap_cost
            if fully_rested(player):
                add_msg(state, 'dim', "You're already fully rested.")
            elif player.gold < cost:
                add_msg(state, 'danger', f'Not enough gold! ({cost}g)')
            else:
                player.gold -= cost
                if act == 'full_rest':
                    player.hp, player.mp = player.max_hp, player.max_mp
                    add_msg(state, 'success', f'You rest well. HP and MP fully restored! (-{cost}g)')
                else:
                    hp, mp = nap_restore(player)
                    player.hp += hp
                    player.mp += mp
                    add_msg(state, 'success', f'You take a short nap: +{hp} HP, +{mp} MP. (-{cost}g)')
                reset_depth(state)

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
                state['explore_options'] = None
                reset_depth(state)
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
            equippable = [i for i in player.inventory if i.item_type in ('weapon', 'armor', 'accessory')]
            if 0 <= idx < len(equippable):
                ok, text = player.equip(equippable[idx])
                add_msg(state, 'success' if ok else 'danger', text)
        elif act.startswith('temper_'):
            _, slot, name = act.split('_', 2)
            ok, text = trades.temper(player, player.equipment.get(slot), name)
            add_msg(state, 'success' if ok else 'danger', text)
        elif act in ('upgrade_weapon', 'upgrade_armor'):
            ok, text = player.upgrade_equipped(act.split('_', 1)[1])
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
            clear_msgs(state)
            node = special_node_for(player, state['zone'], skill_name)
            if node:
                add_msg(state, 'info', 'Something unusual catches your eye…')
                open_node(state, node, return_to='gather')
                result = None
                skill_name = None
            else:
                result = gather_resource(player, state['zone'], skill_name)
            if skill_name is None:
                pass
            elif result is None:
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
        elif act == 'alchemy':
            clear_msgs(state)
            state['alchemy_pick'] = []
            state['screen'] = 'alchemy'
        elif act.startswith('forge_'):
            try:
                idx = int(act.split('_', 1)[1])
            except ValueError:
                idx = -1
            recipes = CRAFTING_RECIPES.get(state['craft_skill'], [])
            if 0 <= idx < len(recipes) and recipes[idx]['output_type'] in ('forge', 'fletch'):
                clear_msgs(state)
                state['workshop'] = {'skill': state['craft_skill'], 'recipe': idx, 'slot': 'weapon',
                                     'profile': 'Power', 'additive': None}
                state['screen'] = 'workshop'
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

    elif screen == 'ending':
        if act == 'new_game_plus':
            start_new_game_plus(state)
        elif act == 'continue':
            state['screen'] = 'hub'

    elif screen == 'game_over':
        if act == 'restart':
            state = fresh_state()

    if state.get('player'):
        for msg in state['player'].pop_unlocks():
            add_msg(state, 'levelup', msg)
    save_state(state)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
