import os
import random
import re

import pytest

import app as game_app

FORM_RE = re.compile(r'<form[^>]*>(.*?)</form>', re.S)
HIDDEN_RE = re.compile(r'name="([^"]+)"\s+value="([^"]*)"')
BUTTON_RE = re.compile(r'<button[^>]*name="([^"]+)"[^>]*value="([^"]*)"')
TEXT_RE = re.compile(r'<input[^>]*type="text"[^>]*name="([^"]+)"')


def _choices(html):
    """Every submittable form/button combination on the page."""
    out = []
    for form in FORM_RE.findall(html):
        fields = dict(HIDDEN_RE.findall(form))
        fields.update({name: 'Hero' for name in TEXT_RE.findall(form)})
        buttons = BUTTON_RE.findall(form)
        for name, value in buttons:
            out.append({**fields, name: value})
        if not buttons and fields:
            out.append(fields)
    return out


@pytest.mark.parametrize('seed', range(15))
def test_random_play_never_errors(seed):
    """Click random buttons for a few hundred steps; no request may 500."""
    rng = random.Random(seed)
    client = game_app.app.test_client()
    resp = client.get('/')
    for _ in range(300):
        assert resp.status_code == 200, resp.get_data(as_text=True)[-2000:]
        choices = _choices(resp.get_data(as_text=True))
        if not choices:
            break
        resp = client.post('/action', data=rng.choice(choices), follow_redirects=True)
    assert resp.status_code == 200


@pytest.mark.parametrize('sid', ['../../etc/passwd', '../x', 'abc', '', None, 123,
                                 '12345678-1234-1234-1234-1234567890AB'])
def test_bad_sids_are_rejected(sid):
    assert not game_app._valid_sid(sid)


def test_forged_sid_cookie_gets_replaced():
    client = game_app.app.test_client()
    with client.session_transaction() as s:
        s['sid'] = '../../../tmp/evil'
    client.post('/action', data={'action': 'new_game'})
    with client.session_transaction() as s:
        assert game_app._valid_sid(s['sid'])


def test_every_screen_has_a_template():
    """game.html includes screens/<state.screen>.html; a missing file would 500."""
    import os
    src = open(game_app.__file__).read()
    screens = set(re.findall(r"state\['screen'\] = '(\w+)'", src)) | {game_app.fresh_state()['screen']}
    tpl_dir = os.path.join(game_app.app.root_path, 'templates', 'screens')
    missing = {s for s in screens if not os.path.exists(os.path.join(tpl_dir, f'{s}.html'))}
    assert not missing, f'screens without a template: {missing}'


def test_save_dir_defaults_to_instance_folder_and_is_overridable(monkeypatch):
    monkeypatch.delenv('RPG_SAVE_DIR', raising=False)
    default = game_app.resolve_save_dir()
    assert default == os.path.join(game_app.app.instance_path, 'saves')
    assert not default.startswith('/tmp')
    monkeypatch.setenv('RPG_SAVE_DIR', '/data/saves')
    assert game_app.resolve_save_dir() == '/data/saves'


def test_failed_save_keeps_previous_save_intact(monkeypatch):
    client = game_app.app.test_client()
    client.post('/action', data={'action': 'new_game'})
    with client.session_transaction() as s:
        sid = s['sid']
    path = os.path.join(game_app.SAVE_DIR, f'{sid}.pkl')
    good = open(path, 'rb').read()

    def boom(*a, **k):
        raise OSError('disk full')
    monkeypatch.setattr(game_app.pickle, 'dump', boom)
    with pytest.raises(OSError):
        with game_app.app.test_request_context('/'):
            from flask import session
            session['sid'] = sid
            game_app.save_state(game_app.fresh_state())

    assert open(path, 'rb').read() == good
    assert os.listdir(game_app.SAVE_DIR) == [f'{sid}.pkl']  # no leftover .tmp file


def test_endgame_flow_through_the_web_ui(monkeypatch):
    """Five seals → confront the Dragon Lord → fight via the real forms → ending → NG+."""
    import pickle
    sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
    import sys
    sys.path.insert(0, sys_path)
    import balance_sim
    from quests import QuestLog

    client = game_app.app.test_client()
    client.get('/')
    with client.session_transaction() as s:
        sid = s['sid']
    st = game_app.fresh_state()
    hero = balance_sim.build_player('Warrior', 19, rarity='Legendary', potions=10)
    st.update(player=hero, quest_log=QuestLog(), zone=5, screen='hub', seals={1, 2, 3, 4, 5},
              narrative_stage=5)
    with open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'wb') as f:
        pickle.dump(st, f)

    page = client.get('/').get_data(as_text=True)
    assert 'Confront the Chaos Dragon Lord' in page
    page = client.post('/action', data={'action': 'final_battle'}, follow_redirects=True).get_data(as_text=True)
    assert 'Chaos Dragon Lord' in page and 'Defend' in page

    random.seed(3)
    for _ in range(80):
        if 'THE REALM IS SAVED' in page:
            break
        assert 'GAME OVER' not in page, 'a Legendary level-19 Warrior should win this'
        with open(os.path.join(game_app.SAVE_DIR, f'{sid}.pkl'), 'rb') as f:
            cur = pickle.load(f)
        kind, ab, item = balance_sim.choose_action(cur['player'], cur['combat_enemy'], 0)
        action = {'ability': f'ability_{ab}', 'item': f'item_{item}'}.get(kind, kind)
        page = client.post('/action', data={'action': action}, follow_redirects=True).get_data(as_text=True)
    assert 'THE REALM IS SAVED' in page
    assert 'New Game+ 1' in page

    page = client.post('/action', data={'action': 'new_game_plus'}, follow_redirects=True).get_data(as_text=True)
    assert 'NG+1' in page and 'Confront the Chaos Dragon Lord' not in page
