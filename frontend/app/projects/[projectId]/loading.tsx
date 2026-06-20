export default function ProjectLoading() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#f4efe5]/78 px-6 backdrop-blur-md">
      <div className="w-full max-w-sm rounded-[30px] border border-white/60 bg-white/88 p-7 shadow-[0_28px_90px_rgba(25,34,41,0.14)]">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-mist">
          <div className="async-orbit relative h-8 w-8">
            <span className="absolute inset-0 rounded-full border-2 border-pine/20" />
            <span className="absolute inset-[3px] rounded-full border-2 border-transparent border-t-pine border-r-pine" />
          </div>
        </div>
        <p className="mt-6 text-center text-xs uppercase tracking-[0.28em] text-pine/65">
          Loading Workspace
        </p>
        <h2 className="mt-3 text-center text-2xl font-semibold text-ink">正在同步项目数据</h2>
        <p className="mt-2 text-center text-sm leading-6 text-ink/65">
          我们正在读取项目配置和数据库内容，请稍等片刻。
        </p>
        <div className="mt-5 flex items-center justify-center gap-1.5">
          <span className="async-dot h-2.5 w-2.5 rounded-full bg-pine/35 [animation-delay:-0.2s]" />
          <span className="async-dot h-2.5 w-2.5 rounded-full bg-pine/55 [animation-delay:-0.1s]" />
          <span className="async-dot h-2.5 w-2.5 rounded-full bg-pine/75" />
        </div>
      </div>
    </div>
  );
}
