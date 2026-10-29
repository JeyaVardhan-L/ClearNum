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
        "AD-HOC-VERIFICATION",
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
      <div className="card p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] flex items-center justify-center text-[var(--pixel-green)]">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-main)]">Verification & Forensic Audit</h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Live SSRF-safe URL verification, local MBOX/SMS parsing, and cryptographic proof export.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 self-start md:self-center">
          <button
            onClick={handleExportReport}
            disabled={exportLoading || !currentIdentity}
            className="btn btn-secondary text-xs py-1.5 px-3"
            title="Download full forensic JSON audit trail"
          >
            <Download className="w-3.5 h-3.5" />
            <span>EXPORT AUDIT TRAIL</span>
          </button>
          <button
            onClick={() => setShowPurgeConfirm(true)}
            className="btn btn-pixel danger text-xs py-1.5 px-3"
            title="Zero-trace cryptographic wipe of all records"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>CRYPTOGRAPHIC PURGE</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Live Rescan & Local SMS / MBOX parsers */}
        <div className="lg:col-span-7 space-y-6">
          {/* Live URL Rescan Box */}
          <div className="card p-5 space-y-4">
            <div className="border-b border-[var(--border-subtle)] pb-3">
              <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-[var(--pixel-green)]" /> Live URL Rescan & Verification
              </h3>
              <p className="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">
                Direct SSRF-safe HTTP inspection to confirm if a broker profile has been de-indexed or deleted.
              </p>
            </div>

            <form onSubmit={handleLiveRescan} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
                  Target Page URL
                </label>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={rescanUrl}
                    onChange={(e) => setRescanUrl(e.target.value)}
                    placeholder="https://www.broker.com/people/j-doe/..."
                    className="input-field font-mono text-xs flex-1"
                    required
                  />
                  <button
                    type="submit"
                    disabled={rescanLoading || !currentIdentity}
                    className="btn btn-primary text-xs py-1.5 px-4 shrink-0 font-semibold"
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
                    ? "border-emerald-500/40 bg-emerald-950/20 text-emerald-400"
                    : rescanResult.status === "VERIFIED"
                    ? "border-rose-500/40 bg-rose-950/20 text-rose-400"
                    : "border-[var(--border-subtle)] bg-[var(--bg-app)] text-[var(--text-main)]"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold flex items-center gap-1.5">
                    {rescanResult.status === "VERIFIED_REMOVED" ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : (
                      <AlertTriangle className="w-4 h-4" />
                    )}
                    Outcome: {rescanResult.status}
                  </span>
                  {rescanResult.http_status_code && (
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
                      HTTP {rescanResult.http_status_code}
                    </span>
                  )}
                </div>
                <p className="text-[11px] leading-relaxed opacity-90">{rescanResult.evidence_notes}</p>
                <div className="text-[10px] text-[var(--text-dim)] font-mono">
                  Checked at: {new Date(rescanResult.verified_at).toLocaleString()}
                </div>
              </div>
            )}
          </div>

          {/* Local MBOX Email Archive Parser */}
          <div className="card p-5 space-y-4">
            <div className="border-b border-[var(--border-subtle)] pb-3">
              <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                <Mail className="w-4 h-4 text-[var(--pixel-cyan)]" /> Local Email Archive (.mbox) Parser
              </h3>
              <p className="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">
                Discovers marketing senders with list-unsubscribe headers and extracted telephone footers without sending data to any server.
              </p>
            </div>

            <form onSubmit={handleMboxUpload} className="space-y-3">
              <div className="border-2 border-dashed border-[var(--border-subtle)] rounded-lg p-5 text-center hover:border-[var(--pixel-green)] transition-colors bg-[var(--bg-app)]">
                <input
                  type="file"
                  accept=".mbox"
                  onChange={(e) => setMboxFile(e.target.files?.[0] || null)}
                  className="text-xs text-[var(--text-dim)] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[var(--bg-surface)] file:text-[var(--text-main)] hover:file:bg-[var(--border-subtle)]"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!mboxFile || mboxLoading}
                  className="btn btn-primary text-xs py-1.5 px-4 font-semibold"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>{mboxLoading ? "Analyzing MBOX Locally..." : "Analyze MBOX"}</span>
                </button>
              </div>
            </form>

            {mboxResult && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center gap-4 text-xs font-semibold">
                  <span className="text-[var(--pixel-cyan)]">
                    {mboxResult.subscriptions_detected} Commercial Subscriptions Found
                  </span>
                  <span className="text-[var(--pixel-green)]">
                    {mboxResult.phone_signatures_found} Phone Signatures
                  </span>
                </div>

                <div className="max-h-48 overflow-y-auto space-y-2">
                  {mboxResult.subscriptions.map((sub, i) => (
                    <div
                      key={i}
                      className="p-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="truncate">
                        <div className="font-semibold text-[var(--text-main)]">{sub.sender_domain}</div>
                        <div className="font-mono text-[10px] text-[var(--text-dim)] truncate">
                          {sub.sender_email}
                        </div>
                      </div>
                      {sub.unsubscribe_url && (
                        <a
                          href={sub.unsubscribe_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-secondary py-1 px-2 text-xs shrink-0"
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
          <div className="card p-5 space-y-4">
            <div className="border-b border-[var(--border-subtle)] pb-3">
              <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-[var(--pixel-green)]" /> Local SMS Backup Parser (.xml / .json / .csv)
              </h3>
              <p className="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">
                Scans SMS backups for 4-6 digit commercial shortcodes and STOP opt-out instructions.
              </p>
            </div>

            <form onSubmit={handleSmsUpload} className="space-y-3">
              <div className="border-2 border-dashed border-[var(--border-subtle)] rounded-lg p-5 text-center hover:border-[var(--pixel-green)] transition-colors bg-[var(--bg-app)]">
                <input
                  type="file"
                  accept=".xml,.json,.csv"
                  onChange={(e) => setSmsFile(e.target.files?.[0] || null)}
                  className="text-xs text-[var(--text-dim)] file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[var(--bg-surface)] file:text-[var(--text-main)] hover:file:bg-[var(--border-subtle)]"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!smsFile || smsLoading}
                  className="btn btn-primary text-xs py-1.5 px-4 font-semibold"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>{smsLoading ? "Scanning Messages..." : "Scan SMS Backup"}</span>
                </button>
              </div>
            </form>

            {smsResult && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center gap-4 text-xs font-semibold">
                  <span className="text-[var(--pixel-cyan)]">
                    {smsResult.shortcode_senders_found} Commercial Shortcodes
                  </span>
                  <span className="text-[var(--pixel-green)]">
                    {smsResult.stop_optouts_found} STOP Opt-Outs Identified
                  </span>
                </div>

                <div className="max-h-48 overflow-y-auto space-y-2">
                  {smsResult.shortcode_senders.map((sc, i) => (
                    <div
                      key={i}
                      className="p-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] flex items-center justify-between gap-2 text-xs"
                    >
                      <div>
                        <span className="font-mono font-bold text-[var(--pixel-cyan)] mr-2">
                          {sc.shortcode}
                        </span>
                        <span className="text-[var(--text-muted)] text-[11px]">
                          {sc.campaign_snippet || "Automated marketing sender"}
                        </span>
                      </div>
                      <span className="font-mono text-[9px] px-1.5 py-0.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-dim)] font-semibold">
                        REPLY STOP
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
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                <Lock className="w-4 h-4 text-[var(--pixel-green)]" /> Cryptographic Guarantees
              </h3>
              <span className="status-pill pill-pixel-green text-[9px]">ACTIVE</span>
            </div>

            <div className="space-y-3.5 text-xs text-[var(--text-muted)] leading-relaxed">
              <div className="p-3.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] space-y-2 font-mono text-[11px]">
                <div className="text-[var(--text-dim)] font-semibold uppercase tracking-wider text-[10px]">
                  Current Identity HMAC-SHA256:
                </div>
                <div className="text-[var(--pixel-green)] break-all select-all font-bold">
                  {currentIdentity?.hmac_id || "UNINITIALIZED"}
                </div>
                <div className="text-[var(--text-dim)] pt-1 font-semibold uppercase tracking-wider text-[10px]">
                  Masked Representation:
                </div>
                <div className="text-[var(--text-main)] font-semibold text-xs">
                  {currentIdentity?.masked_display || "—"}
                </div>
              </div>

              <ul className="list-disc list-inside space-y-2 text-xs text-[var(--text-dim)] leading-relaxed">
                <li>
                  <strong className="text-[var(--text-main)]">Keyed HMAC Protection:</strong> Phone numbers are keyed with a random 256-bit local secret (.numbershield_key) preventing rainbow table attacks.
                </li>
                <li>
                  <strong className="text-[var(--text-main)]">Zero Cloud Egress:</strong> All database operations, parsing, and regex dorking execute strictly on 127.0.0.1.
                </li>
                <li>
                  <strong className="text-[var(--text-main)]">Forensic Scrubbing:</strong> Application logs redact all E.164 and localized telephone representations before writing to disk.
                </li>
                <li>
                  <strong className="text-[var(--text-main)]">Cryptographic Erasure:</strong> Purging overwrites the SQLite database and secret key with random entropy bytes before unlinking.
                </li>
              </ul>
            </div>
          </div>

          {/* Purge Card */}
          <div className="card p-5 space-y-3 border-rose-900/40 bg-rose-950/10">
            <div className="flex items-center gap-2 text-rose-400 font-bold text-xs uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4" />
              <span>Zero-Trace Cryptographic Purge</span>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Permanently destroys all discovered exposures, remediation records, spam logs, and the 256-bit HMAC key. Irreversible once confirmed.
            </p>
            <button
              onClick={() => setShowPurgeConfirm(true)}
              className="btn btn-pixel danger w-full py-2.5 mt-1 text-xs font-semibold"
            >
              <Trash2 className="w-3.5 h-3.5" /> Launch Cryptographic Purge
            </button>
          </div>
        </div>
      </div>

      {/* Purge Confirmation Modal */}
      {showPurgeConfirm && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="card w-full max-w-md p-6 space-y-4 shadow-2xl border-rose-900/50">
            <div className="flex items-center gap-3 border-b border-[var(--border-subtle)] pb-3">
              <div className="w-10 h-10 rounded-lg bg-rose-950/40 border border-rose-500/30 flex items-center justify-center text-rose-400 shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--text-main)]">Confirm Zero-Trace Erasure</h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  This action will destroy all local data files.
                </p>
              </div>
            </div>

            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              This will overwrite the SQLite database and HMAC seed with random entropy, drop all tables, and reset your session.
              To confirm, type <span className="font-mono font-bold text-rose-400">PURGE</span> below:
            </p>

            <input
              type="text"
              value={purgeInput}
              onChange={(e) => setPurgeInput(e.target.value)}
              placeholder="Type PURGE to confirm"
              className="input-field font-mono text-sm border-rose-500/40 focus:border-rose-500"
              autoFocus
            />

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-subtle)]">
              <button
                type="button"
                onClick={() => {
                  setShowPurgeConfirm(false);
                  setPurgeInput("");
                }}
                className="btn btn-secondary py-2 px-3 text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecutePurge}
                disabled={purgeInput !== "PURGE" || purgeLoading}
                className="btn btn-pixel danger py-2 px-4 text-xs font-semibold"
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

export default VerificationAudit;
