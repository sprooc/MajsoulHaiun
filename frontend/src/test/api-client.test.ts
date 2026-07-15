import { beforeEach, expect, it, vi } from "vitest";
import { listAnalyses } from "../api/client";


beforeEach(() => {
  vi.restoreAllMocks();
});


it("requests and returns a paginated administrator analysis list", async () => {
  const page = { items: [], nextOffset: 35 };
  const controller = new AbortController();
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);

  await expect(listAnalyses({ offset: 25, limit: 10, signal: controller.signal })).resolves.toEqual(page);
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/analyses?offset=25&limit=10",
    { signal: controller.signal },
  );
});
