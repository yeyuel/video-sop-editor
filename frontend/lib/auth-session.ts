import { cookies } from "next/headers";

import { AUTH_COOKIE_NAME, type SessionUser } from "@/lib/auth-users";

export async function getCurrentSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies();
  const username = cookieStore.get(AUTH_COOKIE_NAME)?.value;

  if (!username) {
    return null;
  }

  return { username };
}
