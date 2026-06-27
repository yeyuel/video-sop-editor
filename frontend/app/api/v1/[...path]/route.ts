import { NextRequest, NextResponse } from "next/server";

import { AUTH_COOKIE_NAME } from "@/lib/auth-constants";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function proxyBackendRequest(request: NextRequest, pathSegments: string[]) {
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  const suffix = pathSegments.join("/");
  const targetUrl = `${API_BASE_URL}/${suffix}${request.nextUrl.search}`;

  const headers: Record<string, string> = {};
  if (token) {
    headers["X-Session-Token"] = token;
    headers.Cookie = `${AUTH_COOKIE_NAME}=${token}`;
  }

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  const accept = request.headers.get("accept");
  if (accept) {
    headers.Accept = accept;
  }

  let body: ArrayBuffer | string | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = contentType?.includes("multipart/form-data")
      ? await request.arrayBuffer()
      : await request.text();
  }

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store"
    });

    const responseHeaders = new Headers();
    const responseContentType = response.headers.get("content-type");
    if (responseContentType) {
      responseHeaders.set("Content-Type", responseContentType);
    }
    const cacheControl = response.headers.get("cache-control");
    if (cacheControl) {
      responseHeaders.set("Cache-Control", cacheControl);
    }

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders
    });
  } catch {
    return NextResponse.json({ detail: "暂时无法连接服务。" }, { status: 503 });
  }
}

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function handle(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyBackendRequest(request, path);
}

export async function GET(request: NextRequest, context: RouteContext) {
  return handle(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return handle(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return handle(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return handle(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return handle(request, context);
}
