"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { DIRECTOR_UI_USERNAME } from "@/lib/auth-constants";
import { getBrowserApiBaseUrl } from "@/lib/api-base";

type LoginOption = {
  username: string;
  displayName: string;
  role: string;
};

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loginOptions, setLoginOptions] = useState<LoginOption[]>([]);
  const [username, setUsername] = useState(DIRECTOR_UI_USERNAME);
  const [password, setPassword] = useState("root123");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadLoginOptions() {
      try {
        const response = await fetch(`${getBrowserApiBaseUrl()}/auth/login-options`, {
          credentials: "include",
          cache: "no-store"
        });
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as { data?: LoginOption[] };
        if (cancelled || !payload.data?.length) {
          return;
        }
        setLoginOptions(payload.data);
        if (!payload.data.some((item) => item.username === username)) {
          setUsername(payload.data[0].username);
        }
      } catch {
        // ignore network errors; manual login still works
      }
    }

    void loadLoginOptions();
    return () => {
      cancelled = true;
    };
  }, [username]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
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

  const selectedOption = loginOptions.find((item) => item.username === username);

  return (
    <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
      {loginOptions.length > 0 ? (
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">已开放登录的账号</span>
          <select
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="input-field"
          >
            {loginOptions.map((option) => (
              <option key={option.username} value={option.username}>
                {option.displayName} ({option.username}) ·{" "}
                {option.role === "director" ? "导演" : "剪辑"}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">账号</span>
          <input
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="input-field"
            placeholder="请输入用户名"
            autoComplete="username"
          />
        </label>
      )}

      <label className="block">
        <span className="mb-2 block text-sm text-ink/75">密码</span>
        <input
          type="password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="请输入密码"
          className="input-field"
          autoComplete="current-password"
        />
      </label>

      <div className="stat-cell text-sm leading-6">
        仅「允许登录」的账号可以进入工作台。导演可在用户管理页创建账号并控制是否开放登录。
        {selectedOption ? (
          <span className="mt-1 block">
            当前选择：{selectedOption.displayName}（
            {selectedOption.role === "director" ? "导演 · 全量能力" : "剪辑 · 项目内编辑"}）
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay">
          {error}
        </div>
      ) : null}

      <button type="submit" disabled={submitting} className="btn-primary w-full">
        {submitting ? "登录中..." : "进入工作台"}
      </button>
    </form>
  );
}
