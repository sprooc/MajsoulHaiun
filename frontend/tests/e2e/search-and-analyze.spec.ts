import { expect, test } from "@playwright/test";


test("imports a local three-player fixture and displays all players", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("牌谱文件").setInputFiles("../backend/tests/fixtures/majsoul/three_player_kita.json");
  await page.getByRole("button", { name: "导入文件并开始分析" }).click();
  await expect(page).toHaveURL(/\/analyses\//, { timeout: 60_000 });
  await expect(page.getByTestId("player-luck-score")).toHaveCount(3, { timeout: 60_000 });
  await expect(page.getByRole("link", { name: "查看原始牌谱" })).toHaveCount(0);
  await page.getByRole("button", { name: "English" }).click();
  await expect(page.getByRole("heading", { name: "Analysis result" })).toBeVisible();
  await expect(page.getByText("Match points are not luck")).toBeVisible();
  await expect(page.getByTestId("player-luck-score")).toHaveCount(3);
});
