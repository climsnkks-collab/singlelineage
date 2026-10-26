# Future authenticated LOCAL action: combat settings

This directory is an unselected **server component**, without a native endpoint,
transport, command wire, Factory, source cohort or actual UI request. It does
not extend LUI2 or `local-ui-mode-command-route-v1` LMC1/LMA1. No MAC domain,
action number or wire byte layout is allocated here. The mode worker owns its
wire; a future owner must version and select the combined action contract.

Required native action type: `COMBAT_SETTINGS_V1`, exact fields requested
`CombatSettings(mode, engagement_distance)` and `expected_mage_revision`.
PASSIVE/ASSIST/DEFEND and 1..8 remain **requested preferences**. The effective
mode is PASSIVE, behavior_ready=false, reason
COMPANION_BASIC_ATTACK_PRODUCER_UNAVAILABLE. Never enable attack controls from a
successful preference save. Attack magic policy is deferred.

The genuine paired endpoint must bind one actual OPEN intent, retained native
panel/display epoch+sequence, the selected direct/companion owner lifetime,
server-issued request identity, and the displayed mage revision. Authenticate
and consume the native action only once on the existing event loop. Do not
accept a client character/actor/target UID as authority. A separate settings
action cannot reuse mode's sequence1 or key/token without a coherently selected
successor. No NativeModeEndpoint implementation or Factory is selected here.

Server join API:

1. Install exact `companion_combat` (unchanged basic-combat source), route and
   this Host under one existing package class space. Instantiate
   `CombatSettingsRoute(source=(module,path,SHA), host_source=..., combat_source=...,
   character_source=..., host=actual_host)` on the owner event loop. SourceSeal
   uses the existing `(actual_module,absolute_Path,SHA)` tuple contract; it must resolve these
   actual modules/classes, including the real CanonicalCharacterStore.
2. After actual authenticated native settings intent, inside the original
   owner row operation call `capture_locked(writer, settings=<exact typed DTO>,
   expected_revision=<actual displayed combat_revision>)`. Host view now adds
   requested/effective combat and combat_revision from one canonical mage read.
   A plain server DTO is not proof of user/native intent; the missing endpoint
   must supply that admission. Capture refuses absent actual OPEN and stale CAS.
3. Exit that operation; call `await route.execute_once(request)`. It never
   acquires a row around Host.command. Host takes its one existing row operation,
   rechecks state/epoch/OPEN, and requires an exact issued combat request.
   `save_locked` rechecks live active mage/lease/actor/display and expected mage
   revision before the original canonical update_preferences/atomic writer.
4. The result observes the saved row again using real require_current (which
   reads the canonical persisted file). Exact before/after equality permits
   only preferences.companion.combat and the original idempotent revision delta.
   PREFERENCES_SAVED proves that row readback only. No attack/native receipt.
   If later rendering fails or cancellation occurs, Completion is UNKNOWN and
   any already observed saved result is retained in route.observation/completion.
   No automatic retry, rollback, rebind or native acknowledgement is emitted.
5. A future authenticated result publication must preserve UNKNOWN and saved
   evidence separately; a queued ACK is not a native receipt. Source-owned
   close/successor handling is still required for repeated settings changes.

Exact missing successor before runtime: real selected
`local_ui_selected_open::Bridge` plus exact-source NativeOpenEndpoint delivering
actual OPEN; authenticated native COMBAT_SETTINGS_V1 sender/consumer and result
transport; combined mode+combat Host argument/action dispatch, immutable source
capture/actor-config/click Feature/cohort/loader pins and real normal-session
caller/RUN. Parent d163 and the older basic-combat parent cannot be substituted
in current sealed actor configs. This candidate has no selected cohort to
silently bypass that boundary. Combine mode_request and combat_request in one
owner-reviewed Host successor; retain mode's original hooks and reject both
request types on a single action. Do not replace mode Host with this candidate.

The genuine allied attacker contract remains COMBAT owner's separate work.
Preferences never bind targets, impersonate the selected player, call an attack
handler, apply damage, select magic or manufacture game packets.
