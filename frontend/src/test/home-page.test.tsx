import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { HomePage } from "../pages/home-page";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
});


it("loads recent games after selecting a player", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([
        { source: "amae-koromo", externalId: "7", nickname: "A", mode: "4p" },
      ]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        games: [{
          source: "amae-koromo",
          externalId: "record",
          uuid: "game-uuid",
          mode: "4p",
          startedAt: 1700000000,
          players: [{ nickname: "A" }, { nickname: "B" }],
          scores: [31000, 23000, 25000, 21000],
          gradingScores: [],
        }],
        nextCursor: null,
      }), { status: 200 })),
  );

  render(<HomePage />);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  await userEvent.click(await screen.findByRole("button", { name: /A/ }));

  expect(await screen.findByText("31,000 / 23,000 / 25,000 / 21,000")).toBeInTheDocument();
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining("/players/amae-koromo/7/games"), expect.anything());
});


it("loads the next page using the returned cursor", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([
        { source: "amae-koromo", externalId: "7", nickname: "A", mode: "4p" },
      ]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ games: [], nextCursor: 123 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        games: [{ source: "amae-koromo", externalId: "next", uuid: "next", mode: "4p", players: [], scores: [40000, 30000, 20000, 10000], gradingScores: [] }],
        nextCursor: null,
      }), { status: 200 })),
  );
  render(<HomePage />);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  await userEvent.click(await screen.findByRole("button", { name: /A/ }));
  await userEvent.click(await screen.findByRole("button", { name: "加载更多" }));
  expect(await screen.findByText("40,000 / 30,000 / 20,000 / 10,000")).toBeInTheDocument();
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining("cursor=123"), expect.anything());
});


it("imports a selected recent game and explains unavailable anonymous replay access", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([
        { source: "amae-koromo", externalId: "7", nickname: "A", mode: "4p" },
      ]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        games: [{
          source: "amae-koromo",
          externalId: "record",
          uuid: "game-uuid",
          mode: "4p",
          players: [{ nickname: "A" }, { nickname: "B" }],
          scores: [31000, 23000, 25000, 21000],
          gradingScores: [],
        }],
        nextCursor: null,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        code: "REPLAY_FETCH_UNAVAILABLE",
        message: "unavailable",
        parameters: {},
      }), { status: 503, headers: { "Content-Type": "application/json" } })),
  );

  render(<HomePage />);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  await userEvent.click(await screen.findByRole("button", { name: /A/ }));
  await userEvent.click(await screen.findByRole("button", { name: "导入并分析" }));

  expect(fetch).toHaveBeenLastCalledWith(
    "/api/replays/import-locator",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ locator: "game-uuid" }) }),
  );
  expect(await screen.findByText("匿名原始牌谱暂不可用。公开对局信息仍可查看，请改用本地牌谱文件导入。")).toBeInTheDocument();
});
