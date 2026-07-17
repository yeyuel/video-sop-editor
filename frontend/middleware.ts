import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME, AUTH_ROLE_COOKIE } from "@/lib/auth-constants";
import { createPublicRequestUrl } from "@/lib/request-origin";

const DIRECTOR_ONLY_PREFIXES = ["/settings/llm", "/settings/users"];

function isAllowedPath(pathname: string) {
  return (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/api/llm") ||
    pathname.startsWith("/api/v1") ||
    pathname === "/favicon.ico" ||
    pathname === "/login"
  );
}

function isDirectorOnlyPath(pathname: string) {
  return DIRECTOR_ONLY_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const isAuthed = Boolean(request.cookies.get(AUTH_COOKIE_NAME)?.value);
  const role = request.cookies.get(AUTH_ROLE_COOKIE)?.value ?? "";

  if (pathname === "/login" && isAuthed) {
    return NextResponse.redirect(createPublicRequestUrl(request.url, request.headers, "/"));
  }

  if (isAllowedPath(pathname)) {
    return NextResponse.next();
  }

  if (!isAuthed) {
    const loginUrl = createPublicRequestUrl(request.url, request.headers, "/login");
    const nextPath = `${pathname}${search}`;
    if (nextPath !== "/") {
      loginUrl.searchParams.set("next", nextPath);
    }
    return NextResponse.redirect(loginUrl);
  }

  if (isDirectorOnlyPath(pathname) && role !== "director") {
    return NextResponse.redirect(createPublicRequestUrl(request.url, request.headers, "/"));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"]
};
