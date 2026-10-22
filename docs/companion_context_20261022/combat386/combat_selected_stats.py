"""Existing selected character/equipment/SKILL producer for pure combat inputs.

Default disabled until actual owner selection/setup hooks bind it. Character INFO
is read once at selection. Canonical participant read is confined to existing
selection/commit hooks. capture_locked never opens files or invents NPC stats.
"""
from dataclasses import dataclass, replace
import sys
try:
    from .combat_stats import Stats,PcStats,StatModifier,DerivedStats,derive_stats
    from .combat_physical import Weapon
except ImportError:
    from combat_stats import Stats,PcStats,StatModifier,DerivedStats,derive_stats
    from combat_physical import Weapon

LOCAL_CLASS_NAMES = {0:'royal',1:'knight',2:'elf',3:'wizard'}

@dataclass(frozen=True)
class EquipmentRule:
    """Explicit catalog template policy. Weapon fields are never modifiers."""
    template: int
    weapon: Weapon
    modifiers: tuple[StatModifier,...] = ()

@dataclass(frozen=True)
class SkillRule:
    spell_id: int
    modifier: StatModifier
    physical_effect: str | None = None

# Logical spell IDs from canonical SKILL, not opaque icon/W/client IDs.
# Shield -2 is declared LOCAL normalization independently of its UI W projection.
DEFAULT_SKILL_RULES = (SkillRule(1,StatModifier('light:no_combat')),
                       SkillRule(2,StatModifier('shield:LOCAL_ac_minus2',ac=-2)))

@dataclass(frozen=True)
class SelectedStatsSnapshot:
    uid: int
    writer: object
    generation: object
    selection: object
    derived: DerivedStats
    weapon: Weapon
    effects: tuple[str,...]
    equipment_revision: int
    skill_revision: int

