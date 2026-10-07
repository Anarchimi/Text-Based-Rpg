import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('SECRET_KEY', 'test-secret')

import pytest

import app as game_app
from enemies import spawn_enemy
from player import Player


@pytest.fixture(autouse=True)
def isolated_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(game_app, 'SAVE_DIR', str(tmp_path))


def make_player(cls='Warrior', level=20, profession=None):
    p = Player('Tester', cls)
    p.level = level
    p.max_mp = p.mp = 999
    p.max_hp = p.hp = 10_000
    p.profession = profession
    return p


def make_enemy(hp_frac=1.0):
    e = spawn_enemy(1)
    e.max_hp = 1_000_000
    e.hp = int(e.max_hp * hp_frac)
    e.def_ = 0
    return e


def combat_state(player, enemy):
    return {'player': player, 'combat_enemy': enemy, 'combat_log': [], 'combat_turn': 1}


def ability_index(player, name):
    return [a.name for a in player.get_abilities()].index(name)
