import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { getCurrentSessionUser } from "@/lib/auth-session";

export default async function LoginPage() {
  const user = await getCurrentSessionUser();

  if (user) {
    redirect("/");
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-6xl items-center">
        <section className="grid w-full gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="surface-hero p-8 md:p-10">
            <div className="inline-flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-pine text-xs font-bold text-white">
                TE
              </span>
              <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-pine/80">
                Travel Edit OS
              </p>
            </div>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight text-ink md:text-5xl">
              旅行短视频剪辑导演助手
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-8 text-ink/60">
              从项目创建、素材录入到节奏规划、分镜脚本和导出整理，统一在一个导演工作台里完成。
            </p>

            <div className="mt-8 grid gap-3 md:grid-cols-3">
              <div className="surface-muted p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-pine/70">01</p>
                <p className="mt-2 font-medium text-ink">项目与素材</p>
                <p className="mt-1 text-sm leading-6 text-ink/55">整理项目骨架和素材池。</p>
              </div>
              <div className="surface-muted p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-pine/70">02</p>
                <p className="mt-2 font-medium text-ink">主题与节奏</p>
                <p className="mt-1 text-sm leading-6 text-ink/55">叙事方向与节拍卡点。</p>
              </div>
              <div className="rounded-2xl border border-ai/15 bg-ai-soft p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-ai">03</p>
                <p className="mt-2 font-medium text-ink">AI 分镜与导出</p>
                <p className="mt-1 text-sm leading-6 text-ink/55">LLM 辅助脚本与发布文案。</p>
              </div>
            </div>
          </div>

          <section className="surface-panel p-8 md:p-10">
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-ink/40">
              Director Login
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-ink">登录工作台</h2>
            <p className="mt-3 text-sm leading-7 text-ink/55">
              使用已开放登录的账号进入。导演可在用户管理页新建账号。
            </p>

            <LoginForm />
          </section>
        </section>
      </div>
    </main>
  );
}
