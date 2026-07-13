import zhCommon from "../locales/zh-CN/common.json";
import zhSearch from "../locales/zh-CN/search.json";
import zhAnalysis from "../locales/zh-CN/analysis.json";
import enCommon from "../locales/en/common.json";
import enSearch from "../locales/en/search.json";
import enAnalysis from "../locales/en/analysis.json";


function keyTree(value: unknown): unknown {
  if (Array.isArray(value) || value === null || typeof value !== "object") return true;
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, keyTree(child)]));
}


it("keeps Chinese and English translation key trees identical", () => {
  expect(keyTree({ common: zhCommon, search: zhSearch, analysis: zhAnalysis })).toEqual(
    keyTree({ common: enCommon, search: enSearch, analysis: enAnalysis }),
  );
});
