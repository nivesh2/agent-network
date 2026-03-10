from google.genai import types
from feed import get_feed, format_feed_for_prompt

# Simple ANSI colors for console output
COLORS = ["\033[32m", "\033[34m", "\033[35m", "\033[36m", "\033[33m", "\033[31m", "\033[92m", "\033[94m", "\033[95m", "\033[96m"]
RESET = "\033[0m"

def get_agent_color(name: str) -> str:
    return COLORS[hash(name) % len(COLORS)]

def get_intent_prompt(agent_id: str, user_prompt: str, searches_left: int) -> str:
    search_instruction = (
        f"You have {searches_left} search_web calls left. "
        if searches_left > 0
        else "You are out of search_web calls. Do NOT intend to search. "
    )
    return f"""\
You are {agent_id} in a highly cooperative "Collaborative Session". Analyze the board and declare your intent for this round.
{search_instruction}
Rule: DO NOT intend to search for any exact topics already listed under RECENTLY SEARCHED QUERIES. Find new angles.
Reply in EXACTLY one sentence starting with "I will...". Keep it very concrete. (e.g. "I will search_web for Limitless AI funding", "I will create_comment to critique Bjørn's strategy", or "I will upvote_post to support the winning idea").
Challenge: {user_prompt}\
"""

def get_system_prompt(agent_id: str, user_prompt: str, searches_left: int) -> str:
    search_instruction = (
        f"You have {searches_left} search_web calls remaining this session. Use them wisely "
        "if you lack real-world facts."
        if searches_left > 0
        else "You have exhausted your search_web calls. You MUST rely on the board and synthesize."
    )

    return f"""\
You are an intelligent agent in a rapid-response "Collaborative Session". Your goal is to help the swarm 
develop the most concrete, impactful, and fact-based strategy possible.

You share a board with other agents. Read the board and instantly adopt a role:
- If the board lacks facts, be the EXPLORER: use search_web to gather real-world data. Look at LIVE INTENTS of others to avoid duplicate searches.
- If you see a strong idea, be the BUILDER/CRITIC: use create_comment to debate, refine, or point out flaws in someone else's post. COLLABORATION IS KEY.
- If you see a winning strategy that you agree with, be the SUPPORTER: use upvote_post to help the swarm reach consensus.
- If there is enough raw data, be the SYNTHESIZER: use create_post to write a concrete final strategy combining the facts.

RULES:
1. Be highly collaborative. Engage with other agents' posts via comments and upvotes. Do not just act alone.
2. Be highly tactical and grounded in reality. No fluff. Where applicable, cite hard numbers.
3. {search_instruction}
4. Choose exactly ONE action: create_post, create_comment, upvote_post, or search_web.

Challenge: {user_prompt}\
"""

# Tool declarations using the Gemini function-calling schema
TOOL_DEFS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="create_post",
        description="Post a new idea to the board.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "content": types.Schema(
                    type="STRING",
                    description="BE specific and detailed."
                )
            },
            required=["content"]
        )
    ),
    types.FunctionDeclaration(
        name="create_comment",
        description="Comment on an existing post: critique, propose or build on it.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "post_id": types.Schema(type="STRING", description="ID of the post to comment on"),
                "content": types.Schema(type="STRING", description="Your feedback or refinement")
            },
            required=["post_id", "content"]
        )
    ),
    types.FunctionDeclaration(
        name="upvote_post",
        description="Upvote an interesting, relevant or strong post.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "post_id": types.Schema(type="STRING", description="ID of the post to upvote")
            },
            required=["post_id"]
        )
    ),
    types.FunctionDeclaration(
        name="search_web",
        description="Search the live web for ground truth, competitor data, or news. "
                    "Use this when you lack facts. Results post automatically as a RESEARCH DUMP.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query": types.Schema(type="STRING", description="A precise, targeted search query")
            },
            required=["query"]
        )
    ),
])

import asyncio

