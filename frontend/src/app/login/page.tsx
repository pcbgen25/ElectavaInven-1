"use client";

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
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 transition-colors dark:bg-black">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <img src="/logo-light.png" alt="ELECTAVA INVENTORY" className="h-16 md:h-20 object-contain dark:hidden" />
          <img src="/logo-dark.png" alt="ELECTAVA INVENTORY" className="hidden h-16 md:h-20 object-contain dark:block" />
        </div>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-2xl">
          <div>
            <h1 className="text-base font-semibold text-slate-900 dark:text-white">Sign in</h1>
            <p className="text-sm text-slate-500 dark:text-zinc-400">Use your company account.</p>
          </div>
          {error && <ErrorState message={error} />}
          <Field label={<span className="text-slate-700 dark:text-zinc-300">Email</span>} htmlFor="email" error={errors.email?.message}>
            <Input id="email" type="email" autoComplete="username" autoFocus invalid={!!errors.email}
              className="bg-white text-slate-900 border-slate-300 focus:border-[#5BFF2E] dark:bg-zinc-900 dark:border-zinc-800 dark:text-white dark:focus:ring-[#5BFF2E]/20"
              {...register("email", { required: "Enter your email.", pattern: { value: /^\S+@\S+\.\S+$/, message: "Enter a valid email address." } })} />
          </Field>
          <Field label={<span className="text-slate-700 dark:text-zinc-300">Password</span>} htmlFor="password" error={errors.password?.message}>
            <Input id="password" type="password" autoComplete="current-password" invalid={!!errors.password}
              className="bg-white text-slate-900 border-slate-300 focus:border-[#5BFF2E] dark:bg-zinc-900 dark:border-zinc-800 dark:text-white dark:focus:ring-[#5BFF2E]/20"
              {...register("password", { required: "Enter your password." })} />
          </Field>
          <Button type="submit" className="w-full bg-[#5BFF2E] font-semibold text-black hover:bg-[#4be622]" loading={isSubmitting}>Sign in</Button>
        </form>
        <p className="mt-6 text-center text-xs text-slate-500 dark:text-zinc-600">Internal system. Access is logged.</p>
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
