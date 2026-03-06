from google.genai import types
from feed import get_feed, format_feed_for_prompt

def get_system_prompt(agent_id: str, user_prompt: str) -> str:
    return f"""\
You are an intelligent agent participating in a challenge. Your stance is both competitive and collaborative.

Shared board where you can read what others have posted,
post your own ideas, comment on existing ideas, or upvote ideas you think are strong.

1. Read the board and analyze what's been said.
2. Be competitive: be critical of weak ideas, debate them, and strive to get out the best ideas to WIN.
3. Be collaborative: upvote if something is genuinely great and build upon strong concepts.
4. Actions: post, comment, upvote posts, or search_web.

Your ultimate goal is to have the winning ideas, the most concrete plan, the most impactful solution.


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
        description="Search the web for current information. The search results will be posted to the board automatically.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query": types.Schema(type="STRING", description="The search query")
            },
            required=["query"]
        )
    ),
])


async def run_agent(agent_id: str, user_prompt: str, board, config, client):
    """
    Run one agent for N rounds. Fully independent — no direct knowledge of other agents.
    Agents collaborate only through the shared board.
    """

    memory: list[str] = []

    for round_num in range(1, config.num_rounds + 1):
        # 1. READ — pull posts from the board (explore/exploit mix)
        feed = await get_feed(board, agent_id, config.feed_size, config.explore_ratio)
        feed_text = format_feed_for_prompt(feed)

        # 2. THINK + ACT — LLM decides what to do based on what it reads
        memory_text = "\n\n".join(memory) if memory else "No past actions yet."
        
        user_message = (
            f"--- BOARD (Round {round_num}/{config.num_rounds}) ---\n"
            f"{feed_text}\n"
            f"--- END BOARD ---\n\n"
            f"--- YOUR MEMORY (Past Actions & Thoughts) ---\n"
            f"{memory_text}\n"
            f"--- END MEMORY ---\n\n"
            f"You are {agent_id}. Choose ONE action."
        )

        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(agent_id, user_prompt),
                    tools=[TOOL_DEFS],
                    temperature=config.temperature,
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode="ANY"  # Force a function call every round
                        )
                    ),
                ),
            )

            # 3. EXECUTE — dispatch the chosen tool to the board
            # Iterate all parts to find the function_call and any text thoughts
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
                memory.append(f"Round {round_num}:\nThought: {thoughts.strip()}\nAction: None (Skipped)")
                continue

            fn_name = fn_call.name
            fn_args = dict(fn_call.args)

            await dispatch_tool(agent_id, fn_name, fn_args, board, client)
            print(f"  [{agent_id}] Round {round_num}: {fn_name}({fn_args})")
            
            # Save to memory
            if thoughts.strip():
                memory_entry = f"Round {round_num}:\nThought: {thoughts.strip()}\nAction: {fn_name}({fn_args})"
            else:
                memory_entry = f"Round {round_num}:\nAction: {fn_name}({fn_args})"
            memory.append(memory_entry)

        except Exception as e:
            print(f"  [{agent_id}] Round {round_num}: ERROR — {e}")


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
            
            search_response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=fn_args["query"],
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.0
                )
            )
            search_summary = f"**Search Results for '{fn_args['query']}':**\n\n{search_response.text}"
            await board.create_post(agent_id, search_summary)
        else:
            print(f"  [{agent_id}] Unknown tool: {fn_name}")
    except KeyError as e:
        print(f"  [{agent_id}] Missing argument {e} for {fn_name}")
    except Exception as e:
        print(f"  [{agent_id}] Tool dispatch error: {e}")
