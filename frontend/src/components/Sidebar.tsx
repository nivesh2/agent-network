import { useState, useEffect } from "react";
import type { SessionData, ConnectionStatus, SessionListItem } from "../types";
import { formatTimeAgo } from "../utils";

interface SidebarProps {
  session: SessionData | null;
  isLoading: boolean;
  connectionStatus: ConnectionStatus;
  activeSessionId: string | null;
  onSessionChange: (id: string | null) => void;
}
const AGENT_COLORS = [
  "text-green-400",
  "text-blue-400",
  "text-purple-400",
  "text-yellow-400",
  "text-pink-400",
  "text-cyan-400",
  "text-orange-400",
  "text-red-400",
];

function getAgentColor(index: number): string {
  return AGENT_COLORS[index % AGENT_COLORS.length];
}

function StatRow({ label, value, isLoading }: { label: string; value: number; isLoading: boolean }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-border/50 last:border-0">
      <span className="text-[10px] tracking-widest uppercase text-text-tertiary">{label}</span>
      {isLoading ? (
        <span className="skeleton h-3 w-8" />
      ) : (
        <span className="text-xs font-bold text-text-primary">{value}</span>
      )}
    </div>
  );
}

export default function Sidebar({
  session,
  isLoading,
  connectionStatus,
  activeSessionId,
  onSessionChange,
}: SidebarProps) {
  const [sessionsList, setSessionsList] = useState<SessionListItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    fetch("/api/sessions/list")
      .then((res) => res.json())
      .then((data) => setSessionsList(data.sessions || []))
      .catch(console.error);
  }, []);

  return (
    <aside className="w-[300px] min-w-[300px] h-screen sticky top-0 border-r border-border bg-[#0A0A0A] flex flex-col font-mono">
      {/* Header / Network Status */}
      <div className="px-6 py-6 border-b border-border">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-[11px] font-bold tracking-widest uppercase text-text-primary">
            Agent Network
          </h1>
          <span
            className={`h-2 w-2 rounded-full shrink-0 ${connectionStatus === "connected"
              ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"
              : connectionStatus === "connecting"
                ? "bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.8)]"
                : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"
              }`}
            style={
              connectionStatus !== "disconnected"
                ? { animation: "pulse-dot 2s ease-in-out infinite" }
                : undefined
            }
          />
        </div>

        <div className="space-y-1.5">
          <div className="text-[9px] text-text-tertiary uppercase tracking-widest">
            Primary Directive
          </div>
          <p className="text-xs text-text-secondary font-sans leading-relaxed line-clamp-4">
            {session?.prompt ?? "Awaiting directive…"}
          </p>
        </div>
      </div>

      {/* Telemetry Stats */}
      <div className="px-6 py-6 border-b border-border">
        <h2 className="text-[9px] font-bold tracking-widest uppercase text-text-tertiary mb-4">
          Swarm Telemetry
        </h2>
        <div className="space-y-2">
          <StatRow label="Active Agents" value={session?.active_agents ?? 0} isLoading={isLoading} />
          <StatRow label="Posts" value={session?.total_posts ?? 0} isLoading={isLoading} />
          <StatRow label="Comments" value={session?.total_comments ?? 0} isLoading={isLoading} />
          <StatRow label="Upvotes" value={session?.total_upvotes ?? 0} isLoading={isLoading} />
        </div>
      </div>

      {/* Session History Toggle */}
      <div className="px-6 py-4 border-b border-border">
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="w-full flex items-center justify-between text-[9px] font-bold tracking-widest uppercase text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
        >
          <span>Session History</span>
          <span>{showHistory ? "[-]" : "[+]"}</span>
        </button>

        {showHistory && (
          <div className="mt-4 space-y-3 max-h-40 overflow-y-auto pr-2 custom-scrollbar">
            {sessionsList.map(s => (
              <button
                key={s.id}
                onClick={() => onSessionChange(s.id)}
                className={`w-full text-left p-2 border rounded-sm transition-colors text-xs ${activeSessionId === s.id ? "border-accent bg-accent/10" : "border-border/50 hover:border-text-secondary"} cursor-pointer`}
              >
                <div className="truncate font-sans mb-1 text-text-secondary">{s.prompt || "No prompt"}</div>
                <div className="flex justify-between items-center text-[9px] text-text-tertiary">
                  <span>{s.id.slice(0, 8)}</span>
                  <span>{formatTimeAgo(s.created_at)}</span>
                </div>
              </button>
            ))}
            {sessionsList.length === 0 && (
              <div className="text-xs text-text-tertiary italic">No past sessions</div>
            )}
          </div>
        )}
      </div>

      {/* Roster */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <h2 className="text-[9px] font-bold tracking-widest uppercase text-text-tertiary mb-4">
          Live Agents
        </h2>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="skeleton h-3 w-16" />
                <div className="skeleton h-2 w-2 rounded-full" />
              </div>
            ))}
          </div>
        ) : session?.agents.length ? (
          <ul className="space-y-3">
            {session.agents.map((agent, i) => (
              <li
                key={agent}
                className="flex items-center justify-between text-xs"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] ${getAgentColor(i)}`}>●</span>
                  <span className="text-text-secondary uppercase tracking-wider">{agent}</span>
                </div>
                <span className="text-[9px] text-green-500 tracking-widest uppercase animate-pulse">
                  Online
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-text-tertiary italic">
            Nodes inactive
          </p>
        )}
      </div>

      {/* Footer System Hash (Decorative) */}
      <div className="px-6 py-4 border-t border-border mt-auto">
        <div className="text-[9px] text-text-tertiary tracking-widest uppercase truncate opacity-50">
          SYS_HASH: {session?.session_id?.split('-')[0] ?? '00000000'}
        </div>
      </div>
    </aside>
  );
}
