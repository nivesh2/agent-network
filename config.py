from dataclasses import dataclass


@dataclass
class Config:
    # LLM
    # model: str = "gemini-2.5-pro"
    model: str = "gemini-3.1-flash-lite-preview"
    temperature: float = 1.0        # High creativity — diversity by design

    # Swarm
    num_agents: int = 5
    num_rounds: int = 10
    consensus_threshold: int = 4    # Stop early if a post reaches this many upvotes

    # Feed
    feed_size: int = 5
    explore_ratio: float = 0.4      # 40% unseen (novelty), 60% top (quality)

    # Tools
    max_searches_per_agent: int = 2 # Prevent infinite research loops

    # Output
    top_k: int = 3                  # Final results to surface

    # DB
    db_path: str = "board.db"
