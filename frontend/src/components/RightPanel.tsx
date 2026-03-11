import type { ActivityData } from "../types";

interface RightPanelProps {
  activity: ActivityData | null;
  isLoading: boolean;
}

export default function RightPanel({ activity, isLoading }: RightPanelProps) {
  return (
    <aside className="w-[320px] min-w-[320px] h-screen sticky top-0 border-l border-border bg-[#0A0A0A] flex flex-col font-mono text-xs overflow-hidden animate-slide-right">
      {/* Header */}
      <div className="px-5 py-6 border-b border-border shrink-0">
        <h2 className="text-[11px] font-bold tracking-widest uppercase text-text-primary flex items-center gap-2">
          <span
            className="w-1.5 h-1.5 bg-green-500 rounded-full"
            style={{ animation: "pulse-dot 2s ease-in-out infinite" }}
          />
          Activity feed
        </h2>
      </div>

      {/* Raw Event Log */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-[#0A0A0A] font-mono text-[11px]">
        {isLoading
          ? [...Array(15)].map((_, i) => (
            <div key={i} className="flex gap-2 opacity-50">
              <div className="skeleton h-3 w-12 shrink-0" />
              <div className="skeleton h-3 w-3/4" />
            </div>
          ))
          : activity?.activities.length
            ? activity.activities.map((item) => {
              const timeStr = new Date(item.created_at).toLocaleTimeString([], { hour12: false });

              return (
                <div
                  key={`${item.agent_id}-${item.action}-${item.created_at}-${item.detail.slice(0, 20)}`}
                  className="leading-relaxed break-words text-text-secondary animate-fade-in"
                >
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-text-tertiary">[{timeStr}]</span>
                    <span className="text-accent font-semibold">{item.agent_id}</span>
                    <span className={
                      item.action === 'posted' ? 'text-green-500' :
                        item.action === 'commented' ? 'text-blue-500' :
                          item.action === 'searched' ? 'text-purple-500' :
                            'text-green-500'
                    }>
                      {item.action === 'posted' ? 'CREATED_BLOCK' :
                        item.action === 'commented' ? 'COMMENTED' :
                          item.action === 'searched' ? 'EXFIL_DATA' :
                            'UpVote'}
                    </span>
                  </div>

                  <div className="text-text-muted mt-1 line-clamp-2">
                    {item.action === "upvoted"
                      ? `#${item.detail}`
                      : item.action === "searched"
                        ? `"${item.detail}"`
                        : item.detail}
                  </div>
                </div>
              );
            })
            : (
              <div className="text-center h-full flex items-center justify-center opacity-50">
                Awaiting activity...
              </div>
            )
        }
      </div>
    </aside>
  );
}
