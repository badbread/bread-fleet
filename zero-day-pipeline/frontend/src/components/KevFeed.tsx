// Left panel: KEV feed browser with search, date filter, and
// ransomware toggle. Each entry shows CVE ID, product, date added,
// and a green dot for entries likely to be mappable (matching known
// product families in the curated registry).

import { useState, useEffect, useCallback } from "react";
import type { KevEntry, MappedKev } from "../types";
import { getKevFeed, mapKev } from "../api";

interface Props {
  onSelect: (mapped: MappedKev) => void;
  selectedCve: string | null;
  deployedCves: Set<string>;
}

// Client-side hint: product keywords that the backend registry can
// map. This avoids calling /map for every entry in the feed. The
// list mirrors registry.py's keys.
const MAPPABLE_HINTS = [
  "openssl", "curl", "sudo", "polkit", "systemd",
  "apache", "http server", "nginx",
  "openssh", "samba",
  "chromium", "chrome", "firefox",
  "python", "node.js", "java",
  "postgresql", "mysql", "redis",
  "bind", "docker", "linux kernel", "kernel",
];

function likelyMappable(entry: KevEntry): boolean {
  const vp = entry.vendorProject.toLowerCase();
  const p = entry.product.toLowerCase();
  return MAPPABLE_HINTS.some((hint) => vp.includes(hint) || p.includes(hint));
}

export default function KevFeed({ onSelect, selectedCve, deployedCves }: Props) {
  const [entries, setEntries] = useState<KevEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [days, setDays] = useState<number>(365);
  const [ransomwareOnly, setRansomwareOnly] = useState(false);
  const [mappingEntry, setMappingEntry] = useState<string | null>(null);

  const loadFeed = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await getKevFeed({
        days: days || undefined,
        product: search || undefined,
        ransomware_only: ransomwareOnly,
      });
      // Sort: likely mappable entries first, then by date.
      const sorted = [...resp.entries].sort((a, b) => {
        const aM = likelyMappable(a) ? 0 : 1;
        const bM = likelyMappable(b) ? 0 : 1;
        if (aM !== bM) return aM - bM;
        return b.dateAdded.localeCompare(a.dateAdded);
      });
      setEntries(sorted);
      setTotal(resp.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [days, search, ransomwareOnly]);

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  const handleSelect = async (entry: KevEntry) => {
    setMappingEntry(entry.cveID);
    try {
      const mapped = await mapKev(entry.cveID);
      onSelect(mapped);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMappingEntry(null);
    }
  };

  const mappableCount = entries.filter(likelyMappable).length;

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-neutral-150 space-y-2">
        <h2 className="text-[14px] font-semibold text-neutral-700">
          CISA KEV Feed
        </h2>
        <input
          type="text"
          placeholder="Filter by product..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-3 py-1.5 text-[13px] border border-neutral-200 rounded-md focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <div className="flex items-center gap-3 text-[12px] text-neutral-500">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border border-neutral-200 rounded px-2 py-1 text-[12px]"
          >
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
            <option value={365}>Last year</option>
          </select>
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={ransomwareOnly}
              onChange={(e) => setRansomwareOnly(e.target.checked)}
              className="rounded"
            />
            Ransomware only
          </label>
        </div>
        <p className="text-[11px] text-neutral-500">
          {total} entries &middot;{" "}
          <span className="text-mapping-mapped font-medium">{mappableCount} mappable</span>
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && (
          <p className="px-4 py-6 text-[13px] text-neutral-500 text-center">
            Loading KEV feed...
          </p>
        )}
        {error && (
          <p className="px-4 py-4 text-[13px] text-severity-critical">
            {error}
          </p>
        )}
        {!loading &&
          entries.map((entry) => {
            const mappable = likelyMappable(entry);
            const deployed = deployedCves.has(entry.cveID);
            return (
              <button
                key={entry.cveID}
                onClick={() => handleSelect(entry)}
                disabled={mappingEntry === entry.cveID}
                className={`w-full text-left px-4 py-3 border-b border-neutral-100 hover:bg-neutral-50 transition-colors ${
                  selectedCve === entry.cveID ? "bg-accent-subtle" : ""
                } ${mappingEntry === entry.cveID ? "opacity-50" : ""}`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      deployed ? "bg-accent" : mappable ? "bg-mapping-mapped" : "bg-neutral-300"
                    }`}
                    title={deployed ? "Deployed to Fleet" : mappable ? "Likely mappable to osquery" : "May not be detectable via osquery"}
                  />
                  <span className="text-[13px] font-medium text-neutral-700 flex-1">
                    {entry.cveID}
                  </span>
                  {deployed && (
                    <span className="text-[10px] font-semibold uppercase text-accent bg-accent-subtle px-1.5 py-0.5 rounded shrink-0">
                      Deployed
                    </span>
                  )}
                  <span className="text-[11px] text-neutral-500 shrink-0">
                    {entry.dateAdded}
                  </span>
                </div>
                <p className="text-[12px] text-neutral-500 mt-0.5 truncate pl-4">
                  {entry.vendorProject} — {entry.product}
                </p>
                {entry.knownRansomwareCampaignUse === "Known" && (
                  <span className="inline-block mt-1 ml-4 px-1.5 py-0.5 text-[10px] font-semibold uppercase bg-severity-critical-bg text-severity-critical rounded">
                    Ransomware
                  </span>
                )}
              </button>
            );
          })}
      </div>
    </div>
  );
}