class SelectedStatsSource:
    """Projection only; original selected/commit owners retain all authority.

    Root calls selection_locked after canonical selection setup, then equipment
    and skill refresh hooks at their existing committed boundaries. Retirement
    is detected by original generation/selection identity. There is no arbitrary
    snapshot/document setter and no independent store/commit/RNG authority.
    """
    def __init__(self,owner,*,equipment_rules=(),skill_rules=DEFAULT_SKILL_RULES):
        self.owner=owner
        self.broker=owner.status.broker
        if owner.store.provider is not owner.provider or owner.provider.broker is not self.broker:
            raise ValueError('COMBAT_ACTUAL_CANONICAL_OWNER_REQUIRED')
        if not isinstance(equipment_rules,tuple) or not isinstance(skill_rules,tuple):
            raise ValueError('COMBAT_IMMUTABLE_COLD_RULES_REQUIRED')
        if any(type(r) is not EquipmentRule for r in equipment_rules) or len({r.template for r in equipment_rules})!=len(equipment_rules):
            raise ValueError('COMBAT_UNIQUE_EQUIPMENT_RULES_REQUIRED')
        if any(type(r) is not SkillRule for r in skill_rules) or len({r.spell_id for r in skill_rules})!=len(skill_rules):
            raise ValueError('COMBAT_UNIQUE_SKILL_RULES_REQUIRED')
        self._equipment_rules={r.template:r for r in equipment_rules}
        self._skill_rules={r.spell_id:r for r in skill_rules}
        self._binding=None
        self._base=None
        self._selection=None
        self._equipment=None
        self._skills=None
        self._snapshot=None
        self._snapshot_key=None

    def _current(self,binding):
        b=self.broker;g=binding.generation
        game=b.realm.registry.resolve(binding.writer)
        if (self._binding is None or binding.uid!=self._binding.uid or
            binding.writer is not self._binding.writer or g is not self._binding.generation or
            binding.operation_lock is not self._binding.operation_lock or
            b._inventory_generation is not g or g.phase!='ACTIVE' or
            g.row['writer'] is not binding.writer or g.row['operation_lock'] is not binding.operation_lock or
            not binding.operation_lock.locked() or game is None or game.selection is not self._selection):
            raise ValueError('COMBAT_SELECTED_GENERATION_RETIRED_OR_UNLOCKED')
        return game

    def selection_locked(self,binding):
        """Call inside existing selected lock, after actual canonical setup."""
        self.owner.provider.current(binding)
        b=self.broker;game=b.realm.registry.resolve(binding.writer)
        if (game is None or game.selection is None or b._inventory_generation is not binding.generation or
            binding.generation.phase!='ACTIVE' or not binding.operation_lock.locked()):
            raise ValueError('COMBAT_REAL_SELECTED_BINDING_REQUIRED')
        # Actual CharacterStore owner, not unbound supplied INFO/dictionary.
        uid,info=b.realm.store.select(game.selection.reference)
        if uid!=binding.uid or info[1]!=game.selection.reference or info[3] not in LOCAL_CLASS_NAMES:
            raise ValueError('COMBAT_SELECTED_CHARACTER_INFO_MISMATCH')
        stats=Stats(info[11],info[12],info[13],info[16],info[14],info[15])
        # This store has creation-only attributes and LOCAL starter level1; no
        # separate historical growth exists to fabricate. Future growth owner
        # must extend its genuine record producer before changing this contract.
        if info[10]!=1:
            raise ValueError('COMBAT_CREATION_ONLY_STORE_LEVEL_UNSUPPORTED')
        self._binding=binding;self._selection=game.selection
        self._base=PcStats(stats,stats,LOCAL_CLASS_NAMES[info[3]],info[10])
        self._equipment=self._skills=self._snapshot=self._snapshot_key=None

    def equipment_changed_locked(self,binding):
        """Call after existing equipment initial sync/commit, no disk sampling."""
        self._current(binding)
        effect=getattr(self.broker,'_item_equipment_effect',None)
        life=getattr(effect,'_selection',None)
        if effect is None or effect.broker is not self.broker or not isinstance(life,dict):
            raise ValueError('COMBAT_ACTUAL_EQUIPMENT_SELECTION_REQUIRED')
        identity=life.get('identity');state=life.get('state')
        if (not isinstance(identity,tuple) or len(identity)!=7 or
            identity[0] is not binding.writer or identity[1] is not binding.generation or
            identity[3] is not self._selection or state is None or state.character_uid!=binding.uid):
            raise ValueError('COMBAT_COMMITTED_EQUIPMENT_STATE_REQUIRED')
        # Validate supported real source object type once at its original change
        # boundary, not via serialization/schema on every attack.
        from tools.local_original_session.equipment_store import EquipmentState
        if type(state) is not EquipmentState:
            raise ValueError('COMBAT_SOURCE_EQUIPMENT_STATE_REQUIRED')
        preparation=self._preparation(effect,binding,life,state)
        if state.weapon_uid==0:
            weapon=Weapon('fist',0,0);modifiers=()
        else:
            rule=self._equipment_rules.get(state.template)
            if rule is None:
                raise ValueError('COMBAT_EQUIPPED_TEMPLATE_POLICY_UNSUPPORTED')
            # This source stores a single supported weapon-template family.
            # No opaque ItemInfo field is renamed STR/enchant/damage.
            weapon=rule.weapon
            modifiers=tuple(replace(m,source_id=f'equipment:{state.weapon_uid}:{m.source_id}') for m in rule.modifiers)
        self._equipment=(effect,life,state,weapon,modifiers,preparation)
        self._snapshot=None

    @staticmethod
    def _preparation(effect,binding,life,state):
        if life.get('synced') is True:
            return None
        # Accepted empty/unequipped source intentionally has synced=False:
        # use its original typed, source-issued lifetime witness, never a
        # server_ready boolean as a replacement for notification authority.
        module=sys.modules.get(type(effect).__module__)
        accessor=getattr(module,'_SERVER_PREPARATION_ACCESSOR',None)
        method=getattr(effect,'server_preparation_memory',None)
        if (module is None or type(effect) is not getattr(module,'ItemEquipmentEffect',None) or
            accessor is None or getattr(method,'__func__',None) is not accessor):
            raise ValueError('COMBAT_TYPED_ZERO_PREPARATION_REQUIRED')
        record=accessor(effect,binding.writer)
        if (type(record) is not getattr(module,'ServerPreparationMemory',None) or
            record is not effect._server_preparation or record._life is not life or
            record.state is not state or record.writer is not binding.writer or
            record.generation is not binding.generation or state.weapon_uid!=0):
            raise ValueError('COMBAT_TYPED_ZERO_PREPARATION_REQUIRED')
        return record

    def skills_changed_locked(self,binding):
        """Call after existing SKILL setup or canonical commit; one owner read."""
        self._current(binding)
        participant=self.owner.store.participant(binding,'SKILL')
        row=participant['document']['characters'][str(binding.uid)]
        # The original participant reader validates its own schema. Freeze only
        # fields consumed by combat, rather than repeat that validation here.
        buffs=tuple(sorted((int(spell),expiry) for spell,expiry in row['buffs'].items()))
        self._skills=(row['revision'],row['clock'],buffs)
        self._snapshot=None

    def capture_locked(self,binding):
        """Existing operation callback; memory-only, no producer/Store rereads."""
        self._current(binding)
        if self._base is None or self._equipment is None or self._skills is None:
            raise ValueError('COMBAT_SELECTED_PRODUCER_SETUP_INCOMPLETE')
        effect,life,state,weapon,equipment,preparation=self._equipment
        if (self.broker._item_equipment_effect is not effect or effect._selection is not life or
            life.get('state') is not state):
            raise ValueError('COMBAT_EQUIPMENT_CHANGED_REFRESH_REQUIRED')
        if self._preparation(effect,binding,life,state) is not preparation:
            raise ValueError('COMBAT_EQUIPMENT_PREPARATION_CHANGED')
        revision,clock,buffs=self._skills
        lifecycle=getattr(self.broker,'_buff_lifecycle',None)
        if lifecycle is None or lifecycle.owner is not self.owner:
            raise ValueError('COMBAT_CANONICAL_BUFF_LIFECYCLE_REQUIRED')
        now=max(clock,lifecycle._now())
        # Existing owner selected clock is generation-bound. Both known owner
        # versions name their same-purpose field explicitly.
        for field_name in ('_selection_clocks','_shield_world_clock'):
            clocks=getattr(self.owner,field_name,None)
            selected=clocks.get(id(binding.writer)) if clocks is not None else None
            if selected is not None:
                if selected[0] is not binding.generation:
                    raise ValueError('COMBAT_SKILL_CLOCK_GENERATION_CHANGED')
                now=max(now,selected[1])
        active=tuple(spell for spell,expiry in buffs if expiry>now)
        key=(state.revision,revision,active)
        if self._snapshot is not None and self._snapshot_key==key:
            return self._snapshot
        modifiers=[];effects=[]
        for spell in active:
            rule=self._skill_rules.get(spell)
            if rule is None:
                raise ValueError('COMBAT_ACTIVE_SKILL_POLICY_UNSUPPORTED')
            modifiers.append(replace(rule.modifier,source_id=f'skill:{spell}:{rule.modifier.source_id}'))
            if rule.physical_effect is not None:effects.append(rule.physical_effect)
        derived=derive_stats(replace(self._base,equipment=equipment,skills=tuple(modifiers)))
        self._snapshot=SelectedStatsSnapshot(binding.uid,binding.writer,binding.generation,self._selection,
            derived,weapon,tuple(effects),state.revision,revision)
        self._snapshot_key=key
        return self._snapshot
