"use client";

import { ClipboardList, Cpu, Home, LogOut, Menu, QrCode, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

import { SidebarNav, isActivePath } from "./sidebar";

export function TopBar() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim()) router.push(`/components?search=${encodeURIComponent(q.trim())}`);
  };
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-6">
      <Link href="/dashboard" className="flex items-center gap-2 md:hidden">
        <span className="flex h-7 w-7 items-center justify-center rounded bg-blue-600"><Cpu className="h-4 w-4 text-white" /></span>
        <span className="text-sm font-semibold">Electava</span>
      </Link>
      <form onSubmit={submit} className="relative ml-auto hidden w-full max-w-md md:block" role="search">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} type="search" aria-label="Search components"
          placeholder="Search PN, MPN, manufacturer, value…"
          className="h-9 w-full rounded-md border border-slate-300 bg-slate-50 pl-9 pr-3 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/40" />
      </form>
    </header>
  );
}

const TABS = [
  { label: "Home", href: "/dashboard", icon: Home, enabled: true },
  { label: "Search", href: "/search", icon: Search, enabled: true },
  { label: "Scan", href: "#", icon: QrCode, enabled: false, phase: 3 },
  { label: "BOM", href: "#", icon: ClipboardList, enabled: false, phase: 2 },
];

export function BottomNav() {
  const pathname = usePathname();
  const [more, setMore] = useState(false);
  const { user, logout } = useAuth();
  return (
    <>
      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white md:hidden" aria-label="Mobile">
        <ul className="grid grid-cols-5">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = t.enabled && isActivePath(pathname, t.href);
            return (
              <li key={t.label}>
                {t.enabled ? (
                  <Link href={t.href} className={cn("flex h-14 flex-col items-center justify-center gap-0.5 text-[11px]", active ? "text-blue-700" : "text-slate-600")}>
                    <Icon className="h-5 w-5" /> {t.label}
                  </Link>
                ) : (
                  <span className="flex h-14 flex-col items-center justify-center gap-0.5 text-[11px] text-slate-300" title={`Phase ${t.phase}`} aria-disabled>
                    <Icon className="h-5 w-5" /> {t.label}
                  </span>
                )}
              </li>
            );
          })}
          <li>
            <button onClick={() => setMore(true)} className="flex h-14 w-full flex-col items-center justify-center gap-0.5 text-[11px] text-slate-600">
              <Menu className="h-5 w-5" /> More
            </button>
          </li>
        </ul>
      </nav>
      {more && (
        <div className="fixed inset-0 z-40 bg-slate-900/50 md:hidden" onClick={() => setMore(false)}>
          <div className="safe-bottom absolute inset-x-0 bottom-0 flex max-h-[85vh] flex-col rounded-t-2xl bg-slate-900" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
              <div className="min-w-0 text-sm">
                <div className="truncate font-medium text-white">{user?.full_name}</div>
                <div className="truncate text-xs text-slate-400">{user?.roles.map((r) => r.name).join(", ")}</div>
              </div>
              <button aria-label="Close menu" onClick={() => setMore(false)} className="p-1 text-slate-400"><X className="h-5 w-5" /></button>
            </div>
            <SidebarNav onNavigate={() => setMore(false)} />
            <button onClick={logout} className="flex items-center gap-2 border-t border-slate-800 px-5 py-3 text-sm text-slate-300">
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          </div>
        </div>
      )}
    </>
  );
}
