"""Turn-based combat engine used by the web app.

One call to do_combat_turn() is one round: the player acts, then the enemy acts,
then statuses tick. It returns 'continue', 'victory', 'defeat', 'fled' or 'revived'.
"""
import random

from enemies import ability_spec, mitigate

ENEMY_ABILITY_CHANCE = 0.30
BOSS_ABILITY_CHANCE = 0.40
PHASE2_ABILITY_CHANCE = 0.55
DEFEND_MP_REGEN = 0.08        # Defend restores this fraction of max MP
STUN_IMMUNITY_TURNS = 2       # after being stunned, the player can't be stunned again for a bit
SHADOW_STEP_CRIT_BONUS = 0.25
# Legendary gear effects (items.LEGENDARY_EFFECTS)
VAMPIRIC_HEAL = 0.10
THORNS_REFLECT = 0.20
EXECUTIONER_THRESHOLD = 0.35
BULWARK_HEAL = 0.10
# Profession perks
MOMENTUM_STEP = 0.06
MOMENTUM_MAX = 5
BLIND_MISS = 0.40


def flee_chance(player, enemy):
    """Faster characters escape more often; bosses are harder to shake."""
    chance = 0.40 + player.speed * 0.008
    if enemy.is_boss:
        chance -= 0.20
    return max(0.10, min(0.90, chance))


