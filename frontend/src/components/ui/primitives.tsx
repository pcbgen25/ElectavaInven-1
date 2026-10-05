import { AlertTriangle, Construction, Inbox, Loader2, X } from "lucide-react";
import { useEffect } from "react";

import type { Lifecycle } from "@/lib/types";
import { LIFECYCLE_LABELS } from "@/lib/types";
import { cn } from "@/lib/utils";

type Tone = "slate" | "blue" | "green" | "amber" | "red" | "violet";
const TONES: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  violet: "bg-violet-50 text-violet-700 ring-violet-200",
};

export function Badge({ tone = "slate", className, children }: { tone?: Tone; className?: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset", TONES[tone], className)}>
      {children}
    </span>
  );
}

const LIFECYCLE_TONE: Record<Lifecycle, Tone> = { ACTIVE: "green", NRND: "amber", LAST_TIME_BUY: "amber", OBSOLETE: "red", UNKNOWN: "slate" };
export function LifecycleBadge({ value }: { value: Lifecycle }) {
  return <Badge tone={LIFECYCLE_TONE[value]}>{LIFECYCLE_LABELS[value]}</Badge>;
}

export function Card({ title, actions, className, children }: { title?: React.ReactNode; actions?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <section className={cn("rounded-lg border border-slate-200 bg-white", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-2.5">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-slate-900 md:text-xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500" role="status">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <Inbox className="mb-2 h-8 w-8 text-slate-300" />
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{message}</div>
      {onRetry && <button className="font-medium underline" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function NotImplemented({ feature, phase }: { feature: string; phase: number }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
      <Construction className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
      <div>
        <span className="font-medium text-slate-700">{feature}</span> is not implemented yet — planned for Phase {phase}.
      </div>
    </div>
  );
}

export function Forbidden({ permission }: { permission: string }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div>You do not have permission to access this page (requires <code className="font-mono text-xs">{permission}</code>). Contact an administrator.</div>
    </div>
  );
}

export function Modal({ open, title, onClose, children, footer, wide }: {
  open: boolean; title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 sm:items-center sm:p-4" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn("flex max-h-[92vh] w-full flex-col rounded-t-xl bg-white shadow-xl sm:rounded-lg", wide ? "sm:max-w-2xl" : "sm:max-w-md")}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <button aria-label="Close" onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100"><X className="h-4 w-4" /></button>
        </header>
        <div className="overflow-y-auto p-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-slate-100 px-4 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

export function DescriptionList({ items }: { items: { label: string; value: React.ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map((it) => (
        <div key={it.label} className="min-w-0">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{it.label}</dt>
          <dd className="mt-0.5 break-words text-sm text-slate-900">{it.value || <span className="text-slate-400">—</span>}</dd>
        </div>
      ))}
    </dl>
  );
}
