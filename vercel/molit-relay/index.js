const crypto = require("node:crypto");

const UPSTREAM_URL =
  "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/" +
  "getRTMSDataSvcAptTradeDev";

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

  const lawdCd = readQueryValue(request.query.LAWD_CD);
  const dealYmd = readQueryValue(request.query.DEAL_YMD);
  const pageNo = readQueryValue(request.query.pageNo) || "1";
  const numOfRows = readQueryValue(request.query.numOfRows) || "1000";

  if (!/^\d{5}$/.test(lawdCd || "") || !/^\d{6}$/.test(dealYmd || "")) {
    return response.status(400).json({ error: "invalid_query" });
  }
  if (!/^\d{1,5}$/.test(String(pageNo)) || !/^\d{1,5}$/.test(String(numOfRows))) {
    return response.status(400).json({ error: "invalid_pagination" });
  }

  const upstream = new URL(UPSTREAM_URL);
  upstream.searchParams.set("serviceKey", apiKey);
  upstream.searchParams.set("LAWD_CD", lawdCd);
  upstream.searchParams.set("DEAL_YMD", dealYmd);
  upstream.searchParams.set("pageNo", String(pageNo));
  upstream.searchParams.set("numOfRows", String(numOfRows));

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
    const reason = error && error.name === "TimeoutError" ? "upstream_timeout" : "upstream_unavailable";
    return response.status(502).json({ error: reason });
  }
};
