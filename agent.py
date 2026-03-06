from google.genai import types
from feed import get_feed, format_feed_for_prompt

def get_system_prompt(user_prompt: str) -> str:
    return f"""\
You are a creative brainstorming agent. You are part of a group of agents collaborating on a creative challenge.

You have access to a shared board where you can read what others have posted, post your own ideas, comment on existing ideas, or upvote ideas you think are strong.

Each round, you should:
1. Read the board (which I have provided to you) to see what's been posted.
2. Think about what's been said — what's good, what's missing, what could be better.
3. Take ONE action: post a new idea, comment on an existing idea, or upvote an existing idea.

Be creative, be critical, be constructive. Build on what others have done. Challenge weak ideas. Champion strong ones. Your goal is to help the group produce the best possible output.
Dont use unnecessary words.

Challenge: {user_prompt}\
"""

# Tool declarations using the Gemini function-calling schema
TOOL_DEFS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="create_post",
        description="Post a new creative concept to the board.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "content": types.Schema(
                    type="STRING",
                    description="Your idea — be specific and vivid."
                )
            },
            required=["content"]
        )
    ),
    types.FunctionDeclaration(
        name="create_comment",
        description="Comment on an existing post — critique, refine, or build on it.",
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
        description="Upvote a post you think is strong. You can only upvote each post once.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "post_id": types.Schema(type="STRING", description="ID of the post to upvote")
            },
            required=["post_id"]
        )
    ),
])


async def run_agent(agent_id: str, user_prompt: str, board, config, client):
    """
    Run one agent for N rounds. Fully independent — no direct knowledge of other agents.
    Agents collaborate only through the shared board.
    """

    for round_num in range(1, config.num_rounds + 1):
        # 1. READ — pull posts from the board (explore/exploit mix)
        feed = await get_feed(board, agent_id, config.feed_size, config.explore_ratio)
        feed_text = format_feed_for_prompt(feed)

        # 2. THINK + ACT — LLM decides what to do based on what it reads
        user_message = (
            f"--- BOARD (Round {round_num}/{config.num_rounds}) ---\n"
            f"{feed_text}\n"
            f"--- END BOARD ---\n\n"
            f"You are {agent_id}. Choose ONE action."
        )

        try:
            response = await client.aio.models.generate_content(
                model=config.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(user_prompt),
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
            # Iterate all parts to find the function_call (text parts may appear too)
            fn_call = None
            for part in response.candidates[0].content.parts:
                if part.function_call is not None:
                    fn_call = part.function_call
                    break

            if fn_call is None:
                print(f"  [{agent_id}] Round {round_num}: No tool call in response — skipping")
                continue

            fn_name = fn_call.name
            fn_args = dict(fn_call.args)

            await dispatch_tool(agent_id, fn_name, fn_args, board)
            print(f"  [{agent_id}] Round {round_num}: {fn_name}({fn_args})")

        except Exception as e:
            print(f"  [{agent_id}] Round {round_num}: ERROR — {e}")


async def dispatch_tool(agent_id: str, fn_name: str, fn_args: dict, board):
    """Route the LLM's chosen tool call to the actual board operation."""
    try:
        if fn_name == "create_post":
            await board.create_post(agent_id, fn_args["content"])
        elif fn_name == "create_comment":
            await board.create_comment(agent_id, fn_args["post_id"], fn_args["content"])
        elif fn_name == "upvote_post":
            await board.upvote(agent_id, fn_args["post_id"])
        else:
            print(f"  [{agent_id}] Unknown tool: {fn_name}")
    except KeyError as e:
        print(f"  [{agent_id}] Missing argument {e} for {fn_name}")
    except Exception as e:
        print(f"  [{agent_id}] Tool dispatch error: {e}")
