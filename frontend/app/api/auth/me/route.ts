import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth-constants";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: {
        "X-Session-Token": token
      },
      cache: "no-store"
    });

    if (!response.ok) {
      return NextResponse.json({ ok: false }, { status: response.status });
    }

    const payload = (await response.json()) as {
      data?: { username?: string; displayName?: string; role?: string };
    };

    return NextResponse.json({
      ok: true,
      user: payload.data ?? null
    });
  } catch {
    return NextResponse.json({ ok: false }, { status: 503 });
  }
}
