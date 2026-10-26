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
  ArrowRight,
  XCircle,
  SlidersHorizontal,
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
        return <span className="status-pill pill-emerald">Exact Match</span>;
      case "PROBABLE":
        return <span className="status-pill pill-cyan">Probable Match</span>;
      case "WEAK":
        return <span className="status-pill pill-amber">Weak Match</span>;
      case "FALSE_POSITIVE":
        return <span className="status-pill pill-neutral">False Positive</span>;
      default:
        return <span className="status-pill pill-neutral">{matchType}</span>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SOURCE_CONFIRMED_REMOVAL":
        return <span className="status-pill pill-emerald"><CheckCircle2 className="w-3 h-3" /> Source Confirmed Removal</span>;
      case "NO_LONGER_VISIBLE_AT_CHECKED_URL":
      case "VERIFIED_REMOVED":
        return <span className="status-pill pill-teal"><CheckCircle2 className="w-3 h-3" /> No Longer Visible at URL</span>;
      case "SEARCH_RESULT_DELISTED":
        return <span className="status-pill pill-teal"><FileText className="w-3 h-3" /> Search Result Delisted</span>;
      case "SUBMITTED":
        return <span className="status-pill pill-cyan"><RefreshCw className="w-3 h-3" /> Submitted</span>;
      case "ACKNOWLEDGED":
        return <span className="status-pill pill-cyan"><FileText className="w-3 h-3" /> Acknowledged</span>;
      case "AWAITING_VERIFICATION":
      case "PENDING":
        return <span className="status-pill pill-cyan"><RefreshCw className="w-3 h-3" /> Awaiting Verification</span>;
      case "AWAITING_USER_APPROVAL":
      case "ACTION_AVAILABLE":
        return <span className="status-pill pill-amber"><AlertTriangle className="w-3 h-3" /> Awaiting User Approval</span>;
      case "CONFIRMED_EXPOSURE":
      case "VERIFIED":
        return <span className="status-pill pill-amber">Confirmed Exposure</span>;
      case "REQUEST_PREPARED":
        return <span className="status-pill pill-amber"><FileText className="w-3 h-3" /> Request Prepared</span>;
      case "STILL_VISIBLE":
        return <span className="status-pill pill-rose"><AlertTriangle className="w-3 h-3" /> Still Visible</span>;
      case "INACCESSIBLE_OR_INCONCLUSIVE":
      case "UNABLE_TO_VERIFY":
        return <span className="status-pill pill-amber">Inconclusive / Blocked</span>;
      case "REAPPEARED":
        return <span className="status-pill pill-rose"><AlertTriangle className="w-3 h-3" /> Reappeared</span>;
      case "REJECTED":
      case "REJECTED_MATCH":
        return <span className="status-pill pill-slate"><XCircle className="w-3 h-3" /> Rejected Match</span>;
      case "AWAITING_USER_REVIEW":
        return <span className="status-pill pill-neutral">Awaiting User Review</span>;
      case "DISCOVERED":
      default:
        return <span className="status-pill pill-neutral">Discovered</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 panel-card p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-sky-950/80 border border-sky-800 flex items-center justify-center text-sky-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              Discovered Exposures
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                {exposures.length} Total
              </span>
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              All indexed broker entries and public listings tied to your identity HMAC.
            </p>
          </div>
        </div>

        {/* Filter & Search controls */}
        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
          <div className="relative min-w-[180px]">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Filter by domain..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field pl-8 py-1.5 text-xs"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
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

          <button onClick={onRefresh} className="btn-secondary py-1.5 px-2.5 text-xs" title="Refresh records">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Verification Live Alert Banner (if recently triggered) */}
      {verificationFeedback && (
        <div
          className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
            verificationFeedback.status === "VERIFIED_REMOVED"
              ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
              : verificationFeedback.status === "VERIFIED"
              ? "bg-amber-950/40 border-amber-800 text-amber-300"
              : "bg-slate-900 border-slate-700 text-slate-300"
          }`}
        >
          {verificationFeedback.status === "VERIFIED_REMOVED" ? (
            <ShieldCheck className="w-4 h-4 mt-0.5 text-emerald-400 shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 mt-0.5 text-amber-400 shrink-0" />
          )}
          <div className="flex-1">
            <div className="font-semibold">
              Live Rescan Check: {verificationFeedback.status}{" "}
              {verificationFeedback.code ? `(HTTP ${verificationFeedback.code})` : ""}
            </div>
            <div className="text-[11px] opacity-90 mt-0.5">{verificationFeedback.notes}</div>
          </div>
          <button
            onClick={() => setVerificationFeedback(null)}
            className="text-slate-400 hover:text-slate-200 text-xs px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Exposures Content */}
      {filteredExposures.length === 0 ? (
        <div className="panel-card p-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-200">No Discovered Exposures Found</h3>
            <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto mt-1">
              {searchQuery || statusFilter !== "ALL"
                ? "No exposure matches the selected filter criteria. Try clearing filters."
                : "No phone exposures are currently registered in your local database for this identity."}
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <button onClick={onNavigateToScan} className="btn-primary text-xs py-2 px-4">
              <Search className="w-3.5 h-3.5" /> Start Discovery Scan
            </button>
            <button onClick={onLoadDemo} className="btn-secondary text-xs py-2 px-4">
              Load Demo Dataset
            </button>
          </div>
        </div>
      ) : (
        <div className="panel-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: "24%" }}>Source / Domain</th>
                  <th style={{ width: "38%" }}>Indexed Listing Snippet</th>
                  <th style={{ width: "16%" }}>Match Confidence</th>
                  <th style={{ width: "12%" }}>Lifecycle State</th>
                  <th style={{ width: "10%", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredExposures.map((exp) => (
                  <tr key={exp.id}>
                    {/* Domain & URL */}
                    <td>
                      <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                        <span>{exp.domain}</span>
                        <a
                          href={exp.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-400 hover:text-sky-400 inline-flex items-center"
                          title="Open exposed URL in new tab"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <div className="text-[11px] text-[var(--text-dim)] truncate max-w-xs" title={exp.url}>
                        {exp.url}
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        Discovered: {exp.discovered_at ? new Date(exp.discovered_at).toLocaleDateString() : "Recent"}
                      </div>
                    </td>

                    {/* Snippet / Context */}
                    <td>
                      <div className="text-xs text-slate-200 line-clamp-2 leading-relaxed font-sans bg-slate-900/60 p-2 rounded border border-slate-800/80">
                        {exp.snippet ? (
                          <span>{exp.snippet}</span>
                        ) : (
                          <span className="text-slate-400 italic">Indexed profile record associated with phone match.</span>
                        )}
                      </div>
                    </td>

                    {/* Match Type */}
                    <td>
                      <div>{getMatchBadge(exp.match_type)}</div>
                      <div className="text-[10px] text-slate-400 mt-1 font-mono">
                        Score: {Math.round(exp.confidence * 100)}%
                      </div>
                    </td>

                    {/* Lifecycle Status */}
                    <td>
                      <div>{getStatusBadge(exp.remediation_status)}</div>
                      {exp.last_checked_at && (
                        <div className="text-[10px] text-slate-400 mt-1">
                          Checked: {new Date(exp.last_checked_at).toLocaleDateString()}
                        </div>
                      )}
                    </td>

                    {/* Action buttons */}
                    <td style={{ textAlign: "right" }}>
                      <div className="flex items-center justify-end gap-1.5">
                        {/* Live Rescan button */}
                        <button
                          onClick={() => handleVerifyLive(exp)}
                          disabled={verifyingId === exp.id}
                          className="btn-secondary py-1 px-2 text-xs"
                          title="SSRF-safe live check whether this URL is removed (HTTP 404/cleared text)"
                        >
                          <RefreshCw
                            className={`w-3 h-3 text-sky-400 ${verifyingId === exp.id ? "animate-spin" : ""}`}
                          />
                          <span className="hidden lg:inline text-[11px]">Verify</span>
                        </button>

                        {/* Status Transition Button */}
                        <button
                          onClick={() => {
                            setTransitioningExposure(exp);
                            setTargetNextState(
                              exp.remediation_status === "DISCOVERED"
                                ? "VERIFIED"
                                : exp.remediation_status === "VERIFIED"
                                ? "ACTION_AVAILABLE"
                                : exp.remediation_status === "ACTION_AVAILABLE"
                                ? "SUBMITTED"
                                : exp.remediation_status === "SUBMITTED"
                                ? "ACKNOWLEDGED"
                                : exp.remediation_status === "ACKNOWLEDGED"
                                ? "VERIFIED_REMOVED"
                                : "SUBMITTED"
                            );
                          }}
                          className="btn-secondary py-1 px-2 text-xs"
                          title="Change truthful lifecycle state"
                        >
                          <SlidersHorizontal className="w-3 h-3 text-slate-300" />
                          <span className="hidden lg:inline text-[11px]">Update</span>
                        </button>

                        {/* Remediate link */}
                        {exp.official_removal_url ? (
                          <a
                            href={exp.official_removal_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-primary py-1 px-2 text-xs"
                            title="Open official broker opt-out portal"
                          >
                            <ExternalLink className="w-3 h-3" />
                            <span className="hidden lg:inline text-[11px]">Opt-Out</span>
                          </a>
                        ) : (
                          <button
                            onClick={() => onOpenRemediation(exp.source_id)}
                            className="btn-secondary py-1 px-2 text-xs text-sky-400"
                            title="Open Remediation Hub guide"
                          >
                            <ArrowRight className="w-3 h-3" />
                            <span className="hidden lg:inline text-[11px]">Guide</span>
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

      {/* Truthful State Transition Modal */}
      {transitioningExposure && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="panel-card w-full max-w-lg p-6 space-y-4 border-slate-700 bg-slate-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-100">Update Remediation State</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Enforces verifiable lifecycle state progression for {transitioningExposure.domain}
                </p>
              </div>
              <button
                onClick={() => setTransitioningExposure(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            {transitionError && (
              <div className="p-3 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
                {transitionError}
              </div>
            )}

            <form onSubmit={handleExecuteTransition} className="space-y-4">
              <div>
                <label className="text-xs text-slate-300 font-semibold block mb-1">Target Next State</label>
                <select
                  value={targetNextState}
                  onChange={(e) => setTargetNextState(e.target.value)}
                  className="input-field text-xs"
                >
                  <option value="CONFIRMED_EXPOSURE">CONFIRMED_EXPOSURE (Confirmed phone appearance)</option>
                  <option value="AWAITING_USER_APPROVAL">AWAITING_USER_APPROVAL (Removal path identified)</option>
                  <option value="REQUEST_PREPARED">REQUEST_PREPARED (Legal notice generated)</option>
                  <option value="SUBMITTED">SUBMITTED (Opt-out request sent via portal/email)</option>
                  <option value="ACKNOWLEDGED">ACKNOWLEDGED (Broker confirmation received)</option>
                  <option value="AWAITING_VERIFICATION">AWAITING_VERIFICATION (Pending statutory window)</option>
                  <option value="NO_LONGER_VISIBLE_AT_CHECKED_URL">NO_LONGER_VISIBLE_AT_CHECKED_URL (Page 404 or number absent)</option>
                  <option value="SEARCH_RESULT_DELISTED">SEARCH_RESULT_DELISTED (Delisted from Google/Bing cache)</option>
                  <option value="SOURCE_CONFIRMED_REMOVAL">SOURCE_CONFIRMED_REMOVAL (Affirmative broker deletion receipt)</option>
                  <option value="STILL_VISIBLE">STILL_VISIBLE (Target number still present on live page)</option>
                  <option value="INACCESSIBLE_OR_INCONCLUSIVE">INACCESSIBLE_OR_INCONCLUSIVE (Firewall / anti-bot challenge)</option>
                  <option value="REJECTED">REJECTED (False positive / not my record)</option>
                </select>
                <p className="text-[11px] text-slate-400 mt-1">
                  Current state: <span className="font-mono text-slate-200">{transitioningExposure.remediation_status}</span>
                </p>
              </div>

              <div>
                <label className="text-xs text-slate-300 font-semibold block mb-1">
                  Submission Reference / Confirmation ID (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g., REQ-98421, confirmation email timestamp"
                  value={submissionRef}
                  onChange={(e) => setSubmissionRef(e.target.value)}
                  className="input-field text-xs"
                />
              </div>

              <div>
                <label className="text-xs text-slate-300 font-semibold block mb-1">Audit Notes (Optional)</label>
                <textarea
                  rows={2}
                  placeholder="Details of removal confirmation, broker ticket ID, or rescan notes..."
                  value={transitionNotes}
                  onChange={(e) => setTransitionNotes(e.target.value)}
                  className="input-field text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setTransitioningExposure(null)}
                  className="btn-secondary text-xs py-2 px-3"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={transitionLoading}
                  className="btn-primary text-xs py-2 px-4"
                >
                  {transitionLoading ? "Saving..." : "Confirm Transition"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
