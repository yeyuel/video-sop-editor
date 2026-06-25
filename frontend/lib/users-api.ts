import type { AuthUser } from "@/types/domain";

export type CreateUserPayload = {
  username: string;
  password: string;
  displayName: string;
  role: "director" | "editor";
  uiEnabled: boolean;
};

export type UpdateUserPayload = {
  displayName?: string;
  password?: string;
  role?: "director" | "editor";
  uiEnabled?: boolean;
};

async function readUsersError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { error?: string };
    if (payload.error) {
      return payload.error;
    }
  } catch {
    // ignore
  }
  return "操作失败，请稍后重试。";
}

export async function listUsers(): Promise<AuthUser[]> {
  const response = await fetch("/api/auth/users", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await readUsersError(response));
  }
  const payload = (await response.json()) as { data?: AuthUser[] };
  return payload.data ?? [];
}

export async function createUser(payload: CreateUserPayload): Promise<AuthUser> {
  const response = await fetch("/api/auth/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await readUsersError(response));
  }
  const result = (await response.json()) as { data?: AuthUser };
  if (!result.data) {
    throw new Error("创建用户响应无效。");
  }
  return result.data;
}

export async function updateUser(userId: string, payload: UpdateUserPayload): Promise<AuthUser> {
  const response = await fetch(`/api/auth/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await readUsersError(response));
  }
  const result = (await response.json()) as { data?: AuthUser };
  if (!result.data) {
    throw new Error("更新用户响应无效。");
  }
  return result.data;
}

export async function deleteUser(userId: string): Promise<void> {
  const response = await fetch(`/api/auth/users/${userId}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(await readUsersError(response));
  }
}
