import os

os.makedirs('src/app/(app)/inventory', exist_ok=True)
os.makedirs('src/app/(app)/inventory/warehouses', exist_ok=True)
os.makedirs('src/app/(app)/inventory/stock', exist_ok=True)
os.makedirs('src/app/(app)/inventory/transactions', exist_ok=True)

types_append = """
export interface Warehouse {
    id: string;
    code: string;
    name: string;
    description: string;
    address: string;
    is_active: boolean;
    created_at: string;
}

export interface WarehouseLocation {
    id: string;
    warehouse: string;
    warehouse_code: string;
    code: string;
    name: string;
    description: string;
    location_type: string;
    is_active: boolean;
}

export interface InventoryItem {
    id: string;
    component: string;
    component_mpn: string;
    warehouse: string;
    warehouse_code: string;
    location: string;
    location_code: string;
    quantity_on_hand: string;
    quantity_reserved: string;
    quantity_available: string;
    minimum_stock: string;
    reorder_level: string;
    unit: string;
    lot_batch: string;
}

export interface StockTransaction {
    id: string;
    transaction_type: string;
    component: string;
    component_mpn: string;
    warehouse: string;
    warehouse_code: string;
    location: string;
    location_code: string;
    quantity: string;
    reference_type: string;
    reference_id: string;
    reason: string;
    performed_by_name: string;
    timestamp: string;
}
"""

with open('src/lib/types.ts', 'a') as f:
    f.write(types_append)
