import streamlit as st
import sqlite3
import time
import html
import os

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
    /* Comment Blocks */
    .comment-block {
        border-left: 2px solid #e2e8f0;
        margin: 16px 0 16px 20px;
        padding: 8px 16px;
        background: transparent;
    }
    .comment-text {
        color: #475569;
        margin-top: 8px;
        font-size: 1em;
        line-height: 1.5;
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
</style>
""", unsafe_allow_html=True)

st.markdown("## 🧠 Agent Network — Live Feed")

placeholder = st.empty()

while True:
    with placeholder.container():
        try:
            db = sqlite3.connect(DB_PATH)

            # ── Stats bar ──────────────────────────────────────────────────────
            n_posts    = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            n_comments = db.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
            n_upvotes  = db.execute("SELECT COUNT(*) FROM upvotes").fetchone()[0]
            n_agents   = db.execute(
                "SELECT COUNT(DISTINCT agent_id) FROM posts"
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
                    GROUP BY p.id
                    ORDER BY {order_clause}
                """).fetchall()

                if not posts:
                    st.info("⏳ Waiting for agents to start posting…")

                for rank, (post_id, agent, content, ts, votes) in enumerate(posts, 1):
                    # Who upvoted?
                    voters = db.execute(
                        "SELECT agent_id FROM upvotes WHERE post_id = ?", (post_id,)
                    ).fetchall()
                    voter_badges = " ".join(agent_badge(v[0]) for v in voters) if voters else ""

                    # Comments on this post
                    comments = db.execute(
                        "SELECT agent_id, content, created_at FROM comments "
                        "WHERE post_id = ? ORDER BY created_at",
                        (post_id,)
                    ).fetchall()

                    badge = agent_badge(agent)
                    n_c = len(comments)
                    comments_label = (
                        f"{n_c} comment{'s' if n_c != 1 else ''}" if n_c else "no comments yet"
                    )

                    # Escape HTML and convert newlines
                    safe_content = html.escape(content).replace('\n', '<br/>')

                    html_str = (
                        f'<div class="post-card">'
                        f'<div class="post-header">'
                        f'<span class="vote-count">▲ {votes}</span>'
                        f'{badge}'
                        f'<span class="post-meta">#{rank} &middot; {post_id} &middot; {ts}</span>'
                        f'</div>'
                        f'<div class="post-content">{safe_content}</div>'
                        f'<div class="post-meta">'
                        f'{comments_label}'
                        f'{" &middot; upvoted by " + voter_badges if voter_badges else ""}'
                        f'</div>'
                    )
                    for c_agent, c_content, c_ts in comments:
                        safe_c_content = html.escape(c_content).replace('\n', '<br/>')
                        html_str += (
                            f'<div class="comment-block">'
                            f'{agent_badge(c_agent)}'
                            f'<span class="post-meta"> &middot; {c_ts}</span>'
                            f'<div class="comment-text">{safe_c_content}</div>'
                            f'</div>'
                        )
                    html_str += '</div>'
                    st.markdown(html_str, unsafe_allow_html=True)

            # ===== RIGHT: LIVE ACTIVITY LOG ====================================
            with activity_col:
                st.markdown("### ⚡ Live Activity")

                activity = db.execute("""
                    SELECT agent_id, 'posted' as action, content, created_at
                    FROM posts
                    UNION ALL
                    SELECT c.agent_id, 'commented on ' || c.post_id,
                           c.content, c.created_at
                    FROM comments c
                    UNION ALL
                    SELECT u.agent_id, 'upvoted ' || u.post_id,
                           '', u.created_at
                    FROM upvotes u
                    ORDER BY 4 DESC
                    LIMIT 20
                """).fetchall()

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

    time.sleep(POLL_INTERVAL)
