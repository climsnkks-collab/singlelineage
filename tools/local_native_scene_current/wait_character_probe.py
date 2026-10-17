"""Read the CP36 CharacterSelect UI cache as soon as auto OK reaches it."""
from __future__ import annotations

import json
import time
from pathlib import Path

import inspect_character_select


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work/local_native_login_news_retry_runtime'
RESULT = WORK / 'auto-ok-result.json'
OUTPUT = WORK / 'character-ui-presence.json'
CANDIDATE = ROOT / 'work/local_native_login_news_retry_candidate/native-login.candidate.bin'
SHA = 'dbced3c8bce0942439a438c46f4496407c987a02c0da6e2f410936cb419b63b8'


def main():
    deadline = time.monotonic() + 150
    last = None
    while time.monotonic() < deadline:
        if RESULT.is_file():
            row = json.loads(RESULT.read_bytes())
            if row.get('candidate_sha256') != SHA or not row.get('character_select_memory_seen'):
                raise ValueError('EXACT_AUTOMATIC_CHARACTER_SELECT_REQUIRED')
            try:
                observation = inspect_character_select.inspect(
                    CANDIDATE, SHA, row['pid'], row['birth'])
                with OUTPUT.open('x', encoding='utf-8') as stream:
                    json.dump(observation, stream, indent=2)
                    stream.write('\n')
                print(json.dumps({'status': 'CHARACTER_UI_OBSERVED',
                                  'matches': observation['matches'],
                                  'output': str(OUTPUT)}))
                return
            except Exception as error:
                last = getattr(error, 'reason', type(error).__name__)
        time.sleep(.25)
    print(json.dumps({'status': 'UNKNOWN', 'reason': last or 'AUTO_RESULT_TIMEOUT'}))


if __name__ == '__main__':
    main()
