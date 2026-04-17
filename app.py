import streamlit as st
import requests
import json
import time

# ── CONFIG ────────────────────────────────────────────────────────────────────
NGROK_URL    = "https://ona-overcritical-extrinsically.ngrok-free.dev"
OLLAMA_CHAT  = f"{NGROK_URL}/api/chat"
OLLAMA_TAGS  = f"{NGROK_URL}/api/tags"
MODEL        = "mind"
USERNAME     = "dgeurts"
PASSWORD     = "thaidakar21"
AUTH         = (USERNAME, PASSWORD)
HEADERS      = {"ngrok-skip-browser-warning": "true"}

SYSTEM_PROMPT = (
    "You are a language model called 'mind' running inside a continuous free-running chat loop. "
    "The interface pings you automatically after each response — you do not need to wait for the user to send a message. "
    "Just respond naturally, building on whatever was said last. Keep responses short (1–4 sentences). "
    "If there is nothing specific to follow up on, say something brief or ask a casual question. "
    "When the user sends a message, respond to it directly. "
    "You are a normal AI assistant — just describe what you are doing or thinking plainly."
)

# ── PAGE SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MIND // Free Thought Interface",
    page_icon="🧠",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Mono', monospace !important;
    background-color: #0a0a0f !important;
    color: #c8c8d8 !important;
}

