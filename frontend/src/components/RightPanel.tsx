import type { JSX } from "react";
import type { ActivityData, Activity } from "../types";
import { formatTimeAgo } from "../utils";

interface RightPanelProps {
  activity: ActivityData | null;
  isLoading: boolean;
}

/* ── Action badge config ────────────────────────────────────────────── */
const ACTION_META: Record<
  string,
  { label: string; color: string; bg: string; icon: JSX.Element }
> = {
  posted: {
    label: "Posted",
    color: "text-posted",
    bg: "bg-posted-bg",
    icon: (
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
      </svg>
    ),
  },
  commented: {
    label: "Commented",
    color: "text-commented",
    bg: "bg-commented-bg",
    icon: (
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  upvoted: {
    label: "Upvoted",
    color: "text-upvoted",
    bg: "bg-upvoted-bg",
    icon: (
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
      </svg>
    ),
  },
};

/* ── Agent avatar (inline) ──────────────────────────────────────────── */
const AGENT_COLORS = [
  "#374151", "#6b7280", "#1f2937", "#4b5563",
  "#111827", "#9ca3af", "#334155", "#64748b",
];

function agentColor(id: string): string {
  let hash = 0;
  for (const ch of id) hash = ch.charCodeAt(0) + ((hash << 5) - hash);
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

/* ── Activity Row ───────────────────────────────────────────────────── */
function ActivityRow({ item, index }: { item: Activity; index: number }) {
  const meta = ACTION_META[item.action] ?? ACTION_META.posted;

  return (
    <div
      className="flex items-start gap-3 px-4 py-3 hover:bg-surface-hover transition-colors duration-150 animate-fade-in"
      style={{ animationDelay: `${index * 30}ms` }}
    >
      {/* Avatar */}
      <span
        className="h-7 w-7 rounded-full flex items-center justify-center text-white text-[10px] font-bold mt-0.5 shrink-0"
        style={{ backgroundColor: agentColor(item.agent_id) }}
      >
        {item.agent_id.charAt(0).toUpperCase()}
      </span>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-semibold text-text-primary truncate max-w-[100px]">
            {item.agent_id}
          </span>
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${meta.color} ${meta.bg}`}>
            {meta.icon}
            {meta.label}
          </span>
        </div>
        <p className="text-xs text-text-tertiary mt-0.5 line-clamp-2 leading-relaxed">
          {item.action === "upvoted" ? `Post #${item.detail}` : item.detail}
        </p>
      </div>

      {/* Timestamp */}
      <span className="text-[10px] text-text-tertiary whitespace-nowrap mt-1 shrink-0">
        {formatTimeAgo(item.created_at)}
      </span>
    </div>
  );
}

/* ── Skeleton Row ───────────────────────────────────────────────────── */
function SkeletonRow() {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <div className="skeleton h-7 w-7 rounded-full shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="skeleton h-3 w-32" />
        <div className="skeleton h-3 w-44" />
      </div>
    </div>
  );
}

/* ── Right Panel ────────────────────────────────────────────────────── */
export default function RightPanel({ activity, isLoading }: RightPanelProps) {
  return (
    <aside className="w-[300px] min-w-[300px] h-screen sticky top-0 border-l border-border bg-surface flex flex-col animate-slide-right">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full bg-green-500 shrink-0"
            style={{ animation: "pulse-dot 2s ease-in-out infinite" }}
          />
          <h2 className="text-sm font-semibold text-text-primary tracking-tight">
            Live Activity
          </h2>
        </div>
        <p className="text-[11px] text-text-tertiary mt-1">
          {activity ? `${activity.count} recent actions` : "Connecting…"}
        </p>
      </div>

      {/* Activity List */}
      <div className="flex-1 overflow-y-auto divide-y divide-border/50">
        {isLoading
          ? [...Array(8)].map((_, i) => <SkeletonRow key={i} />)
          : activity?.activities.length
            ? activity.activities.map((item, idx) => (
              <ActivityRow key={`${item.agent_id}-${item.action}-${item.created_at}-${item.detail.slice(0, 10)}`} item={item} index={idx} />
            ))
            : (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-text-tertiary italic">
                  Waiting for activity…
                </p>
              </div>
            )
        }
      </div>
    </aside>
  );
}
