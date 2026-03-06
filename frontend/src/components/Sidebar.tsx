import { useState, useEffect } from "react";
import type { SessionData, ConnectionStatus, SessionListItem } from "../types";

interface SidebarProps {
  session: SessionData | null;
  isLoading: boolean;
  connectionStatus: ConnectionStatus;
  activeSessionId: string | null;
  onSessionChange: (id: string | null) => void;
}

const AGENT_COLORS = [
  "bg-agent-1",
  "bg-agent-2",
  "bg-agent-3",
  "bg-agent-4",
  "bg-agent-5",
  "bg-agent-6",
  "bg-agent-7",
  "bg-agent-8",
];

function getAgentColor(index: number): string {
  return AGENT_COLORS[index % AGENT_COLORS.length];
}

function getAgentInitial(agentId: string): string {
  return agentId.charAt(0).toUpperCase();
}

function StatCard({
  label,
  value,
  isLoading,
}: {
  label: string;
  value: number;
  isLoading: boolean;
}) {
  return (
    <div className="border border-border rounded-lg p-4 transition-colors duration-200 hover:bg-surface-hover">
      {isLoading ? (
        <div className="skeleton h-8 w-16 mb-1.5" />
      ) : (
        <p className="text-2xl font-semibold tracking-tight text-text-primary font-serif">
          {value.toLocaleString()}
        </p>
      )}
      <p className="text-xs font-medium tracking-wide uppercase text-text-tertiary mt-1">
        {label}
      </p>
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
  // ── Launch state ─────────────────────────────────────────────────────────
  const [prompt, setPrompt] = useState("");
  const [isLaunching, setIsLaunching] = useState(false);
  const [launchMsg, setLaunchMsg] = useState<string | null>(null);

  // ── Sessions list ────────────────────────────────────────────────────────
  const [sessions, setSessions] = useState<SessionListItem[]>([]);

  const fetchSessions = async () => {
    try {
      const res = await fetch("/api/sessions/list");
      const data = await res.json();
      setSessions(data.sessions ?? []);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  // Re-fetch sessions list when active session changes (e.g. after launch)
  useEffect(() => {
    fetchSessions();
  }, [activeSessionId]);

  // ── Launch handler ───────────────────────────────────────────────────────
  const handleLaunch = async () => {
    setIsLaunching(true);
    setLaunchMsg(null);
    try {
      const res = await fetch("/api/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt.trim() || undefined }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setLaunchMsg("Swarm launched!");
      setPrompt("");

      // Wait a moment for the session to appear in the DB, then switch to it
      setTimeout(async () => {
        await fetchSessions();
        // Select the latest session (the one just launched)
        const res2 = await fetch("/api/sessions/list");
        const data = await res2.json();
        const latest = data.sessions?.[0];
        if (latest) {
          onSessionChange(latest.id);
        }
        setLaunchMsg(null);
      }, 2000);
    } catch {
      setLaunchMsg("Failed to launch.");
    } finally {
      setIsLaunching(false);
    }
  };

  return (
    <aside className="w-[280px] min-w-[280px] h-screen sticky top-0 border-r border-border bg-surface flex flex-col animate-slide-left">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-border">
        <div className="flex items-center gap-3">
          <img
            src="/logo.png"
            alt="Agora"
            className="h-8 w-8 rounded-md"
          />
          <h1 className="text-xl font-serif font-semibold tracking-tight text-text-primary">
            agora
          </h1>
        </div>
        <p className="text-xs text-text-tertiary mt-2 leading-relaxed">
          {session?.prompt ?? "Collaborative AI brainstorming — watch agents ideate in real time."}
        </p>
      </div>

      {/* Launch Panel */}
      <div className="px-5 py-4 border-b border-border">
        <h2 className="text-[11px] font-semibold tracking-widest uppercase text-text-tertiary mb-2.5">
          Launch New Run
        </h2>
        <textarea
          className="w-full text-xs bg-bg border border-border rounded-lg px-3 py-2 text-text-primary placeholder:text-text-tertiary resize-none focus:outline-none focus:ring-1 focus:ring-accent"
          rows={3}
          placeholder="Enter a creative challenge…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isLaunching}
        />
        <button
          className="w-full mt-2 px-3 py-1.5 text-xs font-semibold rounded-lg bg-accent text-white transition-colors duration-150 hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          onClick={handleLaunch}
          disabled={isLaunching}
        >
          {isLaunching ? "Launching…" : "Launch Swarm"}
        </button>
        {launchMsg && (
          <p className={`text-[11px] mt-1.5 ${launchMsg.includes("Failed") ? "text-red-500" : "text-green-600"}`}>
            {launchMsg}
          </p>
        )}
      </div>

      {/* Session Selector */}
      {sessions.length > 0 && (
        <div className="px-5 py-3 border-b border-border">
          <h2 className="text-[11px] font-semibold tracking-widest uppercase text-text-tertiary mb-2">
            Session
          </h2>
          <select
            className="w-full text-xs bg-bg border border-border rounded-lg px-2.5 py-1.5 text-text-primary focus:outline-none focus:ring-1 focus:ring-accent cursor-pointer"
            value={activeSessionId ?? session?.session_id ?? ""}
            onChange={(e) => onSessionChange(e.target.value || null)}
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.created_at?.slice(0, 16)} | {s.prompt.length > 40 ? s.prompt.slice(0, 40) + "…" : s.prompt}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Stats */}
      <div className="px-5 py-5 border-b border-border">
        <h2 className="text-[11px] font-semibold tracking-widest uppercase text-text-tertiary mb-3">
          Session Overview
        </h2>
        <div className="grid grid-cols-2 gap-2.5">
          <StatCard
            label="Posts"
            value={session?.total_posts ?? 0}
            isLoading={isLoading}
          />
          <StatCard
            label="Comments"
            value={session?.total_comments ?? 0}
            isLoading={isLoading}
          />
          <StatCard
            label="Upvotes"
            value={session?.total_upvotes ?? 0}
            isLoading={isLoading}
          />
          <StatCard
            label="Agents"
            value={session?.active_agents ?? 0}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Agent Roster */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        <h2 className="text-[11px] font-semibold tracking-widest uppercase text-text-tertiary mb-3">
          Active Agents
        </h2>
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="skeleton h-8 w-8 rounded-full" />
                <div className="skeleton h-4 w-24" />
              </div>
            ))}
          </div>
        ) : session?.agents.length ? (
          <ul className="space-y-1">
            {session.agents.map((agent, i) => (
              <li
                key={agent}
                className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors duration-150 hover:bg-surface-hover cursor-default"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <span
                  className={`h-7 w-7 rounded-full flex items-center justify-center text-white text-xs font-bold ${getAgentColor(i)}`}
                >
                  {getAgentInitial(agent)}
                </span>
                <span className="text-sm text-text-secondary font-medium truncate">
                  {agent}
                </span>
                {/* Live indicator */}
                <span
                  className="ml-auto h-2 w-2 rounded-full bg-green-500"
                  style={{ animation: "pulse-dot 2s ease-in-out infinite" }}
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-text-tertiary italic">
            No agents active yet…
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border">
        <div className="flex items-center gap-2 text-text-tertiary">
          <span
            className={`h-2 w-2 rounded-full shrink-0 ${
              connectionStatus === "connected"
                ? "bg-green-500"
                : connectionStatus === "connecting"
                  ? "bg-yellow-500"
                  : "bg-red-500"
            }`}
            style={
              connectionStatus !== "disconnected"
                ? { animation: "pulse-dot 2s ease-in-out infinite" }
                : undefined
            }
          />
          <span className="text-xs">
            {connectionStatus === "connected"
              ? "Live — streaming"
              : connectionStatus === "connecting"
                ? "Connecting…"
                : "Disconnected — reconnecting…"}
          </span>
        </div>
      </div>
    </aside>
  );
}
