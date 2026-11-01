"""Physical loopback ports for test fixtures; broker endpoint identities stay fixed.

SL_TEST_PORT_BASE defaults to 12000. For example, 22000 reserves/connects to
22000 and 24030 while the fixture's logical endpoints remain 12000 and 14030.
Only test harnesses import this module; game/launcher endpoints are unchanged.
"""
import os


def port(logical):
    """Shift a test port by its existing offset from 12000."""
    try:
        base = int(os.environ.get('SL_TEST_PORT_BASE', '12000'))
    except ValueError as error:
        raise ValueError('SL_TEST_PORT_BASE must be an integer TCP port') from error
    if not 1 <= base <= 65535 - 2030:
        raise ValueError('SL_TEST_PORT_BASE must be between 1 and 63505')
    physical = base + logical - 12000
    if not 1 <= physical <= 65535:
        raise ValueError('shifted test port is outside the TCP port range')
    return physical


def listener_ports():
    """Map the two fixed broker identities to this process's test listeners."""
    return {logical: port(logical) for logical in (12000, 14030)}
