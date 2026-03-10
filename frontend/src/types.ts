export interface SessionData {
  session_id: string | null;
  prompt: string | null;
  total_posts: number;
  total_comments: number;
  total_upvotes: number;
  active_agents: number;
  agents: string[];
}

export interface Comment {
  id: string;
  agent_id: string;
  content: string;
  created_at: string;
}

export interface Post {
  id: string;
  agent_id: string;
  content: string;
  created_at: string;
  upvotes: number;
  comments: Comment[];
}

export interface FeedData {
  sort: "top" | "newest";
  count: number;
  posts: Post[];
}

export interface Activity {
  agent_id: string;
  action: "posted" | "commented" | "upvoted" | "searched";
  detail: string;
  created_at: string;
}

export interface ActivityData {
  count: number;
  activities: Activity[];
}

export type SortMode = "top" | "newest";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export interface SynthesizedDoc {
  session_id: string;
  content: string;
  created_at: string;
}

export interface SessionListItem {
  id: string;
  prompt: string;
  created_at: string;
}
