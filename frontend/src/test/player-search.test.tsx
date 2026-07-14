import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { PlayerSearch } from "../components/player-search";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
  sessionStorage.clear();
});


it("searches four-player users and renders the result", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          { source: "amae-koromo", externalId: "7", nickname: "A", mode: "4p", levelId: 10401 },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );
  render(<PlayerSearch />);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  expect(await screen.findByText("A")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("mode=4p"), expect.anything());
});


it("can switch search mode to three-player", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
  render(<PlayerSearch />);
  await userEvent.click(screen.getByRole("button", { name: "三人麻将" }));
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("mode=3p"), expect.anything());
});
