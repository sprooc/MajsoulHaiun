import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { HomePage } from "../pages/home-page";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
  localStorage.clear();
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
          players: [{ accountId: 7, nickname: "A" }, { accountId: 8, nickname: "B" }],
          scores: [31000, 23000, 25000, 21000],
          ranks: [1, 3, 2, 4],
          gradingScores: [],
        }],
        nextCursor: null,
      }), { status: 200 })),
  );

  render(<MemoryRouter><HomePage /></MemoryRouter>);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  await userEvent.click(await screen.findByRole("button", { name: /A/ }));

  const highlightedScore = await screen.findByText("31,000", { selector: "strong" });
  const highlightedRank = screen.getByText("1", { selector: "strong" });
  expect(highlightedScore.closest("td")).toHaveTextContent("31,000 / 23,000 / 25,000 / 21,000");
  expect(highlightedRank.closest("td")).toHaveTextContent("1 / 3 / 2 / 4");
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining("/players/amae-koromo/7/games"), expect.anything());
});


it("opens a provisional analysis page before the remote replay finishes loading", async () => {
  let resolveImport: ((response: Response) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveImport = resolve; })),
  );

  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/analyses/:analysisId" element={<h1>分析中页面</h1>} />
      </Routes>
    </MemoryRouter>,
  );

  const locator = screen.getByPlaceholderText("粘贴雀魂牌谱链接");
  await userEvent.type(locator, "game-uuid");
  await userEvent.click(screen.getByRole("button", { name: "导入链接并开始分析" }));

  expect(await screen.findByRole("heading", { name: "分析中页面" })).toBeInTheDocument();
  expect(resolveImport).toBeTypeOf("function");
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
  render(<MemoryRouter><HomePage /></MemoryRouter>);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  await userEvent.click(await screen.findByRole("button", { name: /A/ }));
  await userEvent.click(await screen.findByRole("button", { name: "加载更多" }));
  const nextScore = await screen.findByText("40,000");
  expect(nextScore.closest("td")).toHaveTextContent("40,000 / 30,000 / 20,000 / 10,000");
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining("cursor=123"), expect.anything());
});


it("imports a selected recent game and explains unavailable configured-account access", async () => {
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

  render(<MemoryRouter><HomePage /></MemoryRouter>);
  await userEvent.type(screen.getByRole("textbox", { name: "玩家名称" }), "A");
  await userEvent.click(screen.getByRole("button", { name: "搜索玩家" }));
  await userEvent.click(await screen.findByRole("button", { name: /A/ }));
  await userEvent.click(await screen.findByRole("button", { name: "开始分析" }));

  expect(fetch).toHaveBeenLastCalledWith(
    "/api/replays/import-locator",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ locator: "game-uuid" }) }),
  );
  expect(await screen.findByText("已配置的雀魂账号均无法获取此牌谱。请检查牌谱权限，或改用本地牌谱文件导入。")).toBeInTheDocument();
});
