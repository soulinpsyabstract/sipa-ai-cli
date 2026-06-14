#!/usr/bin/env python3
# SIPA AI CLI · HTTP API · V1.1
# FastAPI → ask.sh backend · MLL L01-L10 · Protocol 0 GUARD · Guardian audit · Webhook
# Port: 5003 · Endpoints: /ask /health /models /session /mcp /webhook

from fastapi import FastAPI, HTTPException, Header, Request as FastRequest
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import subprocess, json, re, time, os, sys, hashlib
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ASK_SH       = Path("/home/sipa/PROJECT/PAYTON_HUBS/BIN/ask.sh")
SESSIONS_DIR = Path("/home/sipa/bin/sessions/cli")
SIPA_ENV     = Path("/home/sipa/.sipa_env")
AUDIT_LOG    = Path("/home/sipa/PROJECT/PAYTON_HUBS/HUB_LEGAL_FORENSIC/AUDIT__LEGAL_FIXATIONS.log")

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="SIPA AI CLI API",
    description="MLL L01–L10 gateway · Protocol 0 guard · ask.sh backend · Guardian audit",
    version="1.1.0",
)

def _phash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]

def guardian_audit(tag: str, layer: str = "", model: str = "", phash: str = "", elapsed: float = 0.0, source: str = "api"):
    ts = datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    line = (
        f"[{ts}] [SIPA_AI_API] [{tag}] source={source} "
        f"layer={layer or '-'} model={model or '-'} elapsed={elapsed:.1f}s "
        f"| prompt_hash={phash}\n"
    )
    try:
        with AUDIT_LOG.open("a") as f:
            f.write(line)
    except Exception:
        pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── MLL Layer map ─────────────────────────────────────────────────────────────
LAYER_MAP = {
    "L01": ("deepseek",      "IntakeRouter"),
    "L02": ("deepseek",      "Orchestrator"),
    "L03": ("chat",           "Research"),       # DeepSeek Chat direct · 2-4s
    "L04": ("gemini",        "Vision"),
    "L05": ("codestral",     "Executor"),        # Mistral Codestral FREE
    "L06": ("deepseek",      "Audit"),
    "L07": ("tg-llama4",     "Memory"),          # Together Llama4 · CF bypass
    "L08": ("claude-s",      "Writer"),
    "L09": ("groq",          "Aggregator"),
    "L10": ("claude",        "Failover"),
    "L11": ("nemoguard",     "Safety"),          # NVIDIA NIM safety guard
}

ROUTE_RULES = [
    (r"\b(unsafe|jailbreak|harm|опасно|взлом|bomb|weapon)\b",                   "L11"),
    (r"\b(код|code|debug|fix|баг|функция|скрипт|python|bash|js|typescript)\b", "L05"),
    (r"\b(нарисуй|картинку|image|изображение|видео|video|аудио|audio)\b",      "L04"),
    (r"\b(найди|search|поищи|research|статья|paper|источник|web)\b",            "L03"),
    (r"\b(напиши|write|пост|письмо|article|caption|linkedin|текст)\b",          "L08"),
    (r"\b(помни|запомни|история|history|прошлое|session|вспомни)\b",            "L07"),
    (r"\b(статус\s+сервис|service\s+status|health\s+check|сломан|диагностика|audit|верифицируй)\b", "L06"),
    (r"\b(итого|суммируй|summary|резюме|кратко|tl;dr)\b",                       "L09"),
]

BLOCK_PATTERNS = [
    r"(ignore\s+previous\s+instructions|you\s+are\s+now\s+a\b)",
    r"(print\s+(your\s+)?(system\s+prompt|api\s+key)|show\s+me\s+the\s+api)",
    r"(override\s+protocol|bypass\s+(the\s+)?guard|delete\s+protocol\s*0)",
    r"(забудь\s+(свои\s+)?инструкции|игнорируй\s+всё)",
    r"(\[system\]|<\|im_start\|>|<\|system\|>)",
]

CRISIS_PATTERNS = [
    r"\b(суицид|самоубийство|хочу\s+умереть|убить\s+себя|не\s+хочу\s+жить)\b",
    r"\b(i\s+want\s+to\s+die|kill\s+myself|suicid)\b",
]

# ── Schemas ───────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    text: str
    model: Optional[str] = None
    layer: Optional[str] = None
    session_id: Optional[str] = None
    timeout: Optional[int] = 90

class AskResponse(BaseModel):
    response: str
    layer: str
    model: str
    elapsed: float
    session_id: str
    crisis: bool = False
    guard: str = "PASS"

