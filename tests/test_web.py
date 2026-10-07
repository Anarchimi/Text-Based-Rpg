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
