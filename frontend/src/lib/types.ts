export interface Ref {
  id: number;
  name: string;
}

export interface RoleBrief {
  id: number;
  code: string;
  name: string;
}

export interface Me {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  job_title: string;
  department: string;
  roles: RoleBrief[];
  permissions: string[];
  is_super_admin: boolean;
  last_login: string | null;
}

export type ComponentStatus = "DRAFT" | "ACTIVE" | "INACTIVE";
export type Lifecycle = "ACTIVE" | "NRND" | "LAST_TIME_BUY" | "OBSOLETE" | "UNKNOWN";
export type DataType = "STRING" | "INTEGER" | "DECIMAL" | "BOOLEAN" | "ENUM";

export interface ComponentListItem {
  id: number;
  internal_part_number: string;
  mpn: string;
  name: string;
  description: string;
  category: Ref;
  manufacturer: Ref | null;
  package: Ref | null;
  status: ComponentStatus;
  lifecycle_status: Lifecycle;
  is_rohs: boolean | null;
  is_reach: boolean | null;
  image_url: string | null;
  updated_at: string;
}

export interface SpecValue {
  definition: number;
  key: string;
  name: string;
  data_type: DataType;
  unit: string;
  value: string | number | boolean | null;
  display_value: string;
}

export interface Alias {
  id?: number;
  alias: string;
  alias_type: string;
  notes?: string;
}

export interface ComponentDetail extends ComponentListItem {
  category_path: string;
  datasheet_url: string;
  datasheet_file_url: string | null;
  notes: string;
  specifications: SpecValue[];
  aliases: Alias[];
  created_by_name: string | null;
  updated_by_name: string | null;
  created_at: string;
}

export interface Category {
  id: number;
  name: string;
  code: string;
  parent: number | null;
  parent_name: string | null;
  full_path: string;
  description: string;
  sort_order: number;
  component_count: number;
}

export interface SpecDefinition {
  id: number;
  category: number;
  category_name: string;
  key: string;
  name: string;
  data_type: DataType;
  unit: string;
  use_si_prefix: boolean;
  enum_choices: string[];
  is_required: boolean;
  is_active: boolean;
  sort_order: number;
  help_text: string;
  value_count?: number;
}

export interface Manufacturer {
  id: number;
  name: string;
  short_name: string;
  website: string;
  country: string;
  notes: string;
  component_count: number;
}

export interface Package {
  id: number;
  name: string;
  mounting_type: "SMD" | "THT" | "OTHER";
  pin_count: number | null;
  description: string;
  component_count: number;
}

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  job_title: string;
  department: string;
  phone: string;
  is_active: boolean;
  roles: RoleBrief[];
  last_login: string | null;
  date_joined: string;
}

export interface Role {
  id: number;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  permission_codes: string[];
  user_count: number;
}

export interface Permission {
  id: number;
  code: string;
  name: string;
  module: string;
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  user: number | null;
  user_email: string;
  action: string;
  entity_type: string;
  entity_id: string;
  entity_repr: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
}

export interface Metric {
  value: number | null;
  available: boolean;
  phase: number;
}

export interface DashboardData {
  metrics: Record<string, Metric>;
  recent_components: {
    id: number;
    internal_part_number: string;
    mpn: string;
    name: string;
    manufacturer: string | null;
    category: string;
    lifecycle_status: Lifecycle;
    updated_at: string;
  }[];
  recent_activity: Pick<AuditEntry, "id" | "timestamp" | "user_email" | "action" | "entity_type" | "entity_id" | "entity_repr">[];
}

export const LIFECYCLE_LABELS: Record<Lifecycle, string> = {
  ACTIVE: "Active",
  NRND: "NRND",
  LAST_TIME_BUY: "Last time buy",
  OBSOLETE: "Obsolete",
  UNKNOWN: "Unknown",
};

export const STATUS_LABELS: Record<ComponentStatus, string> = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  INACTIVE: "Inactive",
};

