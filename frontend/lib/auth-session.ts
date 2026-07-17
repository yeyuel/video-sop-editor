import { cookies } from "next/headers";

import { getServerApiBaseUrl } from "@/lib/api-base";
import { AUTH_COOKIE_NAME, type SessionUser } from "@/lib/auth-constants";

async function resolveSessionUserFromApi(token: string): Promise<SessionUser | null> {
  try {
    const response = await fetch(`${getServerApiBaseUrl()}/auth/me`, {
      headers: {
        "X-Session-Token": token
      },
      cache: "no-store"
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as {
      data?: { id?: string; username?: string; displayName?: string; role?: string };
    };
    const user = payload.data;
    if (!user?.username) {
      return null;
    }

    return {
      id: user.id ?? "",
      username: user.username,
      displayName: user.displayName ?? user.username,
      role: user.role ?? "editor"
    };
  } catch {
    // Authentication outages should return users to login instead of crashing SSR.
    return null;
  }
}

export async function getCurrentSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return null;
  }

  return resolveSessionUserFromApi(token);
}
