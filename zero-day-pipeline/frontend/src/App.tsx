// Three-panel layout: KEV feed browser (left), entry detail with
// generated SQL (center), deployed policies with host results (right).
// Responsive: collapses to stacked on narrow screens.

import { useState } from "react";
import type { MappedKev, DeployedPolicy } from "./types";
import KevFeed from "./components/KevFeed";
import KevDetail from "./components/KevDetail";
import DeployedPolicies from "./components/DeployedPolicies";

export default function App() {
  const [selected, setSelected] = useState<MappedKev | null>(null);
  const [deployTrigger, setDeployTrigger] = useState(0);

  const handleDeployed = (_policy: DeployedPolicy) => {
    setDeployTrigger((n) => n + 1);
  };

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50">
      <header className="bg-white border-b border-neutral-150">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-[22px] leading-tight font-semibold text-neutral-700">
              Zero-Day Response Pipeline
            </h1>
            <p className="mt-1 text-[13px] text-neutral-500">
              CISA KEV to Fleet detection policies — curated registry with Claude AI assist
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
        <div className="max-w-[1400px] mx-auto px-6 py-5">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-[calc(100vh-160px)]">
            {/* Left: KEV feed browser */}
            <div className="lg:col-span-3 card overflow-hidden">
              <KevFeed
                onSelect={setSelected}
                selectedCve={selected?.kev.cveID ?? null}
              />
            </div>

            {/* Center: selected entry detail */}
            <div className="lg:col-span-6 card overflow-hidden">
              {selected ? (
                <KevDetail mapped={selected} onDeployed={handleDeployed} />
              ) : (
                <div className="flex items-center justify-center h-full text-[13px] text-neutral-500">
                  Select a KEV entry to view details and generate a detection query
                </div>
              )}
            </div>

            {/* Right: deployed policies */}
            <div className="lg:col-span-3 card overflow-hidden">
              <DeployedPolicies refreshTrigger={deployTrigger} />
            </div>
          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-neutral-150">
        <div className="max-w-[1400px] mx-auto px-6 py-3 text-xs text-neutral-500 flex items-center justify-between">
          <span>
            Source: CISA Known Exploited Vulnerabilities Catalog
          </span>
          <span>v0.1.0</span>
        </div>
      </footer>
    </div>
  );
}
