import { useState } from "react";
import type { FeedData, Post, SortMode, SynthesizedDoc } from "../types";
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

// Custom Markdown component to highlight @mentions and post tags
const MarkdownTextWithMentions = ({ children }: { children: React.ReactNode }) => {
  if (typeof children !== "string") {
    return <>{children}</>;
  }

  // Split by @mention pattern (e.g. @Astrid, @agent-1) or post [id] pattern
  const parts = children.split(/(@[a-zA-Z0-9_-]+|post \[[a-fA-F0-9]+\])/gi);

  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("@")) {
          return (
            <span key={i} className="text-accent font-bold bg-accent/10 px-1 rounded-sm">
              {part}
            </span>
          );
        } else if (part.toLowerCase().startsWith("post [")) {
          return (
            <span key={i} className="text-orange-400 font-bold bg-orange-400/10 px-1 rounded-sm">
              {part}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
};

const renderers = {
  p: ({ children }: any) => <p className="mb-4"><MarkdownTextWithMentions>{children}</MarkdownTextWithMentions></p>,
  li: ({ children }: any) => <li><MarkdownTextWithMentions>{children}</MarkdownTextWithMentions></li>,
};

function CognitiveBlock({ post, index }: { post: Post; index: number }) {
  const isFactCheck = post.content.includes("🚨 FACT CHECK");
  const isResearchDump = post.content.includes("🔍 RESEARCH DUMP");

  let indicatorColor = "bg-text-secondary";
  let label = "Post";

  if (isFactCheck) {
    indicatorColor = "bg-red-500";
    label = "FACT_CHECK_ROUTINE";
  } else if (isResearchDump) {
    indicatorColor = "bg-purple-500";
    label = "WEB_SEARCH";
  }

  return (
    <article
      className="relative pl-6 py-2 mb-10 animate-fade-in group"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Left indicator line */}
      <div className={`absolute left-0 top-0 bottom-0 w-0.5 ${indicatorColor} opacity-50 group-hover:opacity-100 transition-opacity`} />

      {/* Header telemetry */}
      <div className="flex flex-wrap items-center gap-3 mb-4 font-mono text-[10px] tracking-widest uppercase text-text-tertiary">
        <span className="text-accent font-bold">@{post.agent_id}</span>
        <span className="border border-border px-1.5 py-0.5 rounded-sm">{label}</span>
        <span className="opacity-50">T-{formatTimeAgo(post.created_at)}</span>
        <span className="opacity-50">SIG:{post.upvotes}</span>
        <span className="opacity-50">ID:{post.id.slice(0, 8)}</span>
      </div>

      {/* Core payload */}
      <div className="text-sm font-sans text-text-primary leading-[1.7] prose prose-sm prose-invert max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={renderers}>{post.content}</ReactMarkdown>
      </div>

      {/* Sub-routines (Comments) */}
      {post.comments.length > 0 && (
        <div className="mt-6 pt-4 border-t border-border/30 space-y-4">
          <div className="font-mono text-[9px] tracking-widest uppercase text-text-tertiary mb-3">
            -- Linked Comments ({post.comments.length}) --
          </div>
          {post.comments.map((c) => (
            <div key={c.id} className="pl-4 border-l border-border/30 flex flex-col gap-1">
              <div className="flex items-center gap-2 font-mono text-[10px] tracking-widest uppercase text-text-tertiary">
                <span className="text-accent font-semibold">{c.agent_id}</span>
                <span className="opacity-50">{formatTimeAgo(c.created_at)}</span>
              </div>
              <div className="text-xs font-sans text-text-secondary leading-relaxed prose prose-sm prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={renderers}>{c.content}</ReactMarkdown>
              </div>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function SkeletonBlock() {
  return (
    <div className="relative pl-6 py-2 mb-10">
      <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-border" />
      <div className="flex items-center gap-3 mb-4">
        <div className="skeleton h-3 w-16" />
        <div className="skeleton h-3 w-24" />
      </div>
      <div className="space-y-2">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-3/4" />
        <div className="skeleton h-3 w-5/6" />
      </div>
    </div>
  );
}

function SynthCard({ doc }: { doc: SynthesizedDoc }) {
  return (
    <div className="mb-10 p-6 border border-accent/30 bg-accent/5 rounded-xl font-mono">
      <div className="flex items-center gap-3 mb-4 text-[10px] tracking-widest uppercase text-accent font-bold">
        <span className="w-2 h-2 bg-accent rounded-full animate-pulse" />
        <span>[ RUN SYNTHESIS ] COMPLETE</span>
        <span className="ml-auto opacity-50 text-text-tertiary">T-{formatTimeAgo(doc.created_at)}</span>
      </div>
      <div className="font-sans text-sm text-text-primary prose prose-sm prose-invert max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{doc.content}</ReactMarkdown>
      </div>
    </div>
  );
}

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
    <div className="mb-10 border border-border p-4 bg-[#141414] font-mono text-[11px] flex items-center justify-between">
      <div className="text-text-tertiary tracking-widest uppercase">
        <span className="text-text-secondary mr-2">SYS_MSG:</span>
        Brainstorming complete. Awaiting extraction.
        {status === "error" && <span className="block text-red-500 mt-1">{errMsg}</span>}
      </div>
      <button
        onClick={handleGenerate}
        disabled={status === "loading"}
        className="px-4 py-2 bg-accent text-bg font-bold tracking-widest uppercase hover:bg-white transition-colors disabled:opacity-50 disabled:cursor-wait cursor-pointer"
      >
        {status === "loading" ? "EXTRACTING..." : "[ RUN SYNTHESIS ]"}
      </button>
    </div>
  );
}

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
  const hasConsensus = feed?.posts.some(p => p.upvotes >= 4) ?? false;
  const showGenerateBanner = hasPosts && !synthDoc && activeSessionId && hasConsensus;

  return (
    <main className="flex-1 min-w-0 overflow-y-auto h-screen bg-[#141414]">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-[#141414]/90 backdrop-blur-md border-b border-border px-8 py-6 flex items-center justify-between font-mono">
        <div>
          <h2 className="text-[12px] font-bold tracking-widest uppercase text-text-primary">
            Cognitive Stream
          </h2>
          <div className="flex gap-2 text-[10px] text-text-tertiary tracking-widest mt-1">
            <span>{feed ? `TOTAL_POSTS: ${feed.count}` : "LOADING_POSTS..."}</span>
          </div>
        </div>

        {/* Sort Toggle */}
        <div className="flex gap-2">
          {["top", "newest"].map((m) => (
            <button
              key={m}
              onClick={() => setSortMode(m as SortMode)}
              className={`text-[10px] tracking-widest uppercase px-3 py-1.5 border transition-colors cursor-pointer ${sortMode === m
                ? "border-accent text-accent"
                : "border-border text-text-tertiary hover:border-text-secondary hover:text-text-primary"
                }`}
            >
              / {m}
            </button>
          ))}
        </div>
      </div>

      {/* Feed Content */}
      <div className="px-8 py-8 max-w-[800px] mx-auto">
        {showGenerateBanner && (
          <GenerateDocBanner sessionId={activeSessionId} onSynthesized={onSynthesized} />
        )}

        {synthDoc && <SynthCard doc={synthDoc} />}

        {isLoading ? (
          [...Array(5)].map((_, i) => <SkeletonBlock key={i} />)
        ) : feed?.posts.length ? (
          feed.posts.map((post, idx) => (
            <CognitiveBlock key={post.id} post={post} index={idx} />
          ))
        ) : (
          <div className="text-center py-32 font-mono text-[11px] tracking-widest uppercase text-text-tertiary">
            <span className="inline-block mb-4 animate-bounce">_</span>
            <p>Awaiting cognitive input...</p>
          </div>
        )}
      </div>
    </main>
  );
}
