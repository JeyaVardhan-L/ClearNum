import React, { useState, useEffect, useMemo } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Filter,
  Search,
  XCircle,
  SlidersHorizontal,
  HelpCircle,
  MessageSquare,
  Clock,
  ArrowRight,
  X,
} from "lucide-react";
import type { DiscoveredExposure, PhoneParseResult, RemediationHistory } from "../types";
import { transitionAction, verifyExposure, getRemediationHistory } from "../api";

interface ExposuresViewProps {
  exposures: DiscoveredExposure[];
  currentIdentity: PhoneParseResult | null;
  onRefresh: () => void;
  onOpenRemediation: (selectedSourceId?: string) => void;
  onNavigateToScan: () => void;
  onLoadDemo: () => void;
}

function calculateDeadlineIndicator(history: RemediationHistory, nowTimestamp: number) {
  const basis = history.deadline_basis || "NONE";
  const hasDates = Boolean(history.expected_response_date || history.follow_up_date);
  if (!hasDates && basis === "NONE") {
    return {
      label: "No response date recorded",
      statusType: "none",
      basisLabel: "No Statutory Basis",
      basisType: "NONE",
    };
  }

  const today = new Date(nowTimestamp);
  today.setHours(0, 0, 0, 0);

  let label = "No response date recorded";
  let statusType: "future" | "reached" | "overdue" | "none" = "none";

  if (history.expected_response_date) {
    const expDate = new Date(history.expected_response_date);
    expDate.setHours(0, 0, 0, 0);
    const diffTime = expDate.getTime() - today.getTime();
    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays > 0) {
      label = `Response expected in ${diffDays} day${diffDays === 1 ? "" : "s"}`;
      statusType = "future";
    } else if (diffDays === 0) {
      label = "Response expected today";
      statusType = "reached";
    } else {
      const overdueDays = Math.abs(diffDays);
      label = `Follow-up overdue by ${overdueDays} day${overdueDays === 1 ? "" : "s"}`;
      statusType = "overdue";
    }
  } else if (history.follow_up_date) {
    const fDate = new Date(history.follow_up_date);
    fDate.setHours(0, 0, 0, 0);
    const diffTime = fDate.getTime() - today.getTime();
    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays > 0) {
      label = `Follow-up scheduled in ${diffDays} day${diffDays === 1 ? "" : "s"}`;
      statusType = "future";
    } else if (diffDays === 0) {
      label = "Follow-up date reached";
      statusType = "reached";
    } else {
      const overdueDays = Math.abs(diffDays);
      label = `Follow-up overdue by ${overdueDays} day${overdueDays === 1 ? "" : "s"}`;
      statusType = "overdue";
    }
  }

  let basisLabel = "No Statutory Basis";
  if (basis === "STATUTORY") {
    basisLabel = "Statutory Legal Deadline";
  } else if (basis === "SOURCE_ESTIMATE") {
    basisLabel = "Industry / Source Estimate";
  } else if (basis === "USER_DEFINED") {
    basisLabel = "User-Defined Date";
  }

  return { label, statusType, basisLabel, basisType: basis };
}

