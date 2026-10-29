import React, { useState, useEffect, useCallback } from "react";
import {
  PhoneOff,
  AlertTriangle,
  PlusCircle,
  ExternalLink,
  Layers,
  Globe,
  Radio,
} from "lucide-react";
import type {
  SpamIncident,
  CampaignGroup,
  ExposureMetrics,
  DNDCountryGuide,
  PhoneParseResult,
} from "../types";
import {
  recordSpam,
  getSpamIncidents,
  getMetrics,
  getDndGuides,
} from "../api";

interface PreventionViewProps {
  currentIdentity: PhoneParseResult | null;
}

export const PreventionView: React.FC<PreventionViewProps> = ({ currentIdentity }) => {
  const [incidents, setIncidents] = useState<SpamIncident[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignGroup[]>([]);
  const [metrics, setMetrics] = useState<ExposureMetrics | null>(null);
  const [dndGuides, setDndGuides] = useState<DNDCountryGuide[]>([]);

  // Form State
  const [senderNumber, setSenderNumber] = useState("");
  const [channel, setChannel] = useState("CALL");
  const [category, setCategory] = useState("ROBOCALL");
  const [spoofSuspected, setSpoofSuspected] = useState(true);
  const [campaignSummary, setCampaignSummary] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  // Active DND Guide tab
  const [selectedCountry, setSelectedCountry] = useState("US");

  const refreshData = useCallback(async () => {
    try {
      const dndRes = await getDndGuides();
      setDndGuides(dndRes.telecom_guides || []);

      if (currentIdentity?.hmac_id) {
        const [incRes, metricsRes] = await Promise.all([
          getSpamIncidents(currentIdentity.hmac_id),
          getMetrics(currentIdentity.hmac_id),
        ]);
        setIncidents(incRes.incidents || []);
        setCampaigns(incRes.campaigns || []);
        setMetrics(metricsRes);
      }
    } catch (err) {
      console.error("Failed to load prevention data", err);
    }
  }, [currentIdentity]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      if (active) {
        await refreshData();
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [refreshData]);

  const handleRecordSpam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentIdentity) {
      alert("Please initialize a phone number first.");
      return;
    }
    if (!senderNumber.trim()) {
      alert("Please provide the incoming spam caller number.");
      return;
    }

    setIsSubmitting(true);
    setSubmitMessage(null);
    try {
      await recordSpam(
        currentIdentity.hmac_id,
        senderNumber,
        channel,
        category,
        spoofSuspected,
        campaignSummary
      );
      setSenderNumber("");
      setCampaignSummary("");
      await refreshData();
      setSubmitMessage("Spam incident logged and correlated into campaign syndicates.");
      setTimeout(() => setSubmitMessage(null), 3500);
    } catch (err: any) {
      setSubmitMessage(`Failed to log incident: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeGuide = dndGuides.find((g) => g.country_code === selectedCountry) || dndGuides[0];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="card p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] flex items-center justify-center text-[var(--pixel-green)]">
            <PhoneOff className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-main)]">Spam Reduction & Telecom DND</h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Track unwanted calls, cluster telemarketing campaigns, and enforce statutory do not call rights.
            </p>
          </div>
        </div>

        {/* Live Metrics Counters */}
        {metrics && (
          <div className="flex items-center gap-3 self-start md:self-center flex-wrap">
            <div className="card p-3 text-center min-w-[90px]">
              <div className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider">
                Success Rate
              </div>
              <div className="text-sm font-bold text-[var(--pixel-green)] mt-0.5">
                {Math.round(metrics.removal_success_rate * 100)}%
              </div>
            </div>
            <div className="card p-3 text-center min-w-[90px]">
              <div className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider">
                Removed
              </div>
              <div className="text-sm font-bold text-[var(--pixel-cyan)] mt-0.5">
                {metrics.verified_removed} / {metrics.total_exposures}
              </div>
            </div>
            <div className="card p-3 text-center min-w-[90px]">
              <div className="text-[10px] font-semibold text-[var(--text-dim)] uppercase tracking-wider">
                Spam Incidents
              </div>
              <div className="text-sm font-bold text-[var(--pixel-red)] mt-0.5">
                {metrics.total_spam_incidents}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Log Incident & Correlated Campaigns */}
        <div className="lg:col-span-6 space-y-6">
          {/* Incident Logging Form */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                <PlusCircle className="w-4 h-4 text-[var(--pixel-green)]" /> Log Unwanted Communication
              </h3>
              <span className="text-[10px] font-mono text-[var(--text-dim)] uppercase">
                Feeds Syndicate Clustering
              </span>
            </div>

            {submitMessage && (
              <div className="p-3 rounded-md border border-[var(--pixel-cyan)]/40 bg-[var(--pixel-cyan-dim)] text-xs text-[var(--pixel-cyan)]">
                {submitMessage}
              </div>
            )}

            <form onSubmit={handleRecordSpam} className="space-y-3.5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
                    Caller / Sender Number
                  </label>
                  <input
                    type="text"
                    value={senderNumber}
                    onChange={(e) => setSenderNumber(e.target.value)}
                    placeholder="+1 (555) 019-2834 or shortcode"
                    className="input-field font-mono text-xs"
                    required
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
                    Channel
                  </label>
                  <select
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                    className="input-field text-xs"
                  >
                    <option value="CALL">Phone Call</option>
                    <option value="SMS">SMS / Text</option>
                    <option value="WHATSAPP">WhatsApp</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="input-field text-xs"
                  >
                    <option value="ROBOCALL">Automated Robocall</option>
                    <option value="DEBT_COLLECTION">Debt Collection</option>
                    <option value="HEALTH_INSURANCE">Health / Medicare Pitch</option>
                    <option value="CAR_WARRANTY">Auto Warranty Scam</option>
                    <option value="PHISHING">Smishing / Financial Phish</option>
                    <option value="TELEMARKETING">Generic Commercial Marketing</option>
                  </select>
                </div>

                <div className="flex items-center pt-4">
                  <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-[var(--text-muted)]">
                    <input
                      type="checkbox"
                      checked={spoofSuspected}
                      onChange={(e) => setSpoofSuspected(e.target.checked)}
                      className="w-4 h-4 accent-[var(--pixel-green)]"
                    />
                    <span>Suspected Spoofed Caller ID</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
                  Message Pitch / Voice Script Keywords
                </label>
                <input
                  type="text"
                  value={campaignSummary}
                  onChange={(e) => setCampaignSummary(e.target.value)}
                  placeholder="e.g. 'Important notice regarding your vehicle service contract...'"
                  className="input-field text-xs"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting || !currentIdentity}
                className="btn btn-primary w-full py-2.5 text-xs font-semibold"
              >
                {isSubmitting ? "Logging Incident..." : "Record Incident & Re-Cluster"}
              </button>
            </form>
          </div>

          {/* Clustered Campaigns Section */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                <Layers className="w-4 h-4 text-[var(--pixel-cyan)]" /> Correlated Spam Syndicates
              </h3>
              <span className="text-[10px] font-mono text-[var(--text-dim)] uppercase">
                {campaigns.length} Syndicates
              </span>
            </div>

            {campaigns.length === 0 ? (
              <div className="text-center py-6 text-xs text-[var(--text-dim)]">
                No campaign syndicates identified yet. Log spam calls or load demo data to analyze patterns.
              </div>
            ) : (
              <div className="space-y-3">
                {campaigns.map((camp, idx) => (
                  <div key={idx} className="card p-3.5 space-y-2 bg-[var(--bg-app)]">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="text-xs font-bold text-[var(--text-main)]">{camp.campaign_name}</h4>
                        <div className="font-mono text-[10px] text-[var(--text-dim)] mt-0.5">
                          {camp.incident_count} reported incident{camp.incident_count > 1 ? "s" : ""} across {camp.channels.join(", ")}
                        </div>
                      </div>
                      <span className="status-pill pill-pixel-red text-[9px]">
                        {Math.round(camp.spoof_percentage)}% Spoofed
                      </span>
                    </div>

                    {/* Sample Pitches */}
                    {camp.sample_pitches.length > 0 && (
                      <div className="text-xs text-[var(--text-muted)] bg-[var(--bg-surface)] p-2 rounded border border-[var(--border-subtle)] font-mono text-[10px]">
                        "{camp.sample_pitches[0]}"
                      </div>
                    )}

                    {/* Sender numbers summary */}
                    <div className="flex flex-wrap gap-1 pt-1">
                      {camp.sender_numbers.slice(0, 4).map((num, i) => (
                        <span
                          key={i}
                          className="font-mono text-[10px] bg-[var(--bg-surface)] text-[var(--text-muted)] px-2 py-0.5 rounded border border-[var(--border-subtle)]"
                        >
                          {num}
                        </span>
                      ))}
                      {camp.sender_numbers.length > 4 && (
                        <span className="text-[10px] text-[var(--text-dim)] self-center font-mono">
                          +{camp.sender_numbers.length - 4} more
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Individual Incidents */}
          {incidents.length > 0 && (
            <div className="card p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
                <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                  <Radio className="w-4 h-4 text-[var(--pixel-green)]" /> Recent Logged Incidents
                </h3>
                <span className="text-[10px] font-mono text-[var(--text-dim)] uppercase">
                  {incidents.length} Records
                </span>
              </div>
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {incidents.map((inc) => (
                  <div
                    key={inc.id}
                    className="p-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] flex items-start justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-[var(--text-main)]">
                          {inc.sender_number}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-dim)] font-mono">
                          {inc.channel}
                        </span>
                        {inc.spoof_suspected && (
                          <span className="status-pill pill-pixel-red text-[8px]">
                            SPOOFED
                          </span>
                        )}
                      </div>
                      {inc.campaign_summary && (
                        <p className="text-[11px] text-[var(--text-muted)] italic">
                          "{inc.campaign_summary}"
                        </p>
                      )}
                    </div>
                    <span className="text-[10px] text-[var(--text-dim)] whitespace-nowrap font-mono">
                      {new Date(inc.reported_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: National Telecom DND Guides */}
        <div className="lg:col-span-6 space-y-6">
          <div className="card p-5 space-y-4">
            <div className="border-b border-[var(--border-subtle)] pb-3">
              <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                <Globe className="w-4 h-4 text-[var(--pixel-cyan)]" /> National Do Not Call Registries
              </h3>
              <p className="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">
                Statutory consumer protection frameworks with direct registration links.
              </p>
            </div>

            {/* Country Selector Tabs */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {dndGuides.map((g) => (
                <button
                  key={g.country_code}
                  onClick={() => setSelectedCountry(g.country_code)}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                    selectedCountry === g.country_code
                      ? "bg-[var(--pixel-green)] text-[#022c22] font-bold shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                      : "text-[var(--text-muted)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:text-[var(--text-main)]"
                  }`}
                >
                  {g.country_name} ({g.country_code})
                </button>
              ))}
            </div>

            {/* Active Guide Card */}
            {activeGuide && (
              <div className="space-y-4 pt-2">
                <div className="card p-3.5 flex items-start justify-between gap-3 bg-[var(--bg-app)]">
                  <div>
                    <h4 className="text-sm font-bold text-[var(--text-main)]">
                      {activeGuide.registry_name}
                    </h4>
                    <p className="text-xs text-[var(--pixel-cyan)] mt-0.5">
                      {activeGuide.legal_basis}
                    </p>
                    <p className="font-mono text-[11px] text-[var(--text-dim)] mt-0.5">
                      {activeGuide.official_website}
                    </p>
                  </div>
                  <a
                    href={activeGuide.official_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-primary text-xs py-1.5 px-3 shrink-0"
                  >
                    <ExternalLink className="w-3.5 h-3.5" /> Official Portal
                  </a>
                </div>

                {/* Statutory Window */}
                <div className="flex items-center gap-2.5 text-xs bg-amber-950/20 p-3 rounded-lg border border-amber-500/30 text-amber-300">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                  <span>
                    <strong>Statutory Window:</strong> Telemarketers have{" "}
                    <strong>{activeGuide.statutory_window}</strong> to purge registered numbers from their outbound call lists.
                  </span>
                </div>

                {/* How to Register Steps */}
                <div className="space-y-2">
                  <div className="text-xs font-bold text-[var(--pixel-green)] uppercase tracking-wider">
                    How to Register Your Number:
                  </div>
                  <ol className="list-decimal list-inside space-y-1.5 text-xs text-[var(--text-muted)] leading-relaxed card p-3 bg-[var(--bg-app)]">
                    {activeGuide.how_to_register.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ol>
                </div>

                {/* Carrier 7726 SMS Forwarding */}
                {activeGuide.carrier_spam_forwarding_code && (
                  <div className="space-y-1.5 card p-3 bg-[var(--bg-app)] text-xs">
                    <div className="text-xs font-bold text-[var(--pixel-cyan)] flex items-center gap-1.5 uppercase tracking-wider">
                      <Radio className="w-3.5 h-3.5" /> Carrier SMS Forwarding (
                      <span className="font-mono text-emerald-400 font-bold">
                        {activeGuide.carrier_spam_forwarding_code}
                      </span>
                      )
                    </div>
                    <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                      {activeGuide.carrier_forwarding_instructions}
                    </p>
                  </div>
                )}

                {/* How to File Complaints */}
                <div className="space-y-2">
                  <div className="text-xs font-bold text-[var(--pixel-green)] uppercase tracking-wider">
                    How to File an Enforcement Complaint:
                  </div>
                  <ul className="list-disc list-inside space-y-1.5 text-xs text-[var(--text-muted)] leading-relaxed card p-3 bg-[var(--bg-app)]">
                    {activeGuide.how_to_file_complaint.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Recent Incident Log Table */}
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2">
              <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                Recent Incident Log ({incidents.length})
              </h3>
            </div>
            {incidents.length === 0 ? (
              <div className="text-center py-4 text-xs text-[var(--text-dim)]">
                No incidents reported yet.
              </div>
            ) : (
              <div className="max-h-60 overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Sender</th>
                      <th>Type</th>
                      <th>Campaign Pitch</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incidents.slice(0, 10).map((inc) => (
                      <tr key={inc.id}>
                        <td className="text-[11px] text-[var(--text-dim)] whitespace-nowrap font-mono">
                          {new Date(inc.reported_at).toLocaleDateString()}
                        </td>
                        <td className="font-mono text-xs text-[var(--text-main)] font-semibold">
                          {inc.sender_number}
                        </td>
                        <td>
                          <span className="text-[10px] px-1.5 py-0.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] font-mono text-[var(--text-muted)]">
                            {inc.channel}:{inc.category}
                          </span>
                        </td>
                        <td className="text-xs text-[var(--text-muted)] truncate max-w-[180px]">
                          {inc.campaign_summary || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PreventionView;
