import asyncio
import os
import sys
from dotenv import load_dotenv
from google import genai
from board import Board
from agent import run_agent
from config import Config

load_dotenv()  # Load GOOGLE_API_KEY from .env if present


async def main():
    config = Config()

    # Single shared client — created once, reused by every agent every round
    client = genai.Client()

    # Allow overriding the model from CLI: python main.py --model gemini-2.5-pro
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        config.model = sys.argv[idx + 1]

    user_prompt = (
        input("Creative challenge (or press Enter for default): ").strip()
        or "Generate ad campaign concepts for a sustainable fashion brand's Super Bowl spot"
    )

    # Wipe old DB so each run starts fresh
    if os.path.exists(config.db_path):
        os.remove(config.db_path)

    board = Board(config.db_path)
    await board.init()

    agent_ids = [f"Agent-{i+1}" for i in range(config.num_agents)]

    print(f"\n🚀 Launching {config.num_agents} agents × {config.num_rounds} rounds")
    print(f"   Model: {config.model}  |  DB: {config.db_path}\n")
    print(f'   Challenge: "{user_prompt}"\n')
    print("─" * 60)

    # Run all agents concurrently — true swarm, no coordination
    tasks = [
        run_agent(agent_id, user_prompt, board, config, client)
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

    await board.close()


if __name__ == "__main__":
    asyncio.run(main())
