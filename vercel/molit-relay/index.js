const crypto = require("node:crypto");

const TRADE_UPSTREAM =
  "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/" +
  "getRTMSDataSvcAptTradeDev";
const BUILDING_UPSTREAM =
  "https://apis.data.go.kr/1613000/BldRgstService_v2";
const BUILDING_OPERATIONS = new Set([
  "getBrRecapTitleInfo",
  "getBrTitleInfo",
]);

const SEOUL_GU_CODES = new Set([
  "11110", "11140", "11170", "11200", "11215",
  "11230", "11260", "11290", "11305", "11320",
  "11350", "11380", "11410", "11440", "11470",
  "11500", "11530", "11545", "11560", "11590",
  "11620", "11650", "11680", "11710", "11740",
]);

function safeEqual(left, right) {
  const leftBuffer = Buffer.from(left || "", "utf8");
  const rightBuffer = Buffer.from(right || "", "utf8");
  return (
    leftBuffer.length === rightBuffer.length &&
    crypto.timingSafeEqual(leftBuffer, rightBuffer)
  );
}

function readQueryValue(value) {
  return Array.isArray(value) ? value[0] : value;
}

function buildTradeUrl(query, apiKey) {
  const lawdCd = readQueryValue(query.LAWD_CD);
  const dealYmd = readQueryValue(query.DEAL_YMD);
  const pageNo = readQueryValue(query.pageNo) || "1";
  const numOfRows = readQueryValue(query.numOfRows) || "100";

  if (!SEOUL_GU_CODES.has(lawdCd || "") || !/^\d{6}$/.test(dealYmd || "")) {
    return null;
  }
  if (!/^\d{1,5}$/.test(String(pageNo)) || !/^\d{1,4}$/.test(String(numOfRows))) {
    return null;
  }

  const upstream = new URL(TRADE_UPSTREAM);
  upstream.searchParams.set("serviceKey", apiKey);
  upstream.searchParams.set("LAWD_CD", lawdCd);
  upstream.searchParams.set("DEAL_YMD", dealYmd);
  upstream.searchParams.set("pageNo", String(pageNo));
  upstream.searchParams.set("numOfRows", String(numOfRows));
  return upstream;
}

function buildBuildingUrl(query, apiKey) {
  const operation = readQueryValue(query.operation);
  const sigunguCd = readQueryValue(query.sigunguCd);
  const bjdongCd = readQueryValue(query.bjdongCd);
  const platGbCd = readQueryValue(query.platGbCd);
  const bun = readQueryValue(query.bun);
  const ji = readQueryValue(query.ji);
  const pageNo = readQueryValue(query.pageNo) || "1";
  const numOfRows = readQueryValue(query.numOfRows) || "100";

  if (
    !BUILDING_OPERATIONS.has(operation || "") ||
    !SEOUL_GU_CODES.has(sigunguCd || "") ||
    !/^\d{5}$/.test(bjdongCd || "") ||
    !/^[01]$/.test(platGbCd || "") ||
    !/^\d{4}$/.test(bun || "") ||
    !/^\d{4}$/.test(ji || "")
  ) {
    return null;
  }
  if (!/^\d{1,5}$/.test(String(pageNo)) || !/^\d{1,4}$/.test(String(numOfRows))) {
    return null;
  }

  const upstream = new URL(`${BUILDING_UPSTREAM}/${operation}`);
  upstream.searchParams.set("serviceKey", apiKey);
  upstream.searchParams.set("sigunguCd", sigunguCd);
  upstream.searchParams.set("bjdongCd", bjdongCd);
  upstream.searchParams.set("platGbCd", platGbCd);
  upstream.searchParams.set("bun", bun);
  upstream.searchParams.set("ji", ji);
  upstream.searchParams.set("pageNo", String(pageNo));
  upstream.searchParams.set("numOfRows", String(numOfRows));
  return upstream;
}

module.exports = async function handler(request, response) {
  response.setHeader("Cache-Control", "no-store");

  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ error: "method_not_allowed" });
  }

  const apiKey = process.env.MOLIT_API_KEY || "";
  const authorization = request.headers.authorization || "";
  const expectedAuthorization = `Bearer ${apiKey}`;

  if (!apiKey || !safeEqual(authorization, expectedAuthorization)) {
    return response.status(401).json({ error: "unauthorized" });
  }

  const service = readQueryValue(request.query.service) || "apartment-trade";
  let upstream;
  if (service === "apartment-trade") {
    upstream = buildTradeUrl(request.query, apiKey);
  } else if (service === "building-register") {
    upstream = buildBuildingUrl(request.query, apiKey);
  } else {
    return response.status(400).json({ error: "invalid_service" });
  }

  if (!upstream) {
    return response.status(400).json({ error: "invalid_query" });
  }

  try {
    const upstreamResponse = await fetch(upstream, {
      headers: { Accept: "application/xml, text/xml;q=0.9" },
      signal: AbortSignal.timeout(25000),
    });
    const body = await upstreamResponse.text();

    response.status(upstreamResponse.status);
    response.setHeader(
      "Content-Type",
      upstreamResponse.headers.get("content-type") ||
        "application/xml; charset=utf-8"
    );
    return response.send(body);
  } catch (error) {
    const reason =
      error && error.name === "TimeoutError"
        ? "upstream_timeout"
        : "upstream_unavailable";
    return response.status(502).json({ error: reason });
  }
};