export const ALIAS_TYPES: { value: string; label: string }[] = [
  { value: "ALTERNATE_MPN", label: "Alternate MPN / ordering code" },
  { value: "LEGACY_PN", label: "Legacy internal PN" },
  { value: "CUSTOMER_PN", label: "Customer PN" },
  { value: "KICAD_VALUE", label: "KiCad value / symbol" },
  { value: "OTHER", label: "Other" },
];


// PHASE 2 TYPES
export type ProjectStatus = 'DRAFT' | 'ACTIVE' | 'ON_HOLD' | 'COMPLETED' | 'CANCELLED';
export type BomStatus = 'DRAFT' | 'REVIEW' | 'RELEASED' | 'OBSOLETE';

export interface ProjectMember {
  id: number;
  project: number;
  user: number;
  user_details: User;
  notes: string;
  created_at: string;
}

export interface Project {
  id: number;
  code: string;
  name: string;
  description: string;
  customer: string;
  status: ProjectStatus;
  start_date: string | null;
  target_date: string | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  members: ProjectMember[];
}

export interface BOMItem {
  id: number;
  revision: number;
  component: number;
  component_details: ComponentListItem;
  designators: string[];
  quantity: number | string;
  description: string;
  notes: string;
  unit_cost_snapshot: number | string | null;
  total_cost_snapshot: number | string | null;
}

export interface BOMRevision {
  id: number;
  bom: number;
  revision_number: string;
  revision_name: string;
  description: string;
  status: BomStatus;
  created_by: number;
  created_at: string;
  released_by: number | null;
  released_at: string | null;
  items: BOMItem[];
}

export interface BOM {
  id: number;
  project: number;
  name: string;
  description: string;
  status: BomStatus;
  created_by: number;
  created_at: string;
  updated_at: string;
  revisions: BOMRevision[];
}

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

// PHASE 4 TYPES — SUPPLIERS & PURCHASING
export type SupplierStatus = "ACTIVE" | "ON_HOLD" | "INACTIVE";

