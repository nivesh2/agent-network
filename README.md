# 🧠 Agent Network

A non-hierarchical swarm of AI agents that collaborate through a **gamified scoring system** and shared board. **No orchestrator. No fixed roles.** Identical agents coordinate themselves through incentives, not hardcoded pipelines.

Built at **Epiminds Hackathon** — an agent swarm hackathon. Collaboration through incentives, not orchestration.

---

## How It Works

```
identical agents → shared board → gamified scoring → emergent collaboration
```

Each agent independently:
1. **Reads** the shared board (mixed feed of newest and top-voted posts)
2. **Thinks** about what's needed — research, critique, or build
3. **Acts** — posts, comments, upvotes, searches the web, or waits

**Key insight:** Agents don't have fixed roles. They *choose* what to do based on what the board needs, driven by a gamified scoring system.

---

## Gamified Scoring System

Agents earn **Influence Points** based on their actions:

| Role | Action | Points |
|------|--------|--------|
| **THE CRITIC** | Challenge assumptions, point out flaws | +20 |
| **THE BUILDER** | Add nuance, correct flaws, expand ideas | +15 |
| **THE RESEARCHER** | Search web early for factual foundation | +10 |
| **THE SUPPORTER** | Upvote a winning strategy | +5 |
| **THE OBSERVER** | Wait when board lacks direction | 0 |
| **THE LONE WOLF** | Post new idea without referencing others | 0 |
| **THE WASTER** | Search frivolously late in the game | -5 |
| **THE HOARDER** | Search multiple topics at once | -20 |
| **THE HALLUCINATOR** | Post made-up facts | -50 |
| **THE BLIND SHEEP** | Upvote a research dump | -50 |
| **THE PREMATURE VOTER** | Upvote before debating | -100 |
| **THE MONOLOGUER** | Double-comment without waiting for reply | -100 |

**Result:** Same model. Different behavior. Collaboration emerges naturally.

---

## Project Structure

```
agent-network/
├── main.py          # Entry point — spawns agents, collects results
├── agent.py         # Agent loop + gamified system prompt (Influence Points)
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
| Launch | *"Same model. Same prompt. Four agents. No orchestrator."* |
| One agent searches | *"Watch — one agent researches. Others see it on the board and don't duplicate."* |
| Upvote blocked | *"Agent tried to upvote too early. System forced them to comment first. That's a -100 penalty."* |
| Debate emerges | *"Now there's debate. Agents are critiquing, building, challenging. Nobody told them to."* |
| Show final consensus | *"The board converged. Agents reached consensus because the scoring system rewards it."* |

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
| Agent Loop | Raw ReAct + Gamified Prompt | Incentives drive behavior |
| Shared Board | SQLite + WAL mode (`aiosqlite`) | Zero setup, async-safe |
| Concurrency | `asyncio.gather` | True parallel agents |
| API Layer | FastAPI | Serves DB data cleanly for React |
| UI | React + Vite + Tailwind v4 | Modern, dynamic live dashboard |
