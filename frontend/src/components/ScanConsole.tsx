import React, { useState, useEffect } from "react";
import {
  Search,
  ExternalLink,
  ShieldCheck,
  Info,
  Check,
  Copy,
  Lock,
  Bug,
  Database,
  MessageSquare,
  Upload,
  HelpCircle,
} from "lucide-react";
import type { PhoneParseResult, ManualDorkItem, ProviderOutcome, AnalyzeSmsResult, DiscoveredSMSSender } from "../types";
import { parsePhone, scanDiscovery, getManualDorks, analyzeSmsMessage, uploadSmsFile } from "../api";

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

const DISCOVERY_PROVIDERS = [
  {
    key: "searxng",
    name: "SearXNG Meta-Search",
    badge: "Meta-Search",
    desc: "Aggregates public indexes with zero tracking. (Local instance recommended)",
  },
  {
    key: "duckduckgo",
    name: "DuckDuckGo HTML",
    badge: "HTML Web",
    desc: "Searches open web text. (Subject to Cloudflare anti-bot verification challenges)",
  },
  {
    key: "wikimedia",
    name: "Wikipedia / Wikimedia",
    badge: "MediaWiki",
    desc: "Official MediaWiki API searching public discussions, pages & leaks.",
  },
  {
    key: "hackernews",
    name: "Hacker News (Algolia)",
    badge: "Algolia",
    desc: "Official Algolia API querying comments, resumes & public listings.",
  },
  {
    key: "wayback",
    name: "Internet Archive (Wayback CDX)",
    badge: "CDX Pastes",
    desc: "Official CDX API searching historical pastes, forums & directory archives.",
  },
] as const;

