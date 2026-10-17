"""One exact Return input after the owned local login ACK is sent."""
from __future__ import annotations

import json
import time
from pathlib import Path

import press_owned

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work/local_native_login_character_input_runtime'
CONTEXT = ROOT / 'work/local_native_login_key_invoke_boundary/runs/cp26-input-20261008-01/context.json'
METADATA = WORK / 'broker/packet-metadata.jsonl'
RESULT = WORK / 'input-probe.json'
CANDIDATE_SHA = '0fbbec9082a40addede16f4c1d48188fe3f3aaa049e013b2d60f73da11305440'


def wait_until(check, duration):
    end = time.monotonic() + duration
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.25)
    raise ValueError('EXACT_INPUT_TRIGGER_TIMEOUT')


def login_ack_sent():
    if not METADATA.is_file():
        return False
    for line in METADATA.read_text(encoding='utf-8').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('event') == 'reply_sent' and row.get('opcode') == 612:
            return True
    return False


def main():
    if RESULT.exists():
        raise ValueError('CREATE_NEW_INPUT_RESULT_REQUIRED')
    context = wait_until(lambda: json.loads(CONTEXT.read_bytes()) if CONTEXT.is_file() else None,
                         110)
    if context.get('candidate_sha256') != CANDIDATE_SHA:
        raise ValueError('EXACT_CP26_CLIENT_REQUIRED')
    pid, birth = context['pid'], str(context['birth'])
    wait_until(login_ack_sent, 55)
    time.sleep(2)
    report = wait_until(lambda: try_enter(pid, birth), 10)
    row = {'schema': 'lc-owned-login-return-probe-v1', 'pid': pid, 'birth': birth,
           'candidate_sha256': CANDIDATE_SHA, 'trigger': 'local_0264_reply_sent',
           'result': report, 'scene_result': 'UNKNOWN'}
    WORK.mkdir(parents=True, exist_ok=True)
    with RESULT.open('x', encoding='utf-8') as stream:
        json.dump(row, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'result': str(RESULT)}))


def try_enter(pid, birth):
    try:
        return press_owned.enter(pid, birth)
    except ValueError as error:
        if str(error) in ('OWNED_WINDOW_NOT_VISIBLE', 'OWNED_WINDOW_NOT_FOREGROUND'):
            return None
        raise


if __name__ == '__main__':
    main()
