"""Core owners for shared inventory transactions and catalog publication.

The existing warehouse journal/JSON serializer remains the durable transaction
implementation. Ordinary inventory/equipment changes do not depend on enabling
warehouse menus or on any feature's private state.
"""
from __future__ import annotations


class InventoryTransactions:
    def __init__(self, inventory_store):
        from tools.local_original_session.world_warehouse import WarehouseStore
        self.inventory = inventory_store
        self._warehouse = WarehouseStore(inventory_store)

    def restore_warehouse(self, uid):
        return self._warehouse.restore(uid)

    def commit_warehouse(self, uid, before, after, warehouse_before, warehouse_after,
                         **equipment_change):
        return self._warehouse.commit(uid, before, after, warehouse_before,
                                      warehouse_after, **equipment_change)

    def commit_inventory(self, uid, before, after, *, append=False, joint=False,
                         equipment_store=None, equipment_before=None,
                         equipment_after=None):
        if not joint and (equipment_store is None or equipment_after == equipment_before):
            if append:
                return self.inventory.replace_kit(uid, before, after, append=True)
            return self.inventory.replace_kit(uid, before, after)
        warehouse = self._warehouse.restore(uid)
        change = ({} if equipment_store is None else dict(equipment_store=equipment_store,
            equipment_before=equipment_before, equipment_after=equipment_after))
        return self._warehouse.commit(uid, before, after, warehouse, warehouse, **change)