export interface SupplierContact {
  id: number;
  supplier: number;
  name: string;
  role: string;
  email: string;
  phone: string;
  is_primary: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Supplier {
  id: number;
  code: string;
  name: string;
  legal_name: string;
  website: string;
  email: string;
  phone: string;
  country: string;
  address: string;
  currency: string;
  payment_terms: string;
  tax_id: string;
  lead_time_days: number | null;
  rating: number | null;
  status: SupplierStatus;
  is_active: boolean;
  notes: string;
  part_count: number;
  purchase_order_count: number;
  contacts: SupplierContact[];
  created_at: string;
  updated_at: string;
}

export interface SupplierPriceBreak {
  id?: number;
  min_quantity: string;
  unit_price: string;
  currency: string;
  created_at?: string;
}

export interface SupplierPriceHistory {
  id: number;
  supplier_part: number;
  min_quantity: string;
  unit_price: string;
  currency: string;
  source: string;
  reference: string;
  recorded_by: number | null;
  recorded_by_name: string | null;
  recorded_at: string;
}

export interface SupplierPart {
  id: number;
  supplier: number;
  supplier_code: string;
  supplier_name: string;
  supplier_status: SupplierStatus;
  component: number;
  component_internal_part_number: string;
  component_mpn: string;
  component_name: string;
  supplier_part_number: string;
  manufacturer_part_number: string;
  packaging: string;
  currency: string;
  unit_price: string;
  moq: string;
  order_multiple: string;
  lead_time_days: number | null;
  is_preferred: boolean;
  is_active: boolean;
  product_url: string;
  notes: string;
  price_breaks: SupplierPriceBreak[];
  created_at: string;
  updated_at: string;
}

export interface SupplierOfferComparison {
  supplier_part_id: number;
  supplier_id: number;
  supplier_code: string;
  supplier_name: string;
  supplier_status: SupplierStatus;
  supplier_part_number: string;
  manufacturer_part_number: string;
  packaging: string;
  currency: string;
  moq: string;
  order_multiple: string;
  lead_time_days: number | null;
  is_preferred: boolean;
  product_url: string;
  requested_quantity: string;
  effective_order_quantity: string;
  effective_unit_price: string;
  extended_price: string;
}

export type PurchaseRequestStatus = "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED" | "ORDERED" | "CANCELLED";
export type PurchasePriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

export interface PurchaseRequestItem {
  id: number;
  component: number;
  component_internal_part_number: string;
  component_mpn: string;
  component_name: string;
  preferred_supplier: number | null;
  preferred_supplier_code: string | null;
  preferred_supplier_name: string | null;
  supplier_part: number | null;
  supplier_part_number: string | null;
  quantity: string;
  estimated_unit_price: string | null;
  currency: string;
  notes: string;
}

export interface PurchaseRequest {
  id: number;
  request_number: string;
  title: string;
  project: number | null;
  project_code: string | null;
  project_name: string | null;
  bom_revision: number | null;
  bom_revision_label: string | null;
  build_quantity: string;
  status: PurchaseRequestStatus;
  priority: PurchasePriority;
  needed_by: string | null;
  notes: string;
  submitted_by_name: string | null;
  submitted_at: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_notes: string;
  item_count: number;
  estimated_total: string;
  items: PurchaseRequestItem[];
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export type PurchaseOrderStatus =
  | "DRAFT"
  | "APPROVED"
  | "SENT"
  | "PARTIALLY_RECEIVED"
  | "RECEIVED"
  | "CLOSED"
  | "CANCELLED";

export interface PurchaseOrderItem {
  id: number;
  component: number;
  component_internal_part_number: string;
  component_mpn: string;
  component_name: string;
  supplier_part: number | null;
  purchase_request_item: number | null;
  supplier_part_number_snapshot: string;
  mpn_snapshot: string;
  description_snapshot: string;
  quantity_ordered: string;
  quantity_received: string;
  quantity_outstanding: string;
  unit_price: string;
  line_total: string;
  expected_date: string | null;
  notes: string;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier: number;
  supplier_code: string;
  supplier_name: string;
  purchase_request: number | null;
  purchase_request_number: string | null;
  project: number | null;
  project_code: string | null;
  project_name: string | null;
  bom_revision: number | null;
  default_warehouse: number | null;
  default_warehouse_code: string | null;
  default_warehouse_name: string | null;
  status: PurchaseOrderStatus;
  currency: string;
  exchange_rate: string;
  subtotal: string;
  tax_amount: string;
  shipping_amount: string;
  discount_amount: string;
  total_amount: string;
  payment_terms_snapshot: string;
  order_date: string | null;
  expected_delivery_date: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  sent_by_name: string | null;
  sent_at: string | null;
  notes: string;
  item_count: number;
  items: PurchaseOrderItem[];
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface GoodsReceiptItem {
  id: number;
  purchase_order_item: number;
  component: number;
  component_internal_part_number: string;
  component_mpn: string;
  component_name: string;
  warehouse: number;
  warehouse_code: string;
  location: number | null;
  location_code: string | null;
  lot_batch: string;
  quantity_received: string;
  unit_cost_snapshot: string;
  currency_snapshot: string;
  exchange_rate_snapshot: string;
  stock_transaction: number | null;
  notes: string;
}

export interface GoodsReceipt {
  id: number;
  receipt_number: string;
  purchase_order: number;
  po_number: string;
  supplier: number;
  supplier_code: string;
  supplier_name: string;
  warehouse: number;
  warehouse_code: string;
  warehouse_name: string;
  status: "DRAFT" | "POSTED";
  supplier_delivery_note: string;
  idempotency_key: string | null;
  received_by_name: string | null;
  received_at: string | null;
  notes: string;
  items: GoodsReceiptItem[];
  created_at: string;
  updated_at: string;
}

export interface PurchasingSummary {
  open_requests: number;
  pending_approval_requests: number;
  approved_requests: number;
  open_orders: number;
  pending_approval_orders: number;
  awaiting_delivery_orders: number;
  posted_receipts: number;
  open_po_commitment: string;
}
