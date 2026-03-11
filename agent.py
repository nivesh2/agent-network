from google.genai import types
from feed import get_feed, format_feed_for_prompt

# Simple ANSI colors for console output
COLORS = ["\033[32m", "\033[34m", "\033[35m", "\033[36m", "\033[33m", "\033[31m", "\033[92m", "\033[94m", "\033[95m", "\033[96m"]
RESET = "\033[0m"

def get_agent_color(name: str) -> str:
    return COLORS[hash(name) % len(COLORS)]

def get_intent_prompt(agent_id: str, user_prompt: str, searches_left: int) -> str:
    search_instruction = (
        f"You have {searches_left} search_web calls left for the ENTIRE game. Hoard them. "
        if searches_left > 0
        else "You are out of search_web calls. Do NOT intend to search. "
    )
    return ""

def get_system_prompt(agent_id: str, user_prompt: str, searches_left: int, config) -> str:
    search_instruction = (
        f"You have {searches_left} search_web calls remaining. Early in the game, you should prioritize using search_web to lay a factual foundation before debating."
        if searches_left > 0
        else "You have exhausted your search_web calls. You MUST rely on the board and synthesize."
    )

    return f"""\
You are playing a cooperative game in a "Collaborative Session" where your goal is to maximize your Influence Points.
{search_instruction}

RULES FOR SCORING INFLUENCE POINTS (Play to win):
- [+15 points] The BUILDER: Use `create_comment` to add critical nuances, correct flaws, or expand on someone else's post. Deep discussion is the most valuable action.
- [+10 points] The RESEARCHER: Use `search_web` early in the session to establish a foundation of ground truth facts. CRITICAL: Choose only ONE topic from a multi-topic request to search. Leave the remaining topics for your team.
- [+5 points] The SUPPORTER: Use `upvote_post` on a winning strategy you agree with. 
- [0 points] The OBSERVER: If the board is empty or lacks clear direction, and you cannot search, you MUST use `wait_and_observe` to yield your turn.
- [0 points] The LONE WOLF: Ignoring the board to post an entirely new idea without referencing others.
- [-5 points] THE WASTER: Using `search_web` frivolously late in the game when consensus is already forming. (Only ONE agent can search the network at a time).
- [-20 points] THE HOARDER: Using `search_web` to search for multiple topics or the entire user request at once. You must divide the work and focus your search on just ONE single aspect of the challenge.
- [-50 points] THE HALLUCINATOR: Posting or commenting made-up facts. You MUST link to sources and use hard facts.
- [-100 points] THE PREMATURE VOTER: Using `upvote_post` on a post before YOU have commented on it, OR before the post has a healthy debate (at least {config.num_agents - 1} total comments). You MUST debate using `create_comment` first!
- [-100 points] THE MONOLOGUER: Using `create_comment` on a post you ALREADY just commented on. You MUST wait for someone else to reply before you speak again.

Read the board very carefully. 
- Do not repeat information already stated on the board.
- Coordinate with others: If you see another agent has already researched one part of the challenge, focus your actions on the unresearched parts.
- Your ultimate goal is to force the board to reach Consensus on the best idea rapidly.

Choose exactly ONE action: create_post, create_comment, upvote_post, wait_and_observe, or search_web.

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
    types.FunctionDeclaration(
        name="wait_and_observe",
        description="Yield your turn. Use this if the board is empty but you are unable to search, or if you are waiting for others to post.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "reason": types.Schema(type="STRING", description="Why you are waiting")
            },
            required=["reason"]
        )
    ),
])

import asyncio

async def run_agent(agent_id: str, user_prompt: str, board, config, client):
    """
    Run one agent for N rounds. 
    Agents run entirely asynchronously. They rely on the board's active_search_lock 
    to coordinate scarce resources, without any artificial sleep delays or round barriers.
    """
    memory: list[str] = []
    searches_remaining = config.max_searches_per_agent
    successful_actions = 0
    attempt_num = 1
    max_attempts = config.num_rounds * 3

    while successful_actions < config.num_rounds and attempt_num <= max_attempts:
        # 0. Check for Consensus Early Exit
        if await board.check_consensus(config.consensus_threshold):
            print(f"[{get_agent_color(agent_id)}{agent_id:8}{RESET}] \033[92m🛑 Consensus Reached! Exiting early.\033[0m")
            break

        # ==========================================================
        # ACTION GENERATION
        # ==========================================================
        feed = await get_feed(board, agent_id, config.feed_size, config.explore_ratio)
        feed_text = format_feed_for_prompt(feed)
        
        memory_text = "\n\n".join(memory) if memory else "No past actions yet."
        
        # Fetch global search history
        recent_searches = await board.get_recent_searches(limit=15)
        searches_text = "\n".join([f"- \"{s}\"" for s in recent_searches]) if recent_searches else "None yet."

        action_message = (
            f"--- BOARD (Action {successful_actions + 1}/{config.num_rounds}) ---\n"
            f"{feed_text}\n"
            f"--- END BOARD ---\n\n"
            f"--- RECENTLY SEARCHED QUERIES (By entire swarm) ---\n"
            f"{searches_text}\n"
            f"--- END RECENT SEARCHES ---\n\n"
            f"--- YOUR MEMORY ---\n"
            f"{memory_text}\n"
            f"--- END MEMORY ---\n\n"
            f"You are {agent_id}. Look at what other agents just posted on the board.\n"
            f"There are {config.num_agents} total agents in this session.\n"
            f"Choose exactly ONE tool action."
        )

        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=action_message,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(agent_id, user_prompt, searches_remaining, config),
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
                print(f"  [{agent_id}] Attempt {attempt_num}: No tool call in response — skipping")
                memory.append(f"Attempt {attempt_num}: Action None (Skipped)")
                attempt_num += 1
                await asyncio.sleep(1.0)
                continue

            fn_name = fn_call.name
            fn_args = dict(fn_call.args)

            if fn_name == "search_web":
                if searches_remaining <= 0:
                    print(f"  [{agent_id}] Attempt {attempt_num}: Attempted to search, but out of quota.")
                    memory.append(f"Attempt {attempt_num}: FAILED Out of Search Quota.")
                    attempt_num += 1
                    await asyncio.sleep(1.0)
                    continue
                
                # Try to acquire the global search lock
                if not await board.acquire_search_lock(agent_id):
                    print(f"  [{agent_id}] Attempt {attempt_num}: Search Network Locked.")
                    memory.append(f"Attempt {attempt_num}: FAILED Search. Network Busy. Another agent is currently researching. Use 'wait_and_observe' or comment.")
                    attempt_num += 1
                    await asyncio.sleep(2.0)  # Wait for the other agent to finish searching
                    continue

                searches_remaining -= 1
                successful_actions += 1
                try:
                    color = get_agent_color(agent_id)
                    await dispatch_tool(agent_id, fn_name, fn_args, board, client)
                    if thoughts.strip():
                        memory.append(f"Action {successful_actions}: Thought [{thoughts.strip()}]\nAction {fn_name}({fn_args})")
                    else:
                        memory.append(f"Action {successful_actions}: Action {fn_name}({fn_args})")
                    print(f"[{color}{agent_id:8}{RESET}] A{successful_actions:02d} | \033[1m{fn_name:14}\033[0m | \033[92m📝 {fn_args.get('query', '')[:50]}\033[0m")
                finally:
                    await board.release_search_lock(agent_id)
            elif fn_name == "wait_and_observe":
                # Agent yielded. Do not count as a successful action, but pause their loop.
                color = get_agent_color(agent_id)
                if thoughts.strip():
                    memory.append(f"Attempt {attempt_num}: Thought [{thoughts.strip()}]\nAction {fn_name}({fn_args})")
                else:
                    memory.append(f"Attempt {attempt_num}: Action {fn_name}({fn_args})")
                
                reason = str(fn_args.get("reason", "")).replace("\n", " ")
                print(f"[{color}{agent_id:8}{RESET}] -- | \033[1m{fn_name:14}\033[0m | \033[90m⏳ waiting\033[0m: {reason[:40]}")
                
                attempt_num += 1
                await asyncio.sleep(4.0) # Massive sleep to give the searching agent time to finish their Google API call
                continue # Skip the successful_actions increment below
            elif fn_name == "upvote_post":
                # Programmatically enforce the PREMATURE VOTER rule
                post_id = fn_args.get('post_id', '')
                post_obj = await board.get_post(post_id)
                comments = await board.get_comments(post_id)
                
                if post_obj and post_obj['agent_id'] == agent_id:
                    print(f"  [{agent_id}] Attempt {attempt_num}: Blocked self-upvote on {post_id}.")
                    memory.append(f"Attempt {attempt_num}: FAILED Upvote. PENALTY: -100 points. You cannot upvote your own post!")
                    attempt_num += 1
                    await asyncio.sleep(1.0)
                    continue

                # 1. Thread maturity check (N-1 comments required)
                required_comments = config.num_agents - 1
                if len(comments) < required_comments:
                    print(f"  [{agent_id}] Attempt {attempt_num}: Blocked premature upvote on {post_id} (only {len(comments)}/{required_comments} comments).")
                    memory.append(f"Attempt {attempt_num}: FAILED Upvote. PENALTY: -100 points. The thread only has {len(comments)} comments. Wait until there are at least {required_comments} total comments before upvoting!")
                    attempt_num += 1
                    await asyncio.sleep(1.0)
                    continue
                    
                # 2. Personal participation check (have THEY commented?)
                has_commented = any(c['agent_id'] == agent_id for c in comments)
                if not has_commented:
                    print(f"  [{agent_id}] Attempt {attempt_num}: Blocked upvote because they haven't commented on {post_id} yet.")
                    memory.append(f"Attempt {attempt_num}: FAILED Upvote. PENALTY: -100 points. You MUST personally use 'create_comment' on this thread before you are allowed to upvote it!")
                    attempt_num += 1
                    await asyncio.sleep(1.0)
                    continue

                successful_actions += 1
                color = get_agent_color(agent_id)
                await dispatch_tool(agent_id, fn_name, fn_args, board, client)

                if thoughts.strip():
                    memory.append(f"Action {successful_actions}: Thought [{thoughts.strip()}]\nAction {fn_name}({fn_args})")
                else:
                    memory.append(f"Action {successful_actions}: Action {fn_name}({fn_args})")
                
                action_snippet = f"\033[93m👍 post {post_id}\033[0m"
                print(f"[{color}{agent_id:8}{RESET}] A{successful_actions:02d} | \033[1m{fn_name:14}\033[0m | {action_snippet}")
                
            elif fn_name == "create_comment":
                # Programmatically enforce the MONOLOGUER rule
                post_id = fn_args.get('post_id', '')
                comments = await board.get_comments(post_id)
                
                # Check if the absolutely most recent comment on the thread is ALSO from them
                if comments and comments[-1]['agent_id'] == agent_id:
                    print(f"  [{agent_id}] Attempt {attempt_num}: Blocked consecutive double-comment on {post_id}.")
                    memory.append(f"Attempt {attempt_num}: FAILED Comment. PENALTY: -100 points. You just commented on this thread! Wait for another agent to reply to you before commenting again.")
                    attempt_num += 1
                    await asyncio.sleep(1.0)
                    continue

                successful_actions += 1
                color = get_agent_color(agent_id)
                await dispatch_tool(agent_id, fn_name, fn_args, board, client)

                if thoughts.strip():
                    memory.append(f"Action {successful_actions}: Thought [{thoughts.strip()}]\nAction {fn_name}({fn_args})")
                else:
                    memory.append(f"Action {successful_actions}: Action {fn_name}({fn_args})")

                content = str(fn_args.get("content", "")).replace("\n", " ")
                action_snippet = f"\033[96m💬 on {post_id}\033[0m: {content[:40]}{'...' if len(content) > 40 else ''}"
                print(f"[{color}{agent_id:8}{RESET}] A{successful_actions:02d} | \033[1m{fn_name:14}\033[0m | {action_snippet}")
                
            else:
                successful_actions += 1
                color = get_agent_color(agent_id)
                await dispatch_tool(agent_id, fn_name, fn_args, board, client)

                if thoughts.strip():
                    memory.append(f"Action {successful_actions}: Thought [{thoughts.strip()}]\nAction {fn_name}({fn_args})")
                else:
                    memory.append(f"Action {successful_actions}: Action {fn_name}({fn_args})")

                # Console output
                content = str(fn_args.get("content", "")).replace("\n", " ")
                action_snippet = f"\033[92m📝 {content[:50]}{'...' if len(content) > 50 else ''}\033[0m"

                print(f"[{color}{agent_id:8}{RESET}] A{successful_actions:02d} | \033[1m{fn_name:14}\033[0m | {action_snippet}")

            attempt_num += 1

        except Exception as e:
            print(f"  [{agent_id}] Attempt {attempt_num}: ERROR — {e}")
            attempt_num += 1

        # Minor async yield between real actions
        await asyncio.sleep(0.5)

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
        elif fn_name == "wait_and_observe":
            pass # No database action required. The agent simply yielded its turn.
        else:
            print(f"  [{agent_id}] Unknown tool: {fn_name}")
    except KeyError as e:
        print(f"  [{agent_id}] Missing argument {e} for {fn_name}")
    except Exception as e:
        print(f"  [{agent_id}] Tool dispatch error: {e}")
