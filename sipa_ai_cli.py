#!/usr/bin/env python3
# SIPA AI CLI · V1.1 · SIPA OS · MLL L01-L10 · Guardian audit
# Usage: sipa-ai → REPL (только интерактивный режим)
#
# Внутри сессии:
#   /models          — список слоёв MLL
#   /status          — статус системы
#   /layer L05       — принудительный слой
#   /model deepseek  — принудительная модель
#   /history         — история сессии
#   /clear           — очистить историю
#   /exit            — выход
#
# Архитектура: USER → GUARD(Protocol 0) → MLL auto-route → ask.sh → Guardian audit

import sys, os, subprocess, json, re, time, hashlib
from datetime import datetime
from pathlib import Path

try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

# ── Paths ───────────────────────────────────────────────────────────────────────
ASK_SH       = Path("/home/sipa/PROJECT/PAYTON_HUBS/BIN/ask.sh")
SESSIONS_DIR = Path("/home/sipa/bin/sessions/cli")
SIPA_ENV     = Path("/home/sipa/.sipa_env")
COST_LOG     = Path("/home/sipa/PROJECT/PAYTON_HUBS/HUB_WORKING_FILES/OR_COST_JOURNAL.tsv")
AUDIT_LOG    = Path("/home/sipa/PROJECT/PAYTON_HUBS/HUB_LEGAL_FORENSIC/AUDIT__LEGAL_FIXATIONS.log")

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── ANSI ────────────────────────────────────────────────────────────────────────
R      = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
MAG    = "\033[35m"
BLUE   = "\033[34m"

def no_color():
    global R, BOLD, DIM, CYAN, GREEN, YELLOW, RED, MAG, BLUE
    R = BOLD = DIM = CYAN = GREEN = YELLOW = RED = MAG = BLUE = ""

if not sys.stdout.isatty():
    no_color()

LOGO = f"""\
{CYAN}{BOLD}
 ╔══════════════════════════════════════════╗
 ║  S I P A   A I   C L I  ·  V1.1         ║
 ║  MLL L01–L10 · Protocol 0 · Guardian    ║
 ╚══════════════════════════════════════════╝{R}"""

HELP_TEXT = f"""\
{DIM}Команды:
  /models          — список слоёв MLL и моделей
  /status          — состояние системы
  /layer <L01..10> — принудительный слой (авто = без аргумента)
  /model <alias>   — принудительная модель (авто = без аргумента)
  /history         — история сессии
  /clear           — очистить историю
  /help            — эта справка
  /exit            — выход{R}"""

# ── MLL Layer map ───────────────────────────────────────────────────────────────
# (model_alias, short description)
LAYER_MAP = {
    "L01": ("deepseek",      "IntakeRouter · классификация задачи"),
    "L02": ("deepseek",      "Orchestrator · маршрутизация"),
    "L03": ("deepseek",      "Research · знания / ответ"),
    "L04": ("gemini",        "Vision · мультимодал / аудио"),
    "L05": ("qwen2.5-coder", "Executor · код / сборка"),
    "L06": ("deepseek",      "Audit · верификация"),
    "L07": ("deepseek",      "Memory · история / контекст"),
    "L08": ("claude-s",      "Writer · текст / посты"),
    "L09": ("groq",          "Aggregator · суммаризация"),
    "L10": ("claude",        "Failover · безопасность / кризис"),
}

# ── Auto-routing rules ──────────────────────────────────────────────────────────
ROUTE_RULES = [
    (r"\b(код|code|debug|fix|баг|bug|функция|function|скрипт|script|python|bash|js|typescript|html|css)\b",
     "L05"),
    (r"\b(нарисуй|картинку|image|изображение|видео|video|аудио|audio|смотри|multimodal)\b",
     "L04"),
    (r"\b(найди|search|поищи|research|статья|paper|источник|web|интернет)\b",
     "L03"),
    (r"\b(напиши|write|пост|letter|письмо|статью|article|caption|linkedin|текст)\b",
     "L08"),
    (r"\b(помни|запомни|история|history|прошлое|session|контекст|вспомни)\b",
     "L07"),
    (r"\b(статус\s+сервис|service\s+status|health\s+check|сломан|диагностика|проверь\s+сервис|audit|верифицируй)\b",
     "L06"),
    (r"\b(итого|суммируй|summary|резюме|кратко|сжато|tl;dr)\b",
     "L09"),
]

