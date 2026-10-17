import {
  BarChart3,
  ClipboardList,
  Cpu,
  FileText,
  FolderKanban,
  LayoutDashboard,
  type LucideIcon,
  Settings,
  ShoppingCart,
  Truck,
  Users,
  Warehouse,
} from "lucide-react";

/** Navigation. `phase` > current phase means the module is NOT implemented yet and is shown disabled. */
export const CURRENT_PHASE = 3;

export interface NavChild {
  label: string;
  href: string;
  phase: number;
  permission?: string;
}

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  phase: number;
  permission?: string;
  children?: NavChild[];
}

export const NAV: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, phase: 1 },
  {
    label: "Components",
    href: "/components",
    icon: Cpu,
    phase: 1,
    permission: "component.view",
    children: [
      { label: "All Components", href: "/components", phase: 1 },
      { label: "Categories", href: "/components/categories", phase: 1 },
      { label: "Manufacturers", href: "/components/manufacturers", phase: 1 },
      { label: "Packages", href: "/components/packages", phase: 1 },
    ],
  },
  {
    label: "BOM",
    href: "/bom",
    icon: ClipboardList,
    phase: 2,
    permission: "bom.view",
    children: [
      { label: "All BOMs", href: "/bom", phase: 2 },
      { label: "Compare Revisions", href: "/bom-revisions/compare", phase: 2 },
    ],
  },
  { label: "Projects", href: "/projects", icon: FolderKanban, phase: 2, permission: "project.view" },
  {
    label: "Inventory",
    href: "/inventory",
    icon: Warehouse,
    phase: 3,
    permission: "inventory.view",
    children: [
      { label: "Dashboard", href: "/inventory", phase: 3 },
      { label: "Stock", href: "/inventory/stock", phase: 3 },
      { label: "Warehouses", href: "/inventory/warehouses", phase: 3 },
      { label: "Locations", href: "/inventory/locations", phase: 3 },
      { label: "Transactions", href: "/inventory/transactions", phase: 3 },
      { label: "Receive Stock", href: "/inventory/operations/receive", phase: 3, permission: "inventory.receive" },
      { label: "Transfer Stock", href: "/inventory/operations/transfer", phase: 3, permission: "inventory.transfer" },
    ],
  },
  { label: "Suppliers", href: "/suppliers", icon: Truck, phase: 4, permission: "supplier.view" },
  {
    label: "Purchasing",
    href: "/purchasing",
    icon: ShoppingCart,
    phase: 4,
    permission: "purchase.view",
    children: [
      { label: "Purchase Requests", href: "/purchasing/requests", phase: 4 },
      { label: "Purchase Orders", href: "/purchasing/orders", phase: 4 },
      { label: "Receiving", href: "/purchasing/receiving", phase: 4 },
    ],
  },
  { label: "Documents", href: "/documents", icon: FileText, phase: 5, permission: "document.view" },
  { label: "Reports", href: "/reports", icon: BarChart3, phase: 5, permission: "report.view" },
  { label: "Users", href: "/users", icon: Users, phase: 1, permission: "user.manage" },
  { label: "Settings", href: "/settings", icon: Settings, phase: 1 },
];

export const isAvailable = (phase: number) => phase <= CURRENT_PHASE;
