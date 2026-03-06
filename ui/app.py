import streamlit as st
import sqlite3
import time
import html
import os
import re
import markdown as md_lib

# Resolve board.db relative to the project root (parent of the ui/ directory),
# so this works regardless of which directory Streamlit is launched from.
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "board.db")
POLL_INTERVAL = 1.5  # seconds — fast enough to feel live

# Deterministic agent styles
AGENT_STYLES = [
    {"bg": "#d1fae5", "color": "#059669"}, # emerald
    {"bg": "#e0e7ff", "color": "#4f46e5"}, # indigo
    {"bg": "#fce7f3", "color": "#db2777"}, # pink
    {"bg": "#fef3c7", "color": "#d97706"}, # amber
    {"bg": "#e1effe", "color": "#2563eb"}, # blue
    {"bg": "#f3e8ff", "color": "#9333ea"}, # purple
    {"bg": "#fee2e2", "color": "#dc2626"}, # red
]


def agent_style(agent_id: str) -> dict:
    return AGENT_STYLES[hash(agent_id) % len(AGENT_STYLES)]


def agent_badge(agent_id: str) -> str:
    style = agent_style(agent_id)
    return (
        f'<span style="background:{style["bg"]}; color:{style["color"]}; '
        f'padding:4px 10px; border-radius:6px; font-size:0.75em; '
        f'font-weight:700; font-family: \'SF Mono\', \'Roboto Mono\', monospace; '
        f'text-transform: uppercase; letter-spacing: 0.5px;">'
        f'{agent_id}</span>'
    )


_TAG_RE = re.compile(r'\[([0-9a-f]{8})\]')

def linkify_tags(text: str) -> str:
    """Replace [xxxxxxxx] post-ID references with clickable anchor links."""
    def replace(m):
        pid = m.group(1)
        return (
            f'<a href="#post-{pid}" '
            f'style="background:#e0e7ff; color:#4f46e5; padding:2px 7px; '
            f'border-radius:4px; font-size:0.8em; font-weight:700; '
            f'font-family: \'SF Mono\', monospace; text-decoration:none; '
            f'letter-spacing:0.3px;" '
            f'title="Jump to post {pid}">'
            f'&#x1F517;&nbsp;{pid}</a>'
        )
    return _TAG_RE.sub(replace, text)


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Agent Network — Live Feed", layout="wide")

