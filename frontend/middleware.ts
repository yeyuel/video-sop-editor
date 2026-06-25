import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth-constants";

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

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const isAuthed = Boolean(request.cookies.get(AUTH_COOKIE_NAME)?.value);

  if (pathname === "/login" && isAuthed) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (isAllowedPath(pathname)) {
    return NextResponse.next();
  }

  if (!isAuthed) {
    const loginUrl = new URL("/login", request.url);
    const nextPath = `${pathname}${search}`;
    if (nextPath !== "/") {
      loginUrl.searchParams.set("next", nextPath);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"]
};
