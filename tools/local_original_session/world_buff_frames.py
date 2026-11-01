"""Shared fixed-client 4E91 encoding; callers own authority and lifecycle.

CommonSpell.f7 is the localized tooltip reference (spell_token/README.md:13).
The received child f7 reaches config/row+1C and the same string resolver
(run391/followup_v2/cached-4627e0.txt:252). The packaged selected rows retain
their native-dump source lines. This is a data-based projection, not evidence
of the official server's wire policy or current HUD pixels.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct
from types import MappingProxyType

from tools.local_entry_server import protobuf as pb

BUFF_DESCRIPTION_REFS = MappingProxyType({row['catalog']: row['description_ref']
    for row in json.loads((Path(__file__).parent / 'data/m1/buff_descriptions.json')
                          .read_text(encoding='utf-8'))['descriptions']})


def buff_icon_frame(catalog: int, image_key: int, remaining: float, *, remove=False,
                    description_ref=None, start_chat_ref=None, end_chat_ref=None):
    """Encode explicit catalog/K plus seconds; preserve legacy remove identity.

    f7 defaults to the selected catalog's exact CommonSpell tooltip reference.
    f8/f9 are opt-in references for the client's distinct add/remove callbacks;
    no catalog-to-chat policy has been established. In particular f9 is not a
    generic expiry message: callback475420 also requires its caller's r9b.
    Missing mappings remain omitted rather than substituting catalog or K.
    Removal uses the existing row and sends no fresh description/chat policy.
    """
    child = pb.encode_uint32(4, image_key)
    if not remove:
        child = (pb.encode_uint32(1, catalog) + pb.encode_uint32(2, 1)
                 + pb.encode_uint32(3, max(0, math.ceil(remaining))) + child)
        description_ref = (BUFF_DESCRIPTION_REFS.get(catalog)
                           if description_ref is None else description_ref)
        for field, reference in ((7, description_ref), (8, start_chat_ref), (9, end_chat_ref)):
            if reference is not None:
                child += pb.encode_uint32(field, reference)
    body = pb.encode_uint32(1, 3 if remove else 1) + pb.encode_bytes(2, child)
    return struct.pack('<HH', len(body) + 6, 0x4e91) + body + b'\0\0'
