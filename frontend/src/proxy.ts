import { NextResponse, type NextRequest } from "next/server";

/**
 * UX-only gate: send visitors without a session cookie to /login.
 * This is NOT authorization — Django validates the session and permissions on every API call.
 */
export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has("sessionid");
  const { pathname, search } = request.nextUrl;
  if (!hasSession && pathname !== "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Skip API/media proxying (uploads must not be buffered here), Next internals and static assets.
  matcher: ["/((?!api|media|_next/static|_next/image|icons|favicon.ico|manifest.webmanifest|robots.txt).*)"],
};
