# LRS1 reusable LOCAL settings successor v1

This unselected version uses the original retained post-ACK bootstrap State,
pipe, server/process/Job identity and absolute deadline. It calls only the
corrected OPEN Exchange, then owns all IO serially. It never calls standalone
OPEN/mode Run or creates another reader, key bootstrap, connection or retry.
LRS1 is a distinct wire family; old LOP1/LMB2/LMC1 and 250ms behavior is unchanged.

The concrete new LOCAL presentation policy is retained base display until the
original State deadline (at most30s, often less; original bootstrap currently10s).
No owner read/paint/request or result extends that deadline. Native refuses a
post-ACK State whose remaining duration exceeds30s. This longer presentation is
not fresh owner/Host/lease authority. Every authenticated request is freshly
checked inside the original Host row against current state, selection, direct
and companion leases, actor generation, native OPEN, ui_epoch and mage revision.

One LRS1 OPEN1152 / LRR1 actual owner OPEN128 precedes LSB1 bind128. LSB1 binds
exact original nonce, actual owner HWND/thread/display epoch and fresh32B key /
16B token. Those values authenticate/correlate this display only. The retained
Python objects and actual original current recapture supply authority.

All subsequent messages are128B:96B fixed body plus HMAC-SHA256 under domain
LOCAL-COMPANION-REUSABLE-SETTINGS-V1 plus terminating NUL. Reserved bytes zero.
LSQ1 requests carry next u64 sequence1..16, original open sequence1, current
view epoch/revision, exact HWND/owner thread, and kind1 mode or kind2 combat
preferences. Mode values Follow/Station; combat preference PASSIVE/ASSIST/DEFEND
and distance1..8. Native exposes mode/combat preference save buttons; distance
is shown/reused and does not yet have an edit control. No ITEM/GEAR action kind.
ASSIST/DEFEND are explicitly preferences; effective behavior remains unavailable.
Attack magic remains deferred.

The owner burns a request sequence and disables buttons before publication.
Python burns after authenticated decode, before Host/await. One fresh nominal
Request enters a new SettingsSession route inside Host.command's single original
row operation. It is an exact successor, not reuse of one-shot ModeIngress or
CombatSettingsRoute. Mode reuses actual controller.set_mode and exact canonical
movement CAS/readback; combat reuses actual update_preferences and exact disk
readback. Previous actual save/controller returns and final observations survive
later uncertainty. No native receipt or cached view is a Store success.

LSS1 initial/result body carries sequence, view epoch, canonical revision and
mode/combat preference values. Source queues a successful result only after an
actual corresponding Observation and fresh current revision at the original
checkpoint. One complete write attempt only. Any partial/zero/uncertain delivery,
authentication/current/ordering failure, exception or cancellation is terminal
UNKNOWN; the request is never retried or rebound. The source abort path retains
real observations and reports native close UNKNOWN if no close receipt arrives.

Native validates a result against its burned request kind, sequence and next
epoch/CAS bound. It queues an owning fixed copy, paints outside locks on the
established owner, rechecks the copied epoch/sequence after GDI, and erases stale
settings before redrawing current base. Only EndPaint plus matching owner/current
snapshot produces LSR1 update receipt and re-enables the next request. Sequence16
and UNKNOWN leave controls disabled. UNKNOWN paints once, revokes and closes.
LSC1 explicit idle close also revokes and waits for actual owner DestroyWindow,
WM_NCDESTROY/callback quiescence before authenticated LSR1 close. Failure/deadline
may leave close UNKNOWN; it is never manufactured from a cancellation request.

Optional ITEM input is pinned local-ui-own-inventory-wire-v1 manifest
3a2434725213eafff685675e199255bf27b5d415c76d01d4b27f352ec8757257.
Its LIT1 is actual-owner DATA_ONLY, not item authority/action. This successor
has no LIT1 IO/paint phase; future selection must serialize it after an exclusive
completed settings phase on this same State/key/remaining deadline and retain
actual ITEM require_current immediately before send. Inventory and equipment
controls truthfully remain unavailable; GEAR absence is not an empty state.
