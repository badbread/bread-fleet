// Top-level component. Header with brand mark and title, host search,
// selected host's compliance view, and a thin footer. Layout uses a
// narrow centered column with warm off-white background and subtle
// borders instead of heavy shadows.

import { useState, useCallback } from "react";
import HostSearch from "./components/HostSearch";
import HostDetail from "./components/HostDetail";
import Logo from "./components/Logo";
import type { HostCompliance } from "./types";
import { getHostCompliance } from "./api";

export default function App() {
  const [selectedHost, setSelectedHost] = useState<HostCompliance | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHost = useCallback(async (hostname: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getHostCompliance(hostname);
      setSelectedHost(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSelectedHost(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50">
      <header className="bg-neutral-0 border-b border-neutral-150">
        <div className="max-w-3xl mx-auto px-8 py-6 flex items-center gap-4">
          <Logo size={42} className="shrink-0" />
          <div className="flex-1">
            <h1 className="text-[26px] leading-tight font-semibold text-neutral-700">
              Compliance Troubleshooter
            </h1>
            <p className="mt-1 text-[14px] text-neutral-500 leading-relaxed">
              Look up a device. Read the findings in plain English. Fix the safe ones with one click.
            </p>
          </div>
          <a
            href="/"
            className="text-[13px] text-accent hover:underline shrink-0"
          >
            Back to portal
          </a>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-3xl mx-auto px-8 py-8 space-y-5">
          <HostSearch onPickHost={loadHost} />

          {loading && (
            <div className="card px-6 py-10 text-center text-neutral-500 text-sm">
              Loading device compliance...
            </div>
          )}

          {error && !loading && (
            <div
              className="card px-5 py-4"
              style={{ borderColor: "#FBE4E4" }}
            >
              <p className="text-sm">
                <span className="font-semibold text-severity-critical">Could not load this device. </span>
                <span className="text-neutral-700">{error}</span>
              </p>
            </div>
          )}

          {selectedHost && !loading && (
            <HostDetail
              host={selectedHost}
              onRecheck={() => loadHost(selectedHost.hostname)}
            />
          )}

          {!selectedHost && !loading && !error && (
            <div className="card px-6 py-14 text-center text-neutral-500 text-sm">
              Search for a device by hostname above to see its compliance status.
            </div>
          )}
        </div>
      </main>

      <footer className="bg-neutral-0 border-t border-neutral-150">
        <div className="max-w-3xl mx-auto px-8 py-3 text-xs text-neutral-500 flex items-center justify-between">
          <span>Operator: anonymous (SSO integration pending)</span>
          <span>v0.1.0</span>
        </div>
      </footer>
    </div>
  );
}
