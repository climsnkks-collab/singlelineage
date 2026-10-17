"""CP73: small live dependencies and separately reviewed immutable snapshots."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LIVE_LIMIT = 2097152
CHUNK = 1048576
PINSETS = {
    'tile-render-pins.json': 'e0a46cbf027fb46917d3fb741032b5e5a7451e76adeda0f0937a8724dfe5fb78',
    'cp59-frozen-pins.json': '59e9be4ed058ab35a5b9742cce63c368607229fce9891516eb97963b70e2e980',
    'cp62-frozen-pins.json': '0d5942acff08e9b3ee809b354f9da9a8c55ab4346e1b81a5eb5d0765e884fca3',
    'cp63-frozen-pins.json': '7167ab2ae6578874e8bc8732d73a1081b3db2139943333d3b5615a7d034e6424',
}
HISTORY_SHA = 'd6fd0fa5feb86f442a3a91646b9d9d4c5b4e67452c0ba386a987ae5cd2c40a85'
HISTORICAL_PATHS = (
    'work/local_native_login_tile_render_runtime/slot/control.snapshot.bin',
    'work/local_native_login_tile_render_stable_runtime/slot/control.snapshot.bin',
)


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def checked_stat(path, bound):
    for parent in (path, *path.parents):
        row = parent.lstat()
        need(not parent.is_symlink() and not getattr(row, 'st_file_attributes', 0) & 0x400,
             'CP73_DEPENDENCY_REPARSE')
    row = path.stat()
    need(path.is_file() and row.st_nlink == 1 and row.st_size <= bound,
         'CP73_DEPENDENCY_BOUND:' + path.relative_to(ROOT).as_posix())
    return row


def read_pinset(name, digest):
    path = HERE / name
    checked_stat(path, LIVE_LIMIT)
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == digest, 'CP73_EXACT_PINSET:' + name)
    return json.loads(raw)


def history_pins():
    rows = read_pinset('historical-artifacts.json', HISTORY_SHA)
    need(set(rows) == set(HISTORICAL_PATHS), 'CP73_EXACT_HISTORICAL_PATHS')
    return rows


def pins():
    result = {}
    historical = history_pins()
    for name, digest in PINSETS.items():
        rows = read_pinset(name, digest)
        for path, expected in rows.items():
            if path in historical:
                need(expected == historical[path]['sha256'], 'CP73_HISTORICAL_PIN_DISAGREEMENT')
                continue
            need(path not in result or result[path] == expected, 'CP73_PIN_CONFLICT:' + path)
            result[path] = expected
        result[(HERE / name).relative_to(ROOT).as_posix()] = digest
    result[(HERE / 'historical-artifacts.json').relative_to(ROOT).as_posix()] = HISTORY_SHA
    for name, digest in result.items():
        path = ROOT / name
        checked_stat(path, LIVE_LIMIT)
        need(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'CP73_DEPENDENCY_CHANGED:' + name)
    return result


def verify_history():
    """Static/preflight review only; do not add these snapshots to live pins."""
    verified = {}
    for name, expected in history_pins().items():
        path = ROOT / name
        before = checked_stat(path, expected['size'])
        need(before.st_size == expected['size'], 'CP73_HISTORICAL_SIZE:' + name)
        stamp = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns, row.st_nlink)
        digest = hashlib.sha256()
        read = 0
        with path.open('rb') as stream:
            need(stamp(os.fstat(stream.fileno())) == stamp(before), 'CP73_HISTORICAL_OPEN_CHANGED')
            for chunk in iter(lambda: stream.read(CHUNK), b''):
                read += len(chunk)
                need(read <= expected['size'], 'CP73_HISTORICAL_READ_BOUND')
                digest.update(chunk)
            need(stamp(os.fstat(stream.fileno())) == stamp(before), 'CP73_HISTORICAL_HANDLE_CHANGED')
        need(stamp(checked_stat(path, expected['size'])) == stamp(before), 'CP73_HISTORICAL_CHANGED')
        need(read == expected['size'] and digest.hexdigest() == expected['sha256'],
             'CP73_HISTORICAL_SHA:' + name)
        verified[name] = dict(expected, verified=True, read_chunk_maximum=CHUNK,
                             live_runtime_dependency=False)
    return verified
