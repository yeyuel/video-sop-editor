"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { DIRECTOR_UI_USERNAME } from "@/lib/auth-constants";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState(DIRECTOR_UI_USERNAME);
  const [password, setPassword] = useState("root123");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: username.trim(),
          password
        })
      });

      const payload = (await response.json()) as { error?: string; ok?: boolean };

      if (!response.ok || !payload.ok) {
        setError(payload.error ?? "登录失败，请检查账号和密码。");
        return;
      }

      const next = searchParams.get("next");
      router.replace(next && next.startsWith("/") ? next : "/");
      router.refresh();
    } catch {
      setError("登录失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
      <label className="block">
        <span className="mb-2 block text-sm text-ink/75">账号</span>
        <input
          required
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          className="w-full rounded-2xl border border-pine/20 bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-pine"
          placeholder="请输入用户名"
          autoComplete="username"
        />
      </label>

      <label className="block">
        <span className="mb-2 block text-sm text-ink/75">密码</span>
        <input
          type="password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="请输入密码"
          className="w-full rounded-2xl border border-pine/20 bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-pine"
          autoComplete="current-password"
        />
      </label>

      <div className="rounded-2xl border border-pine/10 bg-sand/50 px-4 py-3 text-sm leading-6 text-ink/70">
        仅「允许登录」的账号可以进入工作台。导演可在用户管理页创建账号并控制是否开放登录。
      </div>

      {error ? (
        <div className="rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay">
          {error}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={submitting}
        className="inline-flex w-full items-center justify-center rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "登录中..." : "进入工作台"}
      </button>
    </form>
  );
}
