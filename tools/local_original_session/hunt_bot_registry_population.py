"""Use the existing production population audit with exact saved-map checks.

Only the bot's obsolete final map allowlist is extended. FIRST, roster/select,
entered ACK/map/status/self checks, server state and production spawns remain
the retained audit's responsibility.
"""
import hashlib
from pathlib import Path
from unittest.mock import patch

from tools.local_original_session import hunt_bot_spawn_audit as audit


class RegistryPopulation(audit.Audit):
    async def open(self, **options):
        expected = self.map_start
        original = audit.hs.ScenarioBot
        notes = self.fixture_notes

        class ExactSavedMapBot(original):
            async def login(bot):
                try:
                    return await super().login()
                except audit.hb.BotFailure as error:
                    if (str(error) != 'MAP0_SELF_POSITION_AND_HP_REQUIRED'
                            or expected[0] not in (53, 72, 73)
                            or not bot.selected or bot.self_uid != 1
                            or bot.position is None
                            or (bot.map_id, *bot.position) != expected
                            or bot.hp is None or not bot.max_hp):
                        raise
                    notes.append(dict(exact_saved_map_login=expected,
                        received_self_uid=bot.self_uid,
                        scope='obsolete bot map allowlist only; entered packet checks already completed'))
                    await bot.alive()

        with patch.object(audit.hs, 'ScenarioBot', ExactSavedMapBot):
            await super().open(**options)


def main(argv=None):
    source = Path(__file__)
    audit.matrix.SOURCE_SHA256[str(source)] = dict(file=str(source),
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        basis='exact selected saved-map bot expectation; production audit unchanged')
    with patch.object(audit, 'Audit', RegistryPopulation):
        return audit.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
