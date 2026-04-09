// Host search component. Type-as-you-go input that hits the backend
// /api/hosts/search endpoint with a 250ms debounce, then renders the
// matching hosts as clickable rows. Picking a host triggers the
// onPickHost callback in App which loads the full compliance view.

import { useEffect, useState } from "react";
import type { HostSearchResult } from "../types";
import { searchHosts } from "../api";

interface Props {
  onPickHost: (hostname: string) => void;
}

export default function HostSearch({ onPickHost }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HostSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (query.trim().length === 0) {
      setResults([]);
      return;
    }
    // Debounce: only fire the search 250ms after the user stops typing.
    // Avoids hammering Fleet with one request per keystroke.
    const handle = setTimeout(async () => {
      setSearching(true);
      setError(null);
      try {
        const hosts = await searchHosts(query.trim());
        setResults(hosts);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  return (
    <div className="card">
      <div className="px-5 pt-4 pb-3 border-b border-neutral-150">
        <label
          htmlFor="host-search"
          className="block text-[13px] font-medium text-neutral-700 mb-1.5"
        >
          Search for a device
        </label>
        <input
          id="host-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. mrlinux1, mrlinux2"
          className="w-full px-3 py-1.5 bg-neutral-0 border border-neutral-200 rounded-md text-[14px] text-neutral-700 placeholder:text-neutral-300 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors"
          autoFocus
        />
      </div>

      {searching && (
        <div className="px-5 py-3 text-[13px] text-neutral-500">
          Searching...
        </div>
      )}

      {error && (
        <div className="px-5 py-3 text-[13px] text-severity-critical bg-severity-critical-bg border-t border-neutral-150">
          {error}
        </div>
      )}

      {results.length > 0 && (
        <ul>
          {results.map((host) => (
            <li key={host.id} className="border-t border-neutral-150 first:border-t-0">
              <button
                type="button"
                onClick={() => onPickHost(host.hostname)}
                className="w-full px-5 py-3 text-left hover:bg-neutral-50 focus:bg-neutral-50 focus:outline-none transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[14px] font-medium text-neutral-700">
                      {host.hostname}
                    </div>
                    <div className="text-[12px] text-neutral-500 mt-0.5">
                      {host.platform || "unknown platform"}
                    </div>
                  </div>
                  <StatusBadge status={host.status} />
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      {query.trim() && !searching && results.length === 0 && !error && (
        <div className="px-5 py-3 text-[13px] text-neutral-500">
          No devices match "{query}".
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isOnline = status === "online";
  return (
    <span
      className={
        "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium " +
        (isOnline
          ? "text-[#0F7B6C] bg-[#DDEDE8]"
          : "text-neutral-500 bg-neutral-100")
      }
    >
      {status}
    </span>
  );
}
