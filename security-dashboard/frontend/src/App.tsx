// Dashboard layout. Fetches all data on mount and distributes it to
// the six visualization sections. The layout uses a two-column grid
// on wider screens and stacks on narrow ones.

import { useState, useEffect } from "react";
import type {
  PostureSummary,
  TrendPoint,
  PolicyRanking,
  DeviceRisk,
} from "./types";
import { getSummary, getTrend, getPolicies, getDevices } from "./api";
import HealthScore from "./components/HealthScore";
import ComplianceTrend from "./components/ComplianceTrend";
import PlatformBreakdown from "./components/PlatformBreakdown";
import TopFailingPolicies from "./components/TopFailingPolicies";
import RiskTable from "./components/RiskTable";
import PolicyCoverage from "./components/PolicyCoverage";

export default function App() {
  const [summary, setSummary] = useState<PostureSummary | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [policies, setPolicies] = useState<PolicyRanking[]>([]);
  const [devices, setDevices] = useState<DeviceRisk[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getSummary(), getTrend(), getPolicies(), getDevices()])
      .then(([s, t, p, d]) => {
        setSummary(s);
        setTrend(t);
        setPolicies(p);
        setDevices(d);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="card px-6 py-8 max-w-md text-center">
          <p className="text-sm text-severity-critical font-semibold">
            Failed to load dashboard data
          </p>
          <p className="mt-2 text-sm text-neutral-500">{error}</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <p className="text-sm text-neutral-500">Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50">
      <header className="bg-white border-b border-neutral-150">
        <div className="max-w-6xl mx-auto px-8 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-[22px] leading-tight font-semibold text-neutral-700">
              Security Posture Dashboard
            </h1>
            <p className="mt-1 text-[13px] text-neutral-500">
              Fleet-wide compliance health, trends, and risk concentration
            </p>
          </div>
          <a
            href="/"
            className="text-[13px] text-accent hover:underline"
          >
            Back to portal
          </a>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-6xl mx-auto px-8 py-6 space-y-5">
          {/* Row 1: Health score + platform breakdown side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <HealthScore
              score={summary.health_score}
              deviceCount={summary.device_count}
              totalChecks={summary.total_checks}
            />
            <div className="lg:col-span-2">
              <PlatformBreakdown platforms={summary.platforms} />
            </div>
          </div>

          {/* Row 2: Compliance trend (full width) */}
          <ComplianceTrend data={trend} />

          {/* Row 3: Failing policies + risk table side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <TopFailingPolicies policies={policies} />
            <RiskTable devices={devices.slice(0, 10)} />
          </div>

          {/* Row 4: Policy coverage (full width) */}
          <PolicyCoverage policies={policies} />
        </div>
      </main>

      <footer className="bg-white border-t border-neutral-150">
        <div className="max-w-6xl mx-auto px-8 py-3 text-xs text-neutral-500 flex items-center justify-between">
          <span>
            Data: synthetic (augmented from real Fleet policies to ~{summary.device_count} devices)
          </span>
          <span>v0.1.0</span>
        </div>
      </footer>
    </div>
  );
}
