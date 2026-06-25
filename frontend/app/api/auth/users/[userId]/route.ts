import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth-constants";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

function sessionHeaders(request: NextRequest): HeadersInit {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) {
    return {};
  }
  return { "X-Session-Token": token };
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) {
      return payload.detail;
    }
  } catch {
    // ignore
  }
  return "请求失败，请稍后重试。";
}

type RouteContext = {
  params: Promise<{ userId: string }>;
};

export async function PUT(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ error: "未登录", ok: false }, { status: 401 });
  }

  const { userId } = await context.params;

  try {
    const body = await request.json();
    const response = await fetch(`${API_BASE_URL}/auth/users/${userId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...sessionHeaders(request)
      },
      body: JSON.stringify(body),
      cache: "no-store"
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: await readError(response), ok: false },
        { status: response.status }
      );
    }

    const payload = (await response.json()) as { data?: unknown };
    return NextResponse.json({ ok: true, data: payload.data });
  } catch {
    return NextResponse.json({ error: "暂时无法连接服务。", ok: false }, { status: 503 });
  }
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ error: "未登录", ok: false }, { status: 401 });
  }

  const { userId } = await context.params;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/users/${userId}`, {
      method: "DELETE",
      headers: sessionHeaders(request),
      cache: "no-store"
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: await readError(response), ok: false },
        { status: response.status }
      );
    }

    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ error: "暂时无法连接服务。", ok: false }, { status: 503 });
  }
}
