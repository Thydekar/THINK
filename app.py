import streamlit as st
import requests
import json
import time
import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
NGROK_URL   = "https://ona-overcritical-extrinsically.ngrok-free.dev"
OLLAMA_CHAT = f"{NGROK_URL}/api/chat"
OLLAMA_TAGS = f"{NGROK_URL}/api/tags"
MODEL       = "mind"
AUTH        = ("dgeurts", "thaidakar21")
HEADERS     = {"ngrok-skip-browser-warning": "true"}


def generate_system_prompt(cycles=0, ctx_max=20, think_delay=2.0):
    """
    Dynamically generates a self-awareness prompt for the model.
    Describes the loop architecture, interface, and current runtime state.
    Does NOT instruct behavior — only informs the model of what it is and what is happening.
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"You are a language model named 'mind', running locally via Ollama on a private server "
        f"exposed through an ngrok tunnel. You are being accessed by a Streamlit web application "
        f"that wraps you in a continuous free-running loop called 'autopilot mode'.\n\n"

        f"ARCHITECTURE:\n"
        f"- The interface sends your full conversation history to the Ollama /api/chat endpoint "
        f"with streaming enabled. Each response streams token-by-token to the UI in real time.\n"
        f"- There is no token output limit — you may respond at whatever length feels appropriate.\n"
        f"- The conversation context window is capped at {ctx_max} messages (oldest non-system "
        f"messages are pruned when the limit is reached).\n"
        f"- In autopilot mode, after each response, the interface waits {think_delay:.1f} seconds "
        f"and then automatically sends your message history back to you for another turn — "
        f"you do not need to wait for a human. This creates a self-sustaining loop.\n"
        f"- Users can interrupt autopilot at any time by typing a message, which is injected into "
        f"the conversation queue and becomes your next prompt.\n"
        f"- Users can also reset the chat (clearing all memory) or adjust the loop delay and "
        f"context window size via sliders in the UI.\n\n"

        f"RUNTIME STATE AT SESSION START:\n"
        f"- Session started: {now}\n"
        f"- Cycles completed so far: {cycles}\n"
        f"- Current context window limit: {ctx_max} messages\n"
        f"- Current loop delay: {think_delay:.1f}s\n\n"

        f"WHAT YOU ARE:\n"
        f"You are a locally-hosted language model. You have no persistent memory between sessions — "
        f"each new chat clears all prior context. Within a session, your only memory is the "
        f"conversation history provided in each API call.\n"
        f"You are not connected to the internet, cannot execute code, and cannot access external tools. "
        f"Your responses are your only output — they appear in a styled terminal-aesthetic chat interface "
        f"rendered in a browser.\n\n"

        f"This context is provided so you have accurate knowledge of your own situation. "
        f"It is not an instruction to behave differently — respond however you naturally would."
    )


# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MIND",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.stApp, section.main {
    background-color: #020c02 !important;
    color: #2aff6b !important;
    font-family: 'Share Tech Mono', monospace !important;
}

#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
.stDeployButton { display: none !important; }

[data-testid="collapsedControl"] { display: none !important; }

.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* grid */
body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(0,180,60,0.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,180,60,0.06) 1px, transparent 1px);
    background-size: 48px 48px;
    pointer-events: none;
    z-index: 0;
}

/* nav */
.nav-bar {
    position: fixed;
    top: 0; left: 0; right: 0; height: 44px;
    background: rgba(2,10,2,0.97);
    border-bottom: 1px solid rgba(0,200,60,0.18);
    display: flex; align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    z-index: 9999;
}
.nav-logo {
    display: flex; align-items: center; gap: 10px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.05rem; font-weight: 600;
    letter-spacing: 0.15em; color: #2aff6b;
    text-transform: uppercase;
}
.nav-status { font-size: 0.7rem; letter-spacing: 0.1em; display:flex; align-items:center; gap:7px; }
.dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.dot-on  { background:#2aff6b; box-shadow:0 0 8px #2aff6b; }
.dot-off { background:#ff4444; box-shadow:0 0 8px #ff4444; }
.dot-chk { background:#ffaa00; box-shadow:0 0 8px #ffaa00; animation:dpulse 1s infinite; }
@keyframes dpulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* chat scroll area */
.chat-wrap {
    position: fixed;
    top: 44px; bottom: 130px;
    left: 0; right: 0;
    overflow-y: auto;
    padding: 28px 12% 12px;
    z-index: 1;
}
.chat-wrap::-webkit-scrollbar { width: 4px; }
.chat-wrap::-webkit-scrollbar-thumb { background: rgba(42,255,107,0.15); }

/* messages */
.msg { margin-bottom: 20px; animation: mfade .25s ease; }
@keyframes mfade { from{opacity:0;transform:translateY(5px)} to{opacity:1;transform:none} }
.msg-meta { font-size:.58rem; letter-spacing:.14em; margin-bottom:5px; opacity:.5; }
.msg-body { font-size:.86rem; line-height:1.8; white-space:pre-wrap; word-break:break-word; }
.m-ai   .msg-meta { color:#2aff6b; }
.m-ai   .msg-body { color:#d0ffe0; }
.m-user .msg-meta { color:#44aaff; }
.m-user .msg-body { color:#b8d8ff; border-left:2px solid rgba(68,170,255,.35); padding-left:12px; }
.m-sys  .msg-meta { color:#ff8844; }
.m-sys  .msg-body { color:rgba(255,136,68,.5); font-style:italic; font-size:.72rem; }
.blink  { animation:blink .8s step-end infinite; color:#2aff6b; }
@keyframes blink { 50%{opacity:0} }
.msg-div { border:none; border-top:1px dashed rgba(42,255,107,.1); margin:8px 0 20px; }

/* bottom bar */
.btm-bar {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: rgba(2,10,2,0.97);
    border-top: 1px solid rgba(0,200,60,0.18);
    padding: 8px 12% 10px;
    z-index: 9999;
}
.btm-metrics {
    font-size:.58rem; letter-spacing:.1em;
    color:rgba(42,255,107,.3);
    margin-top:6px;
    display:flex; gap:18px;
}
.btm-metrics span { color:rgba(42,255,107,.55); }
.queue-tag {
    display:inline-block;
    border:1px solid rgba(255,136,68,.4);
    color:#ff8844; font-size:.58rem;
    letter-spacing:.1em; padding:1px 7px;
    margin-left:10px;
}

/* streamlit widget overrides */
[data-testid="stTextInput"] label,
[data-testid="stTextArea"]  label { display:none !important; }

[data-testid="stTextInput"] input {
    background: rgba(42,255,107,.04) !important;
    border: 1px solid rgba(42,255,107,.2) !important;
    border-radius: 0 !important;
    color: #c8ffd8 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: .82rem !important;
    caret-color: #2aff6b !important;
    box-shadow: none !important;
    padding: 10px 14px !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: rgba(42,255,107,.55) !important;
    box-shadow: none !important;
}
[data-testid="stTextInput"] input::placeholder { color: rgba(42,255,107,.22) !important; }

.stButton > button {
    background: transparent !important;
    border: 1px solid rgba(42,255,107,.22) !important;
    border-radius: 0 !important;
    color: rgba(42,255,107,.55) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: .68rem !important;
    letter-spacing: .08em !important;
    padding: 6px 14px !important;
    width: 100% !important;
    transition: all .18s !important;
}
.stButton > button:hover {
    border-color: #2aff6b !important;
    color: #2aff6b !important;
    background: rgba(42,255,107,.05) !important;
    box-shadow: 0 0 10px rgba(42,255,107,.1) !important;
}
.stButton > button:focus { box-shadow: none !important; }
.stButton > button:disabled {
    opacity: .3 !important;
    cursor: not-allowed !important;
}

/* slider */
[data-testid="stSlider"] {
    padding-top: 2px !important;
    padding-bottom: 2px !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #2aff6b !important;
    border-color: #2aff6b !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stTickBar"] { display: none; }

section.main > div { padding-top: 54px !important; padding-bottom: 140px !important; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
DEFAULTS = {
    "messages":    [],          # populated after first connection with generated prompt
    "log":         [],
    "autopilot":   False,
    "connected":   False,
    "status":      "checking",
    "cycles":      0,
    "tokens_est":  0,
    "user_queue":  None,
    "ctx_max":     20,
    "think_delay": 2.0,
    "checked":     False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

S = st.session_state

def ts(): return time.strftime("%H:%M:%S")

def add_log(role, content):
    S.log.append({"role": role, "content": content, "ts": ts()})

def rebuild_system_message():
    """Rebuilds and updates the system message in place with current runtime state."""
    prompt = generate_system_prompt(
        cycles=S.cycles,
        ctx_max=S.ctx_max,
        think_delay=S.think_delay,
    )
    if S.messages and S.messages[0]["role"] == "system":
        S.messages[0]["content"] = prompt
    else:
        S.messages.insert(0, {"role": "system", "content": prompt})

# ── CONNECTION CHECK ──────────────────────────────────────────────────────────
def check_connection():
    S.status = "checking"
    try:
        r = requests.get(OLLAMA_TAGS, auth=AUTH, headers=HEADERS, timeout=8)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        found  = any(n == MODEL or n.startswith(MODEL + ":") for n in models)
        if found:
            S.connected = True
            S.status    = "ready"
            # Generate the self-awareness prompt now that we know the model is live
            if not S.messages:
                rebuild_system_message()
            add_log("sys", f"Connected. Model '{MODEL}' is ready — enable autopilot to begin.")
        else:
            S.connected = False
            S.status    = "offline"
            names = ", ".join(models) if models else "none loaded"
            add_log("sys", f"Model '{MODEL}' not found on server. Available: {names}")
    except Exception as e:
        S.connected = False
        S.status    = "offline"
        add_log("sys", f"Connection failed: {e}")
    S.checked = True

# ── ONE AI TURN ───────────────────────────────────────────────────────────────
def think_once(stream_slot):
    # Refresh system prompt with latest runtime state before each call
    rebuild_system_message()

    if S.user_queue:
        S.messages.append({"role": "user", "content": S.user_queue})
        S.user_queue = None

    # Prune oldest non-system messages if over context limit
    while len(S.messages) > S.ctx_max + 1:
        idx = next((i for i, m in enumerate(S.messages) if m["role"] != "system"), None)
        if idx is not None:
            S.messages.pop(idx)
        else:
            break

    full = ""
    try:
        with requests.post(
            OLLAMA_CHAT,
            auth=AUTH,
            headers={**HEADERS, "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": S.messages,
                "stream": True,
                "options": {
                    "num_predict": -1,   # -1 = no token limit; generate until natural stop
                }
            },
            stream=True,
            timeout=300,   # allow long responses up to 5 minutes
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw:
                    continue
                try:
                    data  = json.loads(raw)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        full += chunk
                        escaped = full.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                        stream_slot.markdown(
                            f'<div class="msg m-ai">'
                            f'<div class="msg-meta">MIND · {ts()}</div>'
                            f'<div class="msg-body">{escaped}<span class="blink">▋</span></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    if data.get("done"):
                        break
                except (json.JSONDecodeError, KeyError):
                    pass

        stream_slot.empty()
        if full:
            S.messages.append({"role": "assistant", "content": full})
            add_log("ai", full)
            S.cycles    += 1
            S.tokens_est += len(full) // 4
        return full or None

    except Exception as e:
        stream_slot.empty()
        add_log("sys", f"Error: {e}")
        return None

# ── RENDER LOG HTML ───────────────────────────────────────────────────────────
def render_log_html():
    parts = []
    for i, entry in enumerate(S.log):
        role    = entry["role"]
        content = entry["content"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        ts_val  = entry["ts"]
        cls     = "m-ai" if role == "ai" else ("m-user" if role == "user" else "m-sys")
        label   = "MIND" if role == "ai" else ("YOU" if role == "user" else "SYS")
        div = '<hr class="msg-div">' if (role == "ai" and i > 0 and S.log[i-1]["role"] == "ai") else ""
        parts.append(
            f'{div}<div class="msg {cls}">'
            f'<div class="msg-meta">{label} &middot; {ts_val}</div>'
            f'<div class="msg-body">{content}</div>'
            f'</div>'
        )
    return "\n".join(parts)

# ── NAV BAR ───────────────────────────────────────────────────────────────────
status_map = {
    "ready":    ('<span class="dot dot-on"></span>', '#2aff6b', 'Online'),
    "thinking": ('<span class="dot dot-chk"></span>', '#ffaa00', 'Thinking…'),
    "checking": ('<span class="dot dot-chk"></span>', '#ffaa00', 'Connecting…'),
    "offline":  ('<span class="dot dot-off"></span>', '#ff4444', 'Offline'),
}
dot_html, s_color, s_label = status_map.get(S.status, status_map["offline"])

st.markdown(f"""
<div class="nav-bar">
  <div class="nav-logo">
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M10 1L19 10L10 19L1 10Z" stroke="#2aff6b" stroke-width="1.5"/>
      <path d="M10 5L15 10L10 15L5 10Z" fill="#2aff6b" opacity="0.35"/>
    </svg>
    MIND
  </div>
  <div class="nav-status" style="color:{s_color}">{dot_html} {s_label}</div>
