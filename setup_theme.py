import os
import re

# 1. Update globals.css
globals_css_path = 'frontend/src/app/globals.css'
with open(globals_css_path, 'r', encoding='utf-8') as f:
    css = f.read()

variant = '\n@custom-variant dark (&:is(.dark *));\n'
if '@custom-variant dark' not in css:
    css = css.replace('@import "tailwindcss";', '@import "tailwindcss";' + variant)
    with open(globals_css_path, 'w', encoding='utf-8') as f:
        f.write(css)

# 2. Create theme-toggle.tsx
theme_toggle_code = """\"use client\";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="h-8 w-8" />;

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-slate-500 hover:bg-slate-200 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      Toggle theme
    </button>
  );
}
"""
os.makedirs('frontend/src/components', exist_ok=True)
with open('frontend/src/components/theme-toggle.tsx', 'w', encoding='utf-8') as f:
    f.write(theme_toggle_code)

# 3. Update providers.tsx
providers_path = 'frontend/src/app/providers.tsx'
with open(providers_path, 'r', encoding='utf-8') as f:
    prov = f.read()

if 'ThemeProvider' not in prov:
    prov = prov.replace('import { AuthProvider } from "@/lib/auth";', 'import { AuthProvider } from "@/lib/auth";\nimport { ThemeProvider } from "next-themes";')
    prov = prov.replace('<AuthProvider>', '<ThemeProvider attribute="class" defaultTheme="system" enableSystem>\n      <AuthProvider>')
    prov = prov.replace('</AuthProvider>', '</AuthProvider>\n      </ThemeProvider>')
    with open(providers_path, 'w', encoding='utf-8') as f:
        f.write(prov)

# 4. Update login/page.tsx
login_code = """\"use client\";

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
              {...register("email", { required: "Enter your email.", pattern: { value: /^\\S+@\\S+\\.\\S+$/, message: "Enter a valid email address." } })} />
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
"""
with open('frontend/src/app/login/page.tsx', 'w', encoding='utf-8') as f:
    f.write(login_code)


# 5. Update sidebar.tsx
sidebar_path = 'frontend/src/components/layout/sidebar.tsx'
with open(sidebar_path, 'r', encoding='utf-8') as f:
    side = f.read()

# Make sidebar adapt to light/dark
side = side.replace('bg-slate-900', 'bg-slate-50 dark:bg-zinc-950 border-r border-slate-200 dark:border-zinc-900')

# Update the header block
old_header_regex = r'<Link href="/dashboard" className="flex h-16 items-center justify-center border-b border-slate-800 bg-black">.*?img src="/logo-dark.png".*?</Link>'
new_header = """<Link href="/dashboard" className="flex h-16 items-center justify-center border-b border-slate-200 dark:border-zinc-800 bg-white dark:bg-black transition-colors">
        <img src="/logo-light.png" alt="ELECTAVA INVENTORY" className="h-10 object-contain dark:hidden" />
        <img src="/logo-dark.png" alt="ELECTAVA INVENTORY" className="hidden h-10 object-contain dark:block" />
      </Link>"""
side = re.sub(old_header_regex, new_header, side, flags=re.DOTALL)

# Add the ThemeToggle import and usage
if 'import { ThemeToggle }' not in side:
    side = side.replace('import { useAuth }', 'import { ThemeToggle } from "@/components/theme-toggle";\nimport { useAuth }')

side = side.replace(
    '<button onClick={logout}',
    '<ThemeToggle />\n        <button onClick={logout}'
)

# Update sidebar NavItem colors for light/dark
side = side.replace('text-slate-300 hover:bg-slate-800/60 hover:text-white', 'text-slate-600 hover:bg-slate-200 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-zinc-800/60 dark:hover:text-white')
side = side.replace('bg-slate-800 text-white', 'bg-slate-200 text-slate-900 dark:bg-zinc-800 dark:text-white')
side = side.replace('text-slate-400 hover:text-white', 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white')
side = side.replace('text-slate-200', 'text-slate-800 dark:text-slate-200')
side = side.replace('text-slate-300 hover:bg-slate-800 hover:text-white', 'text-slate-600 hover:bg-slate-200 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-zinc-800 dark:hover:text-white')
side = side.replace('border-slate-800', 'border-slate-200 dark:border-zinc-800')

with open(sidebar_path, 'w', encoding='utf-8') as f:
    f.write(side)

# 6. Update mobile-nav.tsx
mobile_nav_path = 'frontend/src/components/layout/mobile-nav.tsx'
if os.path.exists(mobile_nav_path):
    with open(mobile_nav_path, 'r', encoding='utf-8') as f:
        mob = f.read()
    
    old_mob_header = r'<div className="flex h-16 shrink-0 items-center justify-center border-b border-slate-200 bg-black px-4">.*?</div>'
    new_mob_header = """<div className="flex h-16 shrink-0 items-center justify-center border-b border-slate-200 dark:border-zinc-800 bg-white dark:bg-black px-4 transition-colors">
          <img src="/logo-light.png" alt="ELECTAVA INVENTORY" className="h-10 object-contain dark:hidden" />
          <img src="/logo-dark.png" alt="ELECTAVA INVENTORY" className="hidden h-10 object-contain dark:block" />
        </div>"""
    mob = re.sub(old_mob_header, new_mob_header, mob, flags=re.DOTALL)
    with open(mobile_nav_path, 'w', encoding='utf-8') as f:
        f.write(mob)

print("Light/Dark mode implemented fully with both logos.")
