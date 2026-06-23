# 编码防乱码约束

## 1. 本次已确认的乱码成因

本项目里出现过的 `寤鸿`、`鐢熸垚`、`銆?` 一类乱码，不是数据库存储问题，也不是浏览器渲染问题，而是：

1. 原始中文文本本来是 UTF-8。
2. 某一步被按 GBK / CP936 / ANSI 错误读取。
3. 读取后的乱码文本又被重新保存为 UTF-8。
4. 乱码因此固化进源码。

这类问题在 Windows PowerShell 5.1 环境里尤其容易出现，典型触发方式包括：

- 在控制台里直接传中文字符串，再把结果写回文件。
- 执行无 BOM 的 UTF-8 PowerShell 脚本。
- 从已经显示为乱码的终端输出中复制文本，再粘贴回源码。

## 2. 当前仓库约束

仓库已增加以下保护：

- `.editorconfig`
  - 默认文本文件使用 `utf-8`
  - `*.ps1` 单独使用 `utf-8-bom`
- `.vscode/settings.json`
  - `files.encoding = utf8`
  - `files.autoGuessEncoding = false`
- `scripts/scan-mojibake.ps1`
  - 用于扫描已跟踪源码中的典型乱码片段

## 3. 开发规则

后续开发统一遵守以下规则：

1. 中文源码、文档、配置文件统一保存为 UTF-8。
2. PowerShell 脚本统一保存为 UTF-8 BOM。
3. 不要把终端里已经乱码的文本重新复制回源码。
4. 在 PowerShell 中读取中文文件时，显式使用 `-Encoding utf8`。
5. 如需批量替换中文文案，优先直接在编辑器中修改，不通过控制台中转。
6. 提交前可以执行一次乱码扫描。

## 4. 建议检查命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\scan-mojibake.ps1
```

如果输出：

```text
未发现可疑乱码片段。
```

说明当前扫描规则下没有发现已固化进仓库的典型乱码。

## 5. 提交前自动检查

仓库已提供版本化 Git hook：

- `.githooks/pre-commit`

首次启用时，执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-git-hooks.ps1
```

执行后，提交前会自动运行乱码扫描。若扫描失败，commit 会被拦截。
