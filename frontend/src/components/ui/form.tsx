import { forwardRef } from "react";

import { cn } from "@/lib/utils";

const control =
  "block w-full rounded-md border bg-white px-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 disabled:bg-slate-50 disabled:text-slate-500";

const border = (invalid?: boolean) => (invalid ? "border-red-400" : "border-slate-300");

interface FieldProps {
  label: string;
  htmlFor: string;
  required?: boolean;
  hint?: React.ReactNode;
  error?: string | string[];
  className?: string;
  children: React.ReactNode;
}

export function Field({ label, htmlFor, required, hint, error, className, children }: FieldProps) {
  const msg = Array.isArray(error) ? error.join(" ") : error;
  return (
    <div className={cn("space-y-1", className)}>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-red-600" aria-hidden>*</span>}
      </label>
      {children}
      {msg ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-xs text-red-600">{msg}</p>
      ) : hint ? (
        <p className="text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean; suffix?: string };

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ invalid, suffix, className, ...rest }, ref) {
  const input = (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined}
      className={cn(control, border(invalid), "h-9", suffix && "pr-12", className)}
      {...rest}
    />
  );
  if (!suffix) return input;
  return (
    <div className="relative">
      {input}
      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-slate-500">{suffix}</span>
    </div>
  );
});

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean };

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ invalid, className, children, ...rest }, ref) {
  return (
    <select ref={ref} aria-invalid={invalid || undefined} className={cn(control, border(invalid), "h-9 pr-8", className)} {...rest}>
      {children}
    </select>
  );
});

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean };

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({ invalid, className, ...rest }, ref) {
  return <textarea ref={ref} aria-invalid={invalid || undefined} className={cn(control, border(invalid), "py-2", className)} rows={3} {...rest} />;
});