export const ExposuresView: React.FC<ExposuresViewProps> = ({
  exposures,
  currentIdentity,
  onRefresh,
  onOpenRemediation,
  onNavigateToScan,
  onLoadDemo,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [verificationFeedback, setVerificationFeedback] = useState<{
    id: string;
    status: string;
    notes: string;
    code?: number;
    outcome?: string;
    soft_404_detected?: boolean;
    reappeared?: boolean;
  } | null>(null);

  // Clock baseline timestamp initialized once
  const [nowTimestamp] = useState<number>(() => Date.now());

  // Transition state modal
  const [transitioningExposure, setTransitioningExposure] = useState<DiscoveredExposure | null>(null);
  const [targetNextState, setTargetNextState] = useState<string>("SUBMITTED");
  const [submissionRef, setSubmissionRef] = useState<string>("");
  const [transitionNotes, setTransitionNotes] = useState<string>("");
  const [transitionLoading, setTransitionLoading] = useState<boolean>(false);
  const [transitionError, setTransitionError] = useState<string | null>(null);

  // History timeline modal & cache
  const [selectedHistoryExposure, setSelectedHistoryExposure] = useState<DiscoveredExposure | null>(null);
  const [historyData, setHistoryData] = useState<RemediationHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyCache, setHistoryCache] = useState<Record<string, RemediationHistory>>({});

  // Computed deadline status
  const deadlineIndicator = useMemo(() => {
    if (!historyData) return null;
    return calculateDeadlineIndicator(historyData, nowTimestamp);
  }, [historyData, nowTimestamp]);

  // Keyboard navigation & modal dismiss
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (transitioningExposure) {
          setTransitioningExposure(null);
        } else if (selectedHistoryExposure) {
          setSelectedHistoryExposure(null);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [transitioningExposure, selectedHistoryExposure]);

  const filteredExposures = exposures.filter((exp) => {
    const matchesStatus = statusFilter === "ALL" || exp.remediation_status === statusFilter;
    const matchesSearch =
      searchQuery === "" ||
      exp.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
      exp.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      exp.url.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const fetchHistory = async (exposureId: string, hmac: string) => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const data = await getRemediationHistory(exposureId, hmac);
      setHistoryCache((prev) => ({ ...prev, [exposureId]: data }));
      setHistoryData(data);
    } catch (err: any) {
      setHistoryError(err.message || "Failed to load remediation history.");
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleOpenHistory = (exposure: DiscoveredExposure) => {
    setSelectedHistoryExposure(exposure);
    if (!currentIdentity?.hmac_id) {
      setHistoryError("Identity HMAC not active.");
      return;
    }
    if (historyCache[exposure.id]) {
      setHistoryData(historyCache[exposure.id]);
      setHistoryLoading(false);
      setHistoryError(null);
    } else {
      fetchHistory(exposure.id, currentIdentity.hmac_id);
    }
  };

  const handleVerifyLive = async (exposure: DiscoveredExposure) => {
    if (!currentIdentity) return;
    setVerifyingId(exposure.id);
    setVerificationFeedback(null);

    try {
      const res = await verifyExposure(
        exposure.id,
        exposure.url,
        currentIdentity.e164 || currentIdentity.masked_display,
        currentIdentity.region_code
      );
      setVerificationFeedback({
        id: exposure.id,
        status: res.status,
        notes: res.evidence_notes,
        code: res.http_status_code,
        outcome: res.outcome,
        soft_404_detected: res.soft_404_detected,
        reappeared: res.reappeared,
      });

      // Invalidate cached history for this exposure
      setHistoryCache((prev) => {
        const next = { ...prev };
        delete next[exposure.id];
        return next;
      });
      if (selectedHistoryExposure?.id === exposure.id && currentIdentity.hmac_id) {
        fetchHistory(exposure.id, currentIdentity.hmac_id);
      }

      onRefresh();
    } catch (err: any) {
      setVerificationFeedback({
        id: exposure.id,
        status: "ERROR",
        notes: `Verification check failed: ${err.message}`,
      });
    } finally {
      setVerifyingId(null);
    }
  };

  const handleExecuteTransition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transitioningExposure || !currentIdentity) return;

    setTransitionLoading(true);
    setTransitionError(null);

    try {
      await transitionAction(
        transitioningExposure.id,
        currentIdentity.hmac_id,
        targetNextState,
        submissionRef,
        transitionNotes
      );

      const targetExpId = transitioningExposure.id;
      setTransitioningExposure(null);
      setSubmissionRef("");
      setTransitionNotes("");

      // Invalidate history cache for this exposure
      setHistoryCache((prev) => {
        const next = { ...prev };
        delete next[targetExpId];
        return next;
      });
      if (selectedHistoryExposure?.id === targetExpId && currentIdentity.hmac_id) {
        fetchHistory(targetExpId, currentIdentity.hmac_id);
      }

      onRefresh();
    } catch (err: any) {
      setTransitionError(err.message || "Invalid state transition.");
    } finally {
      setTransitionLoading(false);
    }
  };

  const getEvidenceOriginBadge = (origin?: string) => {
    switch (origin) {
      case "FETCHED_PAGE":
        return (
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-800/40 text-emerald-400 inline-flex items-center gap-1"
            title="Live page content was retrieved and verified directly"
          >
            ● Fetched Page Body
          </span>
        );
      case "ARCHIVED_SNAPSHOT":
        return (
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple-950/40 border border-purple-800/40 text-purple-300 inline-flex items-center gap-1"
            title="Historical archive snapshot (Wayback Machine). Does not confirm current live exposure."
          >
            🕒 Archived Snapshot
          </span>
        );
      case "SEARCH_SNIPPET":
        return (
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-800/40 text-amber-400 inline-flex items-center gap-1"
            title="Match found only in search engine snippet. Page body has not been fetched."
          >
            🔍 Search Snippet Only
          </span>
        );
      case "UNKNOWN":
      default:
        return (
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-400 inline-flex items-center gap-1"
            title="Evidence origin not established from historical records"
          >
            ❓ Unverified Origin
          </span>
        );
    }
  };

  const getMatchBadge = (matchType: string, classification?: string, isExample?: boolean, matchedTier?: string) => {
    const classType = classification || (matchType === "EXACT" ? "CONFIRMED_MATCH" : matchType === "PROBABLE" ? "POSSIBLE_MATCH" : "INCONCLUSIVE");

    let badge;
    switch (classType) {
      case "CONFIRMED_MATCH":
        badge = <span className="status-pill pill-pixel-green font-mono text-[10px]">Exact Match (Confirmed)</span>;
        break;
      case "POSSIBLE_MATCH":
        badge = <span className="status-pill pill-pixel-cyan font-mono text-[10px]">Probable Match</span>;
        break;
      case "INCIDENTAL_MENTION":
        badge = <span className="status-pill pill-pixel-yellow font-mono text-[10px]">Incidental Mention</span>;
        break;
      case "INCONCLUSIVE":
        badge = <span className="status-pill pill-pixel-yellow font-mono text-[10px] text-amber-400">Inconclusive Fragment</span>;
        break;
      case "FALSE_POSITIVE":
        badge = <span className="status-pill pill-pixel-purple font-mono text-[10px]">False Positive</span>;
        break;
      default:
        badge = <span className="status-pill pill-pixel-purple font-mono text-[10px]">{matchType}</span>;
    }

    return (
      <div className="flex flex-col gap-1 items-start">
        {badge}
        {isExample && (
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-800/40 text-amber-300">
            Documentation / Dummy
          </span>
        )}
        {matchedTier && matchedTier !== "NONE" && (
          <span className="text-[9px] font-mono text-[var(--text-dim)] uppercase tracking-wider">
            Tier: {matchedTier.replace("_", " ")}
          </span>
        )}
      </div>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "REQUEST_PREPARED":
        return (
          <span className="status-pill pill-pixel-yellow">
            <FileText className="w-3 h-3" /> Request Prepared
          </span>
        );
      case "SOURCE_CONFIRMED_REMOVAL":
        return (
          <span className="status-pill pill-pixel-green">
            <CheckCircle2 className="w-3 h-3" /> Source Confirmed Removal
          </span>
        );
      case "NO_LONGER_VISIBLE_AT_CHECKED_URL":
      case "VERIFIED_REMOVED":
        return (
          <span className="status-pill pill-pixel-cyan">
            <CheckCircle2 className="w-3 h-3" /> No Longer Visible at URL
          </span>
        );
      case "SEARCH_RESULT_DELISTED":
        return (
          <span className="status-pill pill-pixel-cyan">
            <FileText className="w-3 h-3" /> Search Result Delisted
          </span>
        );
      case "REQUEST_SUBMITTED":
      case "SUBMITTED":
        return (
          <span className="status-pill pill-pixel-cyan">
            <RefreshCw className="w-3 h-3" /> Submitted
          </span>
        );
      case "ACKNOWLEDGED":
        return (
          <span className="status-pill pill-pixel-cyan">
            <CheckCircle2 className="w-3 h-3" /> Acknowledged
          </span>
        );
      case "ACTION_AVAILABLE":
        return (
          <span className="status-pill pill-pixel-green">
            <ShieldCheck className="w-3 h-3" /> Opt-Out Available
          </span>
        );
      case "REJECTED_MATCH":
      case "REMOVAL_REJECTED":
        return (
          <span className="status-pill pill-pixel-purple">
            <XCircle className="w-3 h-3" /> {status === "REMOVAL_REJECTED" ? "Removal Rejected" : "Rejected Match"}
          </span>
        );
      case "INACCESSIBLE_OR_INCONCLUSIVE":
        return (
          <span className="status-pill pill-pixel-yellow">
            <AlertTriangle className="w-3 h-3" /> Inaccessible / Inconclusive
          </span>
        );
      case "STILL_VISIBLE":
        return (
          <span className="status-pill pill-pixel-red">
            <AlertTriangle className="w-3 h-3" /> Still Visible at URL
          </span>
        );
      case "CONFIRMED_EXPOSURE":
        return (
          <span className="status-pill pill-pixel-yellow">
            <AlertTriangle className="w-3 h-3" /> Confirmed Exposure
          </span>
        );
      case "AWAITING_USER_APPROVAL":
        return (
          <span className="status-pill pill-pixel-yellow">
            <AlertTriangle className="w-3 h-3" /> Awaiting Approval
          </span>
        );
      default:
        return (
          <span className="status-pill pill-pixel-yellow">
            <AlertTriangle className="w-3 h-3" /> {status}
          </span>
        );
    }
  };

  const getLifecycleExplanation = (status: string) => {
    switch (status) {
      case "REQUEST_PREPARED":
        return "Notice Prepared: Generated locally. Request has not been transmitted externally.";
      case "SUBMITTED":
      case "REQUEST_SUBMITTED":
        return "Submission Recorded: External submission recorded by user. Awaiting recipient response.";
      case "ACKNOWLEDGED":
        return "Receipt Acknowledged: Broker confirmed receiving notice. Listing is not yet verified removed.";
      case "SOURCE_CONFIRMED_REMOVAL":
        return "Source Claimed Removal: Broker claims data is purged. Live verification required.";
      case "NO_LONGER_VISIBLE_AT_CHECKED_URL":
      case "VERIFIED_REMOVED":
        return "Verified Absent at URL: Live HTTP check confirmed phone number is absent (HTTP 404/410/Absence). Does not prove internal database copies are deleted.";
      case "SEARCH_RESULT_DELISTED":
        return "Search Index Delisted: Removed from public search engine cache. Host site may retain data.";
      case "INACCESSIBLE_OR_INCONCLUSIVE":
        return "Check Inconclusive: Target URL unreachable or anti-bot challenge (HTTP 403). Not verified removed.";
      case "STILL_VISIBLE":
        return "Still Visible: Telephone number was detected at the checked URL during verification.";
      case "REMOVAL_REJECTED":
        return "Removal Rejected: Broker or recipient refused compliance or rejected request.";
      case "CONFIRMED_EXPOSURE":
        return "Discovered Exposure: Verified phone number match in public records awaiting remediation action.";
      case "REJECTED_MATCH":
        return "Rejected Match: Filtered out as false positive, UUID, date, or unrelated listing.";
      default:
        return "Current truthful lifecycle state.";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="kicker-tag">[ AUDIT INVENTORY ]</span>
          </div>
          <h2 className="text-lg font-bold text-[var(--text-main)] flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-[var(--pixel-yellow)]" />
            Discovered Exposures &amp; Evidence Audit
          </h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Cryptographically indexed records verified against your 256-bit identity HMAC.
          </p>
        </div>

        {/* Filter & Search controls */}
        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
          <div className="relative min-w-[180px]">
            <Search className="w-3.5 h-3.5 text-[var(--text-dim)] absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Filter by domain..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field pl-8 py-1.5 text-xs"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-[var(--text-dim)]" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input-field py-1.5 text-xs min-w-[140px]"
            >
              <option value="ALL">All Statuses</option>
              <option value="DISCOVERED">Discovered</option>
              <option value="REQUEST_PREPARED">Request Prepared</option>
              <option value="VERIFIED">Verified</option>
              <option value="ACTION_AVAILABLE">Action Available</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="VERIFIED_REMOVED">Verified Removed</option>
              <option value="REJECTED_MATCH">Rejected</option>
            </select>
          </div>

          <button
            onClick={onRefresh}
            className="btn btn-secondary py-1.5 px-2.5"
            title="Refresh records"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Verification Live Alert Banner (if recently triggered) */}
      {verificationFeedback && (
        <div
          className={`p-3 rounded-lg border flex items-start gap-2.5 transition-all ${
            verificationFeedback.reappeared
              ? "border-rose-500/60 bg-rose-950/30 text-rose-300"
              : verificationFeedback.status === "VERIFIED_REMOVED" || verificationFeedback.status === "NO_LONGER_VISIBLE_AT_CHECKED_URL"
              ? "border-teal-500/50 bg-teal-950/30 text-teal-300"
              : verificationFeedback.status === "INACCESSIBLE_OR_INCONCLUSIVE"
              ? "border-amber-500/50 bg-amber-950/30 text-amber-300"
              : "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-main)]"
          }`}
        >
          {verificationFeedback.reappeared ? (
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-rose-400 animate-pulse" />
          ) : verificationFeedback.status === "VERIFIED_REMOVED" || verificationFeedback.status === "NO_LONGER_VISIBLE_AT_CHECKED_URL" ? (
            <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0 text-teal-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-amber-400" />
          )}
          <div className="flex-1">
            <div className="text-xs font-semibold flex items-center gap-1.5 flex-wrap">
              <span>Live Verification: {verificationFeedback.reappeared ? "REAPPEARED" : verificationFeedback.status}</span>
              {verificationFeedback.code ? (
                <span className="font-mono text-[10px] opacity-80">(HTTP {verificationFeedback.code})</span>
              ) : null}
              {verificationFeedback.soft_404_detected && (
                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-teal-900/60 border border-teal-700/50 text-teal-200">
                  Soft-404 Detected
                </span>
              )}
            </div>
            <div className="text-[11px] opacity-90 mt-0.5 font-mono">{verificationFeedback.notes}</div>
          </div>
          <button
            onClick={() => setVerificationFeedback(null)}
            className="text-[var(--text-dim)] hover:text-[var(--text-main)] font-bold text-base px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Exposures Content */}
      {filteredExposures.length === 0 ? (
        <div className="card p-8 sm:p-12 space-y-6">
          <div className="flex flex-col items-center text-center space-y-3 max-w-xl mx-auto">
            <div className="w-12 h-12 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex items-center justify-center text-[var(--text-dim)]">
              <ShieldCheck className="w-6 h-6 text-[var(--pixel-green)]" />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-bold text-[var(--text-main)] uppercase tracking-wider">
                0 Public Web Exposures Indexed
              </h3>
              <p className="text-xs text-[var(--text-muted)] mt-1.5 leading-relaxed">
                {searchQuery || statusFilter !== "ALL"
                  ? "No exposure matches the selected filter criteria. Try clearing search filters."
                  : "No public web exposures referencing your phone number were found in accessible search engines or archive indexes."}
              </p>
            </div>
          </div>

          {/* Educational Honest Reality Card */}
          <div className="p-4 rounded-lg border border-cyan-900/40 bg-[#09111e] space-y-3 text-left max-w-2xl mx-auto text-xs">
            <div className="flex items-center gap-2 font-bold text-[var(--pixel-cyan)]">
              <HelpCircle className="w-4 h-4 shrink-0" />
              <span>What this result proves vs. What it does NOT prove</span>
            </div>
            <div className="space-y-2 text-[11px] text-[var(--text-muted)] leading-relaxed">
              <p>
                <strong>✓ What it proves:</strong> Your telephone number does not appear in publicly indexed websites, Wikipedia discussions, Hacker News threads, or historical paste URLs checked by automated search adapters.
              </p>
              <p>
                <strong>✕ What it does NOT prove:</strong> This does <em>not</em> mean your number is free from spam or marketing lists. Legitimate businesses (banks, shopping apps like Swiggy/Amazon, telecom providers) send promotional SMS and robocalls through <strong>commercial telecom gateways (DLT headers)</strong> or customer merchant records. These are private telecommunication channels that search engines cannot crawl.
              </p>
            </div>
          </div>

          {/* Actionable Next Steps */}
          <div className="pt-2 max-w-md mx-auto space-y-2.5">
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button onClick={onNavigateToScan} className="btn btn-primary py-2.5 px-5 text-xs w-full sm:w-auto flex items-center justify-center gap-2">
                <Search className="w-3.5 h-3.5" />
                <span>Run / Configure Web Scan</span>
              </button>
              <button onClick={onNavigateToScan} className="btn btn-secondary py-2.5 px-5 text-xs w-full sm:w-auto flex items-center justify-center gap-2">
                <MessageSquare className="w-3.5 h-3.5 text-[var(--pixel-cyan)]" />
                <span>Investigate SMS Headers</span>
              </button>
            </div>

            <div className="text-center pt-2">
              <button
                onClick={onLoadDemo}
                className="text-[11px] text-[var(--text-dim)] hover:text-[var(--text-muted)] underline transition-colors"
                title="Loads synthetic test broker records for testing state transitions"
              >
                Inspect Synthetic Test Scenario (5 Sample Brokers)
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: "20%" }}>SOURCE / DOMAIN</th>
                  <th style={{ width: "32%" }}>INDEXED LISTING SNIPPET</th>
                  <th style={{ width: "14%" }}>MATCH CONFIDENCE</th>
                  <th style={{ width: "14%" }}>LIFECYCLE STATE</th>
                  <th style={{ width: "20%", textAlign: "right", whiteSpace: "nowrap" }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {filteredExposures.map((exp) => (
                  <tr key={exp.id}>
                    {/* Domain & URL */}
                    <td>
                      <div className="font-semibold text-xs text-[var(--text-main)] flex items-center gap-1.5">
                        <span>{exp.domain}</span>
                        <a
                          href={exp.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[var(--pixel-cyan)] hover:text-[var(--pixel-green)] inline-flex items-center"
                          title="Open exposed URL in new tab"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <div
                        className="font-mono text-[10px] text-[var(--text-dim)] truncate max-w-xs mt-0.5"
                        title={exp.canonical_url || exp.url}
                      >
                        <span className="text-[var(--text-dim)]">Canonical: </span>
                        {exp.canonical_url || exp.url}
                      </div>
                      <div className="text-[10px] text-[var(--text-dim)] mt-0.5 flex items-center gap-2 flex-wrap">
                        <span>Discovered: {exp.discovered_at ? new Date(exp.discovered_at).toLocaleDateString() : "Recent"}</span>
                        {exp.last_checked_at && exp.last_checked_at !== exp.discovered_at && (
                          <span>Checked: {new Date(exp.last_checked_at).toLocaleDateString()}</span>
                        )}
                        {exp.provider_status && (
                          <span className="kicker-tag text-[8px] py-0">{exp.provider_status}</span>
                        )}
                      </div>
                    </td>

                    {/* Snippet & Evidence */}
                    <td>
                      <div className="text-xs text-[var(--text-muted)] line-clamp-2 leading-relaxed font-mono">
                        {exp.snippet || "No textual context snippet available."}
                      </div>
                      <div className="text-[10px] text-[var(--text-dim)] mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <div>
                          Matched: <span className="font-mono text-[var(--pixel-cyan)] font-semibold">{exp.matched_representation || currentIdentity?.masked_display || "Masked"}</span>
                        </div>
                        <div>
                          Source: <span className="text-[var(--pixel-cyan)] font-mono">{exp.source_id}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-[var(--text-dim)]">Origin:</span>
                          {getEvidenceOriginBadge(exp.evidence_origin)}
                        </div>
                      </div>

                      {/* Honest Evidence Origin & Verification Limitations Callout */}
                      {exp.evidence_origin === "SEARCH_SNIPPET" && (
                        <div className="text-[10px] text-amber-400/90 bg-amber-950/20 border border-amber-900/30 rounded px-2 py-0.5 mt-1.5 flex items-center gap-1.5 font-mono">
                          <AlertTriangle className="w-2.5 h-2.5 text-amber-400 shrink-0" />
                          <span>Snippet only — live page uninspected</span>
                        </div>
                      )}
                      {exp.evidence_origin === "ARCHIVED_SNAPSHOT" && (
                        <div className="text-[10px] text-purple-300/90 bg-purple-950/20 border border-purple-900/30 rounded px-2 py-0.5 mt-1.5 flex items-center gap-1.5 font-mono">
                          <Clock className="w-2.5 h-2.5 text-purple-400 shrink-0" />
                          <span>Historical snapshot — current exposure unconfirmed</span>
                        </div>
                      )}
                      {exp.evidence_origin === "FETCHED_PAGE" && (
                        <div className="text-[10px] text-emerald-400/90 bg-emerald-950/20 border border-emerald-900/30 rounded px-2 py-0.5 mt-1.5 flex items-center gap-1.5 font-mono">
                          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
                          <span>Live page body inspected: presence confirmed</span>
                        </div>
                      )}

                      {exp.confidence_explanation && (
                        <div className="text-[10px] text-[var(--text-dim)] mt-1.5 leading-relaxed bg-[var(--bg-card)]/50 p-1.5 rounded border border-[var(--border-subtle)]">
                          <span className="text-[var(--text-muted)] font-semibold">Evaluation: </span>
                          {exp.confidence_explanation}
                        </div>
                      )}
                    </td>

                    {/* Match Confidence & Classification */}
                    <td>
                      <div className="space-y-1">
                        {getMatchBadge(exp.match_type, exp.match_classification, exp.is_example_or_test, exp.matched_tier)}
                        <div className="text-[10px] text-[var(--text-dim)] font-mono flex items-center gap-1.5 mt-0.5">
                          <span>Confidence:</span>
                          <span className="font-semibold text-[var(--text-main)]">{(exp.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <div className="text-[9px] text-[var(--text-dim)] font-mono">
                          {exp.confidence >= 0.95
                            ? "High Confidence"
                            : exp.confidence >= 0.80
                            ? "Medium-High"
                            : exp.confidence >= 0.65
                            ? "Medium Confidence"
                            : "Low / Inconclusive"}
                        </div>
                      </div>
                    </td>

                    {/* Lifecycle Status */}
                    <td>
                      <div className="space-y-1">
                        {getStatusBadge(exp.remediation_status)}
                        {exp.official_removal_url && (
                          <a
                            href={exp.official_removal_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-[var(--pixel-green)] hover:underline flex items-center gap-1 mt-0.5"
                          >
                            <span>Official Opt-Out Link</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        )}
                      </div>
                    </td>

                    {/* Actions */}
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <div className="flex items-center justify-end gap-1.5 flex-nowrap">
                        <button
                          type="button"
                          onClick={() => handleOpenHistory(exp)}
                          className="btn btn-secondary py-1 px-2.5 text-[11px] font-medium shrink-0 flex items-center gap-1"
                          title="View chronological audit events and follow-up timeline"
                          aria-label={`View history for ${exp.domain}`}
                        >
                          <Clock className="w-3 h-3 text-[var(--pixel-purple)]" />
                          <span>History</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleVerifyLive(exp)}
                          disabled={verifyingId === exp.id}
                          className="btn btn-secondary py-1 px-2 text-[11px] shrink-0"
                          title="Re-fetch this URL live to verify if your phone number is still present (HTTP 404/410/Match)"
                        >
                          <RefreshCw
                            className={`w-3 h-3 ${verifyingId === exp.id ? "animate-spin" : ""}`}
                          />
                          <span>{verifyingId === exp.id ? "Checking..." : "Re-check Live"}</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setTransitioningExposure(exp);
                            setTargetNextState("SUBMITTED");
                            setSubmissionRef("");
                            setTransitionNotes("");
                            setTransitionError(null);
                          }}
                          className="btn btn-secondary py-1 px-2.5 text-[11px] font-semibold shrink-0"
                          title="Update truthful lifecycle state"
                        >
                          <SlidersHorizontal className="w-3 h-3 text-[var(--pixel-cyan)]" />
                          <span>Update</span>
                        </button>

                        {exp.source_id !== "generic_web" && (
                          <button
                            type="button"
                            onClick={() => onOpenRemediation(exp.source_id)}
                            className="btn btn-primary py-1 px-2 text-[11px] shrink-0"
                            title="Generate removal letter or view opt-out instructions"
                          >
                            <FileText className="w-3 h-3 text-[#022c22]" />
                            <span>Remediate</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* State Transition Modal */}
      {transitioningExposure && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="transition-modal-title"
        >
          <div className="card w-full max-w-lg border-[var(--border-subtle)] shadow-2xl overflow-hidden bg-[var(--bg-card)]">
            <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-surface)]">
              <div>
                <h3 id="transition-modal-title" className="font-bold text-sm text-[var(--text-main)] flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-[var(--pixel-cyan)]" />
                  Update Exposure State
                </h3>
                <p className="font-mono text-[10px] text-[var(--text-dim)] truncate max-w-sm mt-0.5">
                  {transitioningExposure.domain} — {transitioningExposure.url}
                </p>
              </div>
              <button
                onClick={() => setTransitioningExposure(null)}
                className="text-[var(--text-dim)] hover:text-[var(--text-main)] p-1 rounded font-bold"
                aria-label="Close transition modal"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleExecuteTransition} className="p-5 space-y-4 text-xs">
              {transitionError && (
                <div className="p-3 rounded border border-rose-900 bg-rose-950/30 text-rose-300">
                  {transitionError}
                </div>
              )}

              <div>
                <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase block mb-1">
                  Current Truthful State
                </span>
                <div>{getStatusBadge(transitioningExposure.remediation_status)}</div>
              </div>

              <div>
                <label className="block text-[10px] font-semibold text-[var(--text-dim)] uppercase mb-1">
                  Target Next State
                </label>
                <select
                  value={targetNextState}
                  onChange={(e) => setTargetNextState(e.target.value)}
                  className="input-field text-xs"
                >
                  <option value="SUBMITTED">SUBMITTED (Opt-out request filed)</option>
                  <option value="ACKNOWLEDGED">ACKNOWLEDGED (Broker confirmation received)</option>
                  <option value="SOURCE_CONFIRMED_REMOVAL">
                    SOURCE_CONFIRMED_REMOVAL (Broker verified full database purge)
                  </option>
                  <option value="SEARCH_RESULT_DELISTED">
                    SEARCH_RESULT_DELISTED (Search engine delisting completed)
                  </option>
                  <option value="REMOVAL_REJECTED">REMOVAL_REJECTED (Broker rejected removal request)</option>
                  <option value="REJECTED_MATCH">REJECTED_MATCH (False positive or unrelated listing)</option>
                </select>
                <p className="text-[10px] text-[var(--text-dim)] mt-1">
                  Transitions enforce ClearNum truthful state rules. Verified absence (<span className="font-mono text-cyan-400">NO_LONGER_VISIBLE_AT_CHECKED_URL</span>) cannot be manually chosen; run the "Re-check Live" button to establish HTTP absence proof.
                </p>
              </div>

              <div>
                <label className="block text-[10px] font-semibold text-[var(--text-dim)] uppercase mb-1">
                  Submission / Confirmation Reference (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Opt-Out Ticket #84920 or confirmation code"
                  value={submissionRef}
                  onChange={(e) => setSubmissionRef(e.target.value)}
                  className="input-field text-xs font-mono"
                />
              </div>

              <div>
                <label className="block text-[10px] font-semibold text-[var(--text-dim)] uppercase mb-1">
                  Audit Notes / Evidence
                </label>
                <textarea
                  rows={2}
                  placeholder="Record timestamp, method used (email, form, phone), or response notes..."
                  value={transitionNotes}
                  onChange={(e) => setTransitionNotes(e.target.value)}
                  className="input-field text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
                <button
                  type="button"
                  onClick={() => setTransitioningExposure(null)}
                  className="btn btn-secondary py-1.5 px-3.5 text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={transitionLoading}
                  className="btn btn-primary py-1.5 px-4 text-xs font-semibold flex items-center gap-1.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{transitionLoading ? "Saving..." : "Commit State Transition"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Remediation & Audit History Modal */}
      {selectedHistoryExposure && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="history-modal-title"
        >
          <div className="card w-full max-w-2xl border-[var(--border-subtle)] shadow-2xl overflow-hidden max-h-[90vh] flex flex-col bg-[var(--bg-card)]">
            {/* Modal Header */}
            <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-surface)] shrink-0">
              <div className="min-w-0 pr-3">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-[var(--pixel-purple)] shrink-0" />
                  <h3 id="history-modal-title" className="font-bold text-sm text-[var(--text-main)] truncate">
                    Remediation &amp; Audit History
                  </h3>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--bg-input)] border border-[var(--border-subtle)] text-[var(--text-dim)] shrink-0">
                    {selectedHistoryExposure.source_id}
                  </span>
                </div>
                <div className="font-mono text-[11px] text-[var(--text-dim)] truncate mt-1" title={selectedHistoryExposure.canonical_url || selectedHistoryExposure.url}>
                  <span className="text-[var(--text-muted)] font-semibold">{selectedHistoryExposure.domain}</span>
                  <span className="mx-1.5 opacity-40">|</span>
                  <span>{selectedHistoryExposure.canonical_url || selectedHistoryExposure.url}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedHistoryExposure(null)}
                className="text-[var(--text-dim)] hover:text-[var(--text-main)] p-1.5 rounded transition-colors"
                aria-label="Close history modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div className="p-4 sm:p-5 overflow-y-auto space-y-4 text-xs">
              {/* Current Truthful Status Banner */}
              <div className="p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider">
                      Current State:
                    </span>
                    {getStatusBadge(historyData?.current_status || selectedHistoryExposure.remediation_status)}
                  </div>
                  {historyData?.submission_ref && (
                    <div className="text-[10px] font-mono text-[var(--text-dim)] bg-[var(--bg-input)] px-2 py-0.5 rounded border border-[var(--border-subtle)]">
                      Ref: <span className="text-[var(--pixel-cyan)] font-semibold">{historyData.submission_ref}</span>
                    </div>
                  )}
                </div>
                <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                  {getLifecycleExplanation(historyData?.current_status || selectedHistoryExposure.remediation_status)}
                </p>
              </div>

              {historyLoading ? (
                <div className="py-12 flex flex-col items-center justify-center text-[var(--text-dim)] space-y-3">
                  <RefreshCw className="w-6 h-6 animate-spin text-[var(--pixel-cyan)]" />
                  <span className="text-xs">Loading forensic audit timeline...</span>
                </div>
              ) : historyError ? (
                <div className="p-4 rounded-lg border border-rose-900 bg-rose-950/20 text-rose-300 space-y-2">
                  <div className="font-semibold flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Failed to load history</span>
                  </div>
                  <p className="text-[11px]">{historyError}</p>
                  <button
                    onClick={() => currentIdentity?.hmac_id && fetchHistory(selectedHistoryExposure.id, currentIdentity.hmac_id)}
                    className="btn btn-secondary py-1 px-3 text-xs mt-2"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <>
                  {/* Follow-up & Deadline Section */}
                  {historyData && (
                    <div className="p-3.5 rounded-lg border border-cyan-900/30 bg-[#0c1424] space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Clock className="w-3.5 h-3.5 text-[var(--pixel-cyan)]" />
                          <span className="text-[11px] font-semibold text-[var(--text-main)] uppercase tracking-wider">
                            Follow-Up &amp; Statutory Indicators
                          </span>
                        </div>
                        {/* Basis badge */}
                        <div>
                          {historyData.deadline_basis === "STATUTORY" ? (
                            <span className="status-pill pill-pixel-cyan text-[10px]">
                              <ShieldCheck className="w-3 h-3" /> Statutory Legal Deadline
                            </span>
                          ) : historyData.deadline_basis === "SOURCE_ESTIMATE" ? (
                            <span className="status-pill pill-pixel-yellow text-[10px]">
                              <Clock className="w-3 h-3" /> Industry / Source Estimate
                            </span>
                          ) : historyData.deadline_basis === "USER_DEFINED" ? (
                            <span className="status-pill pill-pixel-purple text-[10px]">
                              <FileText className="w-3 h-3" /> User-Defined Date
                            </span>
                          ) : (
                            <span className="text-[10px] text-[var(--text-dim)] font-mono">
                              No Statutory Basis
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Relative status pill & dates */}
                      {deadlineIndicator && (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
                          <div className="bg-[var(--bg-card)] p-2 rounded border border-[var(--border-subtle)]">
                            <span className="text-[9px] uppercase font-semibold text-[var(--text-dim)] block">
                              Status Indicator
                            </span>
                            <span
                              className={`text-[11px] font-semibold mt-0.5 block ${
                                deadlineIndicator.statusType === "future"
                                  ? "text-[var(--pixel-cyan)]"
                                  : deadlineIndicator.statusType === "overdue"
                                  ? "text-rose-400"
                                  : deadlineIndicator.statusType === "reached"
                                  ? "text-amber-400"
                                  : "text-[var(--text-dim)]"
                              }`}
                            >
                              {deadlineIndicator.label}
                            </span>
                          </div>

                          <div className="bg-[var(--bg-card)] p-2 rounded border border-[var(--border-subtle)] font-mono">
                            <span className="text-[9px] uppercase font-semibold text-[var(--text-dim)] block">
                              Expected Response
                            </span>
                            <span className="text-[11px] text-[var(--text-main)] mt-0.5 block">
                              {historyData.expected_response_date || "Not recorded"}
                            </span>
                          </div>

                          <div className="bg-[var(--bg-card)] p-2 rounded border border-[var(--border-subtle)] font-mono">
                            <span className="text-[9px] uppercase font-semibold text-[var(--text-dim)] block">
                              Follow-Up Date
                            </span>
                            <span className="text-[11px] text-[var(--text-main)] mt-0.5 block">
                              {historyData.follow_up_date || "Not scheduled"}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Request and submission metadata */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[10px] text-[var(--text-dim)] border-t border-[var(--border-subtle)]/50">
                        <div>
                          <span className="block text-[9px] uppercase font-semibold">Request Type:</span>
                          <span className="text-[var(--text-muted)] font-mono font-semibold">
                            {historyData.request_type || "None"}
                          </span>
                        </div>
                        <div>
                          <span className="block text-[9px] uppercase font-semibold">Channel:</span>
                          <span className="text-[var(--text-muted)] font-mono">
                            {historyData.submission_channel || "None"}
                          </span>
                        </div>
                        <div>
                          <span className="block text-[9px] uppercase font-semibold">Submitted:</span>
                          <span className="text-[var(--text-muted)] font-mono">
                            {historyData.submitted_at
                              ? new Date(historyData.submitted_at).toLocaleDateString()
                              : "Not submitted"}
                          </span>
                        </div>
                        <div>
                          <span className="block text-[9px] uppercase font-semibold">Total Events:</span>
                          <span className="text-[var(--text-muted)] font-mono">
                            {historyData.total_events}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Chronological Audit Trail Timeline */}
                  <div className="space-y-3 pt-2">
                    <div className="flex items-center justify-between">
                      <span className="kicker-tag text-[9px]">[ AUDIT LOG — OLDEST TO NEWEST ]</span>
                      <span className="text-[10px] font-mono text-[var(--text-dim)]">
                        {historyData?.events.length || 0} recorded event{historyData?.events.length === 1 ? "" : "s"}
                      </span>
                    </div>

                    {!historyData || historyData.events.length === 0 ? (
                      <div className="p-6 rounded-lg border border-dashed border-[var(--border-subtle)] bg-[var(--bg-surface)] text-center space-y-1.5">
                        <FileText className="w-5 h-5 text-[var(--text-dim)] mx-auto opacity-50" />
                        <div className="text-xs font-semibold text-[var(--text-muted)]">
                          No audit events recorded yet
                        </div>
                        <p className="text-[10px] text-[var(--text-dim)] max-w-sm mx-auto leading-relaxed">
                          Audit entries are appended automatically when you generate a prepared request, record external submission, run a verification check, or commit state transitions.
                        </p>
                      </div>
                    ) : (
                      <div className="relative pl-6 space-y-4 border-l border-[var(--border-subtle)] ml-3 pt-1">
                        {historyData.events.map((ev, idx) => (
                          <div key={ev.id || idx} className="relative group">
                            {/* Dot indicator */}
                            <div className="absolute -left-[31px] top-1 w-3 h-3 rounded-full bg-[var(--bg-elevated)] border-2 border-[var(--pixel-purple)] group-hover:border-[var(--pixel-cyan)] transition-colors" />

                            <div className="card p-3 space-y-2 bg-[var(--bg-surface)] hover:border-[var(--border-strong)] transition-colors">
                              {/* Header row: timestamp & transition */}
                              <div className="flex flex-wrap items-center justify-between gap-1.5 text-[10px]">
                                <div className="flex items-center gap-1.5">
                                  <Clock className="w-2.5 h-2.5 text-[var(--text-dim)]" />
                                  <span className="font-mono text-[var(--text-dim)]">
                                    {new Date(ev.created_at).toLocaleString()}
                                  </span>
                                </div>
                                <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-[var(--bg-input)] border border-[var(--border-subtle)] text-[var(--pixel-purple)]">
                                  {ev.evidence_type}
                                </span>
                              </div>

                              {/* State Transition */}
                              <div className="flex items-center gap-2 text-[11px] font-mono">
                                {ev.from_state ? (
                                  <>
                                    <span className="text-[var(--text-dim)]">{ev.from_state}</span>
                                    <ArrowRight className="w-3 h-3 text-[var(--text-dim)]" />
                                    <span className="text-[var(--pixel-cyan)] font-semibold">{ev.to_state}</span>
                                  </>
                                ) : (
                                  <span className="text-[var(--pixel-cyan)] font-semibold">{ev.to_state}</span>
                                )}
                              </div>

                              {/* Notes */}
                              {ev.evidence_notes && (
                                <div className="text-[11px] text-[var(--text-muted)] font-mono bg-[var(--bg-input)]/70 p-2 rounded border border-[var(--border-subtle)] break-words leading-relaxed">
                                  {ev.evidence_notes}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Modal Footer Quick Actions */}
            <div className="p-3 sm:p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-wrap items-center justify-between gap-2 shrink-0">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleVerifyLive(selectedHistoryExposure)}
                  disabled={verifyingId === selectedHistoryExposure.id}
                  className="btn btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
                  title="Re-fetch this URL live to verify if phone number is absent (HTTP 404/410/Absence)"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${verifyingId === selectedHistoryExposure.id ? "animate-spin" : ""}`} />
                  <span>{verifyingId === selectedHistoryExposure.id ? "Checking..." : "Verify URL Now"}</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setTransitioningExposure(selectedHistoryExposure);
                    setTargetNextState("ACKNOWLEDGED");
                    setSubmissionRef(historyData?.submission_ref || "");
                    setTransitionNotes("");
                    setTransitionError(null);
                  }}
                  className="btn btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
                  title="Record that recipient acknowledged receiving your request"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--pixel-cyan)]" />
                  <span>Record Acknowledgment</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setTransitioningExposure(selectedHistoryExposure);
                    setTargetNextState("SOURCE_CONFIRMED_REMOVAL");
                    setSubmissionRef(historyData?.submission_ref || "");
                    setTransitionNotes("");
                    setTransitionError(null);
                  }}
                  className="btn btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
                  title="Record that source claimed removal (requires subsequent affirmative verification)"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-[var(--pixel-green)]" />
                  <span>Record Removal Claim</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setTransitioningExposure(selectedHistoryExposure);
                    setTargetNextState("SUBMITTED");
                    setSubmissionRef(historyData?.submission_ref || "");
                    setTransitionNotes("");
                    setTransitionError(null);
                  }}
                  className="btn btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
                  title="Update lifecycle state"
                >
                  <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--pixel-cyan)]" />
                  <span>Update Status</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => setSelectedHistoryExposure(null)}
                className="btn btn-primary py-1.5 px-4 text-xs font-semibold"
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
