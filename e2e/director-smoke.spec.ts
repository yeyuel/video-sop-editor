import { expect, test } from "@playwright/test";

const DEMO_PROJECT_ID = "proj_001";

test.describe("director workflow smoke", () => {
  test("login and traverse theme → rhythm → storyboard → export", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();

    await page.getByLabel("账号").fill("director");
    await page.getByLabel("密码").fill("root123");
    await page.getByRole("button", { name: "进入工作台" }).click();

    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { name: "历史项目列表" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "阿勒泰雪国片" })).toBeVisible();

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
  });
});
