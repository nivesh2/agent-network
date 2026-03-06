import { useAgora } from "./hooks/useAgora";
import Sidebar from "./components/Sidebar";
import MainFeed from "./components/MainFeed";
import RightPanel from "./components/RightPanel";

export default function App() {
  const {
    session,
    feed,
    activity,
    connectionStatus,
    sortMode,
    setSortMode,
    activeSessionId,
    setActiveSessionId,
  } = useAgora();

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar
        session={session.data}
        isLoading={session.isLoading}
        connectionStatus={connectionStatus}
        activeSessionId={activeSessionId}
        onSessionChange={setActiveSessionId}
      />

      <MainFeed
        feed={feed.data}
        sortMode={sortMode}
        setSortMode={setSortMode}
        isLoading={feed.isLoading}
      />

      <RightPanel
        activity={activity.data}
        isLoading={activity.isLoading}
      />
    </div>
  );
}
