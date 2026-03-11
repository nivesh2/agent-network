import aiosqlite
import uuid


class Board:
    def __init__(self, db_path: str, session_id: str):
        self.db_path = db_path
        self.session_id = session_id
        self.db = None

    async def init(self):
        self.db = await aiosqlite.connect(self.db_path, timeout=30.0)
        # WAL mode: allows concurrent reads during writes — critical for parallel agents
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                prompt      TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS posts (
                id          TEXT PRIMARY KEY,
                session_id  TEXT REFERENCES sessions(id),
                agent_id    TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS comments (
                id          TEXT PRIMARY KEY,
                session_id  TEXT REFERENCES sessions(id),
                post_id     TEXT REFERENCES posts(id),
                agent_id    TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS upvotes (
                session_id  TEXT REFERENCES sessions(id),
                post_id     TEXT REFERENCES posts(id),
                agent_id    TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (post_id, agent_id)
            );
            CREATE TABLE IF NOT EXISTS searches (
                id          TEXT PRIMARY KEY,
                session_id  TEXT REFERENCES sessions(id),
                agent_id    TEXT NOT NULL,
                query       TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS intents (
                session_id  TEXT REFERENCES sessions(id),
                round_num   INTEGER NOT NULL,
                agent_id    TEXT NOT NULL,
                intent      TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, round_num, agent_id)
            );
            CREATE TABLE IF NOT EXISTS seen_posts (
                session_id  TEXT REFERENCES sessions(id),
                agent_id    TEXT NOT NULL,
                post_id     TEXT REFERENCES posts(id),
                PRIMARY KEY (agent_id, post_id)
            );
            CREATE TABLE IF NOT EXISTS active_search_lock (
                session_id  TEXT PRIMARY KEY REFERENCES sessions(id),
                agent_id    TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    # ── Writes ────────────────────────────────────────────────────────────────

    async def create_post(self, agent_id: str, content: str) -> str:
        post_id = str(uuid.uuid4())[:8]
        await self.db.execute(
            "INSERT INTO posts (id, session_id, agent_id, content) VALUES (?, ?, ?, ?)",
            (post_id, self.session_id, agent_id, content)
        )
        await self.db.commit()
        return post_id

    async def create_comment(self, agent_id: str, post_id: str, content: str) -> str:
        comment_id = str(uuid.uuid4())[:8]
        await self.db.execute(
            "INSERT INTO comments (id, session_id, post_id, agent_id, content) VALUES (?, ?, ?, ?, ?)",
            (comment_id, self.session_id, post_id, agent_id, content)
        )
        return comment_id

    async def create_search(self, agent_id: str, query: str) -> str:
        search_id = str(uuid.uuid4())[:8]
        await self.db.execute(
            "INSERT INTO searches (id, session_id, agent_id, query) VALUES (?, ?, ?, ?)",
            (search_id, self.session_id, agent_id, query)
        )
        await self.db.commit()
        return search_id

    async def register_intent(self, round_num: int, agent_id: str, intent: str):
        """Phase 1: Record what the agent intends to do this round."""
        await self.db.execute(
            "INSERT OR REPLACE INTO intents (session_id, round_num, agent_id, intent) VALUES (?, ?, ?, ?)",
            (self.session_id, round_num, agent_id, intent)
        )
        await self.db.commit()

    async def upvote(self, agent_id: str, post_id: str) -> bool:
        try:
            await self.db.execute(
                "INSERT INTO upvotes (session_id, post_id, agent_id) VALUES (?, ?, ?)",
                (self.session_id, post_id, agent_id)
            )
            await self.db.commit()
            return True
        except Exception:
            return False  # Already upvoted (PRIMARY KEY constraint)

    async def mark_seen(self, agent_id: str, post_ids: list[str]):
        """Track which posts an agent has read to drive the explore feed."""
        for post_id in post_ids:
            try:
                await self.db.execute(
                    "INSERT OR IGNORE INTO seen_posts (session_id, agent_id, post_id) VALUES (?, ?, ?)",
                    (self.session_id, agent_id, post_id)
                )
            except Exception:
                pass
        await self.db.commit()

    async def check_consensus(self, threshold: int) -> bool:
        """Check if any post in the session has reached the consensus threshold."""
        cursor = await self.db.execute(
            "SELECT COUNT(agent_id) as upvotes FROM upvotes WHERE session_id = ? "
            "GROUP BY post_id ORDER BY upvotes DESC LIMIT 1",
            (self.session_id,)
        )
        row = await cursor.fetchone()
        return (row and row[0] >= threshold)

    async def acquire_search_lock(self, agent_id: str) -> bool:
        """Attempt to acquire the global search lock for this session. Returns True if successful."""
        try:
            # Check if anyone currently holds the lock for this session
            cursor = await self.db.execute(
                "SELECT agent_id, created_at FROM active_search_lock WHERE session_id = ?",
                (self.session_id,)
            )
            row = await cursor.fetchone()
            if row is not None:
                holding_agent = row[0]
                created_at_str = row[1]
                print(f"  [LOCK DIAGNOSTIC] {agent_id} sees lock held by {holding_agent} since {created_at_str}")
                
                # Parse created_at to check if it's a stale lock (older than 30s)
                # SQLite CURRENT_TIMESTAMP is 'YYYY-MM-DD HH:MM:SS' in UTC
                from datetime import datetime
                try:
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                    if (datetime.utcnow() - created_at).total_seconds() > 30:
                        # Stale lock: delete it and let someone else take over
                        await self.db.execute("DELETE FROM active_search_lock WHERE session_id = ?", (self.session_id,))
                        await self.db.commit()
                        row = None # Proceed to grab it below
                except Exception:
                    pass

                if row is not None:
                    # Lock is indeed actively held
                    if holding_agent == agent_id:
                         # We somehow hold it (e.g. from a previous retry)
                         return True
                    return False

            # No one has it, try to insert
            await self.db.execute(
                "INSERT INTO active_search_lock (session_id, agent_id) VALUES (?, ?)",
                (self.session_id, agent_id)
            )
            await self.db.commit()
            print(f"  [LOCK DIAGNOSTIC] {agent_id} **ACQUIRED** lock.")
            return True
        except Exception as e:
            # Catch PRIMARY KEY violation if another agent inserted right after our SELECT
            print(f"  [LOCK DIAGNOSTIC] {agent_id} failed to insert lock due to exception: {e}")
            return False

    async def release_search_lock(self, agent_id: str):
        """Release the global search lock."""
        await self.db.execute(
            "DELETE FROM active_search_lock WHERE session_id = ? AND agent_id = ?",
            (self.session_id, agent_id)
        )
        await self.db.commit()

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def get_intents(self, round_num: int, exclude_agent: str = None) -> list[dict]:
        """Phase 2: Read what other agents are planning to do right now."""
        query = "SELECT agent_id, intent FROM intents WHERE session_id = ? AND round_num = ?"
        params = [self.session_id, round_num]
        
        if exclude_agent:
            query += " AND agent_id != ?"
            params.append(exclude_agent)
            
        cursor = await self.db.execute(query, params)
        return [{"agent_id": r[0], "intent": r[1]} for r in await cursor.fetchall()]

    async def get_recent_searches(self, limit: int = 15) -> list[str]:
        """Fetch the most recent specific queries searched by the swarm."""
        cursor = await self.db.execute(
            "SELECT DISTINCT query FROM searches WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (self.session_id, limit)
        )
        return [r[0] for r in await cursor.fetchall()]

    async def get_top_posts(self, limit: int = 5) -> list[dict]:
        """Posts ordered by upvote count descending."""
        cursor = await self.db.execute("""
            SELECT p.id, p.agent_id, p.content, p.created_at,
                   COUNT(u.agent_id) as upvotes
            FROM posts p
            LEFT JOIN upvotes u ON p.id = u.post_id
            WHERE p.session_id = ?
            GROUP BY p.id
            ORDER BY upvotes DESC
            LIMIT ?
        """, (self.session_id, limit,))
        rows = await cursor.fetchall()
        return [self._row_to_post(r) for r in rows]

    async def get_unseen_posts(self, agent_id: str, limit: int = 5) -> list[dict]:
        """Newest posts this specific agent hasn't read yet."""
        cursor = await self.db.execute(
            "SELECT p.id, p.agent_id, p.content, p.created_at, "
            "COUNT(u.agent_id) as upvotes "
            "FROM posts p "
            "LEFT JOIN upvotes u ON p.id = u.post_id "
            "WHERE p.session_id = ? "
            "AND p.id NOT IN (SELECT post_id FROM seen_posts WHERE agent_id = ? AND session_id = ?) "
            "GROUP BY p.id "
            "ORDER BY p.created_at DESC LIMIT ?",
            (self.session_id, agent_id, self.session_id, limit)
        )
        rows = await cursor.fetchall()
        return [self._row_to_post(r) for r in rows]

    async def get_recent_posts(self, limit: int = 5) -> list[dict]:
        """Newest posts globally — fallback when agent has seen everything."""
        cursor = await self.db.execute(
            "SELECT id, agent_id, content, created_at, 0 as upvotes "
            "FROM posts WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (self.session_id, limit,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_post(r) for r in rows]

    async def get_comments(self, post_id: str) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT id, agent_id, content, created_at FROM comments "
            "WHERE post_id = ? AND session_id = ? ORDER BY created_at",
            (post_id, self.session_id)
        )
        return [
            {"id": r[0], "agent_id": r[1], "content": r[2], "created_at": r[3]}
            for r in await cursor.fetchall()
        ]

    async def get_post(self, post_id: str):
        """Fetch a single post by ID."""
        cursor = await self.db.execute(
            "SELECT id, agent_id, content, created_at FROM posts "
            "WHERE id = ? AND session_id = ?",
            (post_id, self.session_id)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {"id": row[0], "agent_id": row[1], "content": row[2], "created_at": row[3]}

    async def get_results(self, top_k: int = 3) -> list[dict]:
        """Final output: top-k posts with their full comment threads."""
        posts = await self.get_top_posts(top_k)
        for post in posts:
            post["comments"] = await self.get_comments(post["id"])
        return posts

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _row_to_post(self, row) -> dict:
        return {
            "id": row[0], "agent_id": row[1], "content": row[2],
            "created_at": row[3], "upvotes": row[4]
        }

    async def close(self):
        if self.db:
            await self.db.close()
