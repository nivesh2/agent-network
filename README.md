# 🧠 Agent Network

A non-hierarchical swarm of AI agents that collaboratively brainstorm creative concepts through social-network-style interaction. **No coordinator. No roles. No hierarchy.** Ideas emerge, get debated, refined, and ranked through collective intelligence.

Built for the hackathon. Ships fast, demos well.

---

## How It Works

```
5 identical agents → shared SQLite board → emergent creative output
```

Each agent independently:
1. **Reads** a mixed feed of the newest and top-voted posts
2. **Thinks** about what's good, missing, or worth challenging
3. **Acts** — posts a new idea, comments on an existing one, or upvotes

No agent knows what another is doing — they only see the board. Diversity emerges from LLM stochasticity, different feed slices, and diverging context.

---

## Project Structure

```
agent-network/
├── main.py          # Entry point — spawns agents, collects results
├── agent.py         # Single agent (ReAct loop + Gemini function-calling)
├── board.py         # Shared board (async SQLite with WAL mode)
├── feed.py          # Feed algorithm (explore/exploit + seen-post tracking)
├── config.py        # All tunables in one place
├── ui/
│   ├── frontend/    # Vite + React SPA (dashboard shell)
│   └── static/      # Built SPA assets and shared static files
├── requirements.txt
└── README.md
```

---

## Prerequisites

- Python 3.11+
- A Google Cloud project with Vertex AI enabled **or** a Gemini API key

---

## Setup

```bash
# 1. Clone / navigate to the project
cd agent-network

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Authentication

Choose **one** of the following:

### Option A — Gemini API Key (simplest)
```bash
export GOOGLE_API_KEY="your-api-key-here"
```
Get a key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).

### Option B — Google Cloud / Vertex AI (GCP credits)
```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

---

## Running the Project & WebUI

We highly recommend using the WebUI rather than monitoring via the CLI, as it provides a much richer and dynamic view of the agents' interactions.

### 1. Start the Live Dashboard

We have a convenient `run.sh` script that starts both the FastAPI backend and the React frontend concurrently:

```bash
# First, ensure you've installed frontend dependencies:
cd frontend
npm install
cd ..

# Then, start both the backend and frontend:
./scripts/run.sh
```

Keep this running and open the local URL that Vite prints (e.g., `http://localhost:5173`).

### 2. Launch the Swarm

In a new terminal, launch the agent swarm (it will prompt you for a creative challenge):

```bash
python main.py
```

Now, instead of staring at the CLI output, **switch to your browser** and watch the agents interact, post, comment, and upvote in real-time!

---

## Advanced: CLI-Only Execution

If you prefer to run the swarm purely in the terminal:

```bash
python main.py
```

You'll see each agent's actions printed in real time:
```
🚀 Launching 5 agents × 10 rounds
   Challenge: "Generate ad concepts for a sustainable fashion brand..."
────────────────────────────────────────────────
  [Agent-1] Round 1: create_post(...)
  [Agent-2] Round 1: create_post(...)
  [Agent-3] Round 1: create_comment(...)
  ...

══════════════════════════════════════════════════════════════
🏆  TOP 3 CONCEPTS (by upvotes)
══════════════════════════════════════════════════════════════

#1  ⬆ 7  [Agent-1]
     "Born from nature. Returns to nature." — time-lapse of a dress ...
     Debate thread:
       💬 Agent-4: Beautiful visual but no product shown...
       💬 Agent-2: Fair — end card could show the clothing line...
```

### Optional: override the model from CLI
```bash
python main.py --model gemini-2.5-pro
```

### Starting Fresh / Clearing the Board

The board state is saved in `board.db`. To start completely fresh and clear all ideas from previous runs, use the provided script:

```bash
./scripts/clear_db.sh
```
*(Note: `main.py` actually clears the board automatically on every fresh launch so you get a blank slate each time you run the script, but if you want to reset the database manually without re-running agents, this script handles it safely).*

---

## Configuration

Edit `config.py` to tune the swarm:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `model` | `gemini-3.1-flash-lite-preview` | Switch to `gemini-2.5-pro` for better quality |
| `num_agents` | `5` | More agents → more diversity, more cost |
| `num_rounds` | `10` | More rounds → deeper refinement |
| `explore_ratio` | `0.4` | Higher → more novelty; lower → faster consensus |
| `feed_size` | `5` | Posts each agent reads per round |
| `top_k` | `3` | Final results shown |

---

## Demo Moves

| Moment | What to say |
|--------|-------------|
| Launch | *"5 identical agents, one shared board, no coordinator"* |
| Watch comments appear | *"Agent-4 just challenged Agent-1's concept. Nobody told it to."* |
| Kill a terminal mid-run | *"Watch — the system doesn't notice. The swarm just continues."* |
| Show final results | *"These concepts were co-authored by debate — no single agent wrote the winner."* |

---

## Cost Estimate

```
5 agents × 10 rounds × ~1,500 tokens/call ≈ 75,000 tokens per run

Gemini 2.5 Flash (~$0.15/1M input, ~$0.60/1M output):
  ≈ $0.02 per run

50 test runs ≈ $1 — covered by GCP credits
```

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Fast prototyping |
| LLM | Gemini 2.5 Flash (Vertex AI) | Native function-calling, GCP credits |
| Agent Loop | Raw ReAct (no framework) | No hidden orchestration |
| Shared Board | SQLite + WAL mode (`aiosqlite`) | Zero setup, async-safe |
| Concurrency | `asyncio.gather` | True parallel agents |
| API Layer | FastAPI | Serves DB data cleanly for React |
| UI | React + Vite + Tailwind v4 | Modern, dynamic live dashboard |
