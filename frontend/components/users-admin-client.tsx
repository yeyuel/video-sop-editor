"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useState, useTransition } from "react";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import {
  createUser,
  deleteUser,
  listUsers,
  updateUser,
  type CreateUserPayload
} from "@/lib/users-api";
import type { AuthUser } from "@/types/domain";

type UsersAdminClientProps = {
  currentUserId: string;
};

const ROLE_LABELS: Record<string, string> = {
  director: "导演",
  editor: "剪辑"
};

function roleBadgeClass(role: string) {
  return role === "director"
    ? "border-pine/20 bg-mist text-pine"
    : "border-black/10 bg-white text-ink/70";
}

function loginBadgeClass(enabled: boolean) {
  return enabled
    ? "border-pine/20 bg-mist text-pine"
    : "border-clay/15 bg-[#fff5ef] text-clay";
}

function emptyCreateForm() {
  return {
    username: "",
    password: "",
    displayName: "",
    role: "editor" as CreateUserPayload["role"],
    uiEnabled: false
  };
}

export function UsersAdminClient({ currentUserId }: UsersAdminClientProps) {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const [isPending, startTransition] = useTransition();

  const [editingUser, setEditingUser] = useState<AuthUser | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<CreateUserPayload["role"]>("editor");
  const [uiEnabled, setUiEnabled] = useState(false);

  const refreshUsers = useCallback(async () => {
    const nextUsers = await listUsers();
    setUsers(nextUsers);
  }, []);

  const resetCreateForm = useCallback(() => {
    const empty = emptyCreateForm();
    setEditingUser(null);
    setUsername(empty.username);
    setPassword(empty.password);
    setDisplayName(empty.displayName);
    setRole(empty.role);
    setUiEnabled(empty.uiEnabled);
    setError("");
  }, []);

  const startEdit = useCallback((user: AuthUser) => {
    setEditingUser(user);
    setUsername(user.username);
    setPassword("");
    setDisplayName(user.displayName);
    setRole(user.role === "director" ? "director" : "editor");
    setUiEnabled(user.uiEnabled);
    setError("");
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      setError("");
      try {
        const nextUsers = await listUsers();
        if (!cancelled) {
          setUsers(nextUsers);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "加载用户列表失败。");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!notice) {
      return;
    }
    const timer = window.setTimeout(() => setNotice(null), 2800);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        if (editingUser) {
          const updated = await updateUser(editingUser.id, {
            displayName: displayName.trim() || editingUser.username,
            role,
            uiEnabled,
            ...(password.trim() ? { password: password.trim() } : {})
          });
          await refreshUsers();
          resetCreateForm();
          setNotice({
            title: "用户已更新",
            message: `「${updated.username}」的信息已保存。`,
            tone: "success"
          });
          return;
        }

        const created = await createUser({
          username: username.trim(),
          password,
          displayName: displayName.trim() || username.trim(),
          role,
          uiEnabled
        });
        await refreshUsers();
        resetCreateForm();
        setNotice({
          title: "用户已创建",
          message: created.uiEnabled
            ? `「${created.username}」已创建，并已开放登录。`
            : `「${created.username}」已创建，暂未开放登录。`,
          tone: "success"
        });
      } catch (submitError) {
        const message =
          submitError instanceof Error ? submitError.message : "保存用户失败，请稍后重试。";
        setError(message);
        setNotice({ title: editingUser ? "更新失败" : "创建失败", message, tone: "error" });
      }
    });
  }

  function handleDelete(user: AuthUser) {
    const confirmed = window.confirm(`确定删除用户「${user.username}」吗？此操作不可恢复。`);
    if (!confirmed) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        await deleteUser(user.id);
        if (editingUser?.id === user.id) {
          resetCreateForm();
        }
        await refreshUsers();
        setNotice({
          title: "用户已删除",
          message: `「${user.username}」已从系统中移除。`,
          tone: "success"
        });
      } catch (deleteError) {
        const message =
          deleteError instanceof Error ? deleteError.message : "删除用户失败，请稍后重试。";
        setError(message);
        setNotice({ title: "删除失败", message, tone: "error" });
      }
    });
  }

  const isEditingSelf = editingUser?.id === currentUserId;

  if (loading) {
    return <BlockingNotice visible title="正在加载用户列表" description="请稍候…" />;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
      <section className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
        <p className="text-xs uppercase tracking-[0.22em] text-pine/70">
          {editingUser ? "Edit User" : "New User"}
        </p>
        <h2 className="mt-2 text-2xl font-semibold text-ink">
          {editingUser ? "编辑用户" : "新建用户"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink/70">
          {editingUser
            ? "修改显示名、角色、登录权限或重置密码。用户名不可修改。"
            : "仅导演账号可创建用户。关闭「允许登录」时，账号会写入数据库但无法进入工作台。"}
        </p>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="text-sm font-medium text-ink">用户名</span>
            <input
              required={!editingUser}
              readOnly={Boolean(editingUser)}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className={`mt-2 w-full rounded-2xl border border-black/10 px-4 py-3 text-sm outline-none ring-pine/20 focus:ring-2 ${
                editingUser ? "bg-sand/45 text-ink/75" : "bg-white"
              }`}
              placeholder="例如 editor_a"
              autoComplete="off"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-ink">显示名称</span>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm outline-none ring-pine/20 focus:ring-2"
              placeholder="例如 剪辑 A"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-ink">
              {editingUser ? "新密码（留空则不修改）" : "初始密码"}
            </span>
            <input
              required={!editingUser}
              type="password"
              minLength={editingUser ? undefined : 6}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm outline-none ring-pine/20 focus:ring-2"
              placeholder={editingUser ? "留空则不修改" : "至少 6 位"}
              autoComplete={editingUser ? "new-password" : "new-password"}
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-ink">角色</span>
            <select
              value={role}
              disabled={isEditingSelf}
              onChange={(event) => {
                const nextRole = event.target.value as CreateUserPayload["role"];
                setRole(nextRole);
                if (nextRole === "director") {
                  setUiEnabled(true);
                }
              }}
              className="mt-2 w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm outline-none ring-pine/20 focus:ring-2 disabled:bg-sand/45 disabled:text-ink/60"
            >
              <option value="editor">剪辑</option>
              <option value="director">导演</option>
            </select>
          </label>

          <label className="flex items-start gap-3 rounded-2xl border border-black/8 bg-mist/50 px-4 py-4">
            <input
              type="checkbox"
              checked={uiEnabled}
              disabled={isEditingSelf || role === "director"}
              onChange={(event) => setUiEnabled(event.target.checked)}
              className="mt-1 h-4 w-4 rounded border-black/20 text-pine focus:ring-pine/30 disabled:opacity-60"
            />
            <span>
              <span className="block text-sm font-medium text-ink">允许登录</span>
              <span className="mt-1 block text-sm leading-6 text-ink/65">
                {isEditingSelf
                  ? "当前登录账号始终允许登录。"
                  : "勾选后，该用户可使用用户名和密码登录工作台。"}
              </span>
            </span>
          </label>

          {error ? <p className="text-sm text-clay">{error}</p> : null}

          <div className="flex gap-3">
            {editingUser ? (
              <button
                type="button"
                onClick={resetCreateForm}
                className="inline-flex flex-1 items-center justify-center rounded-full border border-pine/15 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist"
              >
                取消编辑
              </button>
            ) : null}
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex flex-1 items-center justify-center rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:opacity-60"
            >
              {isPending ? "保存中…" : editingUser ? "保存修改" : "创建用户"}
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
        <p className="text-xs uppercase tracking-[0.22em] text-pine/70">User List</p>
        <h2 className="mt-2 text-2xl font-semibold text-ink">已有用户</h2>
        <p className="mt-2 text-sm leading-6 text-ink/70">共 {users.length} 个账号。</p>

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-black/8 text-ink/55">
                <th className="px-3 py-3 font-medium">用户名</th>
                <th className="px-3 py-3 font-medium">显示名</th>
                <th className="px-3 py-3 font-medium">角色</th>
                <th className="px-3 py-3 font-medium">登录</th>
                <th className="px-3 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const isSelf = user.id === currentUserId;
                return (
                  <tr
                    key={user.id}
                    className={`border-b border-black/5 ${editingUser?.id === user.id ? "bg-mist/40" : ""}`}
                  >
                    <td className="px-3 py-4 font-medium text-ink">
                      {user.username}
                      {isSelf ? (
                        <span className="ml-2 text-xs text-pine/70">（当前）</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-4 text-ink/75">{user.displayName}</td>
                    <td className="px-3 py-4">
                      <span
                        className={`inline-flex rounded-full border px-3 py-1 text-xs ${roleBadgeClass(user.role)}`}
                      >
                        {ROLE_LABELS[user.role] ?? user.role}
                      </span>
                    </td>
                    <td className="px-3 py-4">
                      <span
                        className={`inline-flex rounded-full border px-3 py-1 text-xs ${loginBadgeClass(user.uiEnabled)}`}
                      >
                        {user.uiEnabled ? "可登录" : "未开放"}
                      </span>
                    </td>
                    <td className="px-3 py-4">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => startEdit(user)}
                          className="rounded-full border border-pine/15 px-3 py-1.5 text-xs font-medium text-pine transition hover:bg-mist"
                        >
                          编辑
                        </button>
                        <button
                          type="button"
                          disabled={isSelf || isPending}
                          onClick={() => handleDelete(user)}
                          className="rounded-full border border-clay/20 px-3 py-1.5 text-xs font-medium text-clay transition hover:bg-[#fff5ef] disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {notice ? (
        <ToastNotice visible title={notice.title} message={notice.message} tone={notice.tone} />
      ) : null}
    </div>
  );
}