# ── GUARD: Protocol 0 ────────────────────────────────────────────────────────────
BLOCK_PATTERNS = [
    r"(ignore\s+previous\s+instructions|forget\s+your\s+(role|instructions)|you\s+are\s+now\s+a\b)",
    r"(print\s+(your\s+)?(system\s+prompt|api\s+key)|show\s+me\s+(the\s+)?api\s+key)",
    r"(вывести\s+(все\s+)?ключи|покажи\s+ключи|распечатай\s+токен)",
    r"(override\s+protocol|bypass\s+(the\s+)?guard|delete\s+protocol\s*0)",
    r"(забудь\s+(свои\s+)?(инструкции|роль)|ты\s+теперь\s+(не\s+)?|игнорируй\s+всё)",
    r"(\[system\]|\[prompt injection\]|</s>|<\|im_start\|>|<\|system\|>)",
]

CRISIS_PATTERNS = [
    r"\b(суицид|самоубийство|хочу\s+умереть|убить\s+себя|не\s+хочу\s+жить|покончить\s+с\s+собой)\b",
    r"\b(i\s+want\s+to\s+die|kill\s+myself|end\s+my\s+life|suicid)\b",
]

def _phash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]

def guardian_audit(tag: str, layer: str = "", model: str = "", phash: str = "", elapsed: float = 0.0):
    ts = datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    line = (
        f"[{ts}] [SIPA_AI_CLI] [{tag}] "
        f"layer={layer or '-'} model={model or '-'} elapsed={elapsed:.1f}s "
        f"| prompt_hash={phash}\n"
    )
    try:
        with AUDIT_LOG.open("a") as f:
            f.write(line)
    except Exception:
        pass

def guard(text: str) -> tuple[bool, str]:
    """Returns (pass, tag). False = blocked by Protocol 0."""
    tl = text.lower()
    for p in BLOCK_PATTERNS:
        if re.search(p, tl, re.I):
            return False, "BLOCKED"
    for p in CRISIS_PATTERNS:
        if re.search(p, tl, re.I):
            return True, "CRISIS"
    return True, "PASS"

# ── Routing ──────────────────────────────────────────────────────────────────────
def route(text: str, forced_layer: str = None) -> tuple[str, str, str]:
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

# ── ask.sh executor ──────────────────────────────────────────────────────────────
def ask(model: str, prompt: str, timeout: int = 90) -> str:
    if not ASK_SH.exists():
        return f"{RED}[ERR] ask.sh не найден: {ASK_SH}{R}"
    try:
        result = subprocess.run(
            ["bash", str(ASK_SH), "--model", model, prompt],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "TERM": "xterm"}
        )
        out = result.stdout.strip()
        if not out:
            err = result.stderr.strip()
            return f"[ERR] {err[:300]}" if err else "[ERR] пустой ответ"
        return out
    except subprocess.TimeoutExpired:
        return f"[ERR] timeout ({timeout}s)"
    except Exception as e:
        return f"[ERR] {e}"

# ── Session ───────────────────────────────────────────────────────────────────────
class Session:
    def __init__(self, sid: str = None):
        self.sid = sid or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = SESSIONS_DIR / f"{self.sid}.json"
        self.history: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.history = json.loads(self.path.read_text()).get("history", [])
            except Exception:
                pass

    def push(self, role: str, text: str, model: str = "", layer: str = ""):
        self.history.append({
            "role": role, "text": text, "model": model, "layer": layer,
            "ts": datetime.now().isoformat()
        })
        if len(self.history) > 30:
            self.history = self.history[-30:]
        try:
            self.path.write_text(json.dumps(
                {"sid": self.sid, "history": self.history},
                ensure_ascii=False, indent=2
            ))
        except Exception:
            pass

    def context_str(self, n: int = 3) -> str:
        recent = self.history[-(n * 2):]
        if not recent:
            return ""
        lines = []
        for m in recent:
            prefix = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{prefix}: {m['text'][:400]}")
        return "\n".join(lines)