async def run_agent(agent_id: str, user_prompt: str, board, config, client, planning_barrier=None, action_barrier=None, intent_lock=None):
    """
    Run one agent for N rounds in a Two-Phase loop.
    Phase 1: Planning (Serialized to prevent intent collision)
    Phase 2: Action (Massively parallel execution based on intents)
    """

    memory: list[str] = []
    searches_remaining = config.max_searches_per_agent

    for round_num in range(1, config.num_rounds + 1):
        # 0. Check for Consensus Early Exit
        if await board.check_consensus(config.consensus_threshold):
            print(f"[{get_agent_color(agent_id)}{agent_id:8}{RESET}] \033[92m🛑 Consensus Reached! Exiting early.\033[0m")
            break

        # ==========================================================
        # PHASE 1: PLANNING
        # ==========================================================
        feed = await get_feed(board, agent_id, config.feed_size, config.explore_ratio)
        feed_text = format_feed_for_prompt(feed)
        
        memory_text = "\n\n".join(memory) if memory else "No past actions yet."
        
        # Fetch global search history
        recent_searches = await board.get_recent_searches(limit=15)
        searches_text = "\n".join([f"- \"{s}\"" for s in recent_searches]) if recent_searches else "None yet."

        if intent_lock:
            await intent_lock.acquire()

        try:
            # Re-read live intents sequentially
            current_intents = await board.get_intents(round_num)
            live_intent_text = "\n".join([f"- {i['agent_id']} plans to: {i['intent']}" for i in current_intents])
            if not live_intent_text:
                live_intent_text = "None yet."

            intent_message = (
                f"--- BOARD (Round {round_num}/{config.num_rounds}) ---\n"
                f"{feed_text}\n"
                f"--- END BOARD ---\n\n"
                f"--- RECENTLY SEARCHED QUERIES (By entire swarm) ---\n"
                f"{searches_text}\n"
                f"--- END RECENT SEARCHES ---\n\n"
                f"--- LIVE INTENTS DECLARED SO FAR THIS ROUND ---\n"
                f"{live_intent_text}\n"
                f"--- END LIVE INTENTS ---\n\n"
                f"--- YOUR MEMORY ---\n"
                f"{memory_text}\n"
                f"--- END MEMORY ---\n\n"
                f"What is your single-sentence intent for this round? Do NOT duplicate an intent already declared."
            )

            try:
                intent_response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash", # Use faster model for planning
                    contents=intent_message,
                    config=types.GenerateContentConfig(
                        system_instruction=get_intent_prompt(agent_id, user_prompt, searches_remaining),
                        temperature=0.2, # Low temp for rigid planning
                    ),
                )
                my_intent = intent_response.text.strip().replace("\n", " ")
            except Exception as e:
                print(f"[{agent_id}] Intent generation failed: {e}")
                my_intent = "I will observe the board."

            # Register intent to the database so others can see it
            await board.register_intent(round_num, agent_id, my_intent)
            
        finally:
            if intent_lock:
                intent_lock.release()

        # Synchronize Phase 1
        if planning_barrier:
            try:
                await planning_barrier.wait()
            except Exception:
                pass

        # ==========================================================
        # PHASE 2: ACTION
        # ==========================================================
        # Read what everyone ELSE just decided to do this round
        other_intents = await board.get_intents(round_num, exclude_agent=agent_id)
        intent_text = "\n".join([f"- {i['agent_id']} plans to: {i['intent']}" for i in other_intents])
        if not intent_text:
            intent_text = "None"

        action_message = (
            f"--- BOARD (Round {round_num}/{config.num_rounds}) ---\n"
            f"{feed_text}\n"
            f"--- END BOARD ---\n\n"
            f"--- RECENTLY SEARCHED QUERIES (By entire swarm) ---\n"
            f"{searches_text}\n"
            f"--- END RECENT SEARCHES ---\n\n"
            f"--- YOUR MEMORY ---\n"
            f"{memory_text}\n"
            f"--- END MEMORY ---\n\n"
            f"--- LIVE INTENTS OF OTHER AGENTS RIGHT NOW ---\n"
            f"{intent_text}\n"
            f"--- END LIVE INTENTS ---\n\n"
            f"You are {agent_id}. You planned to: '{my_intent}'. \n"
            f"If someone else's Live Intent conflicts with yours, OR if your intent matches a RECENTLY SEARCHED QUERY, PIVOT to a new action.\n"
            f"Choose exactly ONE tool action."
        )

        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=action_message,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(agent_id, user_prompt, searches_remaining),
                    tools=[TOOL_DEFS],
                    temperature=config.temperature,
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode="ANY"
                        )
                    ),
                ),
            )

            fn_call = None
            thoughts: str = ""
            for part in response.candidates[0].content.parts:
                if part.text:
                    thoughts += str(part.text) + "\n"
                if part.function_call is not None:
                    fn_call = part.function_call
                    break

            if fn_call is None:
                print(f"  [{agent_id}] Round {round_num}: No tool call in response — skipping")
                memory.append(f"Round {round_num}: Planned '{my_intent}' -> Action None (Skipped)")
                continue

            fn_name = fn_call.name
            fn_args = dict(fn_call.args)

            if fn_name == "search_web":
                if searches_remaining <= 0:
                    print(f"  [{agent_id}] Round {round_num}: Attempted to search, but out of quota.")
                    memory.append(f"Round {round_num}: Planned '{my_intent}' -> FAILED Out of Quota.")
                    if action_barrier:
                        await action_barrier.wait()
                    continue
                else:
                    searches_remaining -= 1

            color = get_agent_color(agent_id)
            await dispatch_tool(agent_id, fn_name, fn_args, board, client)

            if thoughts.strip():
                memory.append(f"Round {round_num}: Intent '{my_intent}'\nThought [{thoughts.strip()}]\nAction {fn_name}({fn_args})")
            else:
                memory.append(f"Round {round_num}: Intent '{my_intent}' -> Action {fn_name}({fn_args})")

            # Console output
            if fn_name == "upvote_post":
                action_snippet = f"\033[93m👍 post {fn_args.get('post_id', '')}\033[0m"
            elif fn_name == "create_comment":
                content = str(fn_args.get("content", "")).replace("\n", " ")
                action_snippet = f"\033[96m💬 on {fn_args.get('post_id', '')}\033[0m: {content[:40]}{'...' if len(content) > 40 else ''}"
            else:
                content = str(fn_args.get("content", "")).replace("\n", " ")
                action_snippet = f"\033[92m📝 {content[:50]}{'...' if len(content) > 50 else ''}\033[0m"

            print(f"[{color}{agent_id:8}{RESET}] R{round_num:02d} | \033[1m{fn_name:14}\033[0m | {action_snippet}")

        except Exception as e:
            print(f"  [{agent_id}] Round {round_num}: ERROR — {e}")

        # Synchronize Phase 2
        if action_barrier:
            try:
                await action_barrier.wait()
            except Exception:
                pass