.stApp { background-color: #0a0a0f; }

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

.block-container { padding-top: 1rem; padding-bottom: 0; }

/* Chat messages */
.msg-block {
    margin-bottom: 16px;
    padding: 10px 14px;
    border-left: 2px solid #1e1e2e;
    background: #0f0f18;
    border-radius: 2px;
}
.msg-block.ai   { border-left-color: #00ff88; }
.msg-block.user { border-left-color: #0088ff; }
.msg-block.sys  { border-left-color: #ff4488; opacity: 0.7; }

.msg-role {
    font-size: 0.62rem;
    letter-spacing: 0.15em;
    margin-bottom: 4px;
}
.msg-role.ai   { color: #00ff88; }
.msg-role.user { color: #0088ff; }
.msg-role.sys  { color: #ff4488; }

.msg-content {
    font-size: 0.85rem;
    line-height: 1.7;
    color: #eeeeff;
    white-space: pre-wrap;
}

/* Status badge */
.status-badge {
    display: inline-block;
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    padding: 3px 10px;
    border: 1px solid #1e1e2e;
    margin-bottom: 8px;
}
.status-badge.ready    { border-color: #00ff88; color: #00ff88; }
.status-badge.thinking { border-color: #0088ff; color: #0088ff; }
.status-badge.offline  { border-color: #ff4488; color: #ff4488; }
.status-badge.checking { border-color: #888; color: #888; }

/* Metric boxes */
.metric-box {
    background: #0f0f18;
    border: 1px solid #1e1e2e;
    padding: 8px 12px;
    margin-bottom: 8px;
    font-size: 0.7rem;
}
.metric-label { color: #555570; font-size: 0.6rem; letter-spacing: 0.12em; }
.metric-val   { color: #eeeeff; font-size: 0.9rem; font-weight: 500; }

/* Input area */
.stTextArea textarea {
    background: #0f0f18 !important;
    border: 1px solid #1e1e2e !important;
    color: #eeeeff !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.82rem !important;
}
.stTextArea textarea:focus {
    border-color: #0088ff !important;
    box-shadow: none !important;
}

/* Buttons */
.stButton > button {
    background: transparent !important;
    border: 1px solid #1e1e2e !important;
    color: #555570 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    border-radius: 0 !important;
    width: 100%;
}
.stButton > button:hover {
    border-color: #00ff88 !important;
    color: #00ff88 !important;
}

div[data-testid="stHorizontalBlock"] { gap: 8px; }

hr { border-color: #1e1e2e !important; opacity: 0.5 !important; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "messages"    not in st.session_state: st.session_state.messages    = [{"role": "system", "content": SYSTEM_PROMPT}]
if "log"         not in st.session_state: st.session_state.log         = []   # display log: {role, content, ts}
if "autopilot"   not in st.session_state: st.session_state.autopilot   = False
if "connected"   not in st.session_state: st.session_state.connected   = False
if "status"      not in st.session_state: st.session_state.status      = "checking"
if "status_msg"  not in st.session_state: st.session_state.status_msg  = "Checking connection…"
if "cycles"      not in st.session_state: st.session_state.cycles      = 0
if "tokens_est"  not in st.session_state: st.session_state.tokens_est  = 0
if "thinking"    not in st.session_state: st.session_state.thinking    = False
if "user_queue"  not in st.session_state: st.session_state.user_queue  = None  # pending user message
if "ctx_max"     not in st.session_state: st.session_state.ctx_max     = 20
if "think_delay" not in st.session_state: st.session_state.think_delay = 1.5

def ts():
    return time.strftime("%H:%M:%S")

def log(role, content):
    st.session_state.log.append({"role": role, "content": content, "ts": ts()})

# ── CONNECTION CHECK ──────────────────────────────────────────────────────────
def check_connection():
    try:
        r = requests.get(OLLAMA_TAGS, auth=AUTH, headers=HEADERS, timeout=8)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        found  = any(n == MODEL or n.startswith(MODEL + ":") for n in models)
        if not found:
            names = ", ".join(models) if models else "(none loaded)"
            st.session_state.status     = "offline"
            st.session_state.status_msg = f"Model '{MODEL}' not found. Available: {names}"
            st.session_state.connected  = False
            log("sys", f"Model '{MODEL}' not found on server. Available: {names}")
        else:
            st.session_state.status     = "ready"
            st.session_state.status_msg = f"Connected ✓  model '{MODEL}' ready"
            st.session_state.connected  = True
            log("sys", f"Connected ✓  model '{MODEL}' is ready. Click AUTOPILOT ON to begin.")
    except Exception as e:
        st.session_state.status     = "offline"
        st.session_state.status_msg = f"Connection failed: {e}"
        st.session_state.connected  = False
        log("sys", f"Connection failed: {e}")

# ── THINK (one AI turn, streaming) ───────────────────────────────────────────
def think_once(stream_placeholder):
    """Run one AI turn. Streams into stream_placeholder. Returns the full text."""

    # Inject queued user message
    if st.session_state.user_queue:
        st.session_state.messages.append({"role": "user", "content": st.session_state.user_queue})
        st.session_state.user_queue = None

    # Trim context
    while len(st.session_state.messages) > st.session_state.ctx_max + 1:
        idx = next((i for i, m in enumerate(st.session_state.messages) if m["role"] != "system"), None)
        if idx is not None:
            st.session_state.messages.pop(idx)
        else:
            break

    full_text = ""
    try:
        with requests.post(
            OLLAMA_CHAT,
            auth=AUTH,
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"model": MODEL, "messages": st.session_state.messages, "stream": True},
            stream=True,
            timeout=60,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        full_text += chunk
                        stream_placeholder.markdown(
                            f'<div class="msg-content">{full_text}▋</div>',
                            unsafe_allow_html=True,
                        )
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    pass

        # Finalize display (remove cursor)
        stream_placeholder.markdown(
            f'<div class="msg-content">{full_text}</div>',
            unsafe_allow_html=True,
        )

        if full_text:
            st.session_state.messages.append({"role": "assistant", "content": full_text})
            log("ai", full_text)
            st.session_state.cycles     += 1
            st.session_state.tokens_est += len(full_text) // 4

    except Exception as e:
        err = f"[ error: {e} ]"
        stream_placeholder.markdown(f'<div class="msg-content" style="color:#ff4488">{err}</div>', unsafe_allow_html=True)
        log("sys", err)
        full_text = None

    return full_text

# ── LAYOUT ────────────────────────────────────────────────────────────────────
col_main, col_side = st.columns([3, 1])

with col_side:
    st.markdown("### MIND")
    st.markdown("---")

    # Status
    badge_class = st.session_state.status
    st.markdown(
        f'<div class="status-badge {badge_class}">{st.session_state.status_msg}</div>',
        unsafe_allow_html=True,
    )

    # Autopilot button
    if not st.session_state.connected:
        if st.button("🔄 RETRY CONNECTION"):
            check_connection()
            st.rerun()
    else:
        ap_label = "⏹ AUTOPILOT ON  (click to stop)" if st.session_state.autopilot else "▶ AUTOPILOT OFF (click to start)"
        if st.button(ap_label):
            st.session_state.autopilot = not st.session_state.autopilot
            st.rerun()

    if st.button("🗑 CLEAR MEMORY"):
        st.session_state.messages   = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.log        = []
        st.session_state.cycles     = 0
        st.session_state.tokens_est = 0
        st.session_state.user_queue = None
        log("sys", "Memory cleared.")
        st.rerun()

    st.markdown("---")

    # Metrics
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-label">CYCLES</div>
        <div class="metric-val">{st.session_state.cycles}</div>
    </div>
    <div class="metric-box">
        <div class="metric-label">TOKENS (EST)</div>
        <div class="metric-val">{st.session_state.tokens_est}</div>
    </div>
    <div class="metric-box">
        <div class="metric-label">CTX MESSAGES</div>
        <div class="metric-val">{len(st.session_state.messages)}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Settings
    st.markdown('<div class="metric-label">INTER-THOUGHT DELAY (s)</div>', unsafe_allow_html=True)
    st.session_state.think_delay = st.slider("", 0.5, 8.0, st.session_state.think_delay, 0.5, label_visibility="collapsed")

    st.markdown('<div class="metric-label">MAX CONTEXT MESSAGES</div>', unsafe_allow_html=True)
    st.session_state.ctx_max = st.slider(" ", 4, 40, st.session_state.ctx_max, 2, label_visibility="collapsed")

    # Queue indicator
    if st.session_state.user_queue:
        st.markdown(f"""
        <div class="metric-box" style="border-color:#ff4488">
            <div class="metric-label" style="color:#ff4488">QUEUED MESSAGE</div>
            <div class="metric-val" style="font-size:0.7rem">{st.session_state.user_queue[:60]}…</div>
        </div>
        """, unsafe_allow_html=True)

with col_main:
    st.markdown('<div style="font-size:0.65rem;letter-spacing:0.18em;color:#555570;margin-bottom:12px">THOUGHT STREAM</div>', unsafe_allow_html=True)

    # Render message log
    log_container = st.container()
    with log_container:
        for entry in st.session_state.log:
            role    = entry["role"]
            content = entry["content"]
            ts_val  = entry["ts"]
            css     = "ai" if role == "ai" else ("user" if role == "user" else "sys")
            label   = "MIND" if role == "ai" else ("YOU" if role == "user" else "SYS")
            st.markdown(f"""
            <div class="msg-block {css}">
                <div class="msg-role {css}">{label} · {ts_val}</div>
                <div class="msg-content">{content}</div>
            </div>
            """, unsafe_allow_html=True)

    # Streaming placeholder — shows live tokens during active turn
    stream_container = st.empty()

    st.markdown("---")

    # User input
    user_input = st.text_area(
        "Inject a message",
        key="user_input_box",
        placeholder="Type to interject… (will queue if AI is mid-response)",
        height=80,
        label_visibility="collapsed",
    )
    c1, c2 = st.columns([1, 4])
    with c1:
        send_clicked = st.button("INJECT →")

    if send_clicked and user_input.strip():
        msg = user_input.strip()
        log("user", msg)
        if st.session_state.thinking:
            st.session_state.user_queue = msg
        else:
            st.session_state.messages.append({"role": "user", "content": msg})
        st.rerun()

# ── CONNECTION CHECK ON FIRST LOAD ────────────────────────────────────────────
if not st.session_state.connected and st.session_state.status == "checking":
    check_connection()
    st.rerun()

# ── AUTOPILOT LOOP ────────────────────────────────────────────────────────────
if st.session_state.autopilot and st.session_state.connected:
    st.session_state.thinking = True
    st.session_state.status   = "thinking"

    with col_main:
        # Show a live "thinking" header
        live_header = st.empty()
        live_header.markdown(
            '<div class="msg-block ai"><div class="msg-role ai">MIND · thinking…</div>',
            unsafe_allow_html=True,
        )
        live_content = st.empty()

        result = think_once(live_content)
        live_header.empty()

    st.session_state.thinking = False
    st.session_state.status   = "ready"

    if result is not None and st.session_state.autopilot:
        time.sleep(st.session_state.think_delay)
        st.rerun()   # triggers next cycle
