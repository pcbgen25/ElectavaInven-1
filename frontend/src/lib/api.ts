/** Thin fetch wrapper: same-origin cookies, CSRF header, normalised errors. */

export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  status: number;
  data: unknown;
  fieldErrors: FieldErrors;

  constructor(status: number, data: unknown) {
    super(ApiError.messageFrom(status, data));
    this.status = status;
    this.data = data;
    this.fieldErrors = ApiError.fieldsFrom(data);
  }

  get isAuthError(): boolean {
    const detail = (this.data as { detail?: string } | null)?.detail ?? "";
    return this.status === 401 || (this.status === 403 && /credentials were not provided|not authenticated/i.test(detail));
  }

  static messageFrom(status: number, data: unknown): string {
    if (data && typeof data === "object") {
      const d = data as Record<string, unknown>;
      if (typeof d.detail === "string") return d.detail;
      if (Array.isArray(d.non_field_errors)) return String(d.non_field_errors[0]);
      const first = Object.entries(d)[0];
      if (first) {
        const [field, msgs] = first;
        const msg = Array.isArray(msgs) ? msgs[0] : msgs;
        return `${field.replace(/_/g, " ")}: ${typeof msg === "string" ? msg : JSON.stringify(msg)}`;
      }
    }
    if (status === 0) return "Cannot reach the server. Check your connection.";
    if (status >= 500) return "The server encountered an error. Please try again.";
    return `Request failed (${status}).`;
  }

  static fieldsFrom(data: unknown): FieldErrors {
    const out: FieldErrors = {};
    if (data && typeof data === "object" && !Array.isArray(data)) {
      for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
        if (k === "detail") continue;
        if (Array.isArray(v)) out[k] = v.map((x) => (typeof x === "string" ? x : JSON.stringify(x)));
        else if (typeof v === "string") out[k] = [v];
      }
    }
    return out;
  }
}

export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

export async function ensureCsrf(): Promise<void> {
  if (!getCookie("csrftoken")) await fetch("/api/auth/csrf", { credentials: "same-origin" });
}

type Query = Record<string, string | number | boolean | null | undefined | string[]>;

export function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => params.append(k, x));
    else params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (method !== "GET") {
    await ensureCsrf();
    const token = getCookie("csrftoken");
    if (token) headers["X-CSRFToken"] = token;
  }
  let res: Response;
  try {
    res = await fetch(`/api/${path.replace(/^\/+/, "")}${buildQuery(opts.query)}`, {
      method, headers, body, credentials: "same-origin", signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, null);
  }
  if (res.status === 204) return null as T;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;
  if (!res.ok) {
    const err = new ApiError(res.status, data);
    if (err.isAuthError && typeof window !== "undefined") window.dispatchEvent(new Event("electava:unauthenticated"));
    throw err;
  }
  return data as T;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Fetch every page (bounded) — used for CSV export of the current filter. */
export async function fetchAllPages<T>(path: string, query: Query, maxRows = 5000): Promise<T[]> {
  const rows: T[] = [];
  let page = 1;
  while (rows.length < maxRows) {
    const data = await api<Paginated<T>>(path, { query: { ...query, page, page_size: 200 } });
    rows.push(...data.results);
    if (!data.next) break;
    page += 1;
  }
  return rows.slice(0, maxRows);
}
