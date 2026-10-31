import React, { useState, useEffect } from "react";
import {
  Search,
  ExternalLink,
  ShieldCheck,
  ShieldAlert,
  Info,
  Check,
  Copy,
  Lock,
  Bug,
  Database,
  MessageSquare,
  Upload,
  HelpCircle,
  AlertTriangle,
  ArrowRight,
  Eye,
  EyeOff,
} from "lucide-react";
import type {
  PhoneParseResult,
  ManualDorkItem,
  ProviderOutcome,
  AnalyzeSmsResult,
  DiscoveredSMSSender,
  SearchPrivacyDisclosureResponse,
} from "../types";
import {
  parsePhone,
  scanDiscovery,
  getManualDorks,
  analyzeSmsMessage,
  uploadSmsFile,
  uploadMboxFile,
  getSearchPrivacyDisclosure,
} from "../api";

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
  // Discovery Path: 'local' (SMS/MBOX) or 'web' (Consented/Manual Search)
  const [activeTab, setActiveTab] = useState<"local" | "web">("local");

  // Core Identity Inputs
  const [phoneNumber, setPhoneNumber] = useState(
    currentIdentity?.raw_input || currentIdentity?.e164 || "+918106833178"
  );
  const [region, setRegion] = useState(currentIdentity?.region_code || "IN");
  const [parseData, setParseData] = useState<PhoneParseResult | null>(currentIdentity);
  const [revealRawE164, setRevealRawE164] = useState(false);

  // Scan & Execution States
  const [isScanning, setIsScanning] = useState(false);
  const [scanStage, setScanStage] = useState<"idle" | "normalizing" | "querying" | "deduplicating" | "complete">("idle");
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

  // Local Analysis State (MBOX & SMS)
  const [selectedLocalFile, setSelectedLocalFile] = useState<File | null>(null);
  const [isProcessingLocalFile, setIsProcessingLocalFile] = useState(false);
  const [localFileOutcome, setLocalFileOutcome] = useState<{
    filename: string;
    type: "sms" | "mbox";
    itemsCount: number;
    exposuresCreated: number;
    message: string;
  } | null>(null);

  // Single SMS Header Analyzer State
  const [smsSenderInput, setSmsSenderInput] = useState("VM-HDFCBK");
  const [smsBodyInput, setSmsBodyInput] = useState("Pre-approved personal loan of Rs 5 Lakhs available now. Special low interest rate.");
  const [isAnalyzingSms, setIsAnalyzingSms] = useState(false);
  const [singleSmsResult, setSingleSmsResult] = useState<AnalyzeSmsResult | null>(null);
  const [importedSenders, setImportedSenders] = useState<DiscoveredSMSSender[]>([]);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  // Search Mode & Consent Disclosure
  const [searchMode, setSearchMode] = useState<"manual" | "automated">("manual");
  const [showDisclosureModal, setShowDisclosureModal] = useState(false);
  const [disclosureData, setDisclosureData] = useState<SearchPrivacyDisclosureResponse | null>(null);
  const [loadingDisclosure, setLoadingDisclosure] = useState(false);
  const [consentOptIn, setConsentOptIn] = useState(false);

  // Live normalization as user types
  useEffect(() => {
    if (!phoneNumber || phoneNumber.trim().length < 5) return;
    const timer = setTimeout(async () => {
      try {
        const res = await parsePhone(phoneNumber, region);
        setParseData(res);
      } catch {
        // Silently preserve current parse
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [phoneNumber, region]);

  // Validation warning computation
  const isInputInvalid = Boolean(
    phoneNumber && phoneNumber.trim().length >= 4 && parseData && !parseData.is_possible
  );

  const handleStartScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!parseData || !parseData.is_possible) {
      alert("Please enter a valid, possible phone number before scanning.");
      return;
    }

    if (searchMode === "manual") {
      // ASSISTED MANUAL SEARCH: Zero external network transmission
      setIsScanning(true);
      setScanStage("normalizing");
      setScanMessage("Generating assisted search queries with zero external network transmission...");
      try {
        setScanStage("querying");
        const res = await scanDiscovery(
          parseData.e164 || phoneNumber,
          region,
          [],
          [],
          { granted: false }
        );
        setScanStage("deduplicating");
        setProviderOutcomes(res.provider_outcomes || []);
        setTotalFound(0);
        setScanStage("complete");
        setScanMessage(
          res.privacy_notice || "Assisted manual search generated. Zero outbound requests sent from backend. Inspect 1-click browser dorks below."
        );
        onScanComplete(parseData);
        // Automatically open the dorks modal
        const dorkList = await getManualDorks(parseData.e164 || phoneNumber, region);
        setDorks(dorkList);
        setShowDorksModal(true);
      } catch (err: any) {
        setScanStage("idle");
        setScanMessage(`Scan error: ${err.message}`);
      } finally {
        setIsScanning(false);
      }
    } else {
      // AUTOMATED SEARCH: Fetch disclosure before transmitting any query
      setLoadingDisclosure(true);
      try {
        const disc = await getSearchPrivacyDisclosure(parseData.e164 || phoneNumber, region);
        setDisclosureData(disc);
        setConsentOptIn(false);
        setShowDisclosureModal(true);
      } catch (err: any) {
        alert(`Failed to fetch privacy disclosure: ${err.message}`);
      } finally {
        setLoadingDisclosure(false);
      }
    }
  };

  const handleConfirmAutomatedScan = async () => {
    if (!parseData || !parseData.is_possible) return;
    if (!consentOptIn) {
      alert("Please check the explicit opt-in box to confirm transmission.");
      return;
    }

    setShowDisclosureModal(false);
    setIsScanning(true);
    setScanStage("normalizing");
    setScanMessage("Initiating authorized scan across selected external providers...");

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
      setScanStage("querying");
      const res = await scanDiscovery(
        parseData.e164 || phoneNumber,
        region,
        activeProviders,
        targetList,
        { granted: true, confirmed_providers: activeProviders }
      );
      setScanStage("deduplicating");
      setProviderOutcomes(res.provider_outcomes || []);
      setTotalFound(res.total_found);
      setScanStage("complete");

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
      setScanStage("idle");
      setScanMessage(`Scan error: ${err.message}`);
    } finally {
      setIsScanning(false);
    }
  };

  const handleCancelAutomatedScan = () => {
    setShowDisclosureModal(false);
    setSearchMode("manual");
    setScanMessage("External automated scan cancelled. Switched to privacy-first Assisted Manual Search (no data transmitted).");
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

  // Local File Upload Handler (supporting .mbox and .xml,.json,.csv)
  const handleLocalFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLocalFile) return;

    const lowerName = selectedLocalFile.name.toLowerCase();
    const isMbox = lowerName.endsWith(".mbox");
    const isSms = lowerName.endsWith(".xml") || lowerName.endsWith(".json") || lowerName.endsWith(".csv");

    if (!isMbox && !isSms) {
      alert("Unsupported file format. Please upload an SMS backup (.xml, .json, .csv) or email archive (.mbox).");
      return;
    }

    setIsProcessingLocalFile(true);
    setLocalFileOutcome(null);

    try {
      if (isMbox) {
        const res = await uploadMboxFile(
          selectedLocalFile,
          parseData?.hmac_id || "",
          parseData?.e164 || phoneNumber,
          region
        );
        const exposuresCount = res.exposures_created || 0;
        setLocalFileOutcome({
          filename: res.filename,
          type: "mbox",
          itemsCount: res.discovered_subscriptions_count || 0,
          exposuresCreated: exposuresCount,
          message: `Discovered ${res.discovered_subscriptions_count} commercial email subscriptions. Created ${exposuresCount} exposure findings in your local audit.`,
        });
      } else {
        const res = await uploadSmsFile(
          selectedLocalFile,
          parseData?.hmac_id || "",
          parseData?.e164 || phoneNumber,
          region
        );
        setImportedSenders(res.senders || []);
        const exposuresCount = res.exposures_created || 0;
        setLocalFileOutcome({
          filename: res.filename,
          type: "sms",
          itemsCount: res.senders_count || 0,
          exposuresCreated: exposuresCount,
          message: `Discovered ${res.senders_count} commercial SMS senders. Created ${exposuresCount} exposure findings in your local audit.`,
        });
      }
    } catch (err: any) {
      alert(`Local file analysis failed: ${err.message}`);
    } finally {
      setIsProcessingLocalFile(false);
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
              If you receive promotional SMS or bank calls, your number is typically distributed via <strong>private commercial telecom gateways (DLT headers)</strong> or customer merchant records, which are never indexed on search engines. Use the <strong>Local File & Commercial SMS Analysis</strong> tab below to decode sender headers and generate statutory DND complaints.
            </p>
          </div>
        </div>
      </div>

      {/* Universal Target Identity Bar */}
      <div className="card p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="kicker-tag">[ TELEPHONY NORMALIZATION ]</span>
            </div>
            <h1 className="text-lg sm:text-xl font-bold text-[var(--text-main)] flex items-center gap-2.5">
              <Bug className="w-5 h-5 text-[var(--pixel-green)]" />
              Privacy Exposure Discovery Engine
            </h1>
            <p className="text-xs sm:text-sm text-[var(--text-muted)] mt-1 max-w-2xl leading-relaxed">
              Your raw telephone number is normalized entirely in local RAM using Google's libphonenumber. Database records are indexed exclusively by a 256-bit keyed HMAC token. No raw numbers or identities are ever transmitted to third-party telemetry.
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
              title="Browse verified broker removal procedures"
            >
              <ShieldCheck className="w-4 h-4 text-[#022c22]" />
              <span>Remediation Hub</span>
            </button>
          </div>
        </div>

        {/* Input Fields */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
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
              placeholder="e.g. +1 415 555 2671 or 8106833178"
              className="input-field font-mono text-sm"
              required
            />
          </div>
        </div>

        {/* Live Validation Alert */}
        {isInputInvalid && (
          <div className="p-3 rounded-lg border border-amber-500/40 bg-amber-950/20 text-xs text-amber-300 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <strong>Invalid or Incomplete Number Format:</strong> The entered digits do not form a possible phone number for {region} (+{parseData?.country_code || "1"}). Please enter complete subscriber digits before initiating discovery.
            </div>
          </div>
        )}

        {/* Live Identity Metadata Pills */}
        {parseData && parseData.is_possible && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-[var(--border-subtle)] text-xs">
            <div className="p-2.5 rounded bg-[var(--bg-app)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-dim)] uppercase block">Masked Display</span>
              <span className="font-mono font-bold text-[var(--pixel-green)]">{parseData.masked_display}</span>
            </div>
            <div className="p-2.5 rounded bg-[var(--bg-app)] border border-[var(--border-subtle)] flex items-center justify-between">
              <div>
                <span className="text-[10px] text-[var(--text-dim)] uppercase block">E.164 Canonical</span>
                <span className="font-mono text-[var(--text-main)]">
                  {revealRawE164 ? (parseData.e164 || "N/A") : parseData.masked_display}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setRevealRawE164(!revealRawE164)}
                className="text-[var(--text-dim)] hover:text-[var(--text-main)] p-1 ml-1"
                title={revealRawE164 ? "Mask telephone digits" : "Reveal raw E.164 digits"}
                aria-label={revealRawE164 ? "Mask telephone digits" : "Reveal raw E.164 digits"}
              >
                {revealRawE164 ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
            <div className="p-2.5 rounded bg-[var(--bg-app)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-dim)] uppercase block">Line Type</span>
              <span className="font-medium text-[var(--pixel-cyan)]">{parseData.line_type || "MOBILE"}</span>
            </div>
            <div className="p-2.5 rounded bg-[var(--bg-app)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-dim)] uppercase block">Carrier / Area</span>
              <span className="font-medium text-[var(--text-main)] truncate block">{parseData.carrier_name || parseData.location_desc || "National"}</span>
            </div>
          </div>
        )}
      </div>

      {/* Discovery Path Selector (Tabs) */}
      <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("local")}
          className={`px-4 py-2.5 text-xs font-semibold rounded-t-md transition-colors flex items-center gap-2 ${activeTab === "local"
            ? "bg-[var(--bg-card)] text-[var(--pixel-green)] border-b-2 border-[var(--pixel-green)]"
            : "text-[var(--text-muted)] hover:text-[var(--text-main)]"
            }`}
        >
          <ShieldCheck className="w-4 h-4 text-[var(--pixel-green)]" />
          <span>Local Analysis (Zero Network Outbound)</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("web")}
          className={`px-4 py-2.5 text-xs font-semibold rounded-t-md transition-colors flex items-center gap-2 ${activeTab === "web"
            ? "bg-[var(--bg-card)] text-[var(--pixel-cyan)] border-b-2 border-[var(--pixel-cyan)]"
            : "text-[var(--text-muted)] hover:text-[var(--text-main)]"
            }`}
        >
          <Search className="w-4 h-4 text-[var(--pixel-cyan)]" />
          <span>External Web &amp; Archive Discovery</span>
        </button>
      </div>

      {/* DISCOVERY PATH 1: LOCAL ANALYSIS (ZERO NETWORK OUTBOUND) */}
      {activeTab === "local" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Box A: Unified Local File Archive Dropzone */}
            <div className="card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="section-title">
                  <Upload className="w-4 h-4 text-[var(--pixel-green)]" />
                  Analyze SMS Backups &amp; Email Archives
                </h2>
                <span className="kicker-tag text-[9px]">Zero Network Transmission</span>
              </div>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Import user-provided Android SMS backups (XML, JSON, CSV) or email exports (.mbox). Files are parsed strictly in local memory to identify commercial senders, telemarketing lists, and telephone exposure signatures. Only explicitly selected files are processed.
              </p>

              <form onSubmit={handleLocalFileUpload} className="space-y-3.5">
                <div className="p-5 border-2 border-dashed border-[var(--border-subtle)] rounded-lg text-center bg-[var(--bg-app)]">
                  <input
                    type="file"
                    accept=".xml,.json,.csv,.mbox"
                    onChange={(e) => {
                      setSelectedLocalFile(e.target.files?.[0] || null);
                      setLocalFileOutcome(null);
                    }}
                    className="text-xs text-[var(--text-dim)] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-[var(--bg-surface)] file:text-[var(--text-main)] hover:file:bg-[var(--border-subtle)] cursor-pointer"
                  />
                  <p className="text-[10px] text-[var(--text-dim)] mt-2">
                    Accepted formats: Android SMS Backup XML, Google Takeout JSON/CSV, Apple Mail / Thunderbird .mbox.
                  </p>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <button
                    type="submit"
                    disabled={isProcessingLocalFile || !selectedLocalFile}
                    className="btn btn-primary py-2 px-5 text-xs font-semibold flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white"
                  >
                    <Upload className={`w-3.5 h-3.5 ${isProcessingLocalFile ? "animate-spin" : ""}`} />
                    <span>{isProcessingLocalFile ? "Analyzing File in Local RAM..." : "Analyze File Locally"}</span>
                  </button>

                  {localFileOutcome && (
                    <button
                      type="button"
                      onClick={() => parseData && onScanComplete(parseData)}
                      className="btn btn-secondary py-2 px-4 text-xs font-semibold flex items-center gap-1.5 text-[var(--pixel-cyan)]"
                    >
                      <span>Review Findings in Exposures Audit</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </form>

              {/* Local File Outcome Card */}
              {localFileOutcome && (
                <div className="p-4 rounded-lg border border-emerald-500/40 bg-emerald-950/20 text-xs space-y-2 text-emerald-300">
                  <div className="flex items-center justify-between font-bold">
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" />
                      Local Parse Complete: {localFileOutcome.filename}
                    </span>
                    <span className="font-mono text-[10px] bg-emerald-900/50 px-2 py-0.5 rounded text-emerald-200 uppercase">
                      {localFileOutcome.type} Archive
                    </span>
                  </div>
                  <p className="text-[11px] leading-relaxed text-emerald-200">
                    {localFileOutcome.message}
                  </p>
                  <div className="pt-1 flex items-center justify-between text-[11px] font-mono text-emerald-300">
                    <span>Parsed Elements: {localFileOutcome.itemsCount}</span>
                    <span className="font-bold text-[var(--pixel-green)]">Exposures Added: {localFileOutcome.exposuresCreated}</span>
                  </div>
                </div>
              )}

              {/* Imported Senders Preview */}
              {importedSenders.length > 0 && (
                <div className="space-y-2 pt-3 border-t border-[var(--border-subtle)]">
                  <div className="flex items-center justify-between text-xs font-bold text-[var(--text-main)]">
                    <span>Parsed Commercial Senders ({importedSenders.length})</span>
                  </div>
                  <div className="max-h-52 overflow-y-auto space-y-1.5">
                    {importedSenders.slice(0, 8).map((s, idx) => (
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
                            {s.sample_body || "Commercial promotion"}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="font-mono text-xs text-[var(--pixel-green)] font-semibold block">
                            {s.message_count} msgs
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Box B: Single Commercial SMS / Header Lookup */}
            <div className="card p-6 space-y-4">
              <h2 className="section-title">
                <MessageSquare className="w-4 h-4 text-[var(--pixel-cyan)]" />
                Analyze Single Commercial SMS / DLT Header
              </h2>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Received promotional SMS from a bank, loan app, or shopping delivery? Enter the sender header (e.g. <code>VM-HDFCBK</code>, <code>AD-SWIGGY</code>, <code>VK-AMAZON</code>, <code>CP-AIRTEL</code>) to decode the licensed telecom circle, brand, and generate a 1-click statutory TRAI 1909 complaint.
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
                    Message Body (Optional for Classification)
                  </label>
                  <textarea
                    value={smsBodyInput}
                    onChange={(e) => setSmsBodyInput(e.target.value)}
                    placeholder="Paste the SMS text here..."
                    rows={2}
                    className="input-field text-xs w-full font-mono"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isAnalyzingSms || !smsSenderInput.trim()}
                  className="btn btn-secondary py-2 px-5 text-xs font-semibold flex items-center gap-2"
                >
                  <Search className={`w-3.5 h-3.5 ${isAnalyzingSms ? "animate-spin" : ""}`} />
                  <span>{isAnalyzingSms ? "Analyzing Sender..." : "Analyze Commercial Sender"}</span>
                </button>
              </form>

              {/* Single SMS Analysis Result */}
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
                    {singleSmsResult.telecom_circle && (
                      <div>
                        <span className="text-[10px] text-[var(--text-dim)] block">Telecom Circle:</span>
                        <span className="font-mono text-[var(--pixel-cyan)]">{singleSmsResult.telecom_circle}</span>
                      </div>
                    )}
                  </div>

                  {/* 1-Click TRAI 1909 Complaint SMS */}
                  {singleSmsResult.complaint_sms && (
                    <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold text-[var(--pixel-yellow)] uppercase">
                          TRAI 1909 Statutory Complaint Format
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
                    </div>
                  )}

                  {/* Direct DND Portal */}
                  {singleSmsResult.dnd_portal_url && (
                    <div className="pt-1 flex items-center justify-between">
                      <span className="text-[11px] text-[var(--text-muted)]">Official Opt-Out Portal:</span>
                      <a
                        href={singleSmsResult.dnd_portal_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-secondary text-[11px] py-1 px-2.5 flex items-center gap-1 text-[var(--pixel-cyan)]"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Open Portal</span>
                      </a>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* DISCOVERY PATH 2: EXTERNAL WEB & ARCHIVE DISCOVERY */}
      {activeTab === "web" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Columns: Input & Configuration */}
          <div className="lg:col-span-2 space-y-6">
            <form onSubmit={handleStartScan} className="card p-6 space-y-5">
              <h2 className="section-title">
                <Search className="w-4 h-4 text-[var(--pixel-cyan)]" />
                PUBLIC SEARCH PROVIDERS &amp; ARCHIVES
              </h2>

              {/* Provider Checkboxes */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    Automated Search Adapters
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
              <div className="pt-2 border-t border-[var(--border-subtle)]">
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

              {/* Search Mode Selector */}
              <div className="pt-2 border-t border-[var(--border-subtle)] space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-[var(--text-main)] uppercase tracking-wider flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-[var(--pixel-green)]" />
                    <span>Search Mode</span>
                  </label>
                  <span className="kicker-tag text-[9px]">Privacy Invariant</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label
                    onClick={() => setSearchMode("manual")}
                    className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col justify-between ${searchMode === "manual"
                      ? "border-emerald-500/60 bg-emerald-950/20 text-[var(--text-main)] shadow-[0_0_12px_rgba(16,185,129,0.15)]"
                      : "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-muted)] hover:border-slate-700"
                      }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-xs flex items-center gap-1.5 text-emerald-400">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Assisted Manual Search
                      </span>
                      <input
                        type="radio"
                        name="searchMode"
                        value="manual"
                        checked={searchMode === "manual"}
                        onChange={() => setSearchMode("manual")}
                        className="text-emerald-500"
                      />
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] leading-tight">
                      (Default / Recommended) Generates direct browser search dorks. Zero network requests sent from backend. Complete privacy.
                    </p>
                  </label>

                  <label
                    onClick={() => setSearchMode("automated")}
                    className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col justify-between ${searchMode === "automated"
                      ? "border-amber-500/60 bg-amber-950/20 text-[var(--text-main)] shadow-[0_0_12px_rgba(245,158,11,0.15)]"
                      : "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-muted)] hover:border-slate-700"
                      }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-xs flex items-center gap-1.5 text-amber-400">
                        <Search className="w-3.5 h-3.5" />
                        External Automated Search
                      </span>
                      <input
                        type="radio"
                        name="searchMode"
                        value="automated"
                        checked={searchMode === "automated"}
                        onChange={() => setSearchMode("automated")}
                        className="text-amber-500"
                      />
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] leading-tight">
                      Sends queries to public search engines across HTTPS. Requires explicit user disclosure and opt-in before transmission.
                    </p>
                  </label>
                </div>
              </div>

              {/* Scan Trigger Button */}
              <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                {searchMode === "manual" ? (
                  <button
                    type="submit"
                    disabled={isScanning || !parseData?.is_possible}
                    className="btn btn-primary py-2.5 px-6 font-semibold flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    <span>Generate Assisted Search Dorks (Local Only)</span>
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={isScanning || !parseData?.is_possible || loadingDisclosure}
                    className="btn btn-primary py-2.5 px-6 font-semibold flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-400 text-black border-amber-400"
                  >
                    <Search className={`w-4 h-4 ${isScanning || loadingDisclosure ? "animate-spin" : ""}`} />
                    <span>{loadingDisclosure ? "Loading Disclosure..." : isScanning ? "Scanning Providers..." : "Review Disclosure & Start Automated Scan"}</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleOpenDorks}
                  className="btn btn-secondary py-2.5 px-4 text-xs font-semibold flex items-center justify-center gap-2"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-[var(--pixel-cyan)]" />
                  <span>Open Browser Dorks</span>
                </button>
              </div>

              {/* Execution Stage Progression Bar */}
              {scanStage !== "idle" && (
                <div className="p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] space-y-1.5 text-xs font-mono">
                  <div className="text-[10px] text-[var(--text-dim)] uppercase">Discovery Stage Progression:</div>
                  <div className="flex items-center gap-2 flex-wrap text-[11px]">
                    <span className="text-emerald-400 font-bold">
                      1. Normalization
                    </span>
                    <span className="text-zinc-600">➔</span>
                    <span className={scanStage === "querying" || scanStage === "deduplicating" || scanStage === "complete" ? "text-emerald-400 font-bold" : "text-zinc-600"}>
                      2. Source Audit
                    </span>
                    <span className="text-zinc-600">➔</span>
                    <span className={scanStage === "deduplicating" || scanStage === "complete" ? "text-emerald-400 font-bold" : "text-zinc-600"}>
                      3. Deduplication
                    </span>
                    <span className="text-zinc-600">➔</span>
                    <span className={scanStage === "complete" ? "text-cyan-400 font-bold" : "text-zinc-600"}>
                      4. Complete
                    </span>
                  </div>
                </div>
              )}

              {/* Scan Status & Diagnostics */}
              {scanMessage && (
                <div
                  className={`p-3.5 rounded-lg border text-xs leading-relaxed ${scanMessage.includes("incomplete") || scanMessage.includes("all_failed")
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
                <div className="space-y-3 pt-3 border-t border-[var(--border-subtle)]">
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
                                className={`status-pill ${isHealthy
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
                        No public web directory, Wikipedia article, or paste archive was found mentioning your number. If you receive promotional SMS or calls, they originate from private telecom channels (DLT commercial gateways). Use the <strong>Local Analysis</strong> tab to decode those messages.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </form>
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
                      <span className="font-mono text-xs text-[var(--text-main)] flex items-center gap-1">
                        {revealRawE164 ? (parseData.e164 || "N/A") : parseData.masked_display}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider block mb-0.5">
                        National
                      </span>
                      <span className="font-mono text-xs text-[var(--text-main)]">
                        {revealRawE164 ? (parseData.national || "N/A") : parseData.masked_display}
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
        </div>
      )}

      {/* External Search Privacy Disclosure Modal */}
      {showDisclosureModal && disclosureData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="card max-w-2xl w-full max-h-[90vh] flex flex-col p-6 border-amber-500/40 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
              <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
                <ShieldAlert className="w-5 h-5 shrink-0" />
                <span>EXTERNAL SEARCH PRIVACY DISCLOSURE</span>
              </div>
              <button
                type="button"
                onClick={handleCancelAutomatedScan}
                className="text-[var(--text-dim)] hover:text-[var(--text-main)] font-bold text-lg"
              >
                ✕
              </button>
            </div>

            <div className="py-4 space-y-4 overflow-y-auto flex-1 text-xs">
              <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-500/30 text-amber-200 text-xs leading-relaxed">
                {disclosureData.notice}
              </div>

              <div className="space-y-1 font-mono text-[11px] text-[var(--text-muted)]">
                <div className="flex items-center gap-1.5">
                  <span>Target Phone Number:</span>
                  <span className="text-[var(--pixel-cyan)] font-bold">
                    {revealRawE164 ? (parseData?.e164 || phoneNumber) : (disclosureData.masked_phone || parseData?.masked_display)}
                  </span>
                  <button
                    type="button"
                    onClick={() => setRevealRawE164(!revealRawE164)}
                    className="text-[var(--text-dim)] hover:text-[var(--text-main)] p-0.5"
                    title={revealRawE164 ? "Mask phone digits" : "Reveal raw digits"}
                    aria-label={revealRawE164 ? "Mask phone digits" : "Reveal raw digits"}
                  >
                    {revealRawE164 ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  </button>
                </div>
                <div>Masked Identity: <span className="text-[var(--text-main)] font-bold">{disclosureData.masked_phone}</span></div>
              </div>

              <div className="space-y-3">
                <div className="font-bold text-[var(--text-main)] uppercase tracking-wider text-[11px]">
                  Third-Party Providers That Will Receive Your Telephone Query
                </div>
                <div className="space-y-2">
                  {disclosureData.providers
                    .filter((p) => providers[p.provider_id as keyof typeof providers])
                    .map((p) => (
                      <div key={p.provider_id} className="p-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-surface)] space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[var(--text-main)]">{p.provider_name}</span>
                          <span className="font-mono text-[10px] text-[var(--pixel-cyan)] truncate max-w-xs">{p.endpoint}</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-[var(--text-muted)]">
                          <div><strong className="text-[var(--text-dim)]">Query Sent:</strong> <span className="font-mono text-emerald-400">{p.exact_query_sent}</span></div>
                          <div><strong className="text-[var(--text-dim)]">Data Format:</strong> {p.data_transmitted}</div>
                        </div>
                        <div className="text-[11px] text-[var(--text-muted)]">
                          <strong className="text-[var(--text-dim)]">Purpose:</strong> {p.purpose}
                        </div>
                        <div className="text-[10px] text-amber-400/90 bg-amber-950/30 p-1.5 rounded border border-amber-900/30">
                          <strong>Privacy Risk:</strong> {p.privacy_risk}
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Explicit Consent Opt-In Checkbox */}
              <label className="flex items-start gap-2.5 p-3 rounded-lg border border-cyan-900/40 bg-[#09111e] cursor-pointer hover:border-cyan-700/60 transition-colors">
                <input
                  type="checkbox"
                  checked={consentOptIn}
                  onChange={(e) => setConsentOptIn(e.target.checked)}
                  className="mt-0.5 rounded border-[var(--border-subtle)]"
                />
                <span className="text-[11px] text-[var(--text-main)] font-medium leading-relaxed">
                  I understand that third-party search engines will process and log this telephone query in their server access logs. I explicitly authorize ClearNum to transmit this query to the selected providers.
                </span>
              </label>
            </div>

            <div className="pt-3 border-t border-[var(--border-subtle)] flex flex-col sm:flex-row items-center justify-end gap-3">
              <button
                type="button"
                onClick={handleCancelAutomatedScan}
                className="btn btn-secondary py-2 px-4 text-xs font-semibold w-full sm:w-auto"
              >
                Cancel &amp; Keep Data Local
              </button>
              <button
                type="button"
                onClick={handleConfirmAutomatedScan}
                disabled={!consentOptIn || isScanning}
                className={`btn py-2 px-5 text-xs font-semibold w-full sm:w-auto flex items-center justify-center gap-2 ${consentOptIn
                  ? "btn-primary bg-amber-500 hover:bg-amber-400 text-black border-amber-400 font-bold"
                  : "opacity-40 cursor-not-allowed bg-slate-800 text-slate-400"
                  }`}
              >
                <Search className="w-3.5 h-3.5" />
                <span>Authorize &amp; Execute Query</span>
              </button>
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

            <div className="p-4 overflow-y-auto flex-1 space-y-3">
              {dorks.length === 0 ? (
                <div className="text-center py-8 text-xs text-[var(--text-dim)]">
                  Generating targeted search queries...
                </div>
              ) : (
                dorks.map((d, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-[var(--text-main)]">{d.engine_name}</span>
                        <span className="status-pill pill-pixel-purple text-[9px]">{d.category}</span>
                      </div>
                      <div className="font-mono text-[11px] text-[var(--pixel-cyan)] break-all bg-[var(--bg-surface)] p-1.5 rounded border border-[var(--border-subtle)]">
                        {d.query_text}
                      </div>
                      <p className="text-[10px] text-[var(--text-dim)]">{d.purpose}</p>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => copyToClipboard(d.query_text, `dork-${idx}`)}
                        className="btn btn-secondary py-1.5 px-2.5 text-[11px] flex items-center gap-1"
                      >
                        {copiedText === `dork-${idx}` ? <Check className="w-3 h-3 text-[var(--pixel-green)]" /> : <Copy className="w-3 h-3" />}
                        <span>{copiedText === `dork-${idx}` ? "Copied" : "Copy"}</span>
                      </button>
                      <a
                        href={d.search_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-primary py-1.5 px-3 text-[11px] flex items-center gap-1.5"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Search</span>
                      </a>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] flex justify-end">
              <button
                type="button"
                onClick={() => setShowDorksModal(false)}
                className="btn btn-secondary py-1.5 px-4 text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
