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
        <section className="grid w-full gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[2rem] border border-black/5 bg-white/80 p-8 shadow-card backdrop-blur md:p-10">
            <p className="text-xs uppercase tracking-[0.28em] text-pine">Travel Edit OS</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-ink md:text-6xl">
              旅行短视频剪辑导演助手
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-ink/70 md:text-lg">
              从项目创建、素材录入到节奏规划、分镜脚本和导出整理，统一在一个导演工作台里完成。
            </p>

            <div className="mt-8 grid gap-4 md:grid-cols-3">
              <div className="rounded-3xl bg-mist px-5 py-5">
                <p className="text-xs uppercase tracking-[0.2em] text-pine/65">01</p>
                <p className="mt-3 text-lg font-medium text-ink">项目与素材</p>
                <p className="mt-2 text-sm leading-6 text-ink/65">先把项目骨架和素材池整理清楚。</p>
              </div>
              <div className="rounded-3xl bg-mist px-5 py-5">
                <p className="text-xs uppercase tracking-[0.2em] text-pine/65">02</p>
                <p className="mt-3 text-lg font-medium text-ink">主题与节奏</p>
                <p className="mt-2 text-sm leading-6 text-ink/65">
                  用叙事方向和节拍卡点先把结构站稳。
                </p>
              </div>
              <div className="rounded-3xl bg-mist px-5 py-5">
                <p className="text-xs uppercase tracking-[0.2em] text-pine/65">03</p>
                <p className="mt-3 text-lg font-medium text-ink">分镜与导出</p>
                <p className="mt-2 text-sm leading-6 text-ink/65">
                  输出可执行时间线脚本和发布文案。
                </p>
              </div>
            </div>
          </div>

          <section className="rounded-[2rem] border border-black/5 bg-white/88 p-8 shadow-card backdrop-blur md:p-10">
            <p className="text-xs uppercase tracking-[0.28em] text-pine/75">Director Login</p>
            <h2 className="mt-4 text-3xl font-semibold text-ink">登录工作台</h2>
            <p className="mt-3 text-sm leading-7 text-ink/70">
              使用已开放登录的账号进入工作台。导演可在用户管理页新建账号并决定是否允许登录。
            </p>

            <LoginForm />
          </section>
        </section>
      </div>
    </main>
  );
}