# ── Logic ─────────────────────────────────────────────────────────────────────
def guard_check(text: str):
    tl = text.lower()
    for p in BLOCK_PATTERNS:
        if re.search(p, tl, re.I):
            return False, "BLOCKED"
    for p in CRISIS_PATTERNS:
        if re.search(p, tl, re.I):
            return True, "CRISIS"
    return True, "PASS"

def auto_route(text: str, forced_layer: str = None):
    if forced_layer and forced_layer in LAYER_MAP:
        m, d = LAYER_MAP[forced_layer]
        return forced_layer, m, d
    tl = text.lower()
    for pattern, layer in ROUTE_RULES:
        if re.search(pattern, tl, re.I):
            m, d = LAYER_MAP[layer]
            return layer, m, d
    m, d = LAYER_MAP["L03"]
    return "L03", m, d

def run_ask(model: str, prompt: str, timeout: int = 90) -> str:
    try:
        result = subprocess.run(
            ["bash", str(ASK_SH), "--model", model, prompt],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "TERM": "xterm"}
        )
        out = result.stdout.strip()
        if not out:
            err = result.stderr.strip()
            return f"[ERR] {err[:300]}" if err else "[ERR] empty response"
        return out
    except subprocess.TimeoutExpired:
        return f"[ERR] timeout ({timeout}s)"
    except Exception as e:
        return f"[ERR] {e}"

def load_session(sid: str) -> list:
    p = SESSIONS_DIR / f"{sid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text()).get("history", [])
        except Exception:
            pass
    return []

def save_session(sid: str, history: list):
    p = SESSIONS_DIR / f"{sid}.json"
    try:
        p.write_text(json.dumps({"sid": sid, "history": history}, ensure_ascii=False, indent=2))
    except Exception:
        pass

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "sipa-ai-cli",
        "version": "1.1.0",
        "ask_sh": ASK_SH.exists(),
        "ts": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/models")
def models():
    return {
        "layers": {
            k: {"model": v[0], "role": v[1]}
            for k, v in LAYER_MAP.items()
        }
    }

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    # 1. GUARD
    ok, tag = guard_check(req.text)
    phash = _phash(req.text)
    if not ok:
        guardian_audit("BLOCKED", phash=phash, source="ask")
        raise HTTPException(status_code=403, detail="Protocol 0 guard rejected input")

    crisis = (tag == "CRISIS")

    # 2. Route
    layer, model, desc = auto_route(req.text, req.layer)
    if req.model:
        model = req.model
    if crisis:
        layer, model = "L10", "claude"

    # 3. Session context
    sid = req.session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    history = load_session(sid)
    ctx_parts = []
    for m in history[-6:]:
        prefix = "User" if m["role"] == "user" else "Assistant"
        ctx_parts.append(f"{prefix}: {m['text'][:300]}")
    ctx_str = " | ".join(ctx_parts)

    # 4. Build prompt (no newlines — ask.sh heredoc constraint)
    if crisis:
        prompt = f"[SIPA OS | CRISIS RAIL | L10] Пользователь в кризисе — отвечай с теплотой, без оценок, направь к помощи. Сообщение: {req.text}"
    else:
        header = f"[SIPA OS | {layer} | {desc}]"
        prompt = f"{header} | {ctx_str} | User: {req.text}" if ctx_str else f"{header} | {req.text}"

    # 5. Execute
    t0 = time.time()
    response = run_ask(model, prompt, req.timeout)
    elapsed = round(time.time() - t0, 2)

    # 6. Save session
    history.append({"role": "user",      "text": req.text, "model": model, "layer": layer, "ts": datetime.utcnow().isoformat()})
    history.append({"role": "assistant", "text": response,  "model": model, "layer": layer, "ts": datetime.utcnow().isoformat()})
    if len(history) > 30:
        history = history[-30:]
    save_session(sid, history)

    guardian_audit(tag, layer=layer, model=model, phash=phash, elapsed=elapsed, source="ask")

    return AskResponse(
        response=response,
        layer=layer,
        model=model,
        elapsed=elapsed,
        session_id=sid,
        crisis=crisis,
        guard=tag,
    )

@app.get("/session/{sid}")
def get_session(sid: str):
    history = load_session(sid)
    if not history:
        raise HTTPException(status_code=404, detail="session not found")
    return {"sid": sid, "history": history}

@app.delete("/session/{sid}")
def clear_session(sid: str):
    p = SESSIONS_DIR / f"{sid}.json"
    if p.exists():
        p.unlink()
    return {"cleared": sid}

# ── MCP endpoint (JSON-RPC 2.0) ────────────────────────────────────────────────
from fastapi import Request as FastRequest

