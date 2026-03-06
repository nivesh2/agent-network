"""
Agora API — FastAPI data bridge for the React dashboard.

Reads from board.db (shared with agents) and exposes JSON + SSE endpoints:
  /api/sessions  –  aggregate stats & agent roster (session-scoped)
  /api/feed      –  posts + comments + upvotes (Top / Newest)
  /api/activity  –  unified timeline of recent actions
  /api/stream    –  SSE real-time stream of new posts/comments/upvotes
"""

import asyncio
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Configuration ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = str(PROJECT_ROOT / "board.db")

# ── App lifecycle ───────────────────────────────────────────────────────────
db_connection: aiosqlite.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection
    db_connection = await aiosqlite.connect(DB_PATH, uri=False)
    db_connection.row_factory = aiosqlite.Row
    await db_connection.execute("PRAGMA journal_mode=WAL")
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


async def _resolve_session_id(session_id: str | None) -> str | None:
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
async def get_sessions(session_id: str | None = Query(None)):
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
    session_id: str | None = Query(None),
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
    session_id: str | None = Query(None),
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

        ORDER BY created_at DESC
        LIMIT ?
    """

    activities = []
    async with db.execute(query, (sid, sid, sid, limit)) as cur:
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
        prompt = "Generate ad campaign concepts for a sustainable fashion brand's Super Bowl spot"

    subprocess.Popen(
        [sys.executable, "main.py", "--prompt", prompt],
        cwd=str(PROJECT_ROOT),
    )

    return {"status": "launched", "prompt": prompt}


# ── SSE Stream ──────────────────────────────────────────────────────────────


@app.get("/api/stream")
async def stream_events(
    request: Request,
    session_id: str | None = Query(None),
):
    """Server-Sent Events: pushes new posts/comments/upvotes in real time."""
    sid = await _resolve_session_id(session_id)

    async def event_generator():
        db = _db()
        last_post_ts: str | None = None
        last_comment_ts: str | None = None
        last_upvote_ts: str | None = None

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
