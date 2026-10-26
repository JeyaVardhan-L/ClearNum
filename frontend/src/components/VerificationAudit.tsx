import React, { useState } from "react";
import {
  ShieldCheck,
  Upload,
  Download,
  Trash2,
  RefreshCw,
  ExternalLink,
  Lock,
  Mail,
  MessageSquare,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import type { PhoneParseResult } from "../types";
import {
  verifyExposure,
  uploadMboxFile,
  uploadSmsFile,
  exportAuditReport,
  purgeData,
} from "../api";

interface VerificationAuditProps {
  currentIdentity: PhoneParseResult | null;
  onPurgeComplete: () => void;
}

export const VerificationAudit: React.FC<VerificationAuditProps> = ({
  currentIdentity,
  onPurgeComplete,
}) => {
  // Live Rescan State
  const [rescanUrl, setRescanUrl] = useState("");
  const [rescanLoading, setRescanLoading] = useState(false);
  const [rescanResult, setRescanResult] = useState<{
    url: string;
    status: string;
    http_status_code?: number;
    evidence_notes: string;
    verified_at: string;
  } | null>(null);

  // MBOX State
  const [mboxFile, setMboxFile] = useState<File | null>(null);
  const [mboxLoading, setMboxLoading] = useState(false);
  const [mboxResult, setMboxResult] = useState<{
    subscriptions_detected: number;
    phone_signatures_found: number;
    subscriptions: any[];
  } | null>(null);

  // SMS State
  const [smsFile, setSmsFile] = useState<File | null>(null);
  const [smsLoading, setSmsLoading] = useState(false);
  const [smsResult, setSmsResult] = useState<{
    total_parsed: number;
    shortcode_senders_found: number;
    stop_optouts_found: number;
    shortcode_senders: any[];
  } | null>(null);

  // Export State
  const [exportLoading, setExportLoading] = useState(false);

  // Purge State
  const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);
  const [purgeInput, setPurgeInput] = useState("");
  const [purgeLoading, setPurgeLoading] = useState(false);

  const handleLiveRescan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rescanUrl.trim() || !currentIdentity) {
      alert("Please enter a valid URL and ensure an identity is initialized.");
      return;
    }

    setRescanLoading(true);
    setRescanResult(null);

    try {
      const res = await verifyExposure(
        "ad-hoc-verification",
        rescanUrl.trim(),
        currentIdentity.e164 || currentIdentity.masked_display,
        currentIdentity.region_code
      );
      setRescanResult(res);
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setRescanLoading(false);
    }
  };

  const handleMboxUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mboxFile) return;

    setMboxLoading(true);
    try {
      const res = await uploadMboxFile(mboxFile, currentIdentity?.e164 || "");
      setMboxResult(res);
    } catch (err: any) {
      alert(`MBOX parse error: ${err.message}`);
    } finally {
      setMboxLoading(false);
    }
  };

  const handleSmsUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!smsFile) return;

    setSmsLoading(true);
    try {
      const res = await uploadSmsFile(smsFile, currentIdentity?.hmac_id || "");
      setSmsResult(res);
    } catch (err: any) {
      alert(`SMS parse error: ${err.message}`);
    } finally {
      setSmsLoading(false);
    }
  };

  const handleExportReport = async () => {
    if (!currentIdentity) return;
    setExportLoading(true);
    try {
      const report = await exportAuditReport(currentIdentity.hmac_id);

      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `numbershield_audit_${currentIdentity.hmac_id.slice(0, 8)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setExportLoading(false);
    }
  };

  const handleExecutePurge = async () => {
    if (purgeInput !== "PURGE") {
      alert("Please type PURGE to confirm.");
      return;
    }

    setPurgeLoading(true);
    try {
      await purgeData();
      setShowPurgeConfirm(false);
      onPurgeComplete();
    } catch (err: any) {
      alert(`Purge failed: ${err.message}`);
    } finally {
      setPurgeLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="panel-card p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-sky-950/80 border border-sky-800 flex items-center justify-center text-sky-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100">Verification & Forensic Audit</h2>
            <p className="text-xs text-[var(--text-muted)]">
              Live SSRF-safe URL verification, local MBOX/SMS parsing, and cryptographic proof export.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start md:self-center">
          <button
            onClick={handleExportReport}
            disabled={exportLoading || !currentIdentity}
            className="btn-secondary text-xs py-1.5 px-3"
            title="Download full forensic JSON audit trail"
          >
            <Download className="w-3.5 h-3.5 text-sky-400" />
            <span>Export Audit Trail</span>
          </button>
          <button
            onClick={() => setShowPurgeConfirm(true)}
            className="btn-danger text-xs py-1.5 px-3"
            title="Zero-trace cryptographic wipe of all records"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Cryptographic Purge</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Live Rescan & Local SMS / MBOX parsers */}
        <div className="lg:col-span-7 space-y-6">
          {/* Live URL Rescan Box */}
          <div className="panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 text-sky-400" /> Live URL Rescan & Verification
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Direct SSRF-safe HTTP inspection to confirm if a broker profile has been de-indexed or deleted.
                </p>
              </div>
            </div>

            <form onSubmit={handleLiveRescan} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Target Page URL</label>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={rescanUrl}
                    onChange={(e) => setRescanUrl(e.target.value)}
                    placeholder="https://www.broker.com/people/j-doe/..."
                    className="input-field text-xs font-mono flex-1"
                    required
                  />
                  <button
                    type="submit"
                    disabled={rescanLoading || !currentIdentity}
                    className="btn-primary text-xs py-1.5 px-4 shrink-0"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${rescanLoading ? "animate-spin" : ""}`} />
                    <span>Verify Live</span>
                  </button>
                </div>
              </div>
            </form>

            {rescanResult && (
              <div
                className={`p-3.5 rounded-lg border text-xs space-y-1.5 ${
                  rescanResult.status === "VERIFIED_REMOVED"
                    ? "bg-emerald-950/40 border-emerald-800 text-emerald-200"
                    : rescanResult.status === "VERIFIED"
                    ? "bg-rose-950/40 border-rose-800 text-rose-200"
                    : "bg-slate-900 border-slate-700 text-slate-200"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold uppercase tracking-wider flex items-center gap-1.5">
                    {rescanResult.status === "VERIFIED_REMOVED" ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-rose-400" />
                    )}
                    Outcome: {rescanResult.status}
                  </span>
                  {rescanResult.http_status_code && (
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-950/80 border border-slate-700">
                      HTTP {rescanResult.http_status_code}
                    </span>
                  )}
                </div>
                <p className="text-[11px] leading-relaxed opacity-90">{rescanResult.evidence_notes}</p>
                <div className="text-[10px] text-slate-400">
                  Checked at: {new Date(rescanResult.verified_at).toLocaleString()}
                </div>
              </div>
            )}
          </div>

          {/* Local MBOX Email Archive Parser */}
          <div className="panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <Mail className="w-4 h-4 text-sky-400" /> Local Email Archive (.mbox) Parser
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Discovers marketing senders with List-Unsubscribe headers and extracted telephone footers without sending data to any server.
                </p>
              </div>
            </div>

            <form onSubmit={handleMboxUpload} className="space-y-3">
              <div className="border-2 border-dashed border-slate-800 rounded-lg p-4 text-center hover:border-slate-700 transition-colors">
                <input
                  type="file"
                  accept=".mbox"
                  onChange={(e) => setMboxFile(e.target.files?.[0] || null)}
                  className="text-xs text-slate-400 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!mboxFile || mboxLoading}
                  className="btn-primary text-xs py-1.5 px-4"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>{mboxLoading ? "Analyzing MBOX Locally..." : "Analyze MBOX"}</span>
                </button>
              </div>
            </form>

            {mboxResult && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center gap-4 text-xs font-semibold">
                  <span className="text-sky-400">
                    {mboxResult.subscriptions_detected} Commercial Subscriptions Found
                  </span>
                  <span className="text-emerald-400">
                    {mboxResult.phone_signatures_found} Phone Signatures
                  </span>
                </div>

                <div className="max-h-48 overflow-y-auto space-y-2">
                  {mboxResult.subscriptions.map((sub, i) => (
                    <div key={i} className="bg-slate-900/60 p-2.5 rounded border border-slate-800 text-xs flex items-center justify-between gap-2">
                      <div className="truncate">
                        <div className="font-semibold text-slate-200">{sub.sender_domain}</div>
                        <div className="text-[10px] text-slate-400 truncate">{sub.sender_email}</div>
                      </div>
                      {sub.unsubscribe_url && (
                        <a
                          href={sub.unsubscribe_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-secondary py-1 px-2 text-[10px] shrink-0"
                        >
                          <ExternalLink className="w-3 h-3" /> Unsubscribe
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Local SMS Backup Parser */}
          <div className="panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-sky-400" /> Local SMS Backup Parser (.xml / .json / .csv)
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Scans SMS backups for 4-6 digit commercial shortcodes and STOP opt-out instructions.
                </p>
              </div>
            </div>

            <form onSubmit={handleSmsUpload} className="space-y-3">
              <div className="border-2 border-dashed border-slate-800 rounded-lg p-4 text-center hover:border-slate-700 transition-colors">
                <input
                  type="file"
                  accept=".xml,.json,.csv"
                  onChange={(e) => setSmsFile(e.target.files?.[0] || null)}
                  className="text-xs text-slate-400 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!smsFile || smsLoading}
                  className="btn-primary text-xs py-1.5 px-4"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>{smsLoading ? "Scanning Messages..." : "Scan SMS Backup"}</span>
                </button>
              </div>
            </form>

            {smsResult && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center gap-4 text-xs font-semibold">
                  <span className="text-sky-400">{smsResult.shortcode_senders_found} Commercial Shortcodes</span>
                  <span className="text-emerald-400">{smsResult.stop_optouts_found} STOP Opt-Outs Identified</span>
                </div>

                <div className="max-h-48 overflow-y-auto space-y-2">
                  {smsResult.shortcode_senders.map((sc, i) => (
                    <div key={i} className="bg-slate-900/60 p-2.5 rounded border border-slate-800 text-xs flex items-center justify-between gap-2">
                      <div>
                        <span className="font-mono font-bold text-sky-400 mr-2">{sc.shortcode}</span>
                        <span className="text-slate-300">{sc.campaign_snippet || "Automated marketing sender"}</span>
                      </div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                        Reply STOP
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Cryptographic Privacy Architecture & Purge */}
        <div className="lg:col-span-5 space-y-6">
          {/* Cryptographic Key & Zero-Trace Proof */}
          <div className="panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Lock className="w-4 h-4 text-emerald-400" /> Cryptographic Guarantees
              </h3>
              <span className="status-pill pill-emerald text-[10px]">Active</span>
            </div>

            <div className="space-y-3 text-xs text-slate-300 leading-relaxed">
              <div className="bg-slate-900 p-3 rounded border border-slate-800 space-y-1.5 font-mono text-[11px]">
                <div className="text-slate-400">Current Identity HMAC-SHA256:</div>
                <div className="text-emerald-400 break-all select-all">
                  {currentIdentity?.hmac_id || "Uninitialized"}
                </div>
                <div className="text-slate-400 pt-1">Masked Representation:</div>
                <div className="text-slate-200">
                  {currentIdentity?.masked_display || "—"}
                </div>
              </div>

              <ul className="list-disc list-inside space-y-1.5 text-[11px] text-slate-400">
                <li>
                  <strong className="text-slate-200">Keyed HMAC Protection:</strong> Phone numbers are keyed with a random 256-bit local secret (`.numbershield_key`) preventing rainbow table attacks.
                </li>
                <li>
                  <strong className="text-slate-200">Zero Cloud Egress:</strong> All database operations, parsing, and regex dorking execute strictly on `127.0.0.1`.
                </li>
                <li>
                  <strong className="text-slate-200">Forensic Scrubbing:</strong> Application logs redact all E.164 and localized telephone representations before writing to disk.
                </li>
                <li>
                  <strong className="text-slate-200">Cryptographic Erasure:</strong> Purging overwrites the SQLite database and secret key with random entropy bytes before unlinking.
                </li>
              </ul>
            </div>
          </div>

          {/* Purge Card */}
          <div className="panel-card p-5 space-y-3 border-rose-900/60 bg-rose-950/10">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertTriangle className="w-4 h-4" />
              <h4 className="font-bold text-sm">Zero-Trace Cryptographic Purge</h4>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Permanently destroys all discovered exposures, remediation records, spam logs, and the 256-bit HMAC key. Irreversible once confirmed.
            </p>
            <button
              onClick={() => setShowPurgeConfirm(true)}
              className="btn-danger w-full text-xs py-2 mt-1"
            >
              <Trash2 className="w-3.5 h-3.5" /> Launch Cryptographic Purge
            </button>
          </div>
        </div>
      </div>

      {/* Purge Confirmation Modal */}
      {showPurgeConfirm && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="panel-card w-full max-w-md p-6 space-y-4 border-rose-800 bg-slate-950 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400 border-b border-rose-950 pb-3">
              <AlertTriangle className="w-6 h-6" />
              <div>
                <h3 className="font-bold text-base text-slate-100">Confirm Zero-Trace Erasure</h3>
                <p className="text-xs text-rose-300">This action will destroy all local data files.</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              This will overwrite the SQLite database and HMAC seed with random entropy, drop all tables, and reset your session.
              To confirm, type <span className="font-mono font-bold text-rose-400">PURGE</span> below:
            </p>

            <input
              type="text"
              value={purgeInput}
              onChange={(e) => setPurgeInput(e.target.value)}
              placeholder="Type PURGE to confirm"
              className="input-field text-xs font-mono border-rose-800 focus:border-rose-500"
              autoFocus
            />

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setShowPurgeConfirm(false);
                  setPurgeInput("");
                }}
                className="btn-secondary text-xs py-1.5 px-3"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecutePurge}
                disabled={purgeInput !== "PURGE" || purgeLoading}
                className="btn-danger text-xs py-1.5 px-4"
              >
                {purgeLoading ? "Purging Files..." : "Permanently Destroy Data"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
