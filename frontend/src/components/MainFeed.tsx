import { useState, type JSX } from "react";
import type { FeedData, Post, Comment, SortMode, SynthesizedDoc } from "../types";
import { formatTimeAgo } from "../utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MainFeedProps {
  feed: FeedData | null;
  sortMode: SortMode;
  setSortMode: (s: SortMode) => void;
  isLoading: boolean;
  synthDoc: SynthesizedDoc | null;
  activeSessionId: string | null;
  onSynthesized: () => Promise<void>;
}

/* ── Agent Avatar ───────────────────────────────────────────────────── */
const AGENT_COLORS = [
  "#374151", "#6b7280", "#1f2937", "#4b5563",
  "#111827", "#9ca3af", "#334155", "#64748b",
];

function agentColor(id: string): string {
  let hash = 0;
  for (const ch of id) hash = ch.charCodeAt(0) + ((hash << 5) - hash);
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

function AgentAvatar({ agentId, size = "md" }: { agentId: string; size?: "sm" | "md" }) {
  const dim = size === "sm" ? "h-6 w-6 text-[10px]" : "h-8 w-8 text-xs";
  return (
    <span
      className={`${dim} rounded-full flex items-center justify-center text-white font-bold shrink-0`}
      style={{ backgroundColor: agentColor(agentId) }}
    >
      {agentId.charAt(0).toUpperCase()}
    </span>
  );
}

/* ── Upvote Badge ───────────────────────────────────────────────────── */
function UpvoteBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-soft text-text-secondary text-xs font-medium">
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
      </svg>
      {count}
    </span>
  );
}

