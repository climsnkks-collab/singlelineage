"""Explicit local Athame137 reference-policy subset; plan only, no effect/ACK.

Current catalog1->$14->L1J weapon137 is a declared local mapping, not shared
numeric enums or an original NC rule. Inputs must come from the current selected
character/current canonical item and authoritative server equipment state.
This function produces neither that authority nor once/store/transport rights.
"""
from dataclasses import dataclass
from tools.local_original_session import inventory, item_use

POLICY='LOCAL_ATHAME137_REFERENCE_WEAPON_TOGGLE_SUBSET'
# UI class asset names -> declared local L1J class names, NOT L1J enum numbers.
CLASS_NAMES={0:'royal',1:'knight',2:'elf',3:'mage'}
ALLOWED_CLASSES=frozenset({'royal','knight','elf'})

class AthamePolicyError(ValueError):
    pass

def _need(ok,reason):
    if not ok:raise AthamePolicyError(reason)

@dataclass(frozen=True,slots=True)
class AthamePlan:
    character_uid:int
    item_uid:int
    weapon_uid_before:int
    weapon_uid_after:int
    preserved_f4:int
    action:str
    policy:str=POLICY

def plan_athame_use(request,item,*,selected_character_uid,selected_class,current_weapon_uid,
                    can_switch_weapon,equip_admitted,absolute_barrier_active):
    """Pure bounded plan. None/unknown equipment is never treated as empty.

    Only no weapon or this same Athame is supported. Replacements/active barrier
    require additional actual state/effects and are outside this local subset.
    equip_admitted is the caller's current normal form/weapon admission, required
    only for NEW equip. No cooldown/morph enum or client flag is invented here.
    """
    _need(type(request) is item_use.ItemUseRequest and type(item) is inventory.ItemInfo,
          'ATHAME_PARSED_REQUEST_CURRENT_ITEM_REQUIRED')
    fields=dict(item.raw_fields)
    _need(type(selected_character_uid) is int and 0<selected_character_uid<1<<32,
          'ATHAME_SELECTED_CHARACTER_UID_REQUIRED')
    _need(type(fields.get(1)) is int and 0<fields[1]<1<<32 and
          request.identifier==fields[1], 'ATHAME_SAME_ITEM_UID_REQUIRED')
    _need(type(fields.get(2)) is int and item.template_bits==1,'ATHAME_TEMPLATE1_MAPPING_REQUIRED')
    _need(type(fields.get(4)) is int and 0<=fields[4]<1<<64,'ATHAME_CURRENT_F4_REQUIRED')
    expected={1:1,15:0,16:0};parts=request.params.fields
    _need(request.params.present_fields==expected.keys() and len(parts)==3 and
          all(p.kind=='int32' and type(p.value) is int and p.value==expected[p.number] for p in parts),
          'ATHAME_REVIEWED_RAW0_PARAMS_REQUIRED')
    _need(type(selected_class) is int and selected_class in CLASS_NAMES,'ATHAME_KNOWN_SELECTED_CLASS_REQUIRED')
    # validClass precedes BOTH equip and same-target unequip in pinned C_ItemUSe.
    _need(CLASS_NAMES[selected_class] in ALLOWED_CLASSES,'ATHAME_CLASS_NOT_ALLOWED')
    _need(type(current_weapon_uid) is int and 0<=current_weapon_uid<1<<32,
          'ATHAME_AUTHORITATIVE_WEAPON_STATE_REQUIRED')
    _need(current_weapon_uid in (0,fields[1]),'ATHAME_OTHER_WEAPON_UNSUPPORTED')
    _need(type(can_switch_weapon) is bool,'ATHAME_CURRENT_SWITCH_ADMISSION_REQUIRED')
    _need(can_switch_weapon,'ATHAME_SWITCH_REFUSED')
    equipped=current_weapon_uid==fields[1]
    if not equipped:
        _need(type(equip_admitted) is bool,'ATHAME_CURRENT_EQUIP_ADMISSION_REQUIRED')
        _need(equip_admitted,'ATHAME_EQUIP_REFUSED')
    # Reference useWeapon cancels AbsoluteBarrier. This subset refuses an active
    # or unknown barrier rather than pretending that unimplemented side effect.
    _need(type(absolute_barrier_active) is bool,'ATHAME_CURRENT_BARRIER_STATE_REQUIRED')
    _need(not absolute_barrier_active,'ATHAME_ACTIVE_BARRIER_UNSUPPORTED')
    # Fixed reference row137: min/max0, twohanded false, bless1. No replacement,
    # curse2, shield transition or quantity debit is synthesized in this subset.
    return AthamePlan(selected_character_uid,fields[1],current_weapon_uid,
                      0 if equipped else fields[1],fields[4],'UNEQUIP' if equipped else 'EQUIP')