export const ScanConsole: React.FC<ScanConsoleProps> = ({
  currentIdentity,
  onScanComplete,
  onOpenRemediation,
}) => {
  const [activeTab, setActiveTab] = useState<"web" | "sms">("web");
  const [phoneNumber, setPhoneNumber] = useState(
    currentIdentity?.raw_input || currentIdentity?.e164 || "+918106833178"
  );
  const [region, setRegion] = useState(currentIdentity?.region_code || "IN");
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
  const [totalFound, setTotalFound] = useState<number | null>(null);

  // Direct Browser Dorks Modal
  const [showDorksModal, setShowDorksModal] = useState(false);
  const [dorks, setDorks] = useState<ManualDorkItem[]>([]);

  // SMS / Bank Spam Investigator state
  const [smsSenderInput, setSmsSenderInput] = useState("VM-HDFCBK");
  const [smsBodyInput, setSmsBodyInput] = useState("Pre-approved personal loan of Rs 5 Lakhs available now. Special low interest rate.");
  const [isAnalyzingSms, setIsAnalyzingSms] = useState(false);
  const [singleSmsResult, setSingleSmsResult] = useState<AnalyzeSmsResult | null>(null);
  const [smsFile, setSmsFile] = useState<File | null>(null);
  const [isUploadingSms, setIsUploadingSms] = useState(false);
  const [importedSenders, setImportedSenders] = useState<DiscoveredSMSSender[]>([]);
  const [copiedText, setCopiedText] = useState<string | null>(null);

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
      setTotalFound(res.total_found);
      if (res.scan_status === "partial_failure") {
        setScanMessage(
          `Scan completed with warnings: some public search providers encountered rate-limits or anti-bot challenges. Discovered ${res.total_found} public exposures.`
        );
      } else if (res.scan_status === "all_failed") {
        setScanMessage(
          `Scan incomplete: all queried automated search providers were rate-limited or blocked. Use Direct Browser Dorks to search Google and Bing directly.`
        );
      } else {
        setScanMessage(
          `Scan complete: discovered ${res.total_found} public exposures across queried providers.`
        );
      }
      onScanComplete(parseData);
    } catch (err: any) {
      setScanMessage(`Scan error: ${err.message}`);
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

  const handleAnalyzeSms = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!smsSenderInput.trim()) {
      alert("Please enter a sender header (e.g., VM-HDFCBK, AD-SWIGGY) or phone number.");
      return;
    }
    setIsAnalyzingSms(true);
    try {
      const res = await analyzeSmsMessage(
        smsSenderInput.trim(),
        smsBodyInput.trim(),
        region,
        parseData?.e164 || phoneNumber
      );
      setSingleSmsResult(res);
    } catch (err: any) {
      alert(`SMS analysis failed: ${err.message}`);
    } finally {
      setIsAnalyzingSms(false);
    }
  };

  const handleSmsFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!smsFile) return;
    setIsUploadingSms(true);
    try {
      const res = await uploadSmsFile(smsFile, parseData?.hmac_id || "");
      setImportedSenders(res.senders || []);
    } catch (err: any) {
      alert(`SMS import failed: ${err.message}`);
    } finally {
      setIsUploadingSms(false);
    }
  };

  const copyToClipboard = (text: string, label: string = text) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const getProviderDisplayName = (id: string) => {
    switch (id) {
      case "duckduckgo":
        return "DuckDuckGo Web";
      case "searxng":
        return "SearXNG Engine";
      case "wikimedia":
        return "Wikipedia / Wikimedia";
      case "hackernews":
        return "Hacker News (Algolia)";
      case "wayback":
        return "Wayback Machine (CDX)";
      default:
        return id.toUpperCase();
    }
  };

  return (
    <div className="space-y-6">
      {/* Search Scope & Reality Check Notice */}
      <div className="card p-5 border-cyan-900/40 bg-[#09111e]">
        <div className="flex items-start gap-3">
          <HelpCircle className="w-5 h-5 text-[var(--pixel-cyan)] shrink-0 mt-0.5" />
          <div className="space-y-1.5 text-xs text-[var(--text-muted)] leading-relaxed">
            <div className="font-bold text-sm text-[var(--text-main)] flex items-center gap-2">
              <span>What ClearNum Searches vs. What It Cannot Inspect</span>
            </div>
            <p>
              <strong>Public Leaks vs. Commercial Spam:</strong> A web search can only discover information published on <em>publicly indexed websites</em> (archives, pastebins, forums, and code repositories). It <strong>cannot</strong> inspect private bank accounts, shopping apps (Amazon, Swiggy), carrier billing records, or private SMS inboxes.
            </p>
            <p className="text-[11px] text-[var(--text-dim)]">
              If you receive promotional SMS or bank calls, your number is typically distributed via <strong>private commercial telecom gateways (DLT headers)</strong> or customer merchant records, which are never indexed on search engines. Use the <strong>SMS & Bank Spam Investigator</strong> tab below to decode sender headers and generate statutory DND complaints.
            </p>
          </div>
        </div>
      </div>

      {/* Hero / Introduction Bar */}
      <div className="card p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="kicker-tag">[ DUAL-MODE DISCOVERY ]</span>
            </div>
            <h1 className="text-lg sm:text-xl font-bold text-[var(--text-main)] flex items-center gap-2.5">
              <Bug className="w-5 h-5 text-[var(--pixel-green)]" />
              Privacy Exposure Discovery Engine
            </h1>
            <p className="text-xs sm:text-sm text-[var(--text-muted)] mt-1 max-w-2xl leading-relaxed">
              Investigate public web leaks referencing your phone number, or analyze commercial SMS headers from banks, apps, and telemarketers to enforce statutory Do-Not-Disturb opt-outs.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={handleOpenDorks}
              className="btn btn-secondary text-xs py-2 px-3.5"
              title="Open pre-computed Google, Bing, Brave, and directory search links"
            >
              <ExternalLink className="w-4 h-4 text-[var(--pixel-cyan)]" />
              <span>Direct Search Dorks (1-Click)</span>
            </button>
            <button
              type="button"
              onClick={onOpenRemediation}
              className="btn btn-primary text-xs py-2 px-3.5"
              title="Browse 25+ verified broker removal procedures"
            >
              <ShieldCheck className="w-4 h-4 text-[#022c22]" />
              <span>Remediation Hub</span>
            </button>
          </div>
        </div>
      </div>

      {/* Dual Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("web")}
          className={`px-4 py-2 text-xs font-semibold rounded-t-md transition-colors flex items-center gap-2 ${
            activeTab === "web"
              ? "bg-[var(--bg-card)] text-[var(--pixel-green)] border-b-2 border-[var(--pixel-green)]"
              : "text-[var(--text-muted)] hover:text-[var(--text-main)]"
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          <span>Public Web & Archive Scan</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("sms")}
          className={`px-4 py-2 text-xs font-semibold rounded-t-md transition-colors flex items-center gap-2 ${
            activeTab === "sms"
              ? "bg-[var(--bg-card)] text-[var(--pixel-cyan)] border-b-2 border-[var(--pixel-cyan)]"
              : "text-[var(--text-muted)] hover:text-[var(--text-main)]"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Promotional SMS & Bank Spam Investigator</span>
        </button>
      </div>

      {/* TAB 1: Public Web & Archive Scan */}
      {activeTab === "web" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Columns: Input & Configuration */}
          <div className="lg:col-span-2 space-y-6">
            <form onSubmit={handleStartScan} className="card p-6 space-y-5">
              <h2 className="section-title">
                <Search className="w-4 h-4 text-[var(--pixel-green)]" />
                TARGET NUMBER & PUBLIC SEARCH ENGINES
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1.5 uppercase tracking-wider">
                    Country / Region
                  </label>
                  <select
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    className="input-field"
                  >
                    {COUNTRY_OPTIONS.map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1.5 uppercase tracking-wider">
                    Phone Number
                  </label>
                  <input
                    type="text"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="e.g. +91 81068 33178 or 8106833178"
                    className="input-field font-mono text-sm"
                    required
                  />
                </div>
              </div>

              {/* Provider Checkboxes */}
              <div className="pt-3 border-t border-[var(--border-subtle)] space-y-3">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    Active Automated Providers
                  </label>
                  <span className="text-[10px] text-[var(--text-dim)]">
                    Localhost / Non-telemetry only
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {DISCOVERY_PROVIDERS.map((p) => {
                    const isChecked = providers[p.key as keyof typeof providers];
                    return (
                      <label
                        key={p.key}
                        className={`provider-card ${isChecked ? "selected" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) =>
                            setProviders({ ...providers, [p.key]: e.target.checked })
                          }
                        />
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-xs text-[var(--text-main)]">
                              {p.name}
                            </span>
                            <span className="kicker-tag text-[9px]">{p.badge}</span>
                          </div>
                          <p className="text-[11px] text-[var(--text-muted)] leading-tight">
                            {p.desc}
                          </p>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Custom Target URLs (Collapsible) */}
              <div className="pt-3 border-t border-[var(--border-subtle)]">
                <details className="text-xs group">
                  <summary className="font-semibold text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-main)] transition-colors flex items-center justify-between">
                    <span>Target Specific URLs (Optional SSRF-Safe Audit)</span>
                    <span className="text-[10px] text-[var(--pixel-cyan)] group-open:rotate-180 transition-transform">
                      ▼
                    </span>
                  </summary>
                  <div className="mt-3 space-y-2">
                    <p className="text-[11px] text-[var(--text-dim)] leading-relaxed">
                      Enter specific public URLs (one per line) to check directly for your telephone number. Outbound requests enforce strict SSRF protections against internal IPs.
                    </p>
                    <textarea
                      value={customUrls}
                      onChange={(e) => setCustomUrls(e.target.value)}
                      placeholder="https://example.com/team-directory&#10;https://pastebin.com/raw/example"
                      rows={2}
                      className="input-field font-mono text-xs w-full"
                    />
                  </div>
                </details>
              </div>

              {/* Scan Trigger Button */}
              <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                <button
                  type="submit"
                  disabled={isScanning || !parseData?.is_possible}
                  className="btn btn-primary py-2.5 px-6 font-semibold flex items-center justify-center gap-2"
                >
                  <Search className={`w-4 h-4 ${isScanning ? "animate-spin" : ""}`} />
                  <span>{isScanning ? "Scanning Web & Archives..." : "Start Discovery Scan"}</span>
                </button>

                <button
                  type="button"
                  onClick={handleOpenDorks}
                  className="btn btn-secondary py-2.5 px-4 text-xs font-semibold flex items-center justify-center gap-2"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-[var(--pixel-cyan)]" />
                  <span>Open Browser Dorks</span>
                </button>
              </div>

              {/* Scan Status & Diagnostics */}
              {scanMessage && (
                <div
                  className={`p-3.5 rounded-lg border text-xs leading-relaxed ${
                    scanMessage.includes("incomplete") || scanMessage.includes("all_failed")
                      ? "border-amber-500/40 bg-amber-950/20 text-amber-300"
                      : scanMessage.includes("warnings")
                      ? "border-cyan-500/40 bg-cyan-950/20 text-cyan-300"
                      : "border-emerald-500/40 bg-emerald-950/20 text-emerald-300"
                  }`}
                >
                  {scanMessage}
                </div>
              )}

              {/* Transparent Provider Outcomes Log */}
              {providerOutcomes.length > 0 && (
                <div className="space-y-3 pt-4 border-t border-[var(--border-subtle)]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[var(--text-main)] uppercase tracking-wider">
                      Provider Audit Status ({providerOutcomes.length} Checked)
                    </span>
                    <span className="font-mono text-[11px] text-[var(--text-dim)]">
                      Total Exposures Found: {totalFound ?? 0}
                    </span>
                  </div>

                  <div className="space-y-2">
                    {providerOutcomes.map((po) => {
                      const isHealthy = po.status === "healthy";
                      const isRateLimited = po.status === "rate_limited";
                      return (
                        <div
                          key={po.provider_id}
                          className="flex items-start justify-between gap-3 p-3 rounded bg-[var(--bg-app)] border border-[var(--border-subtle)]"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-xs text-[var(--text-main)]">
                                {getProviderDisplayName(po.provider_id)}
                              </span>
                              <span
                                className={`status-pill ${
                                  isHealthy
                                    ? "pill-pixel-green"
                                    : isRateLimited
                                    ? "pill-pixel-yellow"
                                    : "pill-pixel-purple"
                                }`}
                              >
                                {po.status.toUpperCase()}
                              </span>
                              <span className="font-mono text-[11px] text-[var(--text-dim)]">
                                ({po.duration_ms}ms)
                              </span>
                            </div>
                            <p className="text-[11px] text-[var(--text-muted)]">{po.diagnostic}</p>
                          </div>
                          <div className="font-mono text-xs text-[var(--pixel-green)] font-semibold shrink-0">
                            {po.result_count} {po.result_count === 1 ? "match" : "matches"}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Context for 0 Results */}
                  {totalFound === 0 && (
                    <div className="p-3.5 rounded-md border border-[var(--pixel-cyan)]/30 bg-[var(--bg-surface)] text-xs text-[var(--text-muted)] space-y-1.5">
                      <div className="flex items-center gap-2 font-semibold text-[var(--pixel-cyan)]">
                        <Info className="w-4 h-4 shrink-0" />
                        <span>Why 0 Public Exposures Does Not Mean Zero Spam</span>
                      </div>
                      <p className="text-[11px] leading-relaxed">
                        No public web directory, Wikipedia article, or paste archive was found mentioning your number. If you receive promotional SMS or calls, they originate from private telecom channels (DLT commercial gateways). Use the <strong>Promotional SMS & Bank Spam Investigator</strong> tab to decode those messages.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </form>

            {/* Cryptographic Guarantee Card */}
            <div className="card p-5 space-y-2 border-emerald-900/40 bg-[#0c1424]">
              <div className="flex items-center gap-2 text-xs font-bold text-[var(--pixel-green)] uppercase tracking-wider">
                <Lock className="w-4 h-4" />
                Cryptographic Localhost Invariant
              </div>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Raw phone numbers are parsed entirely in local memory using Google's libphonenumber. Database records are indexed exclusively by a 256-bit keyed HMAC token. No raw numbers or identities are ever transmitted to third-party telemetry or cloud analytics.
              </p>
            </div>
          </div>

          {/* Right 1 Column: Telephony Normalization Metadata */}
          <div className="space-y-6">
            <div className="card p-5 space-y-4">
              <h3 className="section-title">
                <Database className="w-4 h-4 text-[var(--pixel-cyan)]" />
                Telephony Profile
              </h3>

              {parseData ? (
                <div className="space-y-3.5 text-xs">
                  <div>
                    <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                      Masked Display
                    </span>
                    <span className="font-mono text-sm font-semibold text-[var(--text-main)]">
                      {parseData.masked_display}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                        E.164 Format
                      </span>
                      <span className="font-mono text-xs text-[var(--text-main)]">
                        {parseData.e164 || "N/A"}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                        National
                      </span>
                      <span className="font-mono text-xs text-[var(--text-main)]">
                        {parseData.national || "N/A"}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                        Line Type
                      </span>
                      <span className="font-medium text-[var(--text-main)]">
                        {parseData.line_type}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                        Jurisdiction
                      </span>
                      <span className="font-medium text-[var(--text-main)]">
                        +{parseData.country_code} ({parseData.region_code})
                      </span>
                    </div>
                  </div>

                  {parseData.location_desc && (
                    <div>
                      <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                        Geographic Area
                      </span>
                      <span className="font-medium text-[var(--text-main)]">
                        {parseData.location_desc}
                      </span>
                    </div>
                  )}

                  {parseData.carrier_name && (
                    <div>
                      <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                        Original Carrier Block
                      </span>
                      <span className="font-medium text-[var(--text-main)]">
                        {parseData.carrier_name}
                      </span>
                    </div>
                  )}

                  <div className="pt-2 border-t border-[var(--border-subtle)]">
                    <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-1.5">
                      Permutation Queries Generated
                    </span>
                    <div className="space-y-1.5">
                      {parseData.search_queries.slice(0, 4).map((q, idx) => (
                        <div
                          key={idx}
                          className="font-mono text-[11px] bg-[var(--bg-app)] px-2.5 py-1 rounded border border-[var(--border-subtle)] text-[var(--text-muted)]"
                        >
                          {q}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[var(--text-dim)] leading-relaxed">
                  Enter a phone number to inspect telephony normalization.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Promotional SMS & Bank Spam Investigator */}
      {activeTab === "sms" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Single SMS / DLT Header Analyzer */}
            <div className="card p-6 space-y-4">
              <h2 className="section-title">
                <MessageSquare className="w-4 h-4 text-[var(--pixel-cyan)]" />
                Analyze Single Commercial SMS / Header
              </h2>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Received a promotional message from a bank, shopping app, or telemarketer? Enter the sender header (e.g. <code>VM-HDFCBK</code>, <code>AD-SWIGGY</code>, <code>VK-AMAZON</code>, <code>CP-AIRTEL</code>, or a 5-6 digit shortcode) to identify the brand, telecom circle, and generate a 1-click statutory DND complaint.
              </p>

              <form onSubmit={handleAnalyzeSms} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1 uppercase tracking-wider">
                    Sender Address / DLT Header
                  </label>
                  <input
                    type="text"
                    value={smsSenderInput}
                    onChange={(e) => setSmsSenderInput(e.target.value)}
                    placeholder="e.g. VM-HDFCBK, AD-SWIGGY, 223344"
                    className="input-field font-mono text-sm"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1 uppercase tracking-wider">
                    Message Body (Optional for NLP Classification)
                  </label>
                  <textarea
                    value={smsBodyInput}
                    onChange={(e) => setSmsBodyInput(e.target.value)}
                    placeholder="Paste the SMS text here..."
                    rows={3}
                    className="input-field text-xs w-full font-mono"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isAnalyzingSms || !smsSenderInput.trim()}
                  className="btn btn-primary py-2 px-5 text-xs font-semibold flex items-center gap-2"
                >
                  <Search className={`w-3.5 h-3.5 ${isAnalyzingSms ? "animate-spin" : ""}`} />
                  <span>{isAnalyzingSms ? "Analyzing Sender..." : "Analyze Commercial Sender"}</span>
                </button>
              </form>

              {/* Result of Analysis */}
              {singleSmsResult && (
                <div className="p-4 rounded-lg border border-cyan-800/40 bg-[#091526] space-y-3 mt-4 text-xs">
                  <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
                    <div>
                      <span className="text-[10px] text-[var(--text-dim)] uppercase block">Detected Brand</span>
                      <span className="text-sm font-bold text-[var(--text-main)]">
                        {singleSmsResult.brand_name || singleSmsResult.sender}
                      </span>
                    </div>
                    <span className="status-pill pill-pixel-cyan font-mono text-[10px]">
                      {singleSmsResult.category}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-[10px] text-[var(--text-dim)] block">Sender Header:</span>
                      <span className="font-mono text-[var(--text-main)] font-semibold">{singleSmsResult.sender}</span>
                    </div>
                    {singleSmsResult.dlt_prefix && (
                      <div>
                        <span className="text-[10px] text-[var(--text-dim)] block">DLT Header Prefix:</span>
                        <span className="font-mono text-[var(--text-main)]">{singleSmsResult.dlt_prefix}</span>
                      </div>
                    )}
                    {singleSmsResult.telecom_circle && (
                      <div>
                        <span className="text-[10px] text-[var(--text-dim)] block">Licensed Telecom Circle:</span>
                        <span className="font-mono text-[var(--pixel-cyan)]">{singleSmsResult.telecom_circle}</span>
                      </div>
                    )}
                    {singleSmsResult.access_provider && (
                      <div>
                        <span className="text-[10px] text-[var(--text-dim)] block">Telecom Access Provider:</span>
                        <span className="font-mono text-[var(--pixel-cyan)]">{singleSmsResult.access_provider}</span>
                      </div>
                    )}
                  </div>

                  {singleSmsResult.confidence_disclaimer && (
                    <div className="p-2 rounded bg-amber-950/20 border border-amber-800/30 text-[10px] text-amber-300/90 leading-tight">
                      <strong className="text-amber-200">DLT Route Inference:</strong> {singleSmsResult.confidence_disclaimer}
                    </div>
                  )}

                  <div>
                    <span className="text-[10px] text-[var(--text-dim)] block mb-1">Recommended Action:</span>
                    <span className="text-[var(--pixel-green)] font-semibold">
                      {singleSmsResult.recommended_action}
                    </span>
                  </div>

                  {/* Official Direct Opt-Out or Portal Link */}
                  {singleSmsResult.dnd_portal_url && (
                    <div className="pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between">
                      <div>
                        <span className="text-[10px] text-[var(--text-dim)] block">Official Company DND / Opt-Out Portal</span>
                        <span className="text-xs text-[var(--text-main)]">{singleSmsResult.brand_name} Preference Center</span>
                      </div>
                      <a
                        href={singleSmsResult.dnd_portal_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-secondary text-[11px] py-1 px-3 flex items-center gap-1.5"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Open DND Portal</span>
                      </a>
                    </div>
                  )}

                  {/* 1-Click TRAI 1909 Complaint SMS */}
                  {singleSmsResult.complaint_sms && (
                    <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold text-[var(--pixel-yellow)] uppercase">
                          TRAI 1909 Statutory Complaint Format (TCCCPR 2018)
                        </span>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(singleSmsResult.complaint_sms!, "1909")}
                          className="btn btn-secondary text-[10px] py-1 px-2 flex items-center gap-1"
                        >
                          {copiedText === "1909" ? <Check className="w-3 h-3 text-[var(--pixel-green)]" /> : <Copy className="w-3 h-3" />}
                          <span>{copiedText === "1909" ? "Copied!" : "Copy SMS"}</span>
                        </button>
                      </div>
                      <div className="p-2 rounded bg-[var(--bg-app)] font-mono text-[11px] text-[var(--text-main)] break-all border border-[var(--border-subtle)]">
                        {singleSmsResult.complaint_sms}
                      </div>
                      <p className="text-[10px] text-[var(--text-dim)]">
                        Send this exact SMS to <strong>1909</strong> from your mobile SIM within <strong>3 days (72 hours)</strong> of receipt. Your telecom operator (Airtel, Jio, Vi, BSNL) will issue a formal complaint ticket.
                      </p>
                      {singleSmsResult.statutory_deadline_info && (
                        <p className="text-[10px] text-amber-300/90 leading-normal">
                          <strong>TRAI Statutory Rule:</strong> {singleSmsResult.statutory_deadline_info}
                        </p>
                      )}
                    </div>
                  )}

                  {/* DoT Chakshu Portal Escalation (Suspect Fraud) */}
                  {singleSmsResult.chakshu_portal_url && (
                    <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold text-[var(--pixel-purple)] uppercase">
                          DoT Chakshu (Sanchar Saathi) Suspect Fraud Escalation
                        </span>
                        <a
                          href={singleSmsResult.chakshu_portal_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-secondary text-[10px] py-1 px-2 flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3 text-[var(--pixel-purple)]" />
                          <span>Report on Chakshu</span>
                        </a>
                      </div>
                      <p className="text-[10px] text-[var(--text-dim)]">
                        If this message offers fake loans, lottery prizes, electricity bill threats, or suspicious links, report it on DoT's official Chakshu facility to trigger pan-India telecom blacklisting.
                      </p>
                    </div>
                  )}

                  {/* DPDP Act 2023 Statutory Consent Revocation Notice */}
                  {singleSmsResult.dpdp_notice && (
                    <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold text-[var(--pixel-green)] uppercase">
                          DPDP Act 2023 Statutory Consent Revocation &amp; Erasure Demand
                        </span>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(singleSmsResult.dpdp_notice!, "dpdp")}
                          className="btn btn-secondary text-[10px] py-1 px-2 flex items-center gap-1"
                        >
                          {copiedText === "dpdp" ? <Check className="w-3 h-3 text-[var(--pixel-green)]" /> : <Copy className="w-3 h-3" />}
                          <span>{copiedText === "dpdp" ? "Copied!" : "Copy Legal Notice"}</span>
                        </button>
                      </div>
                      <pre className="p-2 rounded bg-[var(--bg-app)] font-mono text-[10px] text-[var(--text-muted)] whitespace-pre-wrap max-h-28 overflow-y-auto border border-[var(--border-subtle)]">
                        {singleSmsResult.dpdp_notice}
                      </pre>
                      {singleSmsResult.grievance_email && (
                        <p className="text-[10px] text-[var(--text-dim)]">
                          Email this statutory demand directly to: <strong>{singleSmsResult.grievance_email}</strong>
                        </p>
                      )}
                      {singleSmsResult.dpdp_status_note && (
                        <p className="text-[10px] text-zinc-400 leading-normal">
                          <strong>Regulatory Status:</strong> {singleSmsResult.dpdp_status_note}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Merchant Opt-Out Notice */}
                  {singleSmsResult.merchant_notice && (
                    <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
                          Statutory Demand for Consent Revocation
                        </span>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(singleSmsResult.merchant_notice!, "notice")}
                          className="btn btn-secondary text-[10px] py-1 px-2 flex items-center gap-1"
                        >
                          {copiedText === "notice" ? <Check className="w-3 h-3 text-[var(--pixel-green)]" /> : <Copy className="w-3 h-3" />}
                          <span>{copiedText === "notice" ? "Copied!" : "Copy Legal Notice"}</span>
                        </button>
                      </div>
                      <pre className="p-2 rounded bg-[var(--bg-app)] font-mono text-[10px] text-[var(--text-muted)] whitespace-pre-wrap max-h-24 overflow-y-auto border border-[var(--border-subtle)]">
                        {singleSmsResult.merchant_notice}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Batch Android SMS XML / JSON File Upload */}
            <div className="card p-6 space-y-4">
              <h2 className="section-title">
                <Upload className="w-4 h-4 text-[var(--pixel-cyan)]" />
                Import Full SMS Backup (XML / JSON / CSV)
              </h2>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Import an encrypted local SMS backup (exported from Android apps such as "SMS Backup &amp; Restore" or Google Takeout) to parse all commercial senders, calculate spam volume, and extract opt-out commands locally in your browser/memory.
              </p>

              <form onSubmit={handleSmsFileUpload} className="space-y-3.5">
                <div className="p-4 border-2 border-dashed border-[var(--border-subtle)] rounded-lg text-center bg-[var(--bg-app)]">
                  <input
                    type="file"
                    accept=".xml,.json,.csv"
                    onChange={(e) => setSmsFile(e.target.files?.[0] || null)}
                    className="text-xs text-[var(--text-dim)] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-[var(--bg-surface)] file:text-[var(--text-main)] hover:file:bg-[var(--border-subtle)] cursor-pointer"
                  />
                  <p className="text-[10px] text-[var(--text-dim)] mt-2">
                    Supported: Android SMS Backup XML, Google Takeout JSON, or CSV. File is parsed in ephemeral local memory and unlinked immediately.
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={isUploadingSms || !smsFile}
                  className="btn btn-secondary py-2 px-5 text-xs font-semibold flex items-center gap-2"
                >
                  <Upload className={`w-3.5 h-3.5 ${isUploadingSms ? "animate-spin" : ""}`} />
                  <span>{isUploadingSms ? "Parsing Backup..." : "Upload & Parse SMS Senders"}</span>
                </button>
              </form>

              {/* Imported Senders Table */}
              {importedSenders.length > 0 && (
                <div className="space-y-2 pt-3 border-t border-[var(--border-subtle)]">
                  <div className="flex items-center justify-between text-xs font-bold text-[var(--text-main)]">
                    <span>Parsed Commercial Senders ({importedSenders.length})</span>
                  </div>
                  <div className="max-h-60 overflow-y-auto space-y-1.5">
                    {importedSenders.map((s, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded bg-[var(--bg-app)] border border-[var(--border-subtle)] flex items-center justify-between gap-3 text-xs"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-[var(--text-main)]">
                              {s.sender_number}
                            </span>
                            {s.brand_name && (
                              <span className="text-[11px] text-[var(--pixel-cyan)]">
                                ({s.brand_name})
                              </span>
                            )}
                            <span className="status-pill pill-pixel-purple text-[9px]">
                              {s.category}
                            </span>
                          </div>
                          <p className="text-[11px] text-[var(--text-dim)] truncate max-w-xs mt-0.5">
                            {s.sample_body || "No sample text"}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="font-mono text-xs text-[var(--pixel-green)] font-semibold block">
                            {s.message_count} msgs
                          </span>
                          {s.has_opt_out_keyword && (
                            <span className="text-[10px] text-[var(--pixel-yellow)] font-mono">
                              Opt: {s.opt_out_command}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Direct Search Dorks Modal */}
      {showDorksModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="card w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden border-[var(--border-subtle)] shadow-2xl">
            <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-surface)]">
              <div>
                <h3 className="font-bold text-sm text-[var(--text-main)] flex items-center gap-2">
                  <ExternalLink className="w-4 h-4 text-[var(--pixel-cyan)]" />
                  Pre-Computed Search Dorks (1-Click Verification)
                </h3>
                <p className="text-[11px] text-[var(--text-dim)] mt-0.5">
                  Bypass automated scraping bot protections by running pre-computed targeted queries in your own authenticated browser.
                </p>
              </div>
              <button
                onClick={() => setShowDorksModal(false)}
                className="text-[var(--text-dim)] hover:text-[var(--text-main)] p-1 rounded font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-3 flex-1">
              {dorks.map((dork, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] hover:border-[var(--pixel-cyan)]/40 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-[var(--text-main)]">
                        {dork.engine_name}
                      </span>
                      <span className="kicker-tag text-[9px]">{dork.category}</span>
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)]">{dork.purpose}</p>
                    <code className="text-[11px] text-[var(--pixel-green)] font-mono block bg-[#050811] px-2 py-0.5 rounded border border-[var(--border-subtle)]">
                      {dork.query_text}
                    </code>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => copyToClipboard(dork.query_text, `dork-${idx}`)}
                      className="btn btn-secondary py-1 px-2.5 text-[11px]"
                      title="Copy query text"
                    >
                      {copiedText === `dork-${idx}` ? (
                        <Check className="w-3 h-3 text-[var(--pixel-green)]" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                      <span>{copiedText === `dork-${idx}` ? "Copied" : "Copy"}</span>
                    </button>
                    <a
                      href={dork.search_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-primary py-1 px-3 text-[11px] flex items-center gap-1 font-semibold"
                    >
                      <span>Search</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] text-right">
              <button
                onClick={() => setShowDorksModal(false)}
                className="btn btn-secondary text-xs py-1.5 px-4"
              >
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