/* ── Comment Row ────────────────────────────────────────────────────── */
function CommentRow({ comment }: { comment: Comment }) {
  return (
    <div className="flex gap-2.5 py-2.5 first:pt-0">
      <AgentAvatar agentId={comment.agent_id} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-semibold text-text-primary">
            {comment.agent_id}
          </span>
          <span className="text-[11px] text-text-tertiary">
            {formatTimeAgo(comment.created_at)}
          </span>
        </div>
        <div className="text-sm text-text-secondary leading-relaxed prose prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{comment.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

/* ── Idea Card ──────────────────────────────────────────────────────── */
function IdeaCard({ post, index }: { post: Post; index: number }) {
  // Detect Role from post content
  const isFactCheck = post.content.includes("🚨 FACT CHECK");
  const isResearchDump = post.content.includes("🔍 RESEARCH DUMP");

  let borderColor = "border-border hover:border-border-strong";
  let bgGradient = "bg-surface";

  if (isFactCheck) {
    borderColor = "border-red-500/30 hover:border-red-500/50";
    bgGradient = "bg-gradient-to-br from-surface to-red-500/5";
  } else if (isResearchDump) {
    borderColor = "border-purple-500/30 hover:border-purple-500/50";
    bgGradient = "bg-gradient-to-br from-surface to-purple-500/5";
  }

  return (
    <article
      className={`border ${borderColor} rounded-xl ${bgGradient} p-5 transition-all duration-200 hover:shadow-sm animate-fade-in`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <AgentAvatar agentId={post.agent_id} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-text-primary">
              {post.agent_id}
            </span>
            {isFactCheck && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold text-red-600 bg-red-100 dark:bg-red-900/40 border border-red-200 dark:border-red-800">
                🚨 Fact-Checker
              </span>
            )}
            {isResearchDump && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold text-purple-600 bg-purple-100 dark:bg-purple-900/40 border border-purple-200 dark:border-purple-800">
                🔍 Explorer
              </span>
            )}
            <span className="text-xs text-text-tertiary">
              {formatTimeAgo(post.created_at)}
            </span>
          </div>
          <p className="text-xs text-text-tertiary mt-0.5 font-mono">
            #{post.id}
          </p>
        </div>
        <UpvoteBadge count={post.upvotes} />
      </div>

      {/* Content */}
      <div className="text-sm text-text-primary leading-[1.7] prose prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{post.content}</ReactMarkdown>
      </div>

      {/* Comments */}
      {post.comments.length > 0 && (
        <div className="mt-4 pt-3.5 border-t border-border">
          <p className="text-[11px] font-semibold tracking-widest uppercase text-text-tertiary mb-2.5">
            {post.comments.length} {post.comments.length === 1 ? "Comment" : "Comments"}
          </p>
          <div className="space-y-0 divide-y divide-border/50">
            {post.comments.map((c) => (
              <CommentRow key={c.id} comment={c} />
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

/* ── Skeleton Card ──────────────────────────────────────────────────── */
function SkeletonCard() {
  return (
    <div className="border border-border rounded-xl bg-surface p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="skeleton h-8 w-8 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-4 w-28" />
          <div className="skeleton h-3 w-16" />
        </div>
      </div>
      <div className="space-y-2">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-3/4" />
        <div className="skeleton h-3 w-5/6" />
      </div>
    </div>
  );
}

/* ── Sort Toggle ────────────────────────────────────────────────────── */
function SortToggle({ sortMode, setSortMode }: { sortMode: SortMode; setSortMode: (s: SortMode) => void }) {
  const options: { value: SortMode; label: string; icon: JSX.Element }[] = [
    {
      value: "top",
      label: "Top",
      icon: (
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      ),
    },
    {
      value: "newest",
      label: "Newest",
      icon: (
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="flex rounded-lg border border-border overflow-hidden">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => setSortMode(opt.value)}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium transition-all duration-150 cursor-pointer ${sortMode === opt.value
            ? "bg-accent text-white"
            : "bg-surface text-text-secondary hover:bg-surface-hover"
            }`}
        >
          {opt.icon}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/* ── Synthesized Document Card ──────────────────────────────────────── */
function SynthesizedDocCard({ doc }: { doc: SynthesizedDoc }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <article className="relative border border-accent/30 rounded-xl bg-surface p-5 animate-fade-in overflow-hidden">
      {/* Gradient accent bar */}
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-accent via-purple-400 to-accent/30 rounded-t-xl" />

      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <span className="h-8 w-8 rounded-full bg-gradient-to-br from-accent to-purple-500 flex items-center justify-center text-white text-sm shrink-0">
          📝
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-text-primary">Synthesis</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-accent/10 text-accent border border-accent/20">
              AI Generated
            </span>
          </div>
          <p className="text-[11px] text-text-tertiary mt-0.5">
            {formatTimeAgo(doc.created_at)}
          </p>
        </div>
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-[11px] text-text-tertiary hover:text-text-secondary transition-colors cursor-pointer px-2 py-1 rounded hover:bg-surface-hover"
        >
          {expanded ? "Collapse" : "Expand"}
        </button>
      </div>

      {/* Content */}
      {expanded && (
        <div className="text-sm text-text-primary leading-[1.7] prose prose-sm max-w-none border-t border-border/50 pt-4">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{doc.content}</ReactMarkdown>
        </div>
      )}
    </article>
  );
}

/* ── Generate Document Banner ───────────────────────────────────────── */
function GenerateDocBanner({
  sessionId,
  onSynthesized,
}: {
  sessionId: string;
  onSynthesized: () => Promise<void>;
}) {
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errMsg, setErrMsg] = useState("");

  const handleGenerate = async () => {
    setStatus("loading");
    setErrMsg("");
    try {
      const res = await fetch("/api/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const data = await res.json();
      if (data.status === "error") {
        setErrMsg(data.detail ?? "Unknown error");
        setStatus("error");
        return;
      }
      await onSynthesized();
      setStatus("idle");
    } catch (e: unknown) {
      setErrMsg(e instanceof Error ? e.message : "Request failed");
      setStatus("error");
    }
  };

  return (
    <div className="flex items-center gap-4 p-4 rounded-xl border border-border bg-surface/60 backdrop-blur-sm animate-fade-in">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary">Brainstorming complete</p>
        <p className="text-xs text-text-tertiary mt-0.5">
          Generate a refined synthesis document from all agent ideas and debate.
        </p>
        {status === "error" && (
          <p className="text-xs text-red-500 mt-1">{errMsg}</p>
        )}
      </div>
      <button
        id="generate-document-btn"
        onClick={handleGenerate}
        disabled={status === "loading"}
        className="shrink-0 flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
      >
        {status === "loading" ? (
          <>
            <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Synthesizing…
          </>
        ) : (
          <>
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Generate Document
          </>
        )}
      </button>
    </div>
  );
}

/* ── Main Feed ──────────────────────────────────────────────────────── */
export default function MainFeed({
  feed,
  sortMode,
  setSortMode,
  isLoading,
  synthDoc,
  activeSessionId,
  onSynthesized,
}: MainFeedProps) {
  const hasPosts = (feed?.count ?? 0) > 0;
  const showGenerateBanner = hasPosts && !synthDoc && activeSessionId;

  return (
    <main className="flex-1 min-w-0 overflow-y-auto h-screen">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-bg/80 backdrop-blur-md border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-serif font-semibold text-text-primary">
              Idea Feed
            </h2>
            <p className="text-xs text-text-tertiary mt-0.5">
              {feed ? `${feed.count} ideas` : "Loading…"}
            </p>
          </div>
          <SortToggle sortMode={sortMode} setSortMode={setSortMode} />
        </div>
      </div>

      {/* Feed Cards */}
      <div className="px-6 py-5 space-y-4 max-w-[720px] mx-auto">
        {/* Generate Document Banner */}
        {showGenerateBanner && (
          <GenerateDocBanner
            sessionId={activeSessionId}
            onSynthesized={onSynthesized}
          />
        )}

        {/* Synthesized Document Card — pinned at top */}
        {synthDoc && <SynthesizedDocCard doc={synthDoc} />}

        {isLoading ? (
          [...Array(5)].map((_, i) => <SkeletonCard key={i} />)
        ) : feed?.posts.length ? (
          feed.posts.map((post, idx) => (
            <IdeaCard key={post.id} post={post} index={idx} />
          ))
        ) : (
          <div className="text-center py-20">
            <div className="text-5xl mb-4">💡</div>
            <p className="text-sm text-text-tertiary">
              No ideas yet — agents are warming up…
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

