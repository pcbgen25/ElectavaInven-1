"use client";

import { Cpu } from "lucide-react";
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
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center justify-center gap-0.5">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-blue-600"><Cpu className="h-5 w-5 text-white" /></span>
            <span className="text-xl font-bold tracking-widest text-slate-900">ELECTAVA</span>
          </div>
          <span className="text-sm font-semibold tracking-wider text-slate-500 uppercase">Inventory</span>
        </div>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <h1 className="text-base font-semibold text-slate-900">Sign in</h1>
            <p className="text-sm text-slate-500">Use your company account.</p>
          </div>
          {error && <ErrorState message={error} />}
          <Field label="Email" htmlFor="email" error={errors.email?.message}>
            <Input id="email" type="email" autoComplete="username" autoFocus invalid={!!errors.email}
              {...register("email", { required: "Enter your email.", pattern: { value: /^\S+@\S+\.\S+$/, message: "Enter a valid email address." } })} />
          </Field>
          <Field label="Password" htmlFor="password" error={errors.password?.message}>
            <Input id="password" type="password" autoComplete="current-password" invalid={!!errors.password}
              {...register("password", { required: "Enter your password." })} />
          </Field>
          <Button type="submit" className="w-full" loading={isSubmitting}>Sign in</Button>
        </form>
        <p className="mt-4 text-center text-xs text-slate-500">Internal system. Access is logged.</p>
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
