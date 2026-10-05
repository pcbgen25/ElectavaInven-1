import os

LOGIN_PAGE = """\"use client\";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { ErrorState } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface LoginForm {
  email: string;
  password: string;
}

function safeNext(next: string | null): string {
  // Only allow same-site relative paths (prevents open redirects).
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

function LoginInner() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginForm>();

  const onSubmit = async (values: LoginForm) => {
    setError(null);
    try {
      await login(values.email.trim(), values.password);
      router.replace(safeNext(params.get("next")));
    } catch (e) {
      setError(e instanceof ApiError ? (e.status === 429 ? "Too many attempts. Wait a minute and try again." : e.message) : "Sign in failed.");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-black px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <img src="/logo-dark.png" alt="ELECTAVA INVENTORY" className="h-16 md:h-20 object-contain" />
        </div>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl">
          <div>
            <h1 className="text-base font-semibold text-white">Sign in</h1>
            <p className="text-sm text-zinc-400">Use your company account.</p>
          </div>
          {error && <ErrorState message={error} />}
          <Field label={<span className="text-zinc-300">Email</span>} htmlFor="email" error={errors.email?.message}>
            <Input id="email" type="email" autoComplete="username" autoFocus invalid={!!errors.email}
              className="bg-zinc-900 border-zinc-800 text-white focus:border-[#5BFF2E] focus:ring-[#5BFF2E]/20"
              {...register("email", { required: "Enter your email.", pattern: { value: /^\\S+@\\S+\\.\\S+$/, message: "Enter a valid email address." } })} />
          </Field>
          <Field label={<span className="text-zinc-300">Password</span>} htmlFor="password" error={errors.password?.message}>
            <Input id="password" type="password" autoComplete="current-password" invalid={!!errors.password}
              className="bg-zinc-900 border-zinc-800 text-white focus:border-[#5BFF2E] focus:ring-[#5BFF2E]/20"
              {...register("password", { required: "Enter your password." })} />
          </Field>
          <Button type="submit" className="w-full bg-[#5BFF2E] font-semibold text-black hover:bg-[#4be622]" loading={isSubmitting}>Sign in</Button>
        </form>
        <p className="mt-6 text-center text-xs text-zinc-600">Internal system. Access is logged.</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
"""

with open('frontend/src/app/login/page.tsx', 'w', encoding='utf-8') as f:
    f.write(LOGIN_PAGE)

import re

with open('frontend/src/components/layout/sidebar.tsx', 'r', encoding='utf-8') as f:
    s = f.read()

# Replace the sidebar header
old_sidebar_header = r'<Link href="/dashboard" className="flex h-14 items-center gap-2 border-b border-slate-800 px-4">.*?</Link>'
new_sidebar_header = '''<Link href="/dashboard" className="flex h-16 items-center justify-center border-b border-slate-800 bg-black">
        <img src="/logo-dark.png" alt="ELECTAVA INVENTORY" className="h-10 object-contain" />
      </Link>'''

s = re.sub(old_sidebar_header, new_sidebar_header, s, flags=re.DOTALL)

with open('frontend/src/components/layout/sidebar.tsx', 'w', encoding='utf-8') as f:
    f.write(s)

with open('frontend/src/components/layout/mobile-nav.tsx', 'r', encoding='utf-8') as f:
    m = f.read()

old_mobile_header = r'<div className="flex h-14 shrink-0 items-center gap-2 border-b border-slate-200 px-4">.*?</div>'
new_mobile_header = '''<div className="flex h-16 shrink-0 items-center justify-center border-b border-slate-200 bg-black px-4">
          <img src="/logo-dark.png" alt="ELECTAVA INVENTORY" className="h-10 object-contain" />
        </div>'''
m = re.sub(old_mobile_header, new_mobile_header, m, flags=re.DOTALL)

with open('frontend/src/components/layout/mobile-nav.tsx', 'w', encoding='utf-8') as f:
    f.write(m)

print("Updated UI themes and injected the logo.")
