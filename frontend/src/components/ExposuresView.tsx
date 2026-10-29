import React, { useState } from "react";
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
} from "lucide-react";
import type { DiscoveredExposure, PhoneParseResult } from "../types";
import { transitionAction, verifyExposure } from "../api";

interface ExposuresViewProps {
  exposures: DiscoveredExposure[];
  currentIdentity: PhoneParseResult | null;
  onRefresh: () => void;
  onOpenRemediation: (selectedSourceId?: string) => void;
  onNavigateToScan: () => void;
  onLoadDemo: () => void;
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
  } | null>(null);

  // Transition state modal
  const [transitioningExposure, setTransitioningExposure] = useState<DiscoveredExposure | null>(null);
  const [targetNextState, setTargetNextState] = useState<string>("SUBMITTED");
  const [submissionRef, setSubmissionRef] = useState<string>("");
  const [transitionNotes, setTransitionNotes] = useState<string>("");
  const [transitionLoading, setTransitionLoading] = useState<boolean>(false);
  const [transitionError, setTransitionError] = useState<string | null>(null);

  const filteredExposures = exposures.filter((exp) => {
    const matchesStatus = statusFilter === "ALL" || exp.remediation_status === statusFilter;
    const matchesSearch =
      searchQuery === "" ||
      exp.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
      exp.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      exp.url.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

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
      });
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
      setTransitioningExposure(null);
      setSubmissionRef("");
      setTransitionNotes("");
      onRefresh();
    } catch (err: any) {
      setTransitionError(err.message || "Invalid state transition.");
    } finally {
      setTransitionLoading(false);
    }
  };

  const getMatchBadge = (matchType: string) => {
    switch (matchType) {
      case "EXACT":
        return <span className="status-pill pill-pixel-green font-mono">Exact Match</span>;
      case "PROBABLE":
        return <span className="status-pill pill-pixel-cyan font-mono">Probable Match</span>;
      case "WEAK":
        return <span className="status-pill pill-pixel-yellow font-mono">Weak Match</span>;
      case "FALSE_POSITIVE":
        return <span className="status-pill pill-pixel-purple font-mono">False Positive</span>;
      default:
        return <span className="status-pill pill-pixel-purple font-mono">{matchType}</span>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
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
        return (
          <span className="status-pill pill-pixel-purple">
            <XCircle className="w-3 h-3" /> Rejected Match
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
          className={`p-3 rounded-lg border flex items-start gap-2.5 ${
            verificationFeedback.status === "VERIFIED_REMOVED"
              ? "border-emerald-500/40 bg-emerald-950/20 text-emerald-400"
              : verificationFeedback.status === "VERIFIED"
              ? "border-amber-500/40 bg-amber-950/20 text-amber-400"
              : "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-main)]"
          }`}
        >
          {verificationFeedback.status === "VERIFIED_REMOVED" ? (
            <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          )}
          <div className="flex-1">
            <div className="text-xs font-semibold">
              Live Rescan Check: {verificationFeedback.status}{" "}
              {verificationFeedback.code ? `(HTTP ${verificationFeedback.code})` : ""}
            </div>
            <div className="text-[11px] opacity-90 mt-0.5">{verificationFeedback.notes}</div>
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
                  <th style={{ width: "34%" }}>INDEXED LISTING SNIPPET</th>
                  <th style={{ width: "14%" }}>MATCH CONFIDENCE</th>
                  <th style={{ width: "14%" }}>LIFECYCLE STATE</th>
                  <th style={{ width: "18%", textAlign: "right", whiteSpace: "nowrap" }}>ACTIONS</th>
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
                        title={exp.url}
                      >
                        {exp.url}
                      </div>
                      <div className="text-[10px] text-[var(--text-dim)] mt-0.5">
                        Discovered:{" "}
                        {exp.discovered_at
                          ? new Date(exp.discovered_at).toLocaleDateString()
                          : "Recent"}
                      </div>
                    </td>

                    {/* Snippet */}
                    <td>
                      <div className="text-xs text-[var(--text-muted)] line-clamp-2 leading-relaxed font-mono">
                        {exp.snippet || "No textual context snippet available."}
                      </div>
                      <div className="text-[10px] text-[var(--text-dim)] mt-1">
                        Source Registry: <span className="text-[var(--pixel-cyan)] font-mono">{exp.source_id}</span>
                      </div>
                    </td>

                    {/* Match Confidence */}
                    <td>
                      <div className="space-y-1">
                        {getMatchBadge(exp.match_type)}
                        <div className="text-[10px] text-[var(--text-dim)] font-mono">
                          Score: {(exp.confidence * 100).toFixed(0)}%
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="card w-full max-w-lg border-[var(--border-subtle)] shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-surface)]">
              <div>
                <h3 className="font-bold text-sm text-[var(--text-main)] flex items-center gap-2">
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
                  <option value="NO_LONGER_VISIBLE_AT_CHECKED_URL">
                    NO_LONGER_VISIBLE_AT_CHECKED_URL (Live verification check confirms removal)
                  </option>
                  <option value="SOURCE_CONFIRMED_REMOVAL">
                    SOURCE_CONFIRMED_REMOVAL (Broker verified full database purge)
                  </option>
                  <option value="SEARCH_RESULT_DELISTED">
                    SEARCH_RESULT_DELISTED (Search engine delisting completed)
                  </option>
                  <option value="REJECTED_MATCH">REJECTED_MATCH (False positive or unrelated listing)</option>
                </select>
                <p className="text-[10px] text-[var(--text-dim)] mt-1">
                  Transitions enforce NumberShield truthful state rules. Premature or unverified claims are rejected.
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
    </div>
  );
};
