import React, { useState, useEffect } from "react";
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

  useEffect(() => {
    refreshData();
  }, [currentIdentity]);

  const refreshData = async () => {
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
  };

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
      <div className="panel-card p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-sky-950/80 border border-sky-800 flex items-center justify-center text-sky-400">
            <PhoneOff className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100">Spam Reduction & Telecom DND</h2>
            <p className="text-xs text-[var(--text-muted)]">
              Track unwanted calls, cluster telemarketing campaigns, and enforce statutory Do Not Call rights.
            </p>
          </div>
        </div>

        {/* Live Metrics Counters */}
        {metrics && (
          <div className="flex items-center gap-3 self-start md:self-center">
            <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-center">
              <div className="text-[10px] uppercase font-semibold text-slate-400">Success Rate</div>
              <div className="text-base font-bold font-mono text-emerald-400">
                {Math.round(metrics.removal_success_rate * 100)}%
              </div>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-center">
              <div className="text-[10px] uppercase font-semibold text-slate-400">Removed</div>
              <div className="text-base font-bold font-mono text-sky-400">
                {metrics.verified_removed} / {metrics.total_exposures}
              </div>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-center">
              <div className="text-[10px] uppercase font-semibold text-slate-400">Spam Incidents</div>
              <div className="text-base font-bold font-mono text-rose-400">
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
          <div className="panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <PlusCircle className="w-4 h-4 text-sky-400" /> Log Unwanted Communication
              </h3>
              <span className="text-[10px] text-slate-400">Feeds syndicate clustering</span>
            </div>

            {submitMessage && (
              <div className="p-2.5 rounded bg-sky-950/60 border border-sky-800 text-sky-300 text-xs">
                {submitMessage}
              </div>
            )}

            <form onSubmit={handleRecordSpam} className="space-y-3.5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Caller / Sender Number
                  </label>
                  <input
                    type="text"
                    value={senderNumber}
                    onChange={(e) => setSenderNumber(e.target.value)}
                    placeholder="+1 (555) 019-2834 or shortcode"
                    className="input-field text-xs font-mono"
                    required
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Channel</label>
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
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Category</label>
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

                <div className="flex items-center pt-5">
                  <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={spoofSuspected}
                      onChange={(e) => setSpoofSuspected(e.target.checked)}
                      className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0"
                    />
                    <span>Suspected Spoofed Caller ID</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  Message Pitch / Voice Script Keywords
                </label>
                <input
                  type="text"
                  value={campaignSummary}
                  onChange={(e) => setCampaignSummary(e.target.value)}
                  placeholder="e.g., 'Important notice regarding your vehicle service contract...'"
                  className="input-field text-xs"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting || !currentIdentity}
                className="btn-primary w-full text-xs py-2"
              >
                {isSubmitting ? "Logging Incident..." : "Record Incident & Re-Cluster"}
              </button>
            </form>
          </div>

          {/* Clustered Campaigns Section */}
          <div className="panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Layers className="w-4 h-4 text-sky-400" /> Correlated Spam Syndicates
              </h3>
              <span className="text-[10px] text-slate-400">{campaigns.length} Syndicates</span>
            </div>

            {campaigns.length === 0 ? (
              <div className="text-center py-6 text-slate-400 text-xs">
                No campaign syndicates identified yet. Log spam calls or load demo data to analyze patterns.
              </div>
            ) : (
              <div className="space-y-3">
                {campaigns.map((camp, idx) => (
                  <div key={idx} className="bg-slate-900/80 p-3.5 rounded-lg border border-slate-800 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="font-semibold text-xs text-slate-100">{camp.campaign_name}</h4>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          {camp.incident_count} reported incident{camp.incident_count > 1 ? "s" : ""} across {camp.channels.join(", ")}
                        </div>
                      </div>
                      <span className="status-pill pill-rose text-[10px]">
                        {Math.round(camp.spoof_percentage)}% Spoofed
                      </span>
                    </div>

                    {/* Sample Pitches */}
                    {camp.sample_pitches.length > 0 && (
                      <div className="text-[11px] font-mono text-slate-300 bg-slate-950 p-2 rounded border border-slate-800/80">
                        "{camp.sample_pitches[0]}"
                      </div>
                    )}

                    {/* Sender numbers summary */}
                    <div className="flex flex-wrap gap-1 pt-1">
                      {camp.sender_numbers.slice(0, 4).map((num, i) => (
                        <span key={i} className="text-[10px] font-mono bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
                          {num}
                        </span>
                      ))}
                      {camp.sender_numbers.length > 4 && (
                        <span className="text-[10px] text-slate-400 self-center">
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
            <div className="panel-card p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <Radio className="w-4 h-4 text-rose-400" /> Recent Logged Incidents
                </h3>
                <span className="text-[10px] text-slate-400">{incidents.length} Records</span>
              </div>
              <div className="space-y-2.5 max-h-80 overflow-y-auto">
                {incidents.map((inc) => (
                  <div key={inc.id} className="p-2.5 rounded bg-slate-900 border border-slate-800 flex items-start justify-between gap-3 text-xs">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-slate-200">{inc.sender_number}</span>
                        <span className="text-[10px] font-semibold text-slate-400 px-1.5 py-0.5 rounded bg-slate-800">
                          {inc.channel}
                        </span>
                        {inc.spoof_suspected && (
                          <span className="text-[9px] font-semibold text-rose-400 px-1.5 py-0.2 rounded bg-rose-950/60 border border-rose-800/80">
                            Spoofed
                          </span>
                        )}
                      </div>
                      {inc.campaign_summary && (
                        <p className="text-[11px] text-slate-400 italic">"{inc.campaign_summary}"</p>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-500 whitespace-nowrap">
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
          <div className="panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-sky-400" /> National Do Not Call Registries
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Statutory consumer protection frameworks with direct registration links.
                </p>
              </div>
            </div>

            {/* Country Selector Tabs */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {dndGuides.map((g) => (
                <button
                  key={g.country_code}
                  onClick={() => setSelectedCountry(g.country_code)}
                  className={`px-3 py-1.5 rounded text-xs font-semibold transition-all ${
                    selectedCountry === g.country_code
                      ? "bg-sky-950 text-sky-400 border border-sky-800 shadow-sm"
                      : "bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800"
                  }`}
                >
                  {g.country_name} ({g.country_code})
                </button>
              ))}
            </div>

            {/* Active Guide Card */}
            {activeGuide && (
              <div className="space-y-4 pt-2">
                <div className="flex items-start justify-between gap-3 bg-slate-900/60 p-3 rounded border border-slate-800">
                  <div>
                    <h4 className="text-sm font-bold text-slate-100">{activeGuide.registry_name}</h4>
                    <p className="text-xs text-sky-400 font-mono mt-0.5">{activeGuide.legal_basis}</p>
                  </div>
                  <a
                    href={activeGuide.official_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary text-xs py-1.5 px-3 shrink-0"
                  >
                    <ExternalLink className="w-3.5 h-3.5" /> Official Portal
                  </a>
                </div>

                {/* Statutory Window */}
                <div className="flex items-center gap-2 text-xs bg-amber-950/40 p-2.5 rounded border border-amber-800 text-amber-300">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                  <span>
                    <strong>Statutory Window:</strong> Telemarketers have{" "}
                    <strong>{activeGuide.statutory_window}</strong> to purge registered numbers from their outbound call lists.
                  </span>
                </div>

                {/* How to Register Steps */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-200 uppercase tracking-wide">
                    How to Register Your Number:
                  </div>
                  <ol className="list-decimal list-inside space-y-1 text-xs text-slate-300 leading-relaxed bg-slate-900/40 p-3 rounded border border-slate-800">
                    {activeGuide.how_to_register.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ol>
                </div>

                {/* Carrier 7726 SMS Forwarding */}
                {activeGuide.carrier_spam_forwarding_code && (
                  <div className="space-y-1.5 bg-slate-900/80 p-3 rounded border border-slate-800 text-xs">
                    <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                      <Radio className="w-3.5 h-3.5 text-sky-400" /> Carrier SMS Forwarding (
                      <span className="font-mono text-sky-400">{activeGuide.carrier_spam_forwarding_code}</span>)
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      {activeGuide.carrier_forwarding_instructions}
                    </p>
                  </div>
                )}

                {/* How to File Complaints */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-200 uppercase tracking-wide">
                    How to File an Enforcement Complaint:
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-xs text-slate-300 leading-relaxed bg-slate-900/40 p-3 rounded border border-slate-800">
                    {activeGuide.how_to_file_complaint.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Recent Incident Log Table */}
          <div className="panel-card p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Recent Incident Log ({incidents.length})
              </h3>
            </div>
            {incidents.length === 0 ? (
              <div className="text-center py-4 text-xs text-slate-400">
                No incidents reported yet.
              </div>
            ) : (
              <div className="max-h-60 overflow-y-auto">
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
                        <td className="text-[11px] text-slate-400 whitespace-nowrap">
                          {new Date(inc.reported_at).toLocaleDateString()}
                        </td>
                        <td className="font-mono text-xs text-slate-200">{inc.sender_number}</td>
                        <td>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                            {inc.channel}:{inc.category}
                          </span>
                        </td>
                        <td className="text-xs text-slate-300 truncate max-w-[180px]">
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
