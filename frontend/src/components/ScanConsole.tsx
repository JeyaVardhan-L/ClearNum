import React, { useState, useEffect } from "react";
import {
  Search,
  ExternalLink,
  ShieldCheck,
  Info,
  Check,
  Copy,
  Lock,
  AlertTriangle,
  Activity,
} from "lucide-react";
import type { PhoneParseResult, ManualDorkItem, ProviderOutcome } from "../types";
import { parsePhone, scanDiscovery, getManualDorks } from "../api";

interface ScanConsoleProps {
  currentIdentity: PhoneParseResult | null;
  onScanComplete: (identity: PhoneParseResult) => void;
  onOpenRemediation: () => void;
}

const COUNTRY_OPTIONS = [
  { code: "US", name: "United States (+1)", dial: "1" },
  { code: "GB", name: "United Kingdom (+44)", dial: "44" },
  { code: "IN", name: "India (+91)", dial: "91" },
  { code: "CA", name: "Canada (+1)", dial: "1" },
  { code: "AU", name: "Australia (+61)", dial: "61" },
  { code: "DE", name: "Germany (+49)", dial: "49" },
  { code: "FR", name: "France (+33)", dial: "33" },
  { code: "JP", name: "Japan (+81)", dial: "81" },
  { code: "BR", name: "Brazil (+55)", dial: "55" },
  { code: "SG", name: "Singapore (+65)", dial: "65" },
];

