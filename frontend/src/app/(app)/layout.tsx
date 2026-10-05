"use client";

import { Suspense } from "react";

import { BottomNav, TopBar } from "@/components/layout/mobile-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { Spinner } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading || !user) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Loading Electava Inventory…" /></div>;
  }
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="md:pl-60">
        <TopBar />
        <main className="mx-auto max-w-7xl px-3 pb-24 pt-4 sm:px-4 md:px-6 md:pb-10 md:pt-6">
          <Suspense fallback={<Spinner />}>{children}</Suspense>
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
