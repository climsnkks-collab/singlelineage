"""Pure bounded traceback diagnostics; arbitrary stderr content is never emitted."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOGUE_SHA = '59685b73466672824e0b59072bd8b4d5685ac54e677e6da3e4e7530face91a32'
TAIL_LIMIT = 1600
FRAME_LIMIT = 6
FRAME = re.compile(r'^  File "([^"\r\n]+)", line ([0-9]{1,9}), in ([^\r\n]+)$')
EXCEPTION = re.compile(r'^([A-Za-z_][A-Za-z0-9_]{0,63})(?:: (.*))?$')


def catalogue():
    path = HERE / 'helper-error-catalogue.json'
    raw = path.read_bytes()
    if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != CATALOGUE_SHA:
        raise ValueError('EXACT_CP73_HELPER_ERROR_CATALOGUE_REQUIRED')
    return json.loads(raw)


def diagnostic(stderr, returncode, result_file_created, trusted):
    """Only known source constants/classes and known frame names survive parsing.

    Input is the already collected helper stderr, with no additional process or
    memory operation. Parse the last <=1600 UTF-8-decoded characters. Discard
    source snippets, caret lines, arbitrary messages, full paths and addresses.
    """
    decoded = stderr.decode('utf-8', 'replace')
    raw_tail = decoded[-TAIL_LIMIT:]
    frames = []
    exception_type = 'UNKNOWN'
    reason = 'NO_STDERR_OUTPUT' if not stderr else 'UNKNOWN_REASON_CONSTANT'
    exception_seen = False
    discarded_lines = 0
    traceback_headers = 0
    lines = raw_tail.splitlines()
    final_index = next((index for index in range(len(lines) - 1, -1, -1) if lines[index]), -1)
    for index, line in enumerate(lines):
        if line == 'Traceback (most recent call last):':
            traceback_headers += 1
            continue
        match = FRAME.fullmatch(line)
        if match:
            basename = match[1].replace('\\', '/').rsplit('/', 1)[-1]
            function = match[3]
            if (basename in trusted['frames']
                    and function in trusted['frames'][basename]
                    and len(basename) <= 96 and len(function) <= 64):
                frames.append({'file': basename, 'line': int(match[2]), 'function': function})
                continue
        match = EXCEPTION.fullmatch(line)
        if index == final_index and match and match[1] in trusted['exception_types']:
            exception_type = match[1]
            exception_seen = True
            message = match[2] or ''
            # Source guards often append details after a constant + colon.
            # Only the exact frozen constant is retained; details are discarded.
            constant = message.split(':', 1)[0]
            reason = constant if constant in trusted['reason_constants'] else 'UNKNOWN_REASON_CONSTANT'
            continue
        if line:
            discarded_lines += 1
    retained = frames[-FRAME_LIMIT:]
    safe_lines = ['Traceback (most recent call last):'] if traceback_headers else []
    safe_lines += [f'  File "{f["file"]}", line {f["line"]}, in {f["function"]}' for f in retained]
    if exception_seen:
        safe_lines.append(exception_type + ': ' + reason)
    safe_tail = '\n'.join(safe_lines)[-TAIL_LIMIT:]
    return {
        'schema': 'cp73-helper-failure-tail-v1',
        'returncode': returncode,
        'result_file_created': bool(result_file_created),
        'status': 'HELPER_FAILURE' if returncode != 0 else 'HELPER_EXIT_ZERO',
        'stderr_tail': safe_tail,
        'stderr_tail_policy': 'LAST_1600_UTF8_CHARACTERS_SOURCE_ALLOWLISTED_STRUCTURE_ONLY',
        'stderr_total_bytes': len(stderr),
        'stderr_total_decoded_characters': len(decoded),
        'stderr_examined_tail_characters': len(raw_tail),
        'stderr_input_tail_truncated': len(decoded) > TAIL_LIMIT,
        'stderr_tail_characters': len(safe_tail),
        'stderr_tail_utf8_bytes': len(safe_tail.encode('utf-8')),
        'discarded_nonstructural_lines_in_tail': discarded_lines,
        'frame_count_in_tail': len(frames),
        'frame_limit': FRAME_LIMIT,
        'frames_truncated': len(frames) > FRAME_LIMIT,
        'frames': retained,
        'final_frame': retained[-1] if retained else None,
        'exception_type': exception_type,
        'reason_constant': reason,
        'final_exception_parsed': exception_seen,
        'raw_stderr_or_source_snippets_saved': False,
        'additional_process_or_memory_queries': 0,
        'runtime_or_cleanup_policy_changed': False,
    }
