import Link from "next/link";

import { LlmSettingsClient } from "@/components/llm-settings-client";
import { Topbar } from "@/components/topbar";

export default function LlmSettingsPage() {
  return (
    <main className="pb-12">
      <Topbar
        eyebrow="Settings"
        title="LLM 配置"
        action={{ label: "返回首页", href: "/" }}
        settingsHref=""
      />
      <div className="mx-auto max-w-7xl px-6">
        <section className="mb-6 rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-pine/70">LLM Gateway</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">大模型 Provider 配置</h2>
              <p className="mt-2 text-sm leading-6 text-ink/70">
                在此配置 API Key、Base URL 和 Model。配置保存在后端，供主题建议、分镜建议、导出文案和节奏说明等能力使用。
              </p>
            </div>
            <Link
              href="/"
              className="inline-flex rounded-full border border-pine/15 bg-white/85 px-5 py-3 text-sm font-medium text-pine transition hover:border-pine/30 hover:bg-mist"
            >
              项目列表
            </Link>
          </div>
        </section>

        <LlmSettingsClient />
      </div>
    </main>
  );
}
