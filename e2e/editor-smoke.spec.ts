import { expect, test } from "@playwright/test";

const DEMO_PROJECT_ID = "proj_001";

test.describe("editor workflow smoke", () => {
  test("editor login, traverse project workflow, blocked from LLM settings", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();

    await page.getByLabel("已开放登录的账号").selectOption("editor");
    await page.getByLabel("密码").fill("edit123");
    await page.getByRole("button", { name: "进入工作台" }).click();

    await expect(page).toHaveURL("/");
    await expect(page.getByText("Demo Editor · 剪辑")).toBeVisible();
    await expect(page.getByRole("link", { name: "LLM 配置" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "用户管理" })).toHaveCount(0);

    await page.getByRole("link", { name: "进入项目" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/projects/${DEMO_PROJECT_ID}$`));

    await page.goto(`/projects/${DEMO_PROJECT_ID}/themes`);
    await expect(page.getByRole("heading", { name: "主题生成与确认" })).toBeVisible();

    await page.goto(`/projects/${DEMO_PROJECT_ID}/rhythm`);
    await expect(page.getByRole("heading", { name: "节奏规划" })).toBeVisible();

    await page.goto(`/projects/${DEMO_PROJECT_ID}/storyboard`);
    await expect(page.getByRole("heading", { name: "分镜时间线" })).toBeVisible();

    await page.goto(`/projects/${DEMO_PROJECT_ID}/export`);
    await expect(page.getByRole("heading", { name: "导出信息与脚本预览" })).toBeVisible();

    await page.goto("/settings/llm");
    await expect(page).toHaveURL("/");
  });
});
