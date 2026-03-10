import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from board import Board
from agent import run_agent
from config import Config

load_dotenv()  # Load GOOGLE_API_KEY from .env if present

class SimpleBarrier:
    def __init__(self, parties: int):
        self.parties = parties
        self._count = 0
        self._cond = asyncio.Condition()

    async def wait(self):
        async with self._cond:
            self._count += 1
            if self._count == self.parties:
                self._count = 0
                self._cond.notify_all()
            else:
                await self._cond.wait()


async def main():
    config = Config()
    project_root = Path(__file__).resolve().parent

    # Single shared client — created once, reused by every agent every round
    client = genai.Client()

    # Allow overriding the model from CLI: python main.py --model gemini-2.5-pro
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        config.model = sys.argv[idx + 1]

    # Accept prompt from CLI: python main.py --prompt "..."
    # Falls back to a default if not provided (useful for direct CLI runs)
    if "--prompt" in sys.argv:
        idx = sys.argv.index("--prompt")
        user_prompt = sys.argv[idx + 1]
    else:
        user_prompt = "Conduct a rapid competitive due diligence on the top 3 emerging AI wearable devices (e.g. Humane Pin, Rabbit R1, Limitless). Aggregate their current pricing, funding amounts, and pinpoint the biggest technical limitation for each based on recent reviews or facts."

    # Create a new session for this run — no longer wipes the DB
    session_id = str(uuid.uuid4())

    board = Board(config.db_path, session_id)
    await board.init()

    # Register session in the DB
    await board.db.execute(
        "INSERT INTO sessions (id, prompt) VALUES (?, ?)",
        (session_id, user_prompt)
    )
    await board.db.commit()

    # Scandinavian agent personas
    AGENT_PERSONAS = [
        "Bjørn", "Sigrid", "Lars", "Astrid", "Erik",
        "Ingrid", "Sven", "Freya", "Gunnar", "Maja",
        "Ragnar", "Elsa", "Leif", "Karin", "Tor",
    ]
    agent_ids = [
        AGENT_PERSONAS[i % len(AGENT_PERSONAS)]
        if i < len(AGENT_PERSONAS)
        else f"{AGENT_PERSONAS[i % len(AGENT_PERSONAS)]}-{i // len(AGENT_PERSONAS) + 1}"
        for i in range(config.num_agents)
    ]

    print(f"\n🚀 Launching {config.num_agents} agents × {config.num_rounds} rounds")
    print(f"   Model: {config.model}  |  DB: {config.db_path}")
    print(f"   Session: {session_id}\n")
    print(f'   Challenge: "{user_prompt}"\n')
    print("─" * 60)

    # Run all agents concurrently with a two-phase barrier system
    planning_barrier = SimpleBarrier(config.num_agents)
    action_barrier = SimpleBarrier(config.num_agents)
    intent_lock = asyncio.Lock()
    tasks = [
        run_agent(agent_id, user_prompt, board, config, client, planning_barrier, action_barrier, intent_lock)
        for agent_id in agent_ids
    ]
    await asyncio.gather(*tasks)

    # ── Final results ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"🏆  TOP {config.top_k} CONCEPTS (by upvotes)")
    print("=" * 60 + "\n")

    results = await board.get_results(config.top_k)
    if not results:
        print("No posts were created. Try increasing num_rounds.")
    else:
        for i, post in enumerate(results, 1):
            print(f"#{i}  ⬆ {post['upvotes']}  [{post['agent_id']}]")
            print(f"     {post['content']}")
            if post["comments"]:
                print("     Debate thread:")
                for c in post["comments"]:
                    print(f"       💬 {c['agent_id']}: {c['content']}")
            print()

    # ── Final Document Synthesis ───────────────────────────────────────────────
    # Skip synthesis entirely when spawned by the API (avoids blocking on stdin)
    no_synthesize = "--no-synthesize-document" in sys.argv
    if not no_synthesize:
        synthesize = input("\nGenerate a final synthesized document? [y/N]: ").strip().lower()
    else:
        synthesize = 'n'
    if synthesize == 'y':
        print("\n📝 Synthesizing final document...")
        
        posts_query = await board.db.execute(
            "SELECT p.id, p.agent_id, p.content, COUNT(u.agent_id) as upvotes "
            "FROM posts p LEFT JOIN upvotes u ON p.id = u.post_id "
            "WHERE p.session_id = ? GROUP BY p.id ORDER BY upvotes DESC",
            (session_id,)
        )
        posts = await posts_query.fetchall()
        board_text = ""
        for post in posts:
            post_id, agent, content, upvotes = post
            board_text += f"\n--- POST {post_id} by {agent} ({upvotes} upvotes) ---\n{content}\n"
            
            comments_query = await board.db.execute(
                "SELECT agent_id, content FROM comments WHERE post_id = ? AND session_id = ? ORDER BY created_at",
                (post_id, session_id)
            )
            comments = await comments_query.fetchall()
            if comments:
                board_text += "Comments:\n"
                for c_agent, c_content in comments:
                    board_text += f" - {c_agent}: {c_content}\n"
        
        sys_prompt = "You are an expert synthesizer. Your job is to read the brainstorming board and produce a highly refined, professional markdown document that extracts the best ideas, combines them logically, assesses their viability based on the debate, and presents a cohesive solution."
        user_msg = f"Challenge: {user_prompt}\n\nBoard Content:\n{board_text}\n\nPlease generate the final document."
        
        from google.genai import types
        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    temperature=0.4,
                ),
            )
            file_name = f"refined_document_{session_id[:8]}.md"
            with open(file_name, "w") as f:
                f.write(response.text)
            print(f"✅ Saved to {file_name}")
        except Exception as e:
            print(f"❌ Error during synthesis: {e}")

    # Persist results for the React dashboard to consume.
    try:
        frontend_public = project_root / "ui" / "frontend" / "public"
        frontend_public.mkdir(parents=True, exist_ok=True)
        out_path = frontend_public / "results.json"
        payload = {
            "challenge": user_prompt,
            "model": config.model,
            "num_agents": config.num_agents,
            "num_rounds": config.num_rounds,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "results": results,
        }
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"📄 Wrote results for dashboard to {out_path}")
    except Exception as e:  # pragma: no cover - defensive
        print(f"⚠️ Failed to write results.json for dashboard: {e}")

    await board.close()


if __name__ == "__main__":
    asyncio.run(main())
