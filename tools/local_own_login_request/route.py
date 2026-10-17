"""Attach a real 0263 receiver to the existing post-COUNTS owned dispatcher."""
import importlib.util
from pathlib import Path
import sys

_path = Path(__file__).resolve().with_name('codec.py')
_spec = importlib.util.spec_from_file_location('_own_login_codec', _path)
codec = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = codec
_spec.loader.exec_module(codec)

class LoginExtension:
    """Bind the new local route immediately after the existing grant creates it."""
    def __init__(self, expectation):
        codec.need(type(expectation) is codec.LocalLoginRequest, 'EXPLICIT_OWN_LOGIN_EXPECTATION_REQUIRED')
        self.expectation = expectation
        # Stable own identity, never recycled Python writer IDs. One UUID may
        # be consumed once in this runtime, including across reconnects.
        self.receipts = {}  # Local consumption only; no vendor-login state.

    def bind(self, game):
        connection, registry = game.connection, game.registry
        codec.need(registry.resolve(connection) is game, 'REGISTERED_OWN_SESSION_REQUIRED')
        codec.need(codec.OPCODE not in game.routes, 'OWN_LOGIN_ROUTE_ALREADY_REGISTERED')
        consumed = False

        async def received(payload):
            nonlocal consumed
            codec.need(registry.resolve(connection) is game, 'REGISTERED_OWN_SESSION_REQUIRED')
            codec.need(not consumed and not game.list_sent and game.selection is None,
                       'OWN_LOGIN_ORDER_OR_REPLAY')
            request = codec.parse(payload)
            codec.need(request == self.expectation, 'OWN_LOGIN_EXPECTATION_MISMATCH')
            codec.need(request.guest_uuid not in self.receipts, 'OWN_UUID_ALREADY_CONSUMED')
            consumed = True
            self.receipts[request.guest_uuid] = request
            # 0264 response/ACK/SDK result remain unbound. No unsolicited roster.
            return ()

        game.routes[codec.OPCODE] = received

class LoginRegistry:
    """The unchanged grant still creates the session; then extension.bind runs."""
    def __init__(self, registry, extension):
        self.registry, self.extension = registry, extension

    def __getattr__(self, name):
        return getattr(self.registry, name)

    def register_own(self, connection, config, *, on_selection=None):
        game = self.registry.register_own(connection, config, on_selection=on_selection)
        self.extension.bind(game)
        return game

def attach(serve_both, expectation):
    """Call immediately after hook.bind_serve_both, before its first await.

    The existing grant method reads adapter.registry at request time. Its
    already-captured connection handler still resolves the same original
    registry, because this extension delegates registration into that registry.
    """
    adapter = serve_both.owned_game_adapter
    codec.need(not isinstance(adapter.registry, LoginRegistry), 'OWN_LOGIN_ALREADY_ATTACHED')
    codec.need(not adapter.registry._sessions, 'ATTACH_BEFORE_CONNECTIONS_REQUIRED')
    extension = LoginExtension(expectation)
    adapter.registry = LoginRegistry(adapter.registry, extension)
    return extension
