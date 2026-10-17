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
