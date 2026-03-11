import { useState } from "react";
import { useAgora } from "./hooks/useAgora";
import Sidebar from "./components/Sidebar";
import MainFeed from "./components/MainFeed";
import RightPanel from "./components/RightPanel";
import LandingPage from "./components/LandingPage";

export default function App() {
  const [isDashboard, setIsDashboard] = useState(false);

  const {
    session,
    feed,
    activity,
    connectionStatus,
    sortMode,
    setSortMode,
    activeSessionId,
    setActiveSessionId,
    synthDoc,
    refreshSynthDoc,
    clearData,
  } = useAgora();

  const handleLaunch = (_: string, sessionId: string) => {
    // Clear out the previous session's data right before sliding into the dashboard
    clearData();
    // Force the SSE stream to lock onto the newly generated backend session
    setActiveSessionId(sessionId);
    setIsDashboard(true);
  };

  if (!isDashboard) {
    return <LandingPage onLaunch={handleLaunch} />;
  }

  return (
    <div className="flex min-h-[100vh] bg-bg flex-1">
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
        synthDoc={synthDoc}
        activeSessionId={activeSessionId}
        onSynthesized={refreshSynthDoc}
      />

      <RightPanel
        activity={activity.data}
        isLoading={activity.isLoading}
      />
    </div>
  );
}