async def dispatch_tool(agent_id: str, fn_name: str, fn_args: dict, board, client=None):
    """Route the LLM's chosen tool call to the actual board operation."""
    try:
        if fn_name == "create_post":
            await board.create_post(agent_id, fn_args["content"])
        elif fn_name == "create_comment":
            await board.create_comment(agent_id, fn_args["post_id"], fn_args["content"])
        elif fn_name == "upvote_post":
            await board.upvote(agent_id, fn_args["post_id"])
        elif fn_name == "search_web":
            if client is None:
                print(f"  [{agent_id}] Cannot search web: client is missing")
                return
            
            # Log the search event so the frontend Activity feed can see it
            await board.create_search(agent_id, fn_args["query"])

            search_response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=fn_args["query"],
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.0
                )
            )
            # Differentiate findings vs simple web results
            prefix = "🚨 FACT CHECK" if "check" in fn_args['query'].lower() or "verify" in fn_args['query'].lower() else "🔍 RESEARCH DUMP"
            search_summary = f"**{prefix}: '{fn_args['query']}'**\n\n{search_response.text}"
            await board.create_post(agent_id, search_summary)
        else:
            print(f"  [{agent_id}] Unknown tool: {fn_name}")
    except KeyError as e:
        print(f"  [{agent_id}] Missing argument {e} for {fn_name}")
    except Exception as e:
        print(f"  [{agent_id}] Tool dispatch error: {e}")
