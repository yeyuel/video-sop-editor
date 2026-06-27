import { cookies } from "next/headers";

import { AUTH_COOKIE_NAME } from "@/lib/auth-constants";

export async function getServerAuthHeaders(): Promise<Record<string, string>> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;
  if (!token) {
    return {};
  }

  return {
    Cookie: `${AUTH_COOKIE_NAME}=${token}`,
    "X-Session-Token": token
  };
}
