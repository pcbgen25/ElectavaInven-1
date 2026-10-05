"use client";

import Link from "next/link";

import { ComponentForm } from "@/components/components/component-form";
import { Forbidden, PageHeader } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";

export default function NewComponentPage() {
  const { can } = useAuth();
  return (
    <>
      <PageHeader
        title="Add component"
        subtitle={<><Link href="/components" className="text-blue-700 hover:underline">Components</Link> / New</>}
      />
      {can("component.create") ? <ComponentForm /> : <Forbidden permission="component.create" />}
    </>
  );
}