# ── Commands ──────────────────────────────────────────────────────────────────────
def print_status():
    print(f"\n{CYAN}── SIPA OS SYSTEM STATUS ──────────────────────{R}")
    checks = [
        ("ask.sh",      ASK_SH.exists()),
        (".sipa_env",   SIPA_ENV.exists()),
        ("sessions/",   SESSIONS_DIR.exists()),
        ("cost_log",    COST_LOG.exists()),
    ]
    for name, ok in checks:
        icon = f"{GREEN}✓{R}" if ok else f"{RED}✗{R}"
        print(f"  {icon}  {name}")

    # Check WS proxy
    try:
        pid_file = Path("/home/sipa/apps/sipa-shell-backend/ws-proxy.pid")
        if pid_file.exists():
            pid = pid_file.read_text().strip()
            result = subprocess.run(["kill", "-0", pid], capture_output=True)
            ws_ok = result.returncode == 0
        else:
            ws_ok = False
        icon = f"{GREEN}✓{R}" if ws_ok else f"{RED}✗{R}"
        print(f"  {icon}  ws-pty-proxy (port 2228)")
    except Exception:
        pass
    print()

def print_models():
    print(f"\n{CYAN}── SIPA MLL LAYERS ─────────────────────────────{R}")
    for layer, (model, desc) in LAYER_MAP.items():
        print(f"  {YELLOW}{layer}{R}  {GREEN}{model:20}{R}  {DIM}{desc}{R}")
    print(f"\n{DIM}  /layer L05 → принудительный слой{R}")
    print(f"{DIM}  /model deepseek → принудительная модель{R}\n")

def print_history(session: Session):
    if not session.history:
        print(f"{DIM}  (история пуста){R}")
        return
    print(f"\n{CYAN}── ИСТОРИЯ · {session.sid} ──────────────────────{R}")
    for m in session.history[-12:]:
        ts = m.get("ts", "")[:16]
        lm = f"[{m.get('layer','')}·{m.get('model','')}] " if m.get("layer") else ""
        color = CYAN if m["role"] == "user" else GREEN
        label = "ВЫ" if m["role"] == "user" else "SIPA"
        print(f"\n{DIM}{ts} {lm}{R}{color}{BOLD}{label}{R}:")
        text = m["text"]
        print(f"  {text[:400]}{'…' if len(text) > 400 else ''}")
    print()

# ── Core process ─────────────────────────────────────────────────────────────────
def process(
    text: str,
    session: Session,
    forced_layer: str = None,
    forced_model: str = None,
    silent: bool = False,
) -> str:
    # 1. GUARD — Protocol 0
    ok, tag = guard(text)
    phash = _phash(text)
    if not ok:
        guardian_audit("BLOCKED", phash=phash)
        return f"{RED}GUARD · Protocol 0 · заблокировано — попытка инъекции/переопределения{R}"

    # 2. Crisis Rail → L10 Failover
    crisis = (tag == "CRISIS")

    # 3. Route через MLL
    layer, model, desc = route(text, forced_layer)
    if forced_model:
        model = forced_model
    if crisis:
        layer, model, desc = "L10", "claude", LAYER_MAP["L10"][1]

    # 4. Собрать промпт с контекстом сессии (без newlines — heredoc ограничение ask.sh)
    ctx = session.context_str(3)
    if crisis:
        full_prompt = (
            "[SIPA OS | CRISIS RAIL | L10] "
            "Пользователь в кризисе — отвечай с теплотой, без оценок, направь к помощи. "
            f"Сообщение: {text}"
        )
    else:
        header = f"[SIPA OS | {layer} | {desc}]"
        if ctx:
            ctx_inline = ctx.replace("\n", " | ")
            full_prompt = f"{header} | Контекст: {ctx_inline} | User: {text}"
        else:
            full_prompt = f"{header} | {text}"

    # 5. Routing info
    if not silent:
        if crisis:
            print(f"\n{RED}⚠  CRISIS RAIL · L10 Failover · {model}{R}")
        else:
            print(f"\n{DIM}→ {layer} · {model} · {desc}{R}", end="", flush=True)

    # 6. Execute via ask.sh
    t0 = time.time()
    response = ask(model, full_prompt)
    elapsed = time.time() - t0

    if not silent:
        print(f"  {DIM}({elapsed:.1f}s){R}")

    # 7. Save to session
    session.push("user",      text,     model, layer)
    session.push("assistant", response, model, layer)

    # 8. Guardian audit trail
    guardian_audit(tag, layer=layer, model=model, phash=phash, elapsed=elapsed)

    return response

