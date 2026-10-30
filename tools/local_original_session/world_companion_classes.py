"""Class-independent companion definitions (data/companion/classes.json).

A companion is an ordinary saved character. This table only says which saved
classes may follow an owner and where each class keeps its LOCAL growth/spell/
AI data and client action timing. Adding another class (elf, knight) means a
new "classes" row; no companion code names a class. Pure loader, startup only.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

DATA = Path(__file__).parent / 'data' / 'companion'


def _positive(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError('COMPANION_CLASSES_INVALID_' + name)
    return value


@dataclass(frozen=True, slots=True)
class CompanionClass:
    class_id: int
    key: str
    growth: Mapping
    spells: Mapping
    policy: Mapping
    sprites: Mapping            # gender -> client body sprite
    starter_weapon_template: int | None
    action_speed: Mapping       # sprite -> weapon action -> (walk_ms, attack_ms)

    def sprite(self, gender: int) -> int:
        return self.sprites[gender]


@dataclass(frozen=True, slots=True)
class CompanionDefinitions:
    classes: Mapping
    max_active_per_owner: int
    follow_distance: int
    assist_scan_tiles: int
    defend_heal_enter: float
    return_scroll_templates: tuple
    weapon_action: Mapping

    @property
    def class_ids(self) -> frozenset:
        return frozenset(self.classes)

    def action_ms(self, class_id: int, gender: int, weapon_type: str | None) -> tuple[int, int]:
        """Client nominal walk/attack ms for this body and weapon group."""
        definition = self.classes[class_id]
        action = self.weapon_action.get(weapon_type or 'unarmed', 'unarmed')
        rows = definition.action_speed[definition.sprite(gender)]
        return rows.get(action, rows['unarmed'])


def load_definitions(path: str | Path | None = None) -> CompanionDefinitions:
    path = DATA / 'classes.json' if path is None else Path(path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('schema') != 1 or not isinstance(raw.get('classes'), dict) or not raw['classes']:
        raise ValueError('COMPANION_CLASSES_SCHEMA')
    classes = {}
    for key, row in raw['classes'].items():
        class_id = int(key)
        folder = path.parent
        speed = {}
        for sprite, actions in row['action_speed'].items():
            speed[int(sprite)] = MappingProxyType({
                name: (_positive(value['walk_ms']['value'], 'WALK'),
                       _positive(value['attack_ms']['value'], 'ATTACK'))
                for name, value in actions.items()})
            if 'unarmed' not in speed[int(sprite)]:
                raise ValueError('COMPANION_CLASSES_UNARMED_SPEED_REQUIRED')
        sprites = MappingProxyType({int(g): _positive(s, 'SPRITE') for g, s in row['sprites'].items()})
        if any(sprite not in speed for sprite in sprites.values()):
            raise ValueError('COMPANION_CLASSES_SPRITE_SPEED_REQUIRED')
        classes[class_id] = CompanionClass(
            class_id, row['key'],
            json.loads((folder / row['growth']).read_text(encoding='utf-8')),
            json.loads((folder / row['spells']).read_text(encoding='utf-8')),
            json.loads((folder / row['ai_policy']).read_text(encoding='utf-8')),
            sprites, row.get('starter_weapon_template'), MappingProxyType(speed))
    fraction = raw['defend_heal_enter']
    if not isinstance(fraction, (int, float)) or not 0 < fraction < 1:
        raise ValueError('COMPANION_CLASSES_INVALID_DEFEND_HEAL')
    return CompanionDefinitions(
        MappingProxyType(classes), _positive(raw['max_active_per_owner'], 'MAX_ACTIVE'),
        _positive(raw['follow_distance'], 'FOLLOW'), _positive(raw['assist_scan_tiles'], 'SCAN'),
        float(fraction), tuple(_positive(t, 'SCROLL') for t in raw['return_scroll_templates']),
        MappingProxyType(dict(raw['weapon_action'])))
