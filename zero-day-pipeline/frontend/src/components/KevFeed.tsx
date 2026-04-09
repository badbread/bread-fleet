// Left panel: KEV feed browser with search, date filter, and
// ransomware toggle. Each entry shows CVE ID, product, date added,
// and a colored dot indicating mapping status.

import { useState, useEffect, useCallback } from "react";
import type { KevEntry, MappedKev } from "../types";
import { getKevFeed, mapKev } from "../api";

interface Props {
  onSelect: (mapped: MappedKev) => void;
  selectedCve: string | null;
}

export default function KevFeed({ onSelect, selectedCve }: Props) {
  const [entries, setEntries] = useState<KevEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [days, setDays] = useState<number>(90);
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
      setEntries(resp.entries);
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
          {total} {total === 1 ? "entry" : "entries"}
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
          entries.map((entry) => (
            <button
              key={entry.cveID}
              onClick={() => handleSelect(entry)}
              disabled={mappingEntry === entry.cveID}
              className={`w-full text-left px-4 py-3 border-b border-neutral-100 hover:bg-neutral-50 transition-colors ${
                selectedCve === entry.cveID ? "bg-accent-subtle" : ""
              } ${mappingEntry === entry.cveID ? "opacity-50" : ""}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-neutral-700">
                  {entry.cveID}
                </span>
                <span className="text-[11px] text-neutral-500">
                  {entry.dateAdded}
                </span>
              </div>
              <p className="text-[12px] text-neutral-500 mt-0.5 truncate">
                {entry.vendorProject} — {entry.product}
              </p>
              {entry.knownRansomwareCampaignUse === "Known" && (
                <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] font-semibold uppercase bg-severity-critical-bg text-severity-critical rounded">
                  Ransomware
                </span>
              )}
            </button>
          ))}
      </div>
    </div>
  );
}
