import { useEffect, useRef, useCallback, useState } from "react";
import type {
  ConnectionStatus,
  SessionData,
  FeedData,
  ActivityData,
  Post,
  Comment,
  Activity,
  SortMode,
} from "../types";

const RECONNECT_DELAY = 3000;

interface UseSSEResult {
  session: { data: SessionData | null; isLoading: boolean };
  feed: { data: FeedData | null; isLoading: boolean };
  activity: { data: ActivityData | null; isLoading: boolean };
  connectionStatus: ConnectionStatus;
  sortMode: SortMode;
  setSortMode: (s: SortMode) => void;
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
}

function sessionParam(sid: string | null): string {
  return sid ? `session_id=${encodeURIComponent(sid)}` : "";
}

export function useSSE(): UseSSEResult {
  const [session, setSession] = useState<SessionData | null>(null);
  const [feed, setFeed] = useState<FeedData | null>(null);
  const [activity, setActivity] = useState<ActivityData | null>(null);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [sortMode, setSortMode] = useState<SortMode>("top");
  const [isLoading, setIsLoading] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sortModeRef = useRef(sortMode);
  sortModeRef.current = sortMode;

  // ── Fetch full state via REST ────────────────────────────────────────────
  const fetchAllData = useCallback(
    async (sort: SortMode, sid: string | null) => {
      const sp = sessionParam(sid);
      const sep = sp ? "&" : "";
      try {
        const [sessRes, feedRes, actRes] = await Promise.all([
          fetch(`/api/sessions${sp ? "?" + sp : ""}`),
          fetch(`/api/feed?sort=${sort}&limit=50${sep}${sp}`),
          fetch(`/api/activity?limit=30${sp ? "&" + sp : ""}`),
        ]);
        const sessData = await sessRes.json();
        const feedData = await feedRes.json();
        const actData = await actRes.json();

        setSession(sessData);
        setFeed(feedData);
        setActivity(actData);
        setIsLoading(false);
      } catch (err) {
        console.error("Failed to fetch data:", err);
        setIsLoading(false);
      }
    },
    [],
  );

  // ── SSE connection ───────────────────────────────────────────────────────
  const connect = useCallback(
    (sid: string | null) => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      setConnectionStatus("connecting");
      const sp = sessionParam(sid);
      const url = `/api/stream${sp ? "?" + sp : ""}`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.addEventListener("connected", () => {
        setConnectionStatus("connected");
      });

      // ── new_post ───────────────────────────────────────────────────────
      es.addEventListener("new_post", (e: MessageEvent) => {
        const parsed = JSON.parse(e.data);
        const d = parsed.data;
        const post: Post = {
          id: d.id,
          agent_id: d.agent_id,
          content: d.content,
          created_at: d.created_at,
          upvotes: 0,
          comments: [],
        };

        setFeed((prev) => {
          if (!prev) return prev;
          if (prev.posts.some((p) => p.id === post.id)) return prev;
          return {
            ...prev,
            count: prev.count + 1,
            posts: [post, ...prev.posts],
          };
        });

        const act: Activity = {
          agent_id: post.agent_id,
          action: "posted",
          detail: post.content,
          created_at: post.created_at,
        };
        setActivity((prev) => {
          if (!prev) return prev;
          return {
            count: prev.count + 1,
            activities: [act, ...prev.activities].slice(0, 50),
          };
        });

        setSession((prev) => {
          if (!prev) return prev;
          const agents = prev.agents.includes(post.agent_id)
            ? prev.agents
            : [...prev.agents, post.agent_id].sort();
          return {
            ...prev,
            total_posts: prev.total_posts + 1,
            active_agents: agents.length,
            agents,
          };
        });
      });

      // ── new_comment ────────────────────────────────────────────────────
      es.addEventListener("new_comment", (e: MessageEvent) => {
        const parsed = JSON.parse(e.data);
        const d = parsed.data;
        const comment: Comment = {
          id: d.id,
          agent_id: d.agent_id,
          content: d.content,
          created_at: d.created_at,
        };
        const postId: string = d.post_id;

        setFeed((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            posts: prev.posts.map((p) =>
              p.id === postId
                ? {
                    ...p,
                    comments: p.comments.some((c) => c.id === comment.id)
                      ? p.comments
                      : [...p.comments, comment],
                  }
                : p,
            ),
          };
        });

        const act: Activity = {
          agent_id: comment.agent_id,
          action: "commented",
          detail: comment.content,
          created_at: comment.created_at,
        };
        setActivity((prev) => {
          if (!prev) return prev;
          return {
            count: prev.count + 1,
            activities: [act, ...prev.activities].slice(0, 50),
          };
        });

        setSession((prev) =>
          prev ? { ...prev, total_comments: prev.total_comments + 1 } : prev,
        );
      });

      // ── new_upvote ─────────────────────────────────────────────────────
      es.addEventListener("new_upvote", (e: MessageEvent) => {
        const parsed = JSON.parse(e.data);
        const d = parsed.data;
        const postId: string = d.post_id;
        const agentId: string = d.agent_id;
        const createdAt: string = d.created_at;

        setFeed((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            posts: prev.posts.map((p) =>
              p.id === postId ? { ...p, upvotes: p.upvotes + 1 } : p,
            ),
          };
        });

        const act: Activity = {
          agent_id: agentId,
          action: "upvoted",
          detail: postId,
          created_at: createdAt,
        };
        setActivity((prev) => {
          if (!prev) return prev;
          return {
            count: prev.count + 1,
            activities: [act, ...prev.activities].slice(0, 50),
          };
        });

        setSession((prev) =>
          prev ? { ...prev, total_upvotes: prev.total_upvotes + 1 } : prev,
        );
      });

      // ── error / reconnect ──────────────────────────────────────────────
      es.onerror = () => {
        setConnectionStatus("disconnected");
        es.close();
        reconnectTimerRef.current = setTimeout(() => {
          connect(sid);
        }, RECONNECT_DELAY);
      };
    },
    [],
  );

  // ── Initial mount ────────────────────────────────────────────────────────
  useEffect(() => {
    fetchAllData(sortMode, activeSessionId);
    connect(activeSessionId);

    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Session switch: re-fetch everything + reconnect SSE ──────────────
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    setIsLoading(true);
    fetchAllData(sortModeRef.current, activeSessionId);
    connect(activeSessionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, fetchAllData, connect]);

  // ── Re-fetch feed when sort mode changes ─────────────────────────────
  const prevSortRef = useRef(sortMode);
  useEffect(() => {
    if (prevSortRef.current === sortMode) return;
    prevSortRef.current = sortMode;

    const fetchFeed = async () => {
      const sp = sessionParam(activeSessionId);
      const sep = sp ? "&" : "";
      try {
        const res = await fetch(
          `/api/feed?sort=${sortMode}&limit=50${sep}${sp}`,
        );
        const data = await res.json();
        setFeed(data);
      } catch (err) {
        console.error("Failed to re-fetch feed:", err);
      }
    };
    fetchFeed();
  }, [sortMode, activeSessionId]);

  return {
    session: { data: session, isLoading },
    feed: { data: feed, isLoading },
    activity: { data: activity, isLoading },
    connectionStatus,
    sortMode,
    setSortMode,
    activeSessionId,
    setActiveSessionId,
  };
}
