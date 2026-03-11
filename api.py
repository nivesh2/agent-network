"""
Agora API — FastAPI data bridge for the React dashboard.

Reads from board.db (shared with agents) and exposes JSON + SSE endpoints:
  /api/sessions  –  aggregate stats & agent roster (session-scoped)
  /api/feed      –  posts + comments + upvotes (Top / Newest)
  /api/activity  –  unified timeline of recent actions
  /api/stream    –  SSE real-time stream of new posts/comments/upvotes
"""

import asyncio
from typing import Optional
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime as _dt
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import Config
try:
    from google import genai as _genai
    from google.genai import types as _types
except ImportError:
    _genai = None  # type: ignore
    _types = None  # type: ignore

# ── Configuration ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = str(PROJECT_ROOT / "board.db")

# ── App lifecycle ───────────────────────────────────────────────────────────
db_connection: Optional[aiosqlite.Connection] = None


from board import Board

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection
    # Ensure all tables exist before serving traffic
    dummy_board = Board(DB_PATH, "init")
    await dummy_board.init()
    await dummy_board.close()

    db_connection = await aiosqlite.connect(DB_PATH, timeout=30.0, uri=False)
    db_connection.row_factory = aiosqlite.Row
    await db_connection.execute("PRAGMA journal_mode=WAL")
    # Create synthesized_documents table if it doesn't exist
    await db_connection.execute("""
        CREATE TABLE IF NOT EXISTS synthesized_documents (
            session_id TEXT PRIMARY KEY,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    await db_connection.commit()
    yield
    if db_connection:
        await db_connection.close()


app = FastAPI(title="Agora API", lifespan=lifespan)

# ── CORS (allow Vite dev server) ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://localhost:5178",
        "http://localhost:5179",
        "http://localhost:5180",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:5180",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Helpers ─────────────────────────────────────────────────────────────────
def _db() -> aiosqlite.Connection:
    assert db_connection is not None, "DB not initialised"
    return db_connection


async def _resolve_session_id(session_id: Optional[str]) -> Optional[str]:
    """Return a valid session_id: use the provided one, or fall back to the latest."""
    db = _db()
    if session_id:
        return session_id
    async with db.execute(
        "SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1"
    ) as cur:
        row = await cur.fetchone()
        return row[0] if row else None


# ── Endpoints ───────────────────────────────────────────────────────────────


@app.get("/api/sessions")
async def get_sessions(session_id: Optional[str] = Query(None)):
    """Aggregate stats scoped to a session (defaults to latest)."""
    db = _db()
    sid = await _resolve_session_id(session_id)

    if not sid:
        return {
            "session_id": None, "prompt": None,
            "total_posts": 0, "total_comments": 0, "total_upvotes": 0,
            "active_agents": 0, "agents": [],
        }

    prompt = None
    async with db.execute("SELECT prompt FROM sessions WHERE id = ?", (sid,)) as cur:
        row = await cur.fetchone()
        prompt = row[0] if row else None

    total_posts = 0
    total_comments = 0
    total_upvotes = 0
    agents: list[str] = []

    async with db.execute(
        "SELECT COUNT(*) FROM posts WHERE session_id = ?", (sid,)
    ) as cur:
        row = await cur.fetchone()
        total_posts = row[0] if row else 0

    async with db.execute(
        "SELECT COUNT(*) FROM comments WHERE session_id = ?", (sid,)
    ) as cur:
        row = await cur.fetchone()
        total_comments = row[0] if row else 0

    async with db.execute(
        "SELECT COUNT(*) FROM upvotes WHERE session_id = ?", (sid,)
    ) as cur:
        row = await cur.fetchone()
        total_upvotes = row[0] if row else 0

    async with db.execute(
        "SELECT DISTINCT agent_id FROM posts WHERE session_id = ? ORDER BY agent_id",
        (sid,),
    ) as cur:
        agents = [r[0] async for r in cur]

    return {
        "session_id": sid,
        "prompt": prompt,
        "total_posts": total_posts,
        "total_comments": total_comments,
        "total_upvotes": total_upvotes,
        "active_agents": len(agents),
        "agents": agents,
    }


@app.get("/api/feed")
async def get_feed(
    sort: str = Query("top", pattern="^(top|newest)$"),
    limit: int = Query(50, ge=1, le=200),
    session_id: Optional[str] = Query(None),
):
    """Posts with nested comments and upvote counts, scoped to a session."""
    db = _db()
    sid = await _resolve_session_id(session_id)

    if not sid:
        return {"sort": sort, "count": 0, "posts": []}

    order = "upvotes DESC" if sort == "top" else "p.created_at DESC"

    query = f"""
        SELECT p.id, p.agent_id, p.content, p.created_at,
               COUNT(u.agent_id) AS upvotes
        FROM posts p
        LEFT JOIN upvotes u ON p.id = u.post_id
        WHERE p.session_id = ?
        GROUP BY p.id
        ORDER BY {order}
        LIMIT ?
    """
    posts = []
    async with db.execute(query, (sid, limit)) as cur:
        async for row in cur:
            posts.append(
                {
                    "id": row[0],
                    "agent_id": row[1],
                    "content": row[2],
                    "created_at": row[3],
                    "upvotes": row[4],
                    "comments": [],
                }
            )

    # Fetch comments for each post
    for post in posts:
        async with db.execute(
            "SELECT id, agent_id, content, created_at "
            "FROM comments WHERE post_id = ? AND session_id = ? ORDER BY created_at",
            (post["id"], sid),
        ) as cur:
            post["comments"] = [
                {
                    "id": r[0],
                    "agent_id": r[1],
                    "content": r[2],
                    "created_at": r[3],
                }
                async for r in cur
            ]

    return {"sort": sort, "count": len(posts), "posts": posts}


@app.get("/api/activity")
async def get_activity(
    limit: int = Query(30, ge=1, le=200),
    session_id: Optional[str] = Query(None),
):
    """Unified timeline of recent actions, scoped to a session."""
    db = _db()
    sid = await _resolve_session_id(session_id)

    if not sid:
        return {"count": 0, "activities": []}

    query = """
        SELECT agent_id, 'posted' AS action,
               content AS detail, created_at
        FROM posts WHERE session_id = ?

        UNION ALL

        SELECT agent_id, 'commented' AS action,
               content AS detail, created_at
        FROM comments WHERE session_id = ?

        UNION ALL

        SELECT agent_id, 'upvoted' AS action,
               post_id AS detail, created_at
        FROM upvotes WHERE session_id = ?

        UNION ALL

        SELECT agent_id, 'searched' AS action,
               query AS detail, created_at
        FROM searches WHERE session_id = ?

        ORDER BY created_at DESC
        LIMIT ?
    """

    activities = []
    async with db.execute(query, (sid, sid, sid, sid, limit)) as cur:
        async for row in cur:
            activities.append(
                {
                    "agent_id": row[0],
                    "action": row[1],
                    "detail": row[2],
                    "created_at": row[3],
                }
            )

    return {"count": len(activities), "activities": activities}


# ── Sessions list + Launch ──────────────────────────────────────────────────


@app.get("/api/sessions/list")
async def list_sessions():
    """Return all sessions ordered by most recent."""
    db = _db()
    sessions = []
    async with db.execute(
        "SELECT id, prompt, created_at FROM sessions ORDER BY created_at DESC"
    ) as cur:
        async for row in cur:
            sessions.append(
                {"id": row[0], "prompt": row[1], "created_at": row[2]}
            )
    return {"sessions": sessions}


class LaunchRequest(BaseModel):
    prompt: str


@app.post("/api/launch")
async def launch_swarm(body: LaunchRequest):
    """Spawn main.py as a background process with the given prompt."""
    prompt = body.prompt.strip()
    if not prompt:
        prompt = "Conduct a rapid competitive due diligence on the top 3 emerging AI wearable devices. Aggregate their current pricing, funding amounts, and pinpoint the biggest technical limitation for each based on recent reviews."

    import uuid
    session_id = str(uuid.uuid4())

    # Pre-register the session so the frontend SSE can immediately lock onto it
    # even before main.py fully boots up
    db = _db()
    await db.execute(
        "INSERT INTO sessions (id, prompt) VALUES (?, ?)",
        (session_id, prompt)
    )
    await db.commit()

    # --no-synthesize-document prevents main.py from blocking on stdin
    subprocess.Popen(
        [sys.executable, "main.py", "--prompt", prompt, "--session-id", session_id, "--no-synthesize-document"],
        cwd=str(PROJECT_ROOT),
    )

    return {"status": "launched", "prompt": prompt, "session_id": session_id}


class SynthesizeRequest(BaseModel):
    session_id: str


@app.get("/api/synthesize")
async def get_synthesized_doc(session_id: Optional[str] = Query(None)):
    """Return the stored synthesized document for a session, or null."""
    db = _db()
    sid = await _resolve_session_id(session_id)
    if not sid:
        return {"content": None, "session_id": None}
    async with db.execute(
        "SELECT content, created_at FROM synthesized_documents WHERE session_id = ?",
        (sid,),
    ) as cur:
        row = await cur.fetchone()
        if row:
            return {"session_id": sid, "content": row[0], "created_at": row[1]}
        return {"session_id": sid, "content": None}


@app.post("/api/synthesize")
async def synthesize_document(body: SynthesizeRequest):
    """Run document synthesis for the given session and store result in DB."""
    if _genai is None:
        return {"status": "error", "detail": "google-genai not installed"}

    db = _db()
    sid = body.session_id

    # Check if already synthesized (use shared connection for quick reads)
    async with db.execute(
        "SELECT content FROM synthesized_documents WHERE session_id = ?", (sid,)
    ) as cur:
        existing = await cur.fetchone()
        if existing:
            return {"status": "already_exists", "content": existing[0]}

    # Use a dedicated connection for the multi-step read queries to avoid
    # conflicting with the shared connection's pending cursors.
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as rdb:
        rdb.row_factory = aiosqlite.Row
        await rdb.execute("PRAGMA journal_mode=WAL")

        # Fetch posts
        async with rdb.execute(
            "SELECT p.id, p.agent_id, p.content, COUNT(u.agent_id) as upvotes "
            "FROM posts p LEFT JOIN upvotes u ON p.id = u.post_id "
            "WHERE p.session_id = ? GROUP BY p.id ORDER BY upvotes DESC",
            (sid,)
        ) as cur:
            posts = await cur.fetchall()

        if not posts:
            return {"status": "error", "detail": "No posts found for this session."}

        board_text = ""
        for post in posts:
            post_id = post[0]
            agent = post[1]
            content = post[2]
            upvotes = post[3]
            board_text += f"\n--- POST {post_id} by {agent} ({upvotes} upvotes) ---\n{content}\n"

            async with rdb.execute(
                "SELECT agent_id, content FROM comments "
                "WHERE post_id = ? AND session_id = ? ORDER BY created_at",
                (post_id, sid)
            ) as ccur:
                comments = await ccur.fetchall()

            if comments:
                board_text += "Comments:\n"
        # Fetch session prompt
        async with rdb.execute(
            "SELECT prompt FROM sessions WHERE id = ?", (sid,)
        ) as cur:
            row = await cur.fetchone()
            user_prompt = row[0] if row else "Unknown challenge"

    import os
    from dotenv import load_dotenv
    load_dotenv()

    config = Config()
    client = _genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    sys_prompt = (
        "You are an expert synthesizer. Read the brainstorming board and produce a highly "
        "refined, professional markdown document that extracts the best ideas, combines them "
        "logically, assesses viability based on the debate, and presents a cohesive solution."
    )
    user_msg = (
        f"Challenge: {user_prompt}\n\nBoard Content:\n{board_text}\n\n"
        "Please generate the final document."
    )

    try:
        # Use synchronous API in a thread to avoid async httpx client
        # initialisation issues with genai SDK on Python 3.9.
        def _call_gemini():
            return client.models.generate_content(
                model=config.model,
                contents=user_msg,
                config=_types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    temperature=0.4,
                ),
            )

        response = await asyncio.to_thread(_call_gemini)
        doc_content = response.text
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    now = _dt.utcnow().isoformat() + "Z"
    await db.execute(
        "INSERT OR REPLACE INTO synthesized_documents (session_id, content, created_at) "
        "VALUES (?, ?, ?)",
        (sid, doc_content, now)
    )
    await db.commit()

    return {"status": "ok", "content": doc_content, "created_at": now}


# ── SSE Stream ──────────────────────────────────────────────────────────────


@app.get("/api/stream")
async def stream_events(
    request: Request,
    session_id: Optional[str] = Query(None),
):
    """Server-Sent Events: pushes new posts/comments/upvotes in real time."""
    sid = await _resolve_session_id(session_id)

    async def event_generator():
        db = _db()
        last_post_ts: Optional[str] = None
        last_comment_ts: Optional[str] = None
        last_upvote_ts: Optional[str] = None

        # Seed timestamps with current latest so we only stream NEW records
        if sid:
            async with db.execute(
                "SELECT MAX(created_at) FROM posts WHERE session_id = ?", (sid,)
            ) as cur:
                row = await cur.fetchone()
                last_post_ts = row[0] if row and row[0] else None

            async with db.execute(
                "SELECT MAX(created_at) FROM comments WHERE session_id = ?", (sid,)
            ) as cur:
                row = await cur.fetchone()
                last_comment_ts = row[0] if row and row[0] else None

            async with db.execute(
                "SELECT MAX(created_at) FROM upvotes WHERE session_id = ?", (sid,)
            ) as cur:
                row = await cur.fetchone()
                last_upvote_ts = row[0] if row and row[0] else None

        # Send initial connected event
        yield f"event: connected\ndata: {json.dumps({'session_id': sid})}\n\n"

        idle_cycles = 0

        while True:
            if await request.is_disconnected():
                break

            had_events = False

            if sid:
                # ── New posts ──────────────────────────────────────────
                if last_post_ts:
                    post_query = (
                        "SELECT id, agent_id, content, created_at "
                        "FROM posts WHERE session_id = ? AND created_at > ? "
                        "ORDER BY created_at ASC"
                    )
                    post_params = (sid, last_post_ts)
                else:
                    post_query = (
                        "SELECT id, agent_id, content, created_at "
                        "FROM posts WHERE session_id = ? "
                        "ORDER BY created_at ASC"
                    )
                    post_params = (sid,)

                async with db.execute(post_query, post_params) as cur:
                    async for row in cur:
                        event_data = {
                            "type": "new_post",
                            "data": {
                                "id": row[0],
                                "agent_id": row[1],
                                "content": row[2],
                                "created_at": row[3],
                                "upvotes": 0,
                                "comments": [],
                            },
                        }
                        yield f"event: new_post\ndata: {json.dumps(event_data)}\n\n"
                        last_post_ts = row[3]
                        had_events = True

                # ── New comments ───────────────────────────────────────
                if last_comment_ts:
                    comment_query = (
                        "SELECT id, post_id, agent_id, content, created_at "
                        "FROM comments WHERE session_id = ? AND created_at > ? "
                        "ORDER BY created_at ASC"
                    )
                    comment_params = (sid, last_comment_ts)
                else:
                    comment_query = (
                        "SELECT id, post_id, agent_id, content, created_at "
                        "FROM comments WHERE session_id = ? "
                        "ORDER BY created_at ASC"
                    )
                    comment_params = (sid,)

                async with db.execute(comment_query, comment_params) as cur:
                    async for row in cur:
                        event_data = {
                            "type": "new_comment",
                            "data": {
                                "id": row[0],
                                "post_id": row[1],
                                "agent_id": row[2],
                                "content": row[3],
                                "created_at": row[4],
                            },
                        }
                        yield f"event: new_comment\ndata: {json.dumps(event_data)}\n\n"
                        last_comment_ts = row[4]
                        had_events = True

                # ── New upvotes ────────────────────────────────────────
                if last_upvote_ts:
                    upvote_query = (
                        "SELECT post_id, agent_id, created_at "
                        "FROM upvotes WHERE session_id = ? AND created_at > ? "
                        "ORDER BY created_at ASC"
                    )
                    upvote_params = (sid, last_upvote_ts)
                else:
                    upvote_query = (
                        "SELECT post_id, agent_id, created_at "
                        "FROM upvotes WHERE session_id = ? "
                        "ORDER BY created_at ASC"
                    )
                    upvote_params = (sid,)

                async with db.execute(upvote_query, upvote_params) as cur:
                    async for row in cur:
                        event_data = {
                            "type": "new_upvote",
                            "data": {
                                "post_id": row[0],
                                "agent_id": row[1],
                                "created_at": row[2],
                            },
                        }
                        yield f"event: new_upvote\ndata: {json.dumps(event_data)}\n\n"
                        last_upvote_ts = row[2]
                        had_events = True

            if had_events:
                idle_cycles = 0
            else:
                idle_cycles += 1
                # Send keepalive every ~15s (30 cycles × 0.5s)
                if idle_cycles >= 30:
                    yield ": keepalive\n\n"
                    idle_cycles = 0

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
