"""Run the retained ordered map packet scenario against ice_cave.json."""
import asyncio
import hashlib
import json
from pathlib import Path

from tools.local_original_session import hunt_bot_map_expansion4 as expansion


def main(argv=None):
    previous = expansion.DATA
    try:
        expansion.DATA = Path(__file__).parent / 'data/m6/ice_cave.json'
        source = Path(__file__)
        expansion.matrix.SOURCE_SHA256[str(source)] = dict(file=str(source),
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            basis='ice dataset selection wrapper; existing map4 driver unchanged')
        args = expansion.parser().parse_args(argv)
        result = asyncio.run(expansion.run(args))
        # The retained driver's generic summary text names its Tower dataset.
        # Keep the actual fixture and packet boundaries explicit for this data.
        result['scope'] = (f'LOCAL ordered ice cave packets on fresh pre-login '
            f'Lv{args.fixture_level} saved-map knight with finite ordinary starter '
            'equipment. Real stair entry, movement, optional representative combat '
            'and return-position saving only. Starting near an entrance is a '
            'saved fixture. Native client/input/rendering unverified.')
        summary = Path(result['output_directory']) / 'summary.json'
        summary.write_text(json.dumps(expansion.matrix.safe(result),
            ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({key: result[key] for key in ('output_directory', 'counts')},
            ensure_ascii=False))
        return 0 if set(result['counts']) == {'PASS'} else 1
    finally:
        expansion.DATA = previous


if __name__ == '__main__':
    raise SystemExit(main())
