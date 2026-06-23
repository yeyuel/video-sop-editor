import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth-constants";

export async function POST(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/login", request.url));
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: "",
    httpOnly: true,
    maxAge: 0,
    path: "/",
    sameSite: "lax"
  });
  return response;
}
