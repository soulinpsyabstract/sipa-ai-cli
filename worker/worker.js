// SIPA AI CLI · Cloudflare Worker · V1.1
// Domain: sipa-ai.sipa-os.org
// Routes: /ask · /health · /models · /mcp · /session/* · /webhook
// Backend: sipa-ai API on SERVER (via CF Tunnel or direct)

const BACKEND = "http://127.0.0.1:5003"; // overridden by SIPA_AI_BACKEND env var

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const backend = env.SIPA_AI_BACKEND || BACKEND;

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
      });
    }

    const addCors = (r) => {
      const headers = new Headers(r.headers);
      headers.set("Access-Control-Allow-Origin", "*");
      return new Response(r.body, { status: r.status, headers });
    };

    // Proxy to backend
    const proxyUrl = backend + path + url.search;
    try {
      const backendResp = await fetch(proxyUrl, {
        method: request.method,
        headers: {
          "Content-Type": request.headers.get("Content-Type") || "application/json",
        },
        body: ["POST", "PUT", "PATCH"].includes(request.method)
          ? await request.text()
          : undefined,
      });
      return addCors(backendResp);
    } catch (e) {
      return addCors(new Response(JSON.stringify({
        error: "sipa-ai backend unavailable",
        detail: e.message,
      }), { status: 503, headers: { "Content-Type": "application/json" } }));
    }
  },
};