# Explicit two-owned-Athame local replacement. Original singleton function above
# is unchanged. This is a pure plan, never Store/source/current/send authority.
COLLECTION_POLICY='EXPLICIT_LOCAL_OWNED_ATHAME_COLLECTION'


def plan_athame_collection_use(request,items,*,policy,selected_character_uid,
                               selected_class,current_weapon_uid,
                               can_switch_weapon,equip_admitted,absolute_barrier_active):
    _need(type(policy) is str and policy==COLLECTION_POLICY,
          'ATHAME_COLLECTION_EXPLICIT_POLICY_REQUIRED')
    _need(type(request) is item_use.ItemUseRequest,
          'ATHAME_PARSED_REQUEST_CURRENT_ITEM_REQUIRED')
    _need(type(items) is tuple and 1<=len(items)<=2,
          'ATHAME_COLLECTION_ONE_OR_TWO_OWNED_REQUIRED')
    for item in items:
        _need(type(item) is inventory.ItemInfo and type(item.raw_fields) is tuple,
              'ATHAME_COLLECTION_CANONICAL_OWNED_ITEM_REQUIRED')
        try:
            # Pure original exact17/range/type validator; fixed local template1
            # subset only. The caller must supply actual Store-validated members.
            checked=inventory._values(dict(item.raw_fields),frozenset({1}))
        except (KeyError,TypeError,ValueError,OverflowError):
            raise AthamePolicyError('ATHAME_COLLECTION_CANONICAL_OWNED_ITEM_REQUIRED') from None
        _need(inventory._same_static(checked.raw_fields,item.raw_fields),
              'ATHAME_COLLECTION_CANONICAL_OWNED_ITEM_REQUIRED')
    uids=tuple(item.identifier for item in items)
    _need(len(set(uids))==len(uids),'ATHAME_COLLECTION_DISTINCT_OWNED_UIDS_REQUIRED')
    _need(type(request.identifier) is int and request.identifier in uids,
          'ATHAME_COLLECTION_REQUEST_NOT_OWNED')
    _need(type(current_weapon_uid) is int and 0<=current_weapon_uid<1<<32 and
          (current_weapon_uid==0 or current_weapon_uid in uids),
          'ATHAME_COLLECTION_CURRENT_WEAPON_NOT_OWNED')
    selected=items[uids.index(request.identifier)]
    # Reuse unchanged class/rawparams/switch/new-equip/barrier/quantity rules.
    # For a replacement the selected item is NEW equip, not same-item unequip.
    before=selected.identifier if current_weapon_uid==selected.identifier else 0
    plan=plan_athame_use(request,selected,selected_character_uid=selected_character_uid,
         selected_class=selected_class,current_weapon_uid=before,
         can_switch_weapon=can_switch_weapon,equip_admitted=equip_admitted,
         absolute_barrier_active=absolute_barrier_active)
    replacing=current_weapon_uid!=0 and current_weapon_uid!=selected.identifier
    return AthamePlan(plan.character_uid,plan.item_uid,current_weapon_uid,
                      plan.weapon_uid_after,plan.preserved_f4,
                      'REPLACE' if replacing else plan.action,COLLECTION_POLICY)
