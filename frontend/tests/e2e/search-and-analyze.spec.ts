import { expect, test } from "@playwright/test";


test("imports a local three-player fixture and displays all players", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("牌谱文件").setInputFiles("../backend/tests/fixtures/majsoul/three_player_kita.json");
  await page.getByRole("button", { name: "导入文件" }).click();
  await expect(page.getByTestId("player-luck-score")).toHaveCount(3, { timeout: 60_000 });
  await expect(page.locator(".analysis-header").getByText("baseline-v1 · v1.0.0", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English" }).click();
  await expect(page.getByRole("heading", { name: "Game luck" })).toBeVisible();
  await expect(page.getByText("Match points are not luck")).toBeVisible();
  await expect(page.getByTestId("player-luck-score")).toHaveCount(3);
});
