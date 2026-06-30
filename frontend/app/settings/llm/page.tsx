import Link from "next/link";
import { redirect } from "next/navigation";

import { LlmSettingsClient } from "@/components/llm-settings-client";
import { Topbar } from "@/components/topbar";
import { getCurrentSessionUser } from "@/lib/auth-session";

export default async function LlmSettingsPage() {
  const sessionUser = await getCurrentSessionUser();
  if (!sessionUser) {
    redirect("/login?next=/settings/llm");
  }
  if (sessionUser.role !== "director") {
    redirect("/");
  }

  return (
    <main className="pb-12">
      <Topbar
        eyebrow="Settings"
        title="LLM 配置"
        action={{ label: "返回首页", href: "/" }}
        settingsHref=""
        manageUsersHref="/settings/users"
      />
      <div className="mx-auto max-w-7xl px-6">
        <section className="surface-hero mb-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-pine/70">LLM Gateway</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">大模型 Provider 配置</h2>
              <p className="mt-2 text-sm leading-6 text-ink/70">
                仅导演账号可修改 LLM 配置。剪辑账号可正常使用主题/分镜/导出等 LLM
                建议能力，但会使用此处保存的系统级 Provider 与 Key。
              </p>
            </div>
            <Link href="/" className="btn-secondary">
              项目列表
            </Link>
          </div>
        </section>

        <LlmSettingsClient />
      </div>
    </main>
  );
}