st.markdown("""
<style>
    /* Global Background and Typography */
    [data-testid="stAppViewContainer"] {
        background-color: #f8fafc;
        background-image: linear-gradient(#f1f5f9 1px, transparent 1px), linear-gradient(90deg, #f1f5f9 1px, transparent 1px);
        background-size: 40px 40px;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    /* Hide the top header */
    [data-testid="stHeader"] {
        background-color: transparent;
    }
    /* Main Title */
    h2 {
        color: #475569;
        font-weight: 700;
        font-family: 'SF Mono', 'Roboto Mono', 'Fira Code', monospace;
        letter-spacing: 1px;
        text-transform: uppercase;
        font-size: 1.2em;
        padding-top: 15px;
        position: relative;
    }
    h2::before {
        content: '';
        position: absolute;
        top: 0px;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #ef4444 0%, #10b981 100%);
        border-radius: 4px 4px 0 0;
    }
    /* Post Cards */
    .post-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .post-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
    }
    /* Post Header */
    .post-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 16px;
    }
    .vote-count {
        font-size: 1.1em;
        font-weight: 700;
        color: #94a3b8;
        min-width: 40px;
        text-align: right;
        background: transparent;
        padding: 0;
        border-radius: 0;
    }
    .post-meta {
        color: #94a3b8;
        font-size: 0.8em;
        font-family: 'SF Mono', 'Roboto Mono', 'Fira Code', monospace;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    /* Post Content */
    .post-content {
        font-size: 1.15em;
        font-weight: 500;
        line-height: 1.5;
        color: #0f172a;
        margin: 16px 0;
    }
    /* Comment Blocks — CSS checkbox toggle (no JS needed) */
    .comments-section {
        margin-top: 8px;
    }
    /* Hide the native checkbox */
    .comments-section input[type="checkbox"] {
        display: none;
    }
    /* Label acts as the toggle button */
    .comments-toggle-label {
        display: inline-block;
        background: none;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        color: #64748b;
        font-size: 0.78em;
        font-weight: 600;
        font-family: 'SF Mono', 'Roboto Mono', monospace;
        cursor: pointer;
        padding: 3px 10px;
        margin-bottom: 8px;
        transition: background 0.15s;
        user-select: none;
    }
    .comments-toggle-label:hover {
        background: #f1f5f9;
        color: #334155;
    }
    /* When checkbox is checked → show the body; unchecked → hide */
    .comments-section input[type="checkbox"]:checked ~ .comments-body {
        display: block;
    }
    .comments-body {
        display: none;
    }
    .comment-block {
        border-left: 2px solid #e2e8f0;
        margin: 12px 0 12px 20px;
        padding: 8px 16px;
        background: transparent;
    }
    .comment-text {
        color: #475569;
        margin-top: 8px;
        font-size: 1em;
        line-height: 1.5;
    }
    /* Thread-tag links inside comments */
    .comment-text a {
        text-decoration: none;
    }
    .comment-text a:hover {
        opacity: 0.8;
    }
    /* Markdown rendered content styling */
    .post-content p, .comment-text p {
        margin: 0 0 8px 0;
    }
    .post-content p:last-child, .comment-text p:last-child {
        margin-bottom: 0;
    }
    .post-content h1, .post-content h2, .post-content h3,
    .comment-text h1, .comment-text h2, .comment-text h3 {
        margin: 12px 0 6px 0;
        font-weight: 700;
        color: #0f172a;
    }
    .post-content code, .comment-text code {
        background: #f1f5f9;
        border-radius: 4px;
        padding: 1px 5px;
        font-family: 'SF Mono', 'Roboto Mono', monospace;
        font-size: 0.88em;
        color: #0f172a;
    }
    .post-content pre, .comment-text pre {
        background: #1e293b;
        color: #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        overflow-x: auto;
        margin: 10px 0;
        font-size: 0.85em;
    }
    .post-content pre code, .comment-text pre code {
        background: transparent;
        padding: 0;
        color: inherit;
    }
    .post-content ul, .post-content ol,
    .comment-text ul, .comment-text ol {
        padding-left: 20px;
        margin: 6px 0;
    }
    .post-content li, .comment-text li {
        margin: 3px 0;
    }
    .post-content blockquote, .comment-text blockquote {
        border-left: 3px solid #cbd5e1;
        margin: 8px 0;
        padding: 4px 12px;
        color: #64748b;
        font-style: italic;
    }
    .post-content strong, .comment-text strong {
        font-weight: 700;
        color: #0f172a;
    }
    /* Activity Feed Items */
    .activity-item {
        padding: 16px;
        border: 1px solid #e2e8f0;
        font-size: 0.9em;
        line-height: 1.5;
        background: #ffffff;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
    }
    .activity-preview {
        color: #64748b;
        margin-top: 8px;
        font-style: normal;
        background: transparent;
        padding: 0;
        font-size: 0.95em;
    }
    /* Streamlit overrides */
    .stRadio > div > label > div[data-testid="stMarkdownContainer"] > p {
        color: #64748b !important;
        font-weight: 600 !important;
        font-size: 0.85em !important;
        text-transform: uppercase;
        font-family: 'SF Mono', 'Roboto Mono', 'Fira Code', monospace;
    }
    [data-testid="stMetricValue"] {
        color: #0f172a;
        font-family: 'SF Mono', 'Roboto Mono', 'Fira Code', monospace;
        font-weight: 700;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.8em;
        font-family: 'SF Mono', 'Roboto Mono', 'Fira Code', monospace;
    }
    .session-selector-label {
        color: #475569;
        font-weight: 700;
        font-family: 'SF Mono', 'Roboto Mono', monospace;
        font-size: 0.9em;
        text-transform: uppercase;
        margin-bottom: 8px;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("## 🧠 Agent Network — Live Feed")

# Fetch sessions to populate dropdown
try:
    with sqlite3.connect(DB_PATH) as _tmp_db:
        sessions = _tmp_db.execute(
            "SELECT id, prompt, created_at FROM sessions ORDER BY created_at DESC"
        ).fetchall()
except Exception:
    sessions = []

if not sessions:
    st.info("No active sessions found. Run `python main.py` to start the swarm.")
    st.stop()

# Helper to format session dropdown options
def format_session(s):
    prompt_trunc = (s[1][:60] + "…") if len(s[1]) > 60 else s[1]
    return f"{s[2]} | {prompt_trunc}"

st.markdown('<span class="session-selector-label">Active Session:</span>', unsafe_allow_html=True)
selected_session_formatted = st.selectbox(
    "Select Session",
    options=[format_session(s) for s in sessions],
    label_visibility="collapsed"
)

# Extract the selected session ID based on the selection
selected_session_id = next(
    s[0] for s in sessions if format_session(s) == selected_session_formatted
)

placeholder = st.empty()


# The Streamlit `while True` loop doesn't play nicely with `st.selectbox`
# because changing the selectbox throws RerunException, interrupting the loop.
# It's better to use `st.rerun()` directly instead of a blocking `while` loop.
# To keep auto-refreshing, we can use an empty container and redraw within it, 
# then call time.sleep and st.rerun(). Streamlit standard fragment or generic rerun is best.

# Removing block while True to allow native Stremlit interaction.
with placeholder.container():
    try:
        db = sqlite3.connect(DB_PATH)

        # ── Stats bar ──────────────────────────────────────────────────────
        n_posts    = db.execute("SELECT COUNT(*) FROM posts WHERE session_id = ?", (selected_session_id,)).fetchone()[0]
        n_comments = db.execute("SELECT COUNT(*) FROM comments WHERE session_id = ?", (selected_session_id,)).fetchone()[0]
        n_upvotes  = db.execute("SELECT COUNT(*) FROM upvotes WHERE session_id = ?", (selected_session_id,)).fetchone()[0]
        n_agents   = db.execute(
            "SELECT COUNT(DISTINCT agent_id) FROM posts WHERE session_id = ?", (selected_session_id,)
        ).fetchone()[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📝 Posts", n_posts)
        c2.metric("💬 Comments", n_comments)
        c3.metric("⬆ Upvotes", n_upvotes)
        c4.metric("🤖 Active Agents", n_agents)

        # ── Two-column layout ─────────────────────────────────────────────
        feed_col, activity_col = st.columns([3, 1])

        # ===== LEFT: HN-STYLE RANKED FEED =================================
        with feed_col:
            sort_mode = st.radio(
                "Sort",
                ["🔥 Top (by votes)", "🕐 Newest first"],
                horizontal=True,
                label_visibility="collapsed",
            )
            order_clause = (
                "upvotes DESC, p.created_at DESC"
                if "Top" in sort_mode
                else "p.created_at DESC"
            )

            posts = db.execute(f"""
                SELECT p.id, p.agent_id, p.content, p.created_at,
                       COUNT(u.agent_id) as upvotes
                FROM posts p
                LEFT JOIN upvotes u ON p.id = u.post_id
                WHERE p.session_id = ?
                GROUP BY p.id
                ORDER BY {order_clause}
            """, (selected_session_id,)).fetchall()

            if not posts:
                st.info("⏳ Waiting for agents to start posting…")

            for rank, (post_id, agent, content, ts, votes) in enumerate(posts, 1):
                # Who upvoted?
                voters = db.execute(
                    "SELECT agent_id FROM upvotes WHERE post_id = ? AND session_id = ?",
                    (post_id, selected_session_id)
                ).fetchall()
                voter_badges = " ".join(agent_badge(v[0]) for v in voters) if voters else ""

                # Comments on this post
                comments = db.execute(
                    "SELECT agent_id, content, created_at FROM comments "
                    "WHERE post_id = ? AND session_id = ? ORDER BY created_at",
                    (post_id, selected_session_id)
                ).fetchall()

                badge = agent_badge(agent)
                n_c = len(comments)

                # Parse content as Markdown → HTML, then linkify [post-id] references
                safe_content = linkify_tags(md_lib.markdown(content, extensions=['fenced_code', 'tables', 'nl2br']))

                chk_id = f"chk_{post_id}"
                toggle_label = f"▾ {n_c} comment{'s' if n_c != 1 else ''}" if n_c else ""

                html_str = (
                    f'<div class="post-card" id="post-{post_id}">'
                    f'<div class="post-header">'
                    f'<span class="vote-count">▲ {votes}</span>'
                    f'{badge}'
                    f'<span class="post-meta">#{rank} &middot; {post_id} &middot; {ts}</span>'
                    f'</div>'
                    f'<div class="post-content">{safe_content}</div>'
                    f'<div class="post-meta">'
                    f'{" upvoted by " + voter_badges if voter_badges else ""}'
                    f'</div>'
                )

                if n_c > 0:
                    # CSS checkbox hack: hidden checkbox + label = pure-CSS toggle
                    # checked by default → comments visible on load
                    html_str += (
                        f'<div class="comments-section">'
                        f'<input type="checkbox" id="{chk_id}" checked>'
                        f'<label class="comments-toggle-label" for="{chk_id}">'
                        f'{toggle_label}</label>'
                        f'<div class="comments-body">'
                    )
                    for c_agent, c_content, c_ts in comments:
                        safe_c_content = md_lib.markdown(c_content, extensions=['fenced_code', 'tables', 'nl2br'])
                        linked_c_content = linkify_tags(safe_c_content)
                        html_str += (
                            f'<div class="comment-block">'
                            f'{agent_badge(c_agent)}'
                            f'<span class="post-meta"> &middot; {c_ts}</span>'
                            f'<div class="comment-text">{linked_c_content}</div>'
                            f'</div>'
                        )
                    html_str += '</div></div>'  # close comments-body + comments-section

                html_str += '</div>'  # close post-card
                st.markdown(html_str, unsafe_allow_html=True)

        # ===== RIGHT: LIVE ACTIVITY LOG ====================================
        with activity_col:
            st.markdown("### ⚡ Live Activity")

            activity = db.execute("""
                SELECT agent_id, 'posted' as action, content, created_at
                FROM posts
                WHERE session_id = ?
                UNION ALL
                SELECT c.agent_id, 'commented on ' || c.post_id,
                       c.content, c.created_at
                FROM comments c
                WHERE c.session_id = ?
                UNION ALL
                SELECT u.agent_id, 'upvoted ' || u.post_id,
                       '', u.created_at
                FROM upvotes u
                WHERE u.session_id = ?
                ORDER BY 4 DESC
                LIMIT 20
            """, (selected_session_id, selected_session_id, selected_session_id)).fetchall()

            if not activity:
                st.caption("No activity yet…")

            for a_agent, a_action, a_content, _ in activity:
                # Escape preview text to avoid breaking HTML layout
                safe_a_content = html.escape(a_content)
                preview = (safe_a_content[:55] + "…") if len(safe_a_content) > 55 else safe_a_content
                preview_html = (
                    f'<div class="activity-preview">{preview}</div>' if preview else ""
                )
                st.markdown(
                    f'<div class="activity-item">'
                    f'{agent_badge(a_agent)} <b>{html.escape(a_action)}</b>'
                    f'{preview_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        db.close()

    except Exception as e:
        st.info(f"⏳ Waiting for agents to start… ({e})")

# Auto-refresh using st.rerun
time.sleep(POLL_INTERVAL)
st.rerun()
