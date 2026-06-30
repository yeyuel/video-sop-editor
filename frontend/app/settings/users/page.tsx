import Link from "next/link";
import { redirect } from "next/navigation";

import { Topbar } from "@/components/topbar";
import { UsersAdminClient } from "@/components/users-admin-client";
import { getCurrentSessionUser } from "@/lib/auth-session";

export default async function UsersSettingsPage() {
  const user = await getCurrentSessionUser();
  if (!user) {
    redirect("/login?next=/settings/users");
  }
  if (user.role !== "director") {
    redirect("/");
  }

  return (
    <main className="pb-12">
      <Topbar
        eyebrow="Settings"
        title="用户管理"
        action={{ label: "返回首页", href: "/" }}
        settingsHref="/settings/llm"
        manageUsersHref=""
      />
      <div className="mx-auto max-w-7xl px-6">
        <section className="surface-hero mb-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-pine/70">Director Only</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">创建与管理后台用户</h2>
              <p className="mt-2 text-sm leading-6 text-ink/70">
                当前登录：<span className="font-medium text-ink">{user.displayName}</span>
                （导演）。新建用户默认不开放登录，需手动勾选「允许登录」。
              </p>
            </div>
            <Link href="/settings/llm" className="btn-secondary">
              LLM 配置
            </Link>
          </div>
        </section>

        <UsersAdminClient currentUserId={user.id} />
      </div>
    </main>
  );
}
