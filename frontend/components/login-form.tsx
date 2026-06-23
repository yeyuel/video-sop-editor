"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { DIRECTOR_UI_USERNAME } from "@/lib/auth-constants";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
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
          username: DIRECTOR_UI_USERNAME,
          password
        })
      });

      const payload = (await response.json()) as { error?: string; ok?: boolean };

      if (!response.ok || !payload.ok) {
        setError(payload.error ?? "登录失败，请检查密码后重试。");
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
          readOnly
          value={DIRECTOR_UI_USERNAME}
          className="w-full rounded-2xl border border-pine/20 bg-sand/45 px-4 py-3 text-base text-ink/75 outline-none"
        />
      </label>

      <label className="block">
        <span className="mb-2 block text-sm text-ink/75">密码</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="请输入导演账号密码"
          className="w-full rounded-2xl border border-pine/20 bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-pine"
        />
      </label>

      <div className="rounded-2xl border border-pine/10 bg-sand/50 px-4 py-3 text-sm leading-6 text-ink/70">
        当前页面先开放导演账号登录。后续新增用户会保存在后台数据库里，再按阶段逐步开放界面入口。
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
        {submitting ? "登录中..." : "进入导演工作台"}
      </button>
    </form>
  );
}