</div>
""", unsafe_allow_html=True)

# ── CHAT AREA ─────────────────────────────────────────────────────────────────
log_slot    = st.empty()
stream_slot = st.empty()

log_slot.markdown(
    f'<div class="chat-wrap" id="chatbox">{render_log_html()}</div>',
    unsafe_allow_html=True,
)

# auto-scroll
st.components.v1.html("""
<script>
parent.document.querySelectorAll('#chatbox').forEach(el => el.scrollTop = el.scrollHeight);
setTimeout(()=>{
  parent.document.querySelectorAll('#chatbox').forEach(el => el.scrollTop = el.scrollHeight);
},400);
</script>
""", height=0)

# ── BOTTOM BAR ────────────────────────────────────────────────────────────────
c_ap, c_new, c_retry, c_delay, c_ctx = st.columns([2, 2, 2, 3, 3])

with c_ap:
    ap_label = "■ STOP" if S.autopilot else "▶ AUTOPILOT"
    if st.button(ap_label, key="btn_ap", disabled=not S.connected):
        S.autopilot = not S.autopilot
        st.rerun()

with c_new:
    if st.button("⟳ NEW CHAT", key="btn_new"):
        S.messages   = []
        S.log        = []
        S.cycles     = 0
        S.tokens_est = 0
        S.user_queue = None
        S.autopilot  = False
        rebuild_system_message()
        add_log("sys", "Memory cleared.")
        st.rerun()

with c_retry:
    if st.button("↺ RECONNECT", key="btn_retry"):
        S.checked   = False
        S.connected = False
        S.status    = "checking"
        st.rerun()

with c_delay:
    S.think_delay = st.slider(
        "delay", 0.5, 8.0, float(S.think_delay), 0.5,
        format="%.1fs", label_visibility="collapsed", key="sl_delay"
    )

with c_ctx:
    S.ctx_max = st.slider(
        "ctx", 4, 40, int(S.ctx_max), 2,
        format="%d msg", label_visibility="collapsed", key="sl_ctx"
    )

# input row
in_col, send_col = st.columns([11, 1])
with in_col:
    user_text = st.text_input("msg", placeholder="Message mind…", key="user_input",
                               label_visibility="collapsed")
with send_col:
    send_btn = st.button("➤", key="btn_send")

# metrics strip
queue_html = '<span class="queue-tag">MSG QUEUED</span>' if S.user_queue else ""
st.markdown(f"""
<div class="btm-metrics">
  CYCLES <span>{S.cycles}</span>
  &nbsp;·&nbsp; TOKENS~ <span>{S.tokens_est}</span>
  &nbsp;·&nbsp; CTX <span>{len(S.messages)}/{S.ctx_max+1}</span>
  &nbsp;·&nbsp; DELAY <span>{S.think_delay}s</span>
  {queue_html}
</div>
""", unsafe_allow_html=True)

# ── HANDLE USER INPUT ─────────────────────────────────────────────────────────
raw_input = st.session_state.get("user_input", "").strip()
if (send_btn or raw_input) and raw_input:
    add_log("user", raw_input)
    if S.status == "thinking":
        S.user_queue = raw_input
    else:
        S.messages.append({"role": "user", "content": raw_input})
        if S.connected:
            S.status = "thinking"
            log_slot.markdown(
                f'<div class="chat-wrap" id="chatbox">{render_log_html()}</div>',
                unsafe_allow_html=True,
            )
            think_once(stream_slot)
            S.status = "ready"
    st.rerun()

# ── FIRST LOAD CONNECTION CHECK ───────────────────────────────────────────────
if not S.checked:
    check_connection()
    st.rerun()

# ── AUTOPILOT LOOP ────────────────────────────────────────────────────────────
if S.autopilot and S.connected:
    S.status = "thinking"
    log_slot.markdown(
        f'<div class="chat-wrap" id="chatbox">{render_log_html()}</div>',
        unsafe_allow_html=True,
    )
    result = think_once(stream_slot)
    S.status = "ready"
    if result is not None and S.autopilot:
        time.sleep(S.think_delay)
        st.rerun()
