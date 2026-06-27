import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME, AUTH_ROLE_COOKIE } from "@/lib/auth-constants";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { password?: string; username?: string };
  const username = body.username?.trim() ?? "";
  const password = body.password ?? "";

  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ username, password }),
      cache: "no-store"
    });

    if (!response.ok) {
      let error = "登录失败，请检查账号和密码。";
      try {
        const payload = (await response.json()) as { detail?: string };
        if (payload.detail) {
          error = payload.detail;
        }
      } catch {
        // ignore response parse errors
      }

      return NextResponse.json({ error, ok: false }, { status: response.status });
    }

    const payload = (await response.json()) as {
      data?: {
        sessionToken?: string;
        user?: { username?: string; role?: string };
      };
    };
    const sessionToken = payload.data?.sessionToken;
    const role = payload.data?.user?.role ?? "editor";
    if (!sessionToken) {
      return NextResponse.json(
        { error: "登录响应无效，请稍后重试。", ok: false },
        { status: 502 }
      );
    }

    const nextResponse = NextResponse.json({
      ok: true,
      username: payload.data?.user?.username ?? username
    });
    nextResponse.cookies.set({
      name: AUTH_COOKIE_NAME,
      value: sessionToken,
      httpOnly: true,
      maxAge: 60 * 60 * 8,
      path: "/",
      sameSite: "lax"
    });
    nextResponse.cookies.set({
      name: AUTH_ROLE_COOKIE,
      value: role,
      httpOnly: true,
      maxAge: 60 * 60 * 8,
      path: "/",
      sameSite: "lax"
    });
    return nextResponse;
  } catch {
    return NextResponse.json(
      { error: "暂时无法连接服务，请稍后再试。", ok: false },
      { status: 503 }
    );
  }
}
