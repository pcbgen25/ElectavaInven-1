"use client";

import { ChevronDown, Cpu, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth";
import { NAV, isAvailable, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

function PhaseTag({ phase }: { phase: number }) {
  return <span className="ml-auto rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">P{phase}</span>;
}

export function isActivePath(pathname: string, href: string, exact = false) {
  return exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function NavGroup({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const pathname = usePathname();
  const available = isAvailable(item.phase);
  const active = isActivePath(pathname, item.href);
  const [open, setOpen] = useState(active);
  const Icon = item.icon;

  if (!available) {
    return (
      <div className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm text-slate-500" title={`Not implemented yet — Phase ${item.phase}`}>
        <Icon className="h-4 w-4" /> {item.label} <PhaseTag phase={item.phase} />
      </div>
    );
  }

  const base = "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors";
  if (!item.children) {
    return (
      <Link href={item.href} onClick={onNavigate} className={cn(base, active ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800/60 hover:text-white")}>
        <Icon className="h-4 w-4" /> {item.label}
      </Link>
    );
  }
  return (
    <div>
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className={cn(base, "w-full", active ? "text-white" : "text-slate-300 hover:bg-slate-800/60 hover:text-white")}>
        <Icon className="h-4 w-4" /> {item.label}
        <ChevronDown className={cn("ml-auto h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="ml-4 mt-0.5 space-y-0.5 border-l border-slate-800 pl-2.5">
          {item.children.map((c) =>
            isAvailable(c.phase) ? (
              <Link key={c.href} href={c.href} onClick={onNavigate}
                className={cn("block rounded px-2 py-1 text-[13px]", isActivePath(pathname, c.href, c.href === item.href)
                  ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white")}>
                {c.label}
              </Link>
            ) : (
              <div key={c.href} className="flex cursor-not-allowed items-center px-2 py-1 text-[13px] text-slate-600" title={`Not implemented yet — Phase ${c.phase}`}>
                {c.label} <PhaseTag phase={c.phase} />
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  const items = NAV.filter((i) => !i.permission || !isAvailable(i.phase) || can(i.permission));
  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3" aria-label="Main">
      {items.map((i) => <NavGroup key={i.href} item={i} onNavigate={onNavigate} />)}
    </nav>
  );
}

export function Sidebar() {
  const { user, logout } = useAuth();
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col bg-slate-900 md:flex">
      <Link href="/dashboard" className="flex h-16 items-center justify-center border-b border-slate-800 bg-black">
        <img src="/logo-dark.png" alt="ELECTAVA INVENTORY" className="h-10 object-contain" />
      </Link>
      <SidebarNav />
      <div className="border-t border-slate-800 p-3">
        <div className="mb-2 truncate text-xs text-slate-400" title={user?.email}>
          <div className="truncate font-medium text-slate-200">{user?.full_name}</div>
          {user?.roles.map((r) => r.name).join(", ") || "No role assigned"}
        </div>
        <button onClick={logout} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-300 hover:bg-slate-800 hover:text-white">
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>
    </aside>
  );
}
