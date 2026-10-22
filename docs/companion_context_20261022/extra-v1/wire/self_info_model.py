"""Explicit owned-local SelfInfo baseline payload; no transport or game actions."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import MappingProxyType

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_owned_self_profile_source', HERE / 'source.py')
proof = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = proof
spec.loader.exec_module(proof)


class Refused(ValueError):
    """Constant errors only; no names, packet bodies, or personal identifiers."""


def need(ok, code):
    if not ok:
        raise Refused(code)


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'LOCAL_STORE_DUPLICATE_KEY')
        out[key] = value
    return out


def validate_store_bytes(raw):
    """Only the pinned owned-local roster snapshot is admitted."""
    need(type(raw) is bytes and proof.sha(raw) == proof.STORE_SHA, 'OWNED_LOCAL_STORE_SHA_CHANGED')
    try:
        row = json.loads(raw, object_pairs_hook=_no_duplicates)
    except (UnicodeError, json.JSONDecodeError):
        raise Refused('OWNED_LOCAL_STORE_JSON_INVALID') from None
    need(type(row) is dict and set(row) == {'schema', 'next_uid', 'characters'}, 'OWNED_LOCAL_STORE_SCHEMA')
    need(row['schema'] == 'lc-owned-character-store-v1' and type(row['next_uid']) is int and row['next_uid'] == 2, 'OWNED_LOCAL_STORE_SCHEMA')
    need(type(row['characters']) is list and len(row['characters']) == 1, 'OWNED_LOCAL_SINGLE_CHARACTER_REQUIRED')
    record = row['characters'][0]
    need(type(record) is dict and set(record) == {'uid', 'name', 'class', 'gender', 'attributes'}, 'OWNED_LOCAL_CHARACTER_SCHEMA')
    need(type(record['uid']) is int and record['uid'] == 1, 'OWNED_LOCAL_UID_REQUIRED')
    need(type(record['class']) is int and record['class'] == 0 and type(record['gender']) is int and record['gender'] == 0, 'OWNED_LOCAL_CLASS_GENDER_REQUIRED')
    need(type(record['name']) is str and record['name'] == 'SoloKnight', 'OWNED_LOCAL_NAME_REQUIRED')
    need(type(record['attributes']) is list and all(type(v) is int for v in record['attributes']) and record['attributes'] == [13, 10, 10, 11, 13, 10], 'OWNED_LOCAL_STATS_REQUIRED')
    return record


def load_store():
    # No CharacterStore construction: that API can create/write a missing store.
    return validate_store_bytes(proof.STORE.read_bytes())


def world_model():
    path = proof.ROOT / 'tools/local_world_protocol/model.py'
    need(proof.sha(path.read_bytes()) == proof.PINS['tools/local_world_protocol/model.py'], 'FIXED_WORLD_MODEL_CHANGED')
    return proof.module(path, '_owned_self_profile_world_model')


def _clock(value):
    need(type(value) is int and 0 <= value <= 0x7FFFFFFF, 'UTC_SECONDS_SIGNED32_PROJECTION_REQUIRED')
    return value


def _values(record, utc_seconds):
    stats = record['attributes']  # STR, DEX, CON, WIS, CHA, INT in the saved INFO roster.
    return {1: record['uid'], 2: 1, 4: stats[0], 5: stats[1], 6: stats[5],
            7: stats[3], 8: stats[2], 9: stats[4], 10: 20, 11: 20, 12: 10,
            13: 10, 14: -10, 15: _clock(utc_seconds), 16: 0, 17: 0, 18: 0, 20: 0}


def provenance():
    rows = {}
    meanings = {1: 'ActorUID', 2: 'Level', 4: 'STR', 5: 'DEX', 6: 'INT', 7: 'WIS',
                8: 'CON', 9: 'CHA', 10: 'HP_current', 11: 'HP_max', 12: 'MP_current',
                13: 'MP_max', 14: 'negated_ArmorClass', 15: 'UTC_calendar_seconds',
                16: 'Hungry', 17: 'Weight', 18: 'Alignment', 20: 'UNKNOWN'}
    for number in proof.REQUIRED:
        origin = ('owned_store_UID' if number == 1 else 'owned_store_stats' if 4 <= number <= 9
                  else 'existing_realm_starter_policy' if number in (2, 10, 12)
                  else 'explicit_local_full_health_policy' if number in (11, 13)
                  else 'existing_realm_Armor10_negation' if number == 14
                  else 'local_UTC_seconds' if number == 15
                  else 'existing_realm_Alignment0_and_source_init' if number == 18
                  else 'source_logical_zero_baseline')
        rows[number] = MappingProxyType({'meaning': meanings[number], 'origin': origin,
                                        'raw_proto_offset': proof.OFFSETS[number][0],
                                        'CharacterData_offset': proof.OFFSETS[number][1],
                                        'normal_server_value_claim': False})
    return MappingProxyType(rows)


@dataclass(frozen=True)
class SelfInfoProfile:
    fields: Mapping = field(repr=False)
    provenance: Mapping = field(repr=False)
    clock_input: str

    def metadata(self):
        return {'schema': 'owned-local-self-info-baseline-v1', 'opcode': 0x4E38,
                'status': 'LOCAL_BASELINE_EXPERIMENT_ONLY', 'fields': sorted(self.fields),
                'store_sha256': proof.STORE_SHA, 'clock_input': self.clock_input,
                'field_provenance': {n: dict(p) for n, p in self.provenance.items()},
                'normal_server_value_claim': False, 'game_world_ready_claim': False,
                'actual_server_emit': False, 'unknown_downstream_safety_fields': [20],
                'limitations': ['HP/MP/level are owned realm policy; no client creation formula recovered',
                                'hunger0 is low food gauge; weight0 is lowest burden band',
                                'field20 meaning and full downstream safety remain unknown',
                                'current UTC seconds must fit signed32 CharacterData projection']}


def build_profile(*, utc_seconds=None):
    proof.verify()
    clock_input = 'local_current_UTC_clock' if utc_seconds is None else 'caller_explicit_UTC_seconds'
    utc_seconds = int(time.time()) if utc_seconds is None else _clock(utc_seconds)
    values = _values(load_store(), utc_seconds)
    world_model().validate_input(0x4E38, values)
    return SelfInfoProfile(MappingProxyType(values), provenance(), clock_input)


def validate_profile(profile):
    need(isinstance(profile, SelfInfoProfile), 'OWNED_SELF_PROFILE_REQUIRED')
    proof.verify()
    need(isinstance(profile.fields, Mapping) and set(profile.fields) == set(proof.REQUIRED), 'EXACT_SELF_REQUIRED_FIELDS')
    need(dict(profile.fields) == _values(load_store(), profile.fields[15]), 'EXPLICIT_LOCAL_PROFILE_CHANGED')
    need({n: dict(p) for n, p in profile.provenance.items()} == {n: dict(p) for n, p in provenance().items()}, 'EXPLICIT_FIELD_PROVENANCE_REQUIRED')
    need(profile.clock_input in ('local_current_UTC_clock', 'caller_explicit_UTC_seconds'), 'EXPLICIT_CLOCK_PROVENANCE_REQUIRED')
    world_model().validate_input(0x4E38, profile.fields)
    return profile.metadata()


def encode_for_review(profile):
    receipt = validate_profile(profile)
    model = world_model()
    categories = {n: 'source_literal' if n in (16, 17, 20) else 'local_game_configuration' for n in profile.fields}
    encoded = model.encode_with_provenance(0x4E38, profile.fields, categories)
    need(model.decode_payload(0x4E38, encoded.payload) == dict(profile.fields), 'SELF_PROFILE_ROUNDTRIP_FAILED')
    return model.EncodedGameDTO(encoded.payload, {**encoded.metadata(), **receipt, 'roundtrip_verified': True})


def _self_fields(self_info):
    return self_info.fields if isinstance(self_info, SelfInfoProfile) else self_info


def validate_uid_actor(self_info, actor_uid, *, actor_is_player):
    """Necessary equality/subtype checks; does not observe packet consumption."""
    fields = _self_fields(self_info)
    world_model().validate_input(0x4E38, fields)
    need(type(actor_uid) is int and 0 <= actor_uid < (1 << 32), 'ACTOR_UID_UINT32_REQUIRED')
    need(actor_is_player is True, 'MYPLAYER_REQUIRES_ACTOR16_TRUE')
    need(fields[1] == actor_uid, 'SELF_UID_MUST_MATCH_WITHOUT_TRUNCATION')
    return {'UID_necessary_conditions_verified': True, 'prior_SelfInfo_consumption_required': True,
            'prior_SelfInfo_consumption_observed': False, 'Actor3_resource_lookup_verified': False,
            'game_world_ready_claim': False, 'actual_server_emit': False}


def validate_self_actor(self_info, complete_actor):
    model = world_model()
    model.validate_input(0x4E96, complete_actor)
    return validate_uid_actor(self_info, complete_actor[2], actor_is_player=complete_actor[16])