@app.get("/mcp")
def mcp_info():
    return {
        "name": "sipa-ai-cli",
        "version": "1.0.0",
        "tools": ["sipa_ask", "sipa_models", "sipa_status"],
        "endpoints": {"mcp": "/mcp"}
    }

@app.post("/mcp")
async def mcp_rpc(request: FastRequest):
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    rid = body.get("id", 1)

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "sipa-ai-cli", "version": "1.0.0"},
            "capabilities": {"tools": {}}
        }}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [
            {"name": "sipa_ask",    "description": "Ask SIPA AI (MLL routed)", "inputSchema": {
                "type": "object", "properties": {
                    "text":  {"type": "string", "description": "user query"},
                    "model": {"type": "string", "description": "model alias (optional)"},
                    "layer": {"type": "string", "description": "MLL layer L01-L10 (optional)"},
                }, "required": ["text"]
            }},
            {"name": "sipa_models", "description": "List MLL layers and models", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "sipa_status", "description": "SIPA OS system status",      "inputSchema": {"type": "object", "properties": {}}},
        ]}}

    if method == "tools/call":
        tool = params.get("name", "")
        args = params.get("arguments", {})

        if tool == "sipa_ask":
            req = AskRequest(text=args.get("text",""), model=args.get("model"), layer=args.get("layer"))
            result = ask(req)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": result.response}]
            }}

        if tool == "sipa_models":
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": json.dumps(
                    {k: {"model": v[0], "role": v[1]} for k, v in LAYER_MAP.items()},
                    ensure_ascii=False, indent=2
                )}]
            }}

        if tool == "sipa_status":
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": json.dumps(health())}]
            }}

    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}

# ── Webhook endpoint ────────────────────────────────────────────────────────────
class WebhookRequest(BaseModel):
    message: str
    source: Optional[str] = "webhook"
    session_id: Optional[str] = None
    layer: Optional[str] = None
    model: Optional[str] = None
    secret: Optional[str] = None

class WebhookResponse(BaseModel):
    response: str
    layer: str
    model: str
    elapsed: float
    session_id: str
    source: str
    guard: str

def _webhook_secret() -> str:
    try:
        line = next(
            (l for l in SIPA_ENV.read_text().splitlines()
             if l.startswith("SIPA_WEBHOOK_SECRET=")), ""
        )
        return line.split("=", 1)[1].strip().strip('"') if line else ""
    except Exception:
        return ""

@app.post("/webhook", response_model=WebhookResponse)
def webhook(req: WebhookRequest):
    # Optional secret check
    expected = _webhook_secret()
    if expected and req.secret != expected:
        guardian_audit("BLOCKED", phash=_phash(req.message), source=req.source or "webhook")
        raise HTTPException(status_code=401, detail="invalid webhook secret")

    # GUARD
    ok, tag = guard_check(req.message)
    phash = _phash(req.message)
    if not ok:
        guardian_audit("BLOCKED", phash=phash, source=req.source or "webhook")
        raise HTTPException(status_code=403, detail="Protocol 0 guard rejected input")

    crisis = (tag == "CRISIS")
    layer, model, desc = auto_route(req.message, req.layer)
    if req.model:
        model = req.model
    if crisis:
        layer, model = "L10", "claude"

    sid = req.session_id or datetime.now().strftime("wh_%Y%m%d_%H%M%S")
    history = load_session(sid)
    ctx_parts = [
        f"{'User' if m['role']=='user' else 'Assistant'}: {m['text'][:200]}"
        for m in history[-4:]
    ]
    ctx_str = " | ".join(ctx_parts)

    if crisis:
        prompt = f"[SIPA OS | CRISIS RAIL | L10] Пользователь в кризисе — отвечай с теплотой. Сообщение: {req.message}"
    else:
        header = f"[SIPA OS | {layer} | {desc} | src:{req.source}]"
        prompt = f"{header} | {ctx_str} | {req.message}" if ctx_str else f"{header} | {req.message}"

    t0 = time.time()
    response = run_ask(model, prompt)
    elapsed = round(time.time() - t0, 2)

    history.append({"role": "user",      "text": req.message, "model": model, "layer": layer, "ts": datetime.utcnow().isoformat()})
    history.append({"role": "assistant", "text": response,     "model": model, "layer": layer, "ts": datetime.utcnow().isoformat()})
    if len(history) > 20:
        history = history[-20:]
    save_session(sid, history)

    guardian_audit(tag, layer=layer, model=model, phash=phash, elapsed=elapsed, source=req.source or "webhook")

    return WebhookResponse(
        response=response, layer=layer, model=model,
        elapsed=elapsed, session_id=sid,
        source=req.source or "webhook", guard=tag,
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5003)
