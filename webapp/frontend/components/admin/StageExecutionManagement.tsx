"use client";

import { useState } from "react";
import ExecutionHistory from "./ExecutionHistory";
import ScheduleManagement from "./ScheduleManagement";

export default function StageExecutionManagement() {
  const [scheduleRefreshTrigger, setScheduleRefreshTrigger] = useState(0);

  const handleScheduleCreated = () => {
    // Increment trigger to force refresh
    setScheduleRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className="space-y-8">
      {/* Execution History with integrated Manual/Scheduled tabs */}
      <ExecutionHistory onScheduleCreated={handleScheduleCreated} />

      {/* Divider */}
      <div className="border-t border-gray-200"></div>

      {/* Schedule Management */}
      <ScheduleManagement refreshTrigger={scheduleRefreshTrigger} />
    </div>
  );
}