def hit_player(player, dmg, clog, defending=False, attacker=None):
    """Apply incoming enemy damage after Evasion / Defend / Mana Shield. Returns HP lost."""
    if 'Evasion' in player.buffs:
        del player.buffs['Evasion']
        clog('buff', 'You evade the attack!')
        return 0
    if defending:
        dmg = max(1, dmg * (100 - defend_reduction(player)) // 100)
    if 'Mana Shield' in player.buffs:
        absorbed = min(player.mp, dmg // 2)
        if absorbed:
            player.mp -= absorbed
            dmg -= absorbed
            clog('buff', f'Mana Shield absorbs {absorbed} damage!')
    player.hp = max(0, player.hp - dmg)
    if attacker is not None and dmg and 'Riposte' in player.buffs:
        dealt = attacker.take_damage(int(player.attack * 0.6))
        clog('player', f'Riposte! You strike back for {dealt}.')
    if attacker is not None and dmg and player.has_effect('Thorns'):
        reflected = max(1, int(dmg * THORNS_REFLECT))
        attacker.hp = max(0, attacker.hp - reflected)
        clog('player', f'Thorns: {attacker.name} takes {reflected} damage!')
    return dmg


def end_combat(player):
    """Debuffs and once-per-fight effects only exist inside a fight."""
    player.debuffs.clear()
    player.buffs.pop('Steadfast', None)
    player.second_wind_used = False
    player.momentum = 0
    player.deathless_used = False
    if player.meal:  # meals last a number of fights
        player.meal["fights"] -= 1
        if player.meal["fights"] <= 0:
            player.meal = None


def defend_reduction(player):
    """% of incoming damage that Defend blocks (Knight's Bastion perk raises it)."""
    return 75 if player.has_perk('Bastion') else 50


def ability_cost(player, ability):
    if player.has_effect('Arcane Flow') and ability.mp_cost > 0:  # free abilities stay free
        return max(1, -(-ability.mp_cost * 3 // 4))  # 25% off, rounded up
    return ability.mp_cost


def _legendary_damage(player, enemy, dmg):
    if player.has_effect('Executioner') and enemy.hp < enemy.max_hp * EXECUTIONER_THRESHOLD:
        dmg = int(dmg * 1.25)
    return dmg


def _after_hit(player, actual, clog):
    if actual and 'Blood Frenzy' in player.buffs:
        _heal(player, int(actual * 0.15), 'Blood Frenzy', clog)
    if actual and player.has_effect('Vampiric'):
        healed = min(max(1, int(actual * VAMPIRIC_HEAL)), player.max_hp - player.hp)
        if healed:
            player.hp += healed
            clog('heal', f'Vampiric: +{healed} HP')


# ── Player side ────────────────────────────────────────────────────────────────

def _strike(enemy, dmg, clog):
    """Deal player damage to the enemy. Returns damage dealt, or None if dodged."""
    if 'Evading' in enemy.statuses:
        del enemy.statuses['Evading']
        clog('warning', f'{enemy.name} dodges your attack!')
        return None
    return enemy.take_damage(dmg)


def _apply_enemy_status(enemy, status, power, clog):
    if status == 'Stunned':
        enemy.stunned = True
        clog('stun', f'{enemy.name} is stunned next turn!')
    elif status == 'Burning':
        enemy.dot = max(enemy.dot, 3)
        enemy.dot_dmg = max(enemy.dot_dmg, max(1, int(power * 0.25)))
        enemy.dot_name = 'Burn'
        clog('poison', f'{enemy.name} is burning! ({enemy.dot_dmg} dmg/turn)')
    elif status == 'Chilled':
        enemy.statuses['Chilled'] = 3
        clog('stun', f'{enemy.name} is chilled! (ATK -25%)')


def rage_threshold(player):
    return 0.5 if player.has_perk('Undying Rage') else 0.3


def _enemy_afflicted(enemy):
    return enemy.stunned or enemy.dot > 0 or 'Chilled' in enemy.statuses


def _damage_mods(player, enemy, dmg, clog, spell=False):
    """Profession passives, perks and buffs that scale any player damage."""
    if spell and player.profession == 'Sorcerer':
        dmg *= 1.3
    if spell and player.profession == 'Necromancer' and enemy.hp < enemy.max_hp * 0.5:
        dmg *= 1.2
    if player.profession == 'Berserker' and player.hp < player.max_hp * rage_threshold(player):
        dmg *= 1.5
        clog('buff', 'BERSERK RAGE! +50% ATK!')
    if 'Blood Frenzy' in player.buffs:
        dmg *= 1.4
    if player.has_perk('Momentum') and player.momentum:
        dmg *= 1 + MOMENTUM_STEP * player.momentum
    if player.has_perk('Exploit Weakness') and _enemy_afflicted(enemy):
        dmg *= 1.3
    return _legendary_damage(player, enemy, int(dmg))


def _build_momentum(player):
    if player.has_perk('Momentum'):
        player.momentum = min(MOMENTUM_MAX, player.momentum + 1)


def _player_attack(player, enemy, clog):
    bonus = random.randint(-2, 4)
    crit = random.random() < (0.05 + player.dex / 200 + player.crit_bonus)
    dmg = int((player.attack + bonus) * (1.8 if crit else 1.0))

    first_strike = player.profession == 'Ranger' and not player.first_strike_used
    if first_strike:
        boost = 1.5 if player.has_perk("Hunter's Mark") else 1.2
        dmg = int(dmg * boost)
        player.first_strike_used = True
        clog('buff', f'Ranger first-strike bonus! +{int((boost - 1) * 100)}% ATK')
    dmg = _damage_mods(player, enemy, dmg, clog)

    actual = _strike(enemy, dmg, clog)
    _build_momentum(player)
    if actual is None:
        return
    if crit:
        clog('crit', '★ CRITICAL HIT!')
    clog('player', f'{player.name} attacks for {actual} damage.')
    _after_hit(player, actual, clog)
    if first_strike and player.has_perk("Hunter's Mark"):
        enemy.dot, enemy.dot_dmg, enemy.dot_name = max(enemy.dot, 3), max(enemy.dot_dmg, int(player.attack * 0.25)), 'Bleed'
        clog('poison', f"Hunter's Mark: {enemy.name} bleeds for {enemy.dot_dmg}/turn!")


def _ability_hit(player, enemy, picked, power, clog):
    """One strike of a damage ability. Returns damage dealt (0 if dodged)."""
    effect = picked.calculate_effect(power)
    crit_chance = 0.12 + player.crit_bonus
    if picked.name == 'Shadow Step':
        crit_chance += SHADOW_STEP_CRIT_BONUS
    if player.has_perk('Spellweaver'):
        crit_chance += 0.15
    if picked.name == 'Volley':  # arrows crit like basic attacks
        crit_chance = 0.05 + player.dex / 200 + player.crit_bonus
    if picked.name == 'Shadowstrike' and (enemy.stunned or enemy.hp < enemy.max_hp * 0.4):
        crit_chance = 1.0
    crit = random.random() < crit_chance
    dmg = effect * (1.5 if crit else 1.0)

    if picked.name == 'Convergence' and (enemy.dot_name == 'Burn' and enemy.dot > 0 or 'Chilled' in enemy.statuses):
        dmg *= 2
        clog('crit', 'CONVERGENCE! 2× DAMAGE!')
    if picked.name == 'Execute' and enemy.hp < enemy.max_hp * 0.30:
        dmg *= 2
        clog('crit', 'EXECUTE! 2× DAMAGE!')
    if picked.name == 'Death Mark':
        mult = 3
        if player.profession == 'Assassin':
            mult = 5 if enemy.hp < enemy.max_hp * 0.40 else 4
        dmg *= mult
        clog('crit', f'DEATH MARK! {mult}× DAMAGE!')
    dmg = _damage_mods(player, enemy, dmg, clog, spell=player.player_class == 'Mage')

    actual = _strike(enemy, dmg, clog)
    if actual is None:
        return 0
    if crit:
        clog('crit', '★ CRITICAL!')
    clog('player', f'{picked.name}: {actual} damage!')
    _after_hit(player, actual, clog)
    if picked.status and random.random() < picked.status_chance:
        _apply_enemy_status(enemy, picked.status, power, clog)
    if player.profession == 'Elementalist':
        wildfire = player.has_perk('Wildfire')
        if random.random() < (0.5 if wildfire else 0.3):
            _apply_enemy_status(enemy, 'Burning', power * (1.5 if wildfire else 1), clog)
    return actual


def _player_ability(player, enemy, picked, clog):
    cost = ability_cost(player, picked)
    if player.mp < cost:
        clog('danger', 'Not enough MP!')
        return False
    hp_cost = int(player.max_hp * picked.hp_cost_pct)
    if hp_cost and player.hp <= hp_cost:
        clog('danger', 'Too wounded to pay the blood price!')
        return False
    player.mp -= cost
    if hp_cost:
        player.hp -= hp_cost
        clog('danger', f'{picked.name} costs {hp_cost} HP.')
    power = player.ability_power
    effect = picked.calculate_effect(power)

    if picked.ability_type == 'damage':
        total = sum(_ability_hit(player, enemy, picked, power, clog) for _ in range(picked.hits))
        _build_momentum(player)
        if picked.name == 'Rallying Strike':
            _heal(player, int(player.max_hp * 0.10), 'Rallying Strike', clog)
        if picked.name == 'Soul Harvest' and total:
            _heal(player, total // 2, 'Soul Harvest', clog)

    elif picked.ability_type == 'heal':
        healed = min(effect, player.max_hp - player.hp)
        player.hp += healed
        clog('heal', f'{picked.name}: Restored {healed} HP!')
    elif picked.ability_type == 'buff':
        player.buffs[picked.name] = 3
        clog('buff', f'{picked.name} activated for 3 turns!')
    elif picked.ability_type == 'dot':
        turns, dot_dmg = 3, effect
        if player.profession == 'Trickster':
            turns, dot_dmg = 5, int(dot_dmg * 1.5)
        if player.has_perk('Stacking Venom') and enemy.dot > 0 and enemy.dot_name == 'Poison':
            dot_dmg = min(enemy.dot_dmg + dot_dmg, dot_dmg * 3)
            clog('poison', 'Stacking Venom: the poison deepens!')
        enemy.dot = max(enemy.dot, turns)
        enemy.dot_dmg = dot_dmg
        enemy.dot_name = 'Poison'
        clog('poison', f'Poisoned {enemy.name} for {dot_dmg} dmg/turn x{turns} turns!')
    elif picked.name == 'Blinding Powder':
        enemy.statuses['Blinded'] = 4
        clog('stun', f'{enemy.name} is blinded! (misses 40% of attacks for 3 turns)')
    elif picked.ability_type == 'debuff':
        enemy.stunned = True
        clog('stun', f'{enemy.name} is blinded and will lose its next turn!')
    return True


def _heal(player, amount, source, clog):
    healed = min(max(0, amount), player.max_hp - player.hp)
    if healed:
        player.hp += healed
        clog('heal', f'{source}: +{healed} HP')


# ── Enemy side ─────────────────────────────────────────────────────────────────

def _enemy_hit(player, enemy, mult, clog, defending):
    if 'Blinded' in enemy.statuses and random.random() < BLIND_MISS:
        clog('buff', f'{enemy.name} swings blindly and misses!')
        return 0
    raw = enemy.effective_atk * mult * random.uniform(0.9, 1.1)
    return hit_player(player, mitigate(raw, player.defense), clog, defending, attacker=enemy)


def _enemy_ability(player, enemy, name, spec, clog, defending):
    kind = spec['kind']
    text = spec.get('text')
    turns = spec.get('turns', 2)

    if kind == 'enrage':
        enemy.statuses['Enraged'] = 99
        clog('enemy', f'{enemy.name} {text or "becomes enraged"}! (ATK +30%)')
        return
    if kind == 'shield':
        enemy.statuses['Shielded'] = turns + 1
        clog('enemy', f'{enemy.name} {text or "raises a shield"}! (takes half damage)')
        return
    if kind == 'evade':
        enemy.statuses['Evading'] = 3
        clog('enemy', f'{enemy.name} {text or "gets ready to dodge"}! (will dodge your next attack)')
        return

    clog('enemy', f'{enemy.name} {text}!' if text else f'{enemy.name} uses {name}!')
    total, dodged = 0, False
    mult = spec.get('mult', 1.3)
    if mult > 0:
        for _ in range(spec.get('hits', 1)):
            lost = _enemy_hit(player, enemy, mult, clog, defending)
            dodged = dodged or lost == 0
            total += lost
            if not enemy.is_alive():  # killed by Riposte/Thorns mid-sequence
                break
        if total:
            clog('enemy', f'-{total} HP')
    if not enemy.is_alive():
        return  # a dead attacker lands no rider effects (drain, DoT, stun...)
    if dodged and spec.get('hits', 1) == 1:
        return  # a dodged single hit lands no rider effect

    if kind == 'drain' and total:
        healed = min(total // 2, enemy.max_hp - enemy.hp)
        enemy.hp += healed
        if healed:
            clog('enemy', f'{enemy.name} drains {healed} HP from you!')
    if kind in ('dot', 'weaken', 'stun') and player.meal and random.random() < player.meal.get('resist', 0):
        clog('buff', f"Your {player.meal['name']} steadies you — you resist the effect!")
        return
    if kind == 'dot':
        status = spec['status']
        tick = max(1, int(enemy.effective_atk * spec.get('dot', 0.25)))
        player.add_debuff(status, turns + 1, tick)
        clog('danger', f'You are {status.lower()}! ({tick} dmg/turn for {turns} turns)')
    elif kind == 'weaken':
        player.add_debuff('Weakened', turns + 1)
        clog('danger', f'You are weakened! (ATK -25% for {turns} turns)')
    elif kind == 'stun':
        if defending:
            clog('buff', 'You brace yourself and keep your footing.')
        elif 'Steadfast' in player.buffs:
            clog('buff', 'You shrug off the stun.')
        elif random.random() < spec.get('chance', 0.3):
            player.debuffs['Stunned'] = {'turns': 1, 'dmg': 0}
            clog('stun', 'You are stunned! You will lose your next turn.')


def _enemy_turn(player, enemy, clog, defending):
    if enemy.stunned:
        enemy.stunned = False
        if enemy.charging:
            clog('stun', f'{enemy.name}\'s {enemy.charging} is interrupted!')
            enemy.charging = None
        clog('warning', f'{enemy.name} is stunned and loses its turn!')
        return

    if enemy.charging:
        name, enemy.charging = enemy.charging, None
        _enemy_ability(player, enemy, name, ability_spec(name), clog, defending)
        return

    if enemy.phase == 2:
        chance = PHASE2_ABILITY_CHANCE
    elif enemy.is_boss:
        chance = BOSS_ABILITY_CHANCE
    else:
        chance = ENEMY_ABILITY_CHANCE

    if enemy.abilities and random.random() < chance:
        name = random.choice(enemy.abilities)
        spec = ability_spec(name)
        repeat_buff = ((spec['kind'] == 'enrage' and 'Enraged' in enemy.statuses)
                       or (spec['kind'] == 'shield' and 'Shielded' in enemy.statuses)
                       or (spec['kind'] == 'evade' and 'Evading' in enemy.statuses))
        if not repeat_buff:
            if spec.get('charge'):
                enemy.charging = name
                clog('danger', f'⚠ {enemy.name} begins gathering power for {name}! '
                               f'Defend, dodge or stun it!')
                return
            _enemy_ability(player, enemy, name, spec, clog, defending)
            return

    crit = random.random() < 0.1
    lost = _enemy_hit(player, enemy, 1.5 if crit else 1.0, clog, defending)
    if lost:
        clog('enemy', f'{enemy.name} {"CRITS" if crit else "attacks"}: -{lost} HP')


def _check_boss_phase(enemy, clog):
    if enemy.is_boss and enemy.phase == 1 and enemy.hp < enemy.max_hp * 0.5:
        enemy.phase = 2
        enemy.statuses.pop('Chilled', None)
        if enemy.phase2_text:
            clog('lore', enemy.phase2_text)
        clog('danger', f'{enemy.name} enters its second phase! (ATK +15%, uses abilities more often)')


# ── Round ──────────────────────────────────────────────────────────────────────

def do_combat_turn(state, action, ability_idx=None, item_idx=None):
    player = state['player']
    enemy  = state['combat_enemy']
    log    = state['combat_log']

    def clog(kind, text):
        log.append({'kind': kind, 'text': text})

    defending = False
    if action not in ('attack', 'ability'):
        player.momentum = 0
    if 'Stunned' in player.debuffs:
        player.momentum = 0
        del player.debuffs['Stunned']
        player.buffs['Steadfast'] = STUN_IMMUNITY_TURNS
        clog('stun', 'You are stunned and cannot act!')
    elif action == 'attack':
        _player_attack(player, enemy, clog)
    elif action == 'defend':
        defending = True
        regen = min(int(player.max_mp * DEFEND_MP_REGEN), player.max_mp - player.mp)
        player.mp += regen
        reduction = defend_reduction(player)
        clog('buff', f'You raise your guard. ({reduction}% damage reduction, no stuns this turn, +{regen} MP)')
        if player.has_effect('Bulwark'):
            healed = min(int(player.max_hp * BULWARK_HEAL), player.max_hp - player.hp)
            player.hp += healed
            clog('heal', f'Bulwark: +{healed} HP')
    elif action == 'ability' and ability_idx is not None:
        abilities = player.get_abilities()
        if 0 <= ability_idx < len(abilities):
            if not _player_ability(player, enemy, abilities[ability_idx], clog):
                return 'continue'
    elif action == 'item' and item_idx is not None:
        consumables = player.combat_consumables()
        if 0 <= item_idx < len(consumables) and consumables[item_idx].effect == 'smoke_escape':
            if enemy.is_final:
                clog('danger', 'There is no escaping this fight.')
                return 'continue'
            else:
                player.inventory.remove(consumables[item_idx])
                clog('warning', 'You loose a Smoke Arrow and slip away in the haze!')
                return 'fled'
        elif 0 <= item_idx < len(consumables):
            ok, text = player.use_consumable(consumables[item_idx])
            clog('heal' if ok else 'danger', text)
            if not ok:  # nothing happened (e.g. a revive item, elixir cap): no free enemy hit
                return 'continue'
    elif action == 'flee':
        if player.profession == 'Ranger':
            clog('warning', 'Ranger instincts guide you to safety!')
            return 'fled'
        if random.random() < flee_chance(player, enemy):
            clog('warning', 'You fled from the battle!')
            return 'fled'
        clog('danger', "Couldn't flee! The enemy blocks your escape!")

    if not enemy.is_alive():
        return 'victory'
    _check_boss_phase(enemy, clog)

    dot_dmg = enemy.tick_dot()
    if dot_dmg:
        clog('poison', f'{enemy.dot_name} deals {dot_dmg} to {enemy.name}. ({enemy.hp} HP left)')
        if not enemy.is_alive():
            return 'victory'

    _enemy_turn(player, enemy, clog, defending)
    if not enemy.is_alive():  # Thorns
        return 'victory'
    enemy.tick_statuses()

    expired = player.tick_buffs()
    ticks, expired_debuffs = player.tick_debuffs()
    for name, dmg in ticks:
        clog('danger', f'{name}: -{dmg} HP')
    for b in expired + expired_debuffs:
        if not b.endswith('_buff') and b != 'Steadfast':
            clog('warning', f'{b} wore off.')

    if player.hp < player.max_hp * 0.25 and player.has_perk('Deathless') and not player.deathless_used:
        player.deathless_used = True
        player.hp = max(1, player.hp) + int(player.max_hp * 0.30)
        clog('heal', 'Deathless! Death refuses you — +30% HP.')
    if player.hp <= 0 and player.has_effect('Second Wind') and not player.second_wind_used:
        player.hp = 1
        player.second_wind_used = True
        clog('heal', 'Second Wind! You refuse to fall — 1 HP.')
    if player.hp <= 0:
        if player.has_revive():
            name = player.consume_revive()
            clog('warning', f'Defeated... but your {name} saves you!')
            return 'revived'
        return 'defeat'

    state['combat_turn'] += 1
    return 'continue'
