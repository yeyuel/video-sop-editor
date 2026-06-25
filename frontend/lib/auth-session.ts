import { cookies } from "next/headers";
import { headers } from "next/headers";

import { AUTH_COOKIE_NAME, type SessionUser } from "@/lib/auth-constants";

async function resolveSessionUserFromApi(token: string): Promise<SessionUser | null> {
  const headerStore = await headers();
  const host = headerStore.get("host");
  if (!host) {
    return null;
  }

  const protocol = process.env.NODE_ENV === "production" ? "https" : "http";
  const response = await fetch(`${protocol}://${host}/api/auth/me`, {
    headers: {
      Cookie: `${AUTH_COOKIE_NAME}=${token}`
    },
    cache: "no-store"
  });

  if (!response.ok) {
    return null;
  }

  const payload = (await response.json()) as {
    ok?: boolean;
    user?: { id?: string; username?: string; displayName?: string; role?: string };
  };

  if (!payload.ok || !payload.user?.username) {
    return null;
  }

  return {
    id: payload.user.id ?? "",
    username: payload.user.username,
    displayName: payload.user.displayName ?? payload.user.username,
    role: payload.user.role ?? "editor"
  };
}

export async function getCurrentSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return null;
  }

  return resolveSessionUserFromApi(token);
}