export const ScanConsole: React.FC<ScanConsoleProps> = ({
  currentIdentity,
  onScanComplete,
  onOpenRemediation,
}) => {
  const [phoneNumber, setPhoneNumber] = useState(currentIdentity?.raw_input || currentIdentity?.e164 || "+14155552671");
  const [region, setRegion] = useState(currentIdentity?.region_code || "US");
  const [parseData, setParseData] = useState<PhoneParseResult | null>(currentIdentity);
  const [isScanning, setIsScanning] = useState(false);
  const [providers, setProviders] = useState({
    searxng: true,
    duckduckgo: true,
    wikimedia: true,
    hackernews: true,
    wayback: true,
  });
  const [customUrls, setCustomUrls] = useState("");
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [providerOutcomes, setProviderOutcomes] = useState<ProviderOutcome[]>([]);
  
  // Dorks Modal
  const [showDorksModal, setShowDorksModal] = useState(false);
  const [dorks, setDorks] = useState<ManualDorkItem[]>([]);
  const [copiedQuery, setCopiedQuery] = useState<string | null>(null);

  // Live normalization as user types
  useEffect(() => {
    if (!phoneNumber || phoneNumber.trim().length < 5) return;
    const timer = setTimeout(async () => {
      try {
        const res = await parsePhone(phoneNumber, region);
        setParseData(res);
      } catch {
        // Silently keep current parse
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [phoneNumber, region]);

  const handleStartScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!parseData || !parseData.is_possible) {
      alert("Please enter a possible phone number before scanning.");
      return;
    }

    setIsScanning(true);
    setScanMessage("Initiating local discovery engine across authorized search providers...");

    const activeProviders: string[] = [];
    if (providers.searxng) activeProviders.push("searxng");
    if (providers.duckduckgo) activeProviders.push("duckduckgo");
    if (providers.wikimedia) activeProviders.push("wikimedia");
    if (providers.hackernews) activeProviders.push("hackernews");
    if (providers.wayback) activeProviders.push("wayback");

    const targetList = customUrls
      .split("\n")
      .map((u) => u.trim())
      .filter((u) => u.startsWith("http"));

    try {
      const res = await scanDiscovery(parseData.e164 || phoneNumber, region, activeProviders, targetList);
      setProviderOutcomes(res.provider_outcomes || []);
      if (res.scan_status === "partial_failure") {
        setScanMessage(`Scan completed with warnings: Some providers were rate-limited or unreachable. Discovered ${res.total_found} potential exposure records.`);
      } else if (res.scan_status === "all_failed") {
        setScanMessage(`Scan incomplete: All queried search providers failed or were rate-limited. See provider diagnostics below.`);
      } else {
        setScanMessage(`Scan complete: Discovered ${res.total_found} potential exposure records across all queried providers.`);
      }
      onScanComplete(parseData);
    } catch (err: any) {
      setScanMessage(`Scan completed with local fallback: ${err.message}`);
    } finally {
      setIsScanning(false);
    }
  };

  const handleOpenDorks = async () => {
    if (!parseData) return;
    try {
      const list = await getManualDorks(parseData.e164 || phoneNumber, region);
      setDorks(list);
      setShowDorksModal(true);
    } catch (err: any) {
      alert(`Could not fetch manual dorks: ${err.message}`);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedQuery(text);
    setTimeout(() => setCopiedQuery(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Hero / Introduction Bar */}
      <div className="panel-card p-6 border-l-4 border-l-sky-500">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <ShieldCheck className="w-6 h-6 text-sky-400" />
              Privacy Exposure Discovery Engine
            </h1>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Analyze where your personal phone number appears publicly across web directories, code repositories, and paste archives.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleOpenDorks}
              className="btn-secondary text-xs"
              title="Open pre-computed Google, Bing, Brave, and directory search links"
            >
              <ExternalLink className="w-3.5 h-3.5 text-sky-400" />
              Direct Search Dorks (1-Click)
            </button>
            <button
              type="button"
              onClick={onOpenRemediation}
              className="btn-secondary text-xs"
              title="Browse 25+ verified broker removal procedures"
            >
              <ExternalLink className="w-3.5 h-3.5 text-emerald-400" />
              Remediation Hub
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Input & Configuration */}
        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={handleStartScan} className="panel-card p-6 space-y-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-dim)] flex items-center gap-2">
              <Search className="w-4 h-4 text-sky-400" />
              Target Number & Search Scope
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Country / Region</label>
                <select
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  className="input-field cursor-pointer"
                >
                  {COUNTRY_OPTIONS.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Phone Number</label>
                <input
                  type="text"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="e.g. +1 (415) 555-2671"
                  className="input-field font-mono font-medium"
                  required
                />
              </div>
            </div>

            {/* Provider Checkboxes */}
            <div className="pt-3 border-t border-[var(--border-subtle)] space-y-3">
              <label className="block text-xs font-semibold text-slate-300">Active Discovery Providers</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="flex items-start gap-2.5 p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] cursor-pointer hover:border-[var(--border-strong)]">
                  <input
                    type="checkbox"
                    checked={providers.searxng}
                    onChange={(e) => setProviders({ ...providers, searxng: e.target.checked })}
                    className="mt-0.5 accent-sky-500 rounded"
                  />
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">SearXNG Meta-Search</span>
                    <span className="text-[11px] text-[var(--text-dim)]">Aggregates Google, Bing, Brave, and Mojeek with zero logging.</span>
                  </div>
                </label>

                <label className="flex items-start gap-2.5 p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] cursor-pointer hover:border-[var(--border-strong)]">
                  <input
                    type="checkbox"
                    checked={providers.duckduckgo}
                    onChange={(e) => setProviders({ ...providers, duckduckgo: e.target.checked })}
                    className="mt-0.5 accent-sky-500 rounded"
                  />
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">DuckDuckGo HTML</span>
                    <span className="text-[11px] text-[var(--text-dim)]">Lightweight non-tracking query endpoint with polite backoff.</span>
                  </div>
                </label>

                <label className="flex items-start gap-2.5 p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] cursor-pointer hover:border-[var(--border-strong)]">
                  <input
                    type="checkbox"
                    checked={providers.wikimedia}
                    onChange={(e) => setProviders({ ...providers, wikimedia: e.target.checked })}
                    className="mt-0.5 accent-sky-500 rounded"
                  />
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">Wikipedia / Wikimedia</span>
                    <span className="text-[11px] text-[var(--text-dim)]">Official MediaWiki API searching public discussions, pages & leaks.</span>
                  </div>
                </label>

                <label className="flex items-start gap-2.5 p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] cursor-pointer hover:border-[var(--border-strong)]">
                  <input
                    type="checkbox"
                    checked={providers.hackernews}
                    onChange={(e) => setProviders({ ...providers, hackernews: e.target.checked })}
                    className="mt-0.5 accent-sky-500 rounded"
                  />
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">Hacker News (Algolia)</span>
                    <span className="text-[11px] text-[var(--text-dim)]">Official Algolia API querying comments, resumes & public listings.</span>
                  </div>
                </label>

                <label className="flex items-start gap-2.5 p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] cursor-pointer hover:border-[var(--border-strong)]">
                  <input
                    type="checkbox"
                    checked={providers.wayback}
                    onChange={(e) => setProviders({ ...providers, wayback: e.target.checked })}
                    className="mt-0.5 accent-sky-500 rounded"
                  />
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">Internet Archive (Wayback CDX)</span>
                    <span className="text-[11px] text-[var(--text-dim)]">Official CDX API searching historical pastes, forums & directory archives.</span>
                  </div>
                </label>
              </div>
            </div>

            {/* Optional Custom URLs to scan */}
            <div className="pt-2">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Optional: Target URLs to Rescan or Verify (one per line)
              </label>
              <textarea
                value={customUrls}
                onChange={(e) => setCustomUrls(e.target.value)}
                rows={2}
                placeholder="https://example.com/staff/profile&#10;https://thatsthem.com/phone/5551234"
                className="input-field font-mono text-xs"
              />
            </div>

            {/* Submit Action */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-3 border-t border-[var(--border-subtle)]">
              <div className="text-xs text-[var(--text-dim)]">
                Zero API fees • No third-party account required
              </div>
              <button
                type="submit"
                disabled={isScanning || !parseData?.is_possible}
                className="btn-primary w-full sm:w-auto"
              >
                {isScanning ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Scanning Public Indexes...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Run Discovery Scan
                  </>
                )}
              </button>
            </div>

            {scanMessage && (
              <div className="p-3 rounded-md bg-sky-950/40 border border-sky-800 text-xs text-sky-300 flex items-center gap-2">
                <Info className="w-4 h-4 shrink-0" />
                <span>{scanMessage}</span>
              </div>
            )}

            {/* Observable Provider Diagnostics & Health Badges */}
            {providerOutcomes.length > 0 && (
              <div className="panel-card p-4 space-y-3 bg-slate-950/60 border border-slate-800">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-sky-400" />
                    Provider Diagnostics &amp; Health
                  </span>
                  <span className="text-[11px] text-[var(--text-dim)]">Observable Execution</span>
                </div>

                <div className="space-y-2">
                  {providerOutcomes.map((po) => {
                    const isHealthy = po.status === "healthy";
                    const isRateLimited = po.status === "rate_limited";
                    const isUnreachable = po.status === "unreachable";

                    const badgeClass = isHealthy
                      ? "status-pill pill-emerald"
                      : isRateLimited
                      ? "status-pill pill-amber"
                      : isUnreachable
                      ? "status-pill pill-rose"
                      : "status-pill pill-slate";

                    return (
                      <div
                        key={po.provider_id}
                        className="p-2.5 rounded bg-slate-900/80 border border-slate-800 text-xs flex flex-col md:flex-row md:items-center justify-between gap-2"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-200 capitalize">
                              {po.provider_id === "duckduckgo"
                                ? "DuckDuckGo Web"
                                : po.provider_id === "searxng"
                                ? "SearXNG Engine"
                                : po.provider_id === "wikimedia"
                                ? "Wikipedia / Wikimedia"
                                : po.provider_id === "hackernews"
                                ? "Hacker News (Algolia)"
                                : po.provider_id}
                            </span>
                            <span className={`${badgeClass} text-[10px]`}>
                              {po.status.replace("_", " ")}
                            </span>
                            <span className="text-[11px] text-[var(--text-dim)]">({po.duration_ms}ms)</span>
                          </div>
                          <p className="text-[11px] text-[var(--text-muted)]">{po.diagnostic}</p>
                        </div>
                        <div className="text-[11px] font-mono text-slate-300 shrink-0">
                          {po.result_count} {po.result_count === 1 ? "match" : "matches"}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Explicit Truthful Notice when Zero Results Encountered with Unhealthy Providers */}
                {providerOutcomes.some((po) => po.status !== "healthy") && (
                  <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/80 text-xs text-amber-200 space-y-1">
                    <div className="flex items-center gap-2 font-semibold text-amber-300">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                      <span>Zero Exposure Is Unconfirmed</span>
                    </div>
                    <p className="text-[11px] leading-relaxed text-amber-200/90">
                      One or more search adapters encountered upstream obstacles (rate-limiting, missing instance configuration, or network blockage). 
                      An empty automated result under these conditions does <strong>not</strong> prove zero online exposure. 
                      Use the <strong>Direct Search Dorks (1-Click)</strong> button above to independently inspect Google, Bing, and Brave directly.
                    </p>
                  </div>
                )}
              </div>
            )}
          </form>

          {/* Privacy Guarantee Banner */}
          <div className="panel-card p-5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-400">
              <Lock className="w-4 h-4" />
              Cryptographic Local-First Guarantee
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Your phone number is parsed directly in memory using Google&apos;s libphonenumber. Database records are indexed by a 256-bit keyed HMAC token. No phone numbers are sent to third-party telemetry, advertising, or centralized collection services.
            </p>
          </div>
        </div>

        {/* Right 1 Column: Telephony Normalization Metadata */}
        <div className="space-y-6">
          <div className="panel-card p-5 space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-dim)] flex items-center justify-between">
              <span>Telephony Profile</span>
              {parseData?.is_valid ? (
                <span className="status-pill pill-emerald text-[10px]">Valid Number</span>
              ) : parseData?.is_possible ? (
                <span className="status-pill pill-amber text-[10px]">Possible</span>
              ) : (
                <span className="status-pill pill-rose text-[10px]">Invalid Format</span>
              )}
            </h3>

            {parseData ? (
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-[var(--text-dim)] block text-[11px]">Masked Display</span>
                  <span className="font-mono font-semibold text-slate-100">{parseData.masked_display}</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-[var(--text-dim)] block text-[11px]">E.164 Format</span>
                    <span className="font-mono text-slate-300">{parseData.e164 || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-dim)] block text-[11px]">National</span>
                    <span className="font-mono text-slate-300">{parseData.national || "N/A"}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-[var(--text-dim)] block text-[11px]">Line Type</span>
                    <span className="font-medium text-slate-200">{parseData.line_type}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-dim)] block text-[11px]">Jurisdiction</span>
                    <span className="text-slate-300">+{parseData.country_code} ({parseData.region_code})</span>
                  </div>
                </div>

                {parseData.location_desc && (
                  <div>
                    <span className="text-[var(--text-dim)] block text-[11px]">Geographic Area</span>
                    <span className="text-slate-200">{parseData.location_desc}</span>
                  </div>
                )}

                {parseData.carrier_name && (
                  <div>
                    <span className="text-[var(--text-dim)] block text-[11px]">Original Carrier Block</span>
                    <span className="text-slate-200">{parseData.carrier_name}</span>
                  </div>
                )}

                <div className="pt-2 border-t border-[var(--border-subtle)]">
                  <span className="text-[var(--text-dim)] block text-[11px] mb-1">Generated Search Variants</span>
                  <div className="space-y-1">
                    {parseData.search_queries.slice(0, 3).map((q, idx) => (
                      <div key={idx} className="font-mono text-[11px] bg-[var(--bg-surface)] px-2 py-1 rounded text-slate-300 border border-[var(--border-subtle)]">
                        {q}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-[var(--text-dim)]">Enter a phone number to inspect parsing rules.</p>
            )}
          </div>
        </div>
      </div>

      {/* Direct Search Dorks Modal */}
      {showDorksModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="panel-card max-w-4xl w-full max-h-[85vh] flex flex-col bg-[var(--bg-card)] border-[var(--border-strong)] shadow-2xl">
            <div className="p-5 border-b border-[var(--border-subtle)] flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <ExternalLink className="w-5 h-5 text-sky-400" />
                  Pre-Computed Search Dorks ({parseData?.masked_display})
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Click any link to run the query directly in your browser with zero CAPTCHA blockers or API limits.
                </p>
              </div>
              <button
                onClick={() => setShowDorksModal(false)}
                className="text-slate-400 hover:text-white p-1 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {dorks.map((d, i) => (
                  <div
                    key={i}
                    className="p-3.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:border-sky-800 transition-colors space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-200">{d.engine_name}</span>
                      <span className="status-pill pill-cyan text-[10px]">{d.category}</span>
                    </div>

                    <p className="text-[11px] text-[var(--text-dim)]">{d.purpose}</p>

                    <div className="p-1.5 rounded bg-[var(--bg-app)] border border-[var(--border-subtle)] font-mono text-[11px] text-slate-300 truncate">
                      {d.query_text}
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <button
                        onClick={() => copyToClipboard(d.query_text)}
                        className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1"
                      >
                        {copiedQuery === d.query_text ? (
                          <>
                            <Check className="w-3 h-3 text-emerald-400" />
                            <span className="text-emerald-400">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" />
                            Copy Query
                          </>
                        )}
                      </button>

                      <a
                        href={d.search_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn-primary text-xs py-1 px-2.5 inline-flex items-center gap-1"
                      >
                        Open Search
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] flex justify-end">
              <button onClick={() => setShowDorksModal(false)} className="btn-secondary text-xs">
                Close Dorks
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
