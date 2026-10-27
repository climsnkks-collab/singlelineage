"""Compatibility import for the promoted world core; not a selectable feature."""
from tools.local_original_session import world_core_session as _core
globals().update({name: value for name, value in vars(_core).items()
                  if not name.startswith("__")})
