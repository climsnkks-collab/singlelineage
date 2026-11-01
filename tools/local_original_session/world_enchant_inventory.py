"""Pure LOCAL enchant inventory projection; no save, sockets, RNG or authority.

Grade and enchant state deliberately live in the already persisted ItemInfo.f18
name, as an explicit LOCAL instance contract. These names are not a native
grade/level encoding. f7 remains the existing icon/model scalar. The caller owns
the selected inventory, equipped slots, atomic save, stats and actual delivery.

run393 establishes generic SC0965 f18 string update and SC0978 UID removal.
Their exact native enchant causality/order and SC0967 field meanings are still
UNKNOWN. Committed results also supply a LOCAL 4EEA/12066 text notice through
the run392 code-message path; this does not claim the official enchant UI.
SC0967 is omitted unless an explicit experiment is supplied. Existing
wire leaves are reused; source preparation belongs to the caller at startup.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
from tools.local_original_session.world_enchant import EnchantResult, _policy


_GRADE_LABELS = {0: '축복', 1: '일반', 2: '저주'}
_RESULT_CANDIDATES = {'success': 0, 'unchanged': 1, 'destroyed': 2, 'rejected': 3}


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _scroll_base(template):
    _need(type(template) is int, 'ENCHANT_SCROLL_TEMPLATE_REQUIRED')
    row = next((row for row in _policy()['scrolls'] if row['classic_id'] == template), None)
    _need(row is not None, 'ENCHANT_SCROLL_TEMPLATE_UNSUPPORTED')
    return row['name_ko']


def scroll_name(template: int, grade: int) -> bytes:
    """Exact LOCAL instance grade marker: ``[일반/축복/저주] definition name``."""
    _need(type(grade) is int and grade in _GRADE_LABELS, 'ENCHANT_LOCAL_GRADE_REQUIRED')
    return f'[{_GRADE_LABELS[grade]}] {_scroll_base(template)}'.encode('utf-8')


def scroll_grade(item) -> int | None:
    """Recognize only our exact f18 marker; never infer grade from template."""
    if item.template_bits not in (25, 26):
        return None
    name = dict(item.raw_fields).get(18, b'')
    return next((grade for grade in _GRADE_LABELS
                 if name == scroll_name(item.template_bits, grade)), None)


def instance_grade(item) -> int:
    """LOCAL saved f18 grade, independent of the signed enchant level.

    Old unmarked rows remain normal. This is not a native ItemInfo flag.
    Ground DropDef.grade is the producer; never infer curse from negative +N.
    """
    raw = dict(item.raw_fields).get(18, b'')
    return next((grade for grade, label in _GRADE_LABELS.items()
                 if raw.startswith(f'[{label}] '.encode('utf-8'))), 1)


def enchanted_name(definition, level: int, *, grade: int = 1) -> bytes:
    """Canonical LOCAL signed level name; level zero uses the bare definition."""
    _need(type(level) is int, 'ENCHANT_INTEGER_LEVEL_REQUIRED')
    _need(type(grade) is int and grade in _GRADE_LABELS, 'ENCHANT_LOCAL_GRADE_REQUIRED')
    text = definition.name_ko if level == 0 else f'{level:+d} {definition.name_ko}'
    if grade != 1:
        text = f'[{_GRADE_LABELS[grade]}] ' + text
    raw = text.encode('utf-8')
    _need(len(raw) <= inventory_update.MAX_BYTES, 'ENCHANT_NAME_TOO_LONG')
    return raw


def enchant_level(item, definition) -> int:
    """Read only blank/base or exact canonical LOCAL ``+N/-N name``.

    Foreign names and malformed prefixes are rejected rather than silently
    resetting a potentially strengthened instance to zero.
    """
    _need(item.template_bits == definition.template_id, 'ENCHANT_TARGET_DEFINITION_MISMATCH')
    raw = dict(item.raw_fields).get(18, b'')
    _need(type(raw) is bytes, 'ENCHANT_BYTES_NAME_REQUIRED')
    grade = instance_grade(item)
    if grade != 1 or raw.startswith('[일반] '.encode('utf-8')):
        raw = raw[len(f'[{_GRADE_LABELS[grade]}] '.encode('utf-8')):]
    if raw in (b'', definition.name_ko.encode('utf-8')):
        return 0
    try:
        name = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('ENCHANT_LOCAL_NAME_INVALID') from None
    match = re.fullmatch(r'([+-][1-9][0-9]*) ' + re.escape(definition.name_ko), name)
    _need(match is not None, 'ENCHANT_LOCAL_NAME_INVALID')
    level = int(match.group(1))
    _need(enchanted_name(definition, level) == raw, 'ENCHANT_LOCAL_NAME_INVALID')
    return level


@dataclass(frozen=True, slots=True)
class EnchantExperiment:
    """Explicit unverified SC0967 candidates; numeric f1..5 overrides only."""
    overrides: tuple[tuple[int, int], ...] = ()


def parse_experiment(raw: str | None) -> EnchantExperiment | None:
    """Startup parser: empty/0 disables; 1 enables; ``1,f3=2,f4=6`` overrides.

    Candidate meanings: f1 targetUID, f2 scroll template, f3 status (success0,
    unchanged1,destroyed2,rejected3), f4 before, f5 after (before on destruction).
    None of these meanings or status values is an established native contract.
    ``f1=...,f2=...`` without a leading 1 is also an explicit experiment.
    """
    if raw is None or raw in ('', '0'):
        return None
    _need(type(raw) is str, 'ENCHANT_EXPERIMENT_TEXT_REQUIRED')
    parts = raw.split(',')
    if parts[0] == '1':
        parts = parts[1:]
    overrides = {}
    for part in parts:
        match = re.fullmatch(r'f([1-5])=(-?(?:0|[1-9][0-9]*))', part)
        _need(match is not None, 'ENCHANT_EXPERIMENT_OVERRIDE_INVALID')
        number, value = int(match.group(1)), int(match.group(2))
        _need(number not in overrides, 'ENCHANT_EXPERIMENT_OVERRIDE_DUPLICATE')
        low, high = (0, 1 << 32) if number == 1 else (-(1 << 31), 1 << 31)
        _need(low <= value < high, 'ENCHANT_EXPERIMENT_OVERRIDE_RANGE')
        overrides[number] = value
    _need(raw == '1' or bool(overrides), 'ENCHANT_EXPERIMENT_OVERRIDE_INVALID')
    return EnchantExperiment(tuple(sorted(overrides.items())))


def result_frame(scroll_uid: int, target_uid: int, result: EnchantResult,
                 experiment: EnchantExperiment | None, *, scroll_template_id: int) -> bytes | None:
    """SC0967 required f1..5, only behind the explicit unverified experiment.

    scroll_uid is retained as an explicit input to prevent template/instance
    confusion; the default candidate f2 uses the template, not this UID.
    """
    if experiment is None:
        return None
    _need(type(experiment) is EnchantExperiment, 'ENCHANT_EXPERIMENT_REQUIRED')
    _need(type(scroll_uid) is int and 0 < scroll_uid < 1 << 32,
          'ENCHANT_SCROLL_UID_REQUIRED')
    _need(type(result) is EnchantResult and result.status in _RESULT_CANDIDATES,
          'ENCHANT_RESULT_REQUIRED')
    values = {1: target_uid, 2: scroll_template_id, 3: _RESULT_CANDIDATES[result.status],
              4: result.level_before,
              5: result.level_before if result.level_after is None else result.level_after}
    values.update(experiment.overrides)
    for number, value in values.items():
        low, high = (0, 1 << 32) if number == 1 else (-(1 << 31), 1 << 31)
        _need(type(value) is int and low <= value < high, 'ENCHANT_RESULT_SCALAR_RANGE')
    body = b''.join(pb.encode_varint(n << 3) + pb.encode_varint(v & ((1 << 64) - 1))
                    for n, v in sorted(values.items()))
    return (len(body) + 6).to_bytes(2, 'little') + b'\x67\x09' + body + b'\0\0'


@dataclass(frozen=True, slots=True)
class EnchantMutation:
    frame: bytes
    frames: tuple[bytes, ...]
    removed_uids: tuple[int, ...]
    target_level: int | None


def _result_notice(definition, result: EnchantResult) -> bytes:
    """LOCAL result text; CHAT_EVIDENCE 4EEA f1 code/f2 format argument.

    Code12066 is SYSTEM_GM '{}'. Native0967 result fields and official result
    wording remain unverified; no native success/failure enum is inferred.
    """
    name = definition.name_ko
    if result.status == 'success':
        text = f'{name}: 강화에 성공했습니다. ({result.level_before:+d} → {result.level_after:+d})'
    elif result.status == 'unchanged':
        text = f'{name}: 강화 수치가 변하지 않았습니다. ({result.level_before:+d})'
    elif result.status == 'destroyed':
        text = f'{name}: 강화에 실패하여 아이템이 소멸했습니다.'
    else:
        text = f'{name}: 강화할 수 없습니다. 아이템과 주문서는 소모되지 않았습니다.'
    body = pb.encode_uint32(1, 12066) + pb.encode_bytes(2, text.encode('utf-8'))
    return (len(body) + 6).to_bytes(2, 'little') + b'\xea\x4e' + body + b'\0\0'


def kit_mutation(items, scroll_uid: int, target_uid: int, result: EnchantResult,
                 defs) -> EnchantMutation:
    """Propose one canonical saved kit and generic changes, without committing.

    Kept inventory order is unchanged. A consumed last scroll is removed; a
    destroyed target is removed. Existing nonempty-kit representation cannot
    represent losing the last two inventory rows, so that unsupported case
    fails before any save. Caller must clear destroyed equipped UIDs as part
    of its save transaction, then publish frames only after that commit.
    """
    items = tuple(items)
    _need(scroll_uid != target_uid, 'ENCHANT_DISTINCT_ITEMS_REQUIRED')
    by_uid = {item.identifier: item for item in items}
    _need(len(by_uid) == len(items) and scroll_uid in by_uid and target_uid in by_uid,
          'ENCHANT_OWNED_ITEMS_REQUIRED')
    scroll, target = by_uid[scroll_uid], by_uid[target_uid]
    _need(scroll.template_bits in (25, 26) and scroll_grade(scroll) is not None,
          'ENCHANT_EXPLICIT_SCROLL_GRADE_REQUIRED')
    definition = defs.get(target.template_bits)
    _need(definition is not None and definition.kind in ('weapon', 'armor'),
          'ENCHANT_TARGET_DEFINITION_REQUIRED')
    _need((scroll.template_bits == 25) == (definition.kind == 'weapon'),
          'ENCHANT_SCROLL_TARGET_KIND_MISMATCH')
    level = enchant_level(target, definition)
    _need(type(result) is EnchantResult and result.level_before == level,
          'ENCHANT_CURRENT_LEVEL_REQUIRED')
    _need(dict(target.raw_fields)[4] == 1, 'ENCHANT_SINGLE_TARGET_INSTANCE_REQUIRED')
    count = dict(scroll.raw_fields)[4]
    _need(type(count) is int and count > 0, 'ENCHANT_POSITIVE_SCROLL_COUNT_REQUIRED')
    if result.status == 'rejected':
        _need(result.consume_scroll == 0 and not result.remove_target and result.level_after == level,
              'ENCHANT_REJECTED_RESULT_INVALID')
        return EnchantMutation(inventory.build_kit_frame([dict(i.raw_fields) for i in items]),
                               (_result_notice(definition, result),), (), level)
    _need(result.status in ('success', 'unchanged', 'destroyed') and result.consume_scroll == 1
          and result.remove_target == (result.status == 'destroyed')
          and ((result.level_after is None) == result.remove_target), 'ENCHANT_RESULT_INVALID')
    removed = {scroll_uid} if count == 1 else set()
    if result.remove_target:
        removed.add(target_uid)
    rows, frames = [], []
    for item in items:
        uid, fields = item.identifier, dict(item.raw_fields)
        if uid in removed:
            frames.append(item_transfer_protocol._remove_frame(item_transfer_protocol.RemoveInventory(uid)))
            continue
        if uid == scroll_uid:
            fields[4] = count - 1
            frames.append(inventory_update._encode(inventory_update._values({1: uid, 4: fields[4]})))
        if uid == target_uid and result.status == 'success':
            fields[18] = enchanted_name(definition, result.level_after, grade=instance_grade(target))
            frames.append(inventory_update._encode(inventory_update._values({1: uid, 18: fields[18]})))
        rows.append(fields)
    _need(bool(rows), 'ENCHANT_EMPTY_KIT_UNSUPPORTED')
    frames.append(_result_notice(definition, result))
    return EnchantMutation(inventory.build_kit_frame(rows), tuple(frames),
                           tuple(i.identifier for i in items if i.identifier in removed),
                           result.level_after)