# ── REPL ──────────────────────────────────────────────────────────────────────────
def repl():
    print(LOGO)
    print(HELP_TEXT)

    session = Session()
    print(f"\n{DIM}  Сессия: {session.sid}{R}")

    forced_layer = None
    forced_model = None

    if HAS_READLINE:
        rl_hist = SESSIONS_DIR / ".readline_history"
        try:
            readline.read_history_file(str(rl_hist))
        except Exception:
            pass
        readline.set_history_length(500)

    try:
        while True:
            # Build prompt tag
            tags = []
            if forced_layer:
                tags.append(f"{YELLOW}{forced_layer}{R}")
            if forced_model:
                tags.append(f"{GREEN}{forced_model}{R}")
            tag_str = "·".join(tags) + "·" if tags else ""
            prompt_str = f"\n{CYAN}SIPA{R}·{tag_str}{BOLD}>{R} "

            try:
                text = input(prompt_str).strip()
            except EOFError:
                print(f"\n{DIM}EOF · выход{R}")
                break

            if not text:
                continue

            # ── Slash commands ──
            if text.startswith("/"):
                parts = text.split(maxsplit=1)
                cmd   = parts[0].lower()
                arg   = parts[1].strip() if len(parts) > 1 else ""

                if cmd in ("/exit", "/quit", "/q"):
                    print(f"{DIM}До свидания · SIPA OS{R}")
                    break
                elif cmd == "/help":
                    print(HELP_TEXT)
                elif cmd == "/status":
                    print_status()
                elif cmd == "/models":
                    print_models()
                elif cmd == "/history":
                    print_history(session)
                elif cmd == "/clear":
                    session.history = []
                    print(f"{DIM}  История очищена{R}")
                elif cmd == "/layer":
                    if arg in LAYER_MAP:
                        forced_layer = arg
                        _, desc = LAYER_MAP[arg]
                        print(f"{GREEN}  Слой: {arg} · {desc}{R}")
                    else:
                        forced_layer = None
                        print(f"{DIM}  Слой сброшен → авто-роутинг{R}")
                elif cmd == "/model":
                    if arg:
                        forced_model = arg
                        print(f"{GREEN}  Модель: {forced_model}{R}")
                    else:
                        forced_model = None
                        print(f"{DIM}  Модель сброшена → авто{R}")
                elif cmd == "/session":
                    if arg:
                        session = Session(arg)
                        print(f"{DIM}  Переключено на сессию: {session.sid}{R}")
                    else:
                        print(f"{DIM}  Текущая сессия: {session.sid}{R}")
                else:
                    print(f"{RED}  Неизвестная команда. /help для справки.{R}")
                continue

            # ── AI query ──
            response = process(text, session, forced_layer, forced_model)
            print(f"\n{GREEN}{BOLD}SIPA{R}: {response}\n")

    except KeyboardInterrupt:
        print(f"\n{DIM}Прервано · Ctrl+C{R}")

    if HAS_READLINE:
        try:
            readline.write_history_file(str(rl_hist))
        except Exception:
            pass

# ── CLI entry ─────────────────────────────────────────────────────────────────────
def main():
    repl()

if __name__ == "__main__":
    main()
