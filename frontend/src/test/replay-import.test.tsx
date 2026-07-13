import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { ReplayImport } from "../components/replay-import";
import { setLanguage } from "../i18n";


beforeEach(async () => {
  await setLanguage("zh-CN");
  vi.restoreAllMocks();
});


it("reports a saved replay that cannot be parsed without starting analysis", async () => {
  const onImported = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({
      replayId: "replay-id",
      parseErrorCode: "INVALID_REPLAY_DATA",
    }), { status: 200 })),
  );

  render(<ReplayImport onImported={onImported} />);
  await userEvent.upload(screen.getByLabelText("牌谱文件"), new File(["{}"], "bad.json", { type: "application/json" }));
  await userEvent.click(screen.getByRole("button", { name: "导入文件" }));

  expect(await screen.findByText("牌谱已保存，但内容无法解析；请检查文件格式。")).toBeInTheDocument();
  expect(onImported).not.toHaveBeenCalled();
});
