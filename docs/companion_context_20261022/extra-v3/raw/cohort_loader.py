"""One exact nominal source cohort; no sockets, sender or second provider."""
import hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if(p/'tools/local_original_session/broker.py').is_file())
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
import tools.local_original_session as package
SELECTED=json.loads((HERE/'cohort.json').read_text())['selected']
MODULES={}
def install(name,*,plain=False):
    if name in MODULES:return MODULES[name]
    row=SELECTED[name];p=Path(row['path']);raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==row['sha256'],name
    q=name if plain else 'tools.local_original_session.'+name
    if q in sys.modules:
        m=sys.modules[q]
        assert Path(m.__file__).resolve()==p.resolve() and hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()==row['sha256'],'BOOK318_IMPLICIT_SOURCE_CONFLICT'
        if not plain:assert getattr(package,name) is m,'BOOK318_IMPLICIT_ALIAS_CONFLICT'
        MODULES[name]=m;return m
    spec=importlib.util.spec_from_file_location(q,p);m=importlib.util.module_from_spec(spec)
    sys.modules[q]=m
    if not plain:setattr(package,name,m)
    exec(compile(raw,str(p),'exec'),m.__dict__);MODULES[name]=m
    return m
def load():
    for name in ('move_state','observe','buff_passive','light_state','inventory','item_custody','item_uid_namespace','inventory_aggregate','inventory_store','equipment_store','inventory_update','hp_resource_document',
        'hp_resource_owner','hp_status','skill_buff','canonical_skill','npc_hp','attack_session',
        'npc_player_hit','player_life','inventory_observe','item_use_session','item_equipment_effect',
        'combat_buff_reference','buff_lifecycle','buff_skill_document','cast_route','buff_source_response','buff_bootstrap',
        'broker','manual_move_commands','item_equipment_ui','original_screenshot','item_ground','item_transfer_session','item_transfer_frame','item_transfer_entry','item_quantity_popup','ground_client_retirement','item_transfer_ui','item_transfer_runner','manual_source_quit','npc_session','npc_kill_events',
        'feature_config','canonical_feature_bootstrap','canonical_delivery','skill_cost_delivery',
        'npc_approach_hit','npc_player_lethal','player_life_observe','player_death_recovery_focused',
        'npc_player_lethal_recovery_focused','launcher','repeated_dead_restart','repeated_player_life_focused'):
        install(name)
    for name in ('shop_quest','canonical_port','shop_quest_binding','server_death_event','bootstrap_progress',
                 'dialogue_route','trade_request_wire','projection','trade_delivery','trade_ingress'):
        install(name,plain=True)
    launcher=MODULES['launcher'];manual=MODULES['manual_move_commands'];use=MODULES['item_use_session']
    assert use.MANUAL_NATIVE_SOURCE_SHA256==hashlib.sha256(Path(manual.__file__).read_bytes()).hexdigest()
    assert launcher._MANUAL_REJECTION_SOURCE_SHA==use.MANUAL_NATIVE_SOURCE_SHA256
    desktop=launcher._desktop_module
    assert desktop.__name__=='_local_session_desktop' and launcher.PrivateDesktop is desktop.PrivateDesktop
    assert Path(desktop.__file__).resolve()==ROOT/'tools/local_original_session/desktop.py'
    assert hashlib.sha256(Path(desktop.__file__).read_bytes()).hexdigest()=='16c7432939b47e6a8185a00ffb6c0820f11344bc0bf3efbdd727f18d9f9c3c61'
    assert 'tools.local_original_session.desktop' not in sys.modules
    for name,module in MODULES.items():
        assert sys.modules[module.__name__] is module
        if module.__name__.startswith('tools.local_original_session.'):assert getattr(package,name) is module
    ui=MODULES['item_transfer_ui'];transfer=MODULES['item_transfer_runner'];ground=MODULES['ground_client_retirement']
    assert transfer.ItemTransferUI is ui.ItemTransferUI and transfer.retirement is ground
    assert ui.inventory_observe is MODULES['inventory_observe']
    assert ui.PersistentBroker is ground.PersistentBroker is MODULES['broker'].PersistentBroker
    assert ui.item_transfer_session is ground.item_transfer_session is MODULES['item_transfer_session']
    assert ground.item_ground is MODULES['item_ground']
    assert MODULES['item_use_session'].InventoryStore is MODULES['inventory_store'].InventoryStore
    assert MODULES['item_equipment_effect'].item_use_session is MODULES['item_use_session']
    return MODULES
