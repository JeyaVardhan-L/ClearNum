import React, { useState, useEffect } from "react";
import {
  FileText,
  ExternalLink,
  Copy,
  Check,
  Download,
  AlertCircle,
  Clock,
  Mail,
  Phone,
  Search,
  Filter,
  BookOpen,
  Sparkles,
} from "lucide-react";
import type { RemediationSource, PhoneParseResult, GeneratedTemplate } from "../types";
import { getRemediationSources, generateLegalTemplate } from "../api";

interface RemediationHubProps {
  currentIdentity: PhoneParseResult | null;
  selectedSourceId?: string;
}

export const RemediationHub: React.FC<RemediationHubProps> = ({
  currentIdentity,
  selectedSourceId,
}) => {
  const [sources, setSources] = useState<RemediationSource[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [activeTab, setActiveTab] = useState<"directory" | "templates" | "searchengines">("directory");

  // Template state
  const [templateType, setTemplateType] = useState("CCPA_DELETE");
  const [recipientName, setRecipientName] = useState("Data Broker Privacy & Legal Team");
  const [targetUrl, setTargetUrl] = useState("");
  const [violatorNumber, setViolatorNumber] = useState("");
  const [generatedTemplate, setGeneratedTemplate] = useState<GeneratedTemplate | null>(null);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [copiedTemplate, setCopiedTemplate] = useState(false);
  const [copiedSubject, setCopiedSubject] = useState(false);
  const [copiedPreFill, setCopiedPreFill] = useState<string | null>(null);

  useEffect(() => {
    async function loadSources() {
      try {
        const data = await getRemediationSources();
        setSources(data);
      } catch (err) {
        console.error("Failed to load remediation sources", err);
      } finally {
        setLoadingSources(false);
      }
    }
    loadSources();
  }, []);

  const categories = ["ALL", ...Array.from(new Set(sources.map((s) => s.category)))];

  const filteredSources = sources.filter((s) => {
    const matchesCategory = categoryFilter === "ALL" || s.category === categoryFilter;
    const matchesSearch =
      searchQuery === "" ||
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.domains.some((d) => d.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCategory && matchesSearch;
  });

  const handleGenerateTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);
    setTemplateError(null);

    const phoneVal = currentIdentity?.e164 || currentIdentity?.masked_display || "+14155552671";
    const regionVal = currentIdentity?.region_code || "US";

    try {
      const res = await generateLegalTemplate(
        templateType,
        phoneVal,
        regionVal,
        recipientName,
        targetUrl,
        violatorNumber
      );
      setGeneratedTemplate(res);
    } catch (err: any) {
      setTemplateError(`Template generation failed: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = (text: string, type: "body" | "subject" | "field") => {
    navigator.clipboard.writeText(text);
    if (type === "body") {
      setCopiedTemplate(true);
      setTimeout(() => setCopiedTemplate(false), 2000);
    } else if (type === "subject") {
      setCopiedSubject(true);
      setTimeout(() => setCopiedSubject(false), 2000);
    }
  };

  const handleDownloadMarkdown = () => {
    if (!generatedTemplate) return;
    const content = `# ${generatedTemplate.title}\n\n**Subject:** ${generatedTemplate.subject_line}\n\n---\n\n${generatedTemplate.body_markdown}`;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${generatedTemplate.template_type.toLowerCase()}_notice.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="panel-card p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-sky-950/80 border border-sky-800 flex items-center justify-center text-sky-400">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100">Remediation Hub</h2>
            <p className="text-xs text-[var(--text-muted)]">
              Curated official opt-out procedures, statutory legal templates, and search removal workflows.
            </p>
          </div>
        </div>

        {/* Sub-tab Navigation */}
        <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800 self-start md:self-center">
          <button
            onClick={() => setActiveTab("directory")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "directory"
                ? "bg-slate-800 text-sky-400 shadow-sm border border-slate-700"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Broker Directory ({sources.length})
          </button>
          <button
            onClick={() => setActiveTab("templates")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "templates"
                ? "bg-slate-800 text-sky-400 shadow-sm border border-slate-700"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Legal Notice Generator
          </button>
          <button
            onClick={() => setActiveTab("searchengines")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "searchengines"
                ? "bg-slate-800 text-sky-400 shadow-sm border border-slate-700"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Search Engine De-Indexing
          </button>
        </div>
      </div>

      {/* Directory Tab */}
      {activeTab === "directory" && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 panel-card p-3">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search brokers (e.g., FastPeopleSearch, Whitepages, Radaris)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-field pl-8 py-1.5 text-xs"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="input-field py-1.5 text-xs min-w-[150px]"
              >
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c === "ALL" ? "All Categories" : c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Broker Cards Grid */}
          {loadingSources ? (
            <div className="text-center py-12 text-slate-400 text-xs">Loading broker registry...</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredSources.map((source) => (
                <div
                  key={source.source_id}
                  className={`panel-card p-4 space-y-3 flex flex-col justify-between ${
                    selectedSourceId === source.source_id ? "ring-2 ring-sky-500" : ""
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-bold text-sm text-slate-100">{source.name}</h3>
                        <span className="text-[10px] uppercase font-semibold text-sky-400 tracking-wider">
                          {source.category}
                        </span>
                      </div>
                      <span className="status-pill pill-neutral text-[10px] flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-400" />
                        {source.processing_time_estimate}
                      </span>
                    </div>

                    {/* Domains */}
                    <div className="flex flex-wrap gap-1">
                      {source.domains.map((d) => (
                        <span key={d} className="text-[10px] font-mono bg-slate-900 px-1.5 py-0.5 rounded text-slate-300 border border-slate-800">
                          {d}
                        </span>
                      ))}
                    </div>

                    {/* Badges for requirements and rights */}
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {source.requires_email_confirmation && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800 flex items-center gap-1">
                          <Mail className="w-2.5 h-2.5" /> Email Confirm Required
                        </span>
                      )}
                      {source.requires_phone_call && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-950/60 text-rose-300 border border-rose-800 flex items-center gap-1">
                          <Phone className="w-2.5 h-2.5" /> Phone Call Required
                        </span>
                      )}
                      {source.statutory_rights.map((r) => (
                        <span key={r} className="text-[10px] px-1.5 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800">
                          {r}
                        </span>
                      ))}
                    </div>

                    {/* Instructions */}
                    <div className="bg-slate-900/80 p-2.5 rounded border border-slate-800/80 text-xs text-slate-300 space-y-1">
                      <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">
                        Opt-Out Procedure:
                      </div>
                      <ol className="list-decimal list-inside space-y-0.5 text-[11px] leading-relaxed">
                        {source.instructions.map((step, idx) => (
                          <li key={idx} className="text-slate-300">
                            {step}
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between gap-2">
                    {/* Pre-fill clipboard helper */}
                    {currentIdentity && (
                      <button
                        onClick={() => {
                          const val = currentIdentity.e164 || currentIdentity.masked_display;
                          navigator.clipboard.writeText(val);
                          setCopiedPreFill(source.source_id);
                          setTimeout(() => setCopiedPreFill(null), 2000);
                        }}
                        className="btn-secondary text-[11px] py-1 px-2 text-slate-300"
                        title="Copy phone format to clipboard for pasting into broker opt-out form"
                      >
                        {copiedPreFill === source.source_id ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3 text-slate-400" />
                        )}
                        <span className="hidden sm:inline">Copy Phone</span>
                      </button>
                    )}

                    <a
                      href={source.official_removal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-primary text-xs py-1.5 px-3 flex-1 flex items-center justify-center gap-1.5"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Launch Opt-Out Form</span>
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Legal Templates Tab */}
      {activeTab === "templates" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Controls Column */}
          <div className="lg:col-span-5 space-y-4">
            <div className="panel-card p-5 space-y-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-sky-400" />
                  Statutory Notice Configuration
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-1">
                  Draft legally enforceable privacy rights demands citing specific consumer protection statutes.
                </p>
              </div>

              {templateError && (
                <div className="p-3 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
                  {templateError}
                </div>
              )}

              <form onSubmit={handleGenerateTemplate} className="space-y-3.5">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Statutory Framework / Legal Basis
                  </label>
                  <select
                    value={templateType}
                    onChange={(e) => setTemplateType(e.target.value)}
                    className="input-field text-xs"
                  >
                    <option value="CCPA_DELETE">CCPA / CPRA Deletion & Do-Not-Sell (California / US)</option>
                    <option value="GDPR_ERASURE">GDPR Article 17 Erasure & Art. 21 Objection (EU / UK)</option>
                    <option value="TCPA_COMPLAINT">TCPA Revocation & Internal DNC Demand (US FCC/FTC)</option>
                    <option value="TRAI_1909">TRAI 1909 Commercial Comm. Violation (India)</option>
                    <option value="MERCHANT_UNSUBSCRIBE">Merchant Marketing Opt-Out Notice</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Recipient Company / Privacy Officer
                  </label>
                  <input
                    type="text"
                    value={recipientName}
                    onChange={(e) => setRecipientName(e.target.value)}
                    className="input-field text-xs"
                    placeholder="e.g., FastPeopleSearch Legal Team, Acme Corp Marketing"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">
                    Specific Listing URL (Optional)
                  </label>
                  <input
                    type="text"
                    value={targetUrl}
                    onChange={(e) => setTargetUrl(e.target.value)}
                    className="input-field text-xs"
                    placeholder="https://www.broker.com/people/j-doe/..."
                  />
                </div>

                {(templateType === "TCPA_REVOCATION" || templateType === "TRAI_COMMERCIAL") && (
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">
                      Violator Calling / Sender Number (Optional)
                    </label>
                    <input
                      type="text"
                      value={violatorNumber}
                      onChange={(e) => setViolatorNumber(e.target.value)}
                      className="input-field text-xs font-mono"
                      placeholder="+1 (800) 555-0199"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isGenerating}
                  className="btn-primary w-full text-xs py-2 mt-2"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {isGenerating ? "Compiling Statutory Citations..." : "Generate Privacy Rights Notice"}
                </button>
              </form>
            </div>

            <div className="panel-card p-4 text-xs text-slate-400 space-y-2 border-slate-800">
              <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 text-sky-400" /> Statutory Deadlines
              </div>
              <ul className="list-disc list-inside space-y-1 text-[11px] leading-relaxed">
                <li><strong className="text-slate-300">CCPA/CPRA:</strong> 45 calendar days to confirm deletion (Civil Code § 1798.105).</li>
                <li><strong className="text-slate-300">GDPR:</strong> 1 month standard window under Article 12(3).</li>
                <li><strong className="text-slate-300">TCPA:</strong> Immediate internal DNC recording; up to $500–$1,500 statutory damages per willful violation.</li>
                <li><strong className="text-slate-300">TRAI 1909:</strong> Commercial sender blacklisting within 7 business days under TCCCPR 2018.</li>
              </ul>
            </div>
          </div>

          {/* Notice Preview Column */}
          <div className="lg:col-span-7">
            {generatedTemplate ? (
              <div className="panel-card p-5 space-y-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-400 bg-sky-950 px-2 py-0.5 rounded border border-sky-800">
                      {generatedTemplate.template_type}
                    </span>
                    <h3 className="text-sm font-bold text-slate-100 mt-1">{generatedTemplate.title}</h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => copyToClipboard(generatedTemplate.body_markdown, "body")}
                      className="btn-secondary text-xs py-1.5 px-3"
                    >
                      {copiedTemplate ? (
                        <>
                          <Check className="w-3 h-3 text-emerald-400" /> Copied Body
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" /> Copy Notice
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleDownloadMarkdown}
                      className="btn-secondary text-xs py-1.5 px-3"
                      title="Download as Markdown"
                    >
                      <Download className="w-3 h-3" /> .md
                    </button>
                  </div>
                </div>

                {/* Subject line box */}
                <div className="bg-slate-900 p-2.5 rounded border border-slate-800 flex items-center justify-between gap-2 text-xs">
                  <div className="truncate">
                    <span className="text-slate-400 font-semibold mr-2">Subject:</span>
                    <span className="text-slate-200 font-mono">{generatedTemplate.subject_line}</span>
                  </div>
                  <button
                    onClick={() => copyToClipboard(generatedTemplate.subject_line, "subject")}
                    className="text-slate-400 hover:text-slate-200 text-xs px-2 py-1 rounded bg-slate-800"
                    title="Copy subject line"
                  >
                    {copiedSubject ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>

                {/* Formatted body display */}
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-xs font-mono text-slate-200 whitespace-pre-wrap max-h-[500px] overflow-y-auto leading-relaxed">
                  {generatedTemplate.body_markdown}
                </div>
              </div>
            ) : (
              <div className="panel-card p-12 text-center space-y-3">
                <FileText className="w-10 h-10 text-slate-600 mx-auto" />
                <h4 className="text-sm font-semibold text-slate-300">No Notice Generated Yet</h4>
                <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
                  Configure the recipient parameters on the left and click "Generate Privacy Rights Notice" to preview the formal legal notice.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Search Engine De-Indexing Workflows Tab */}
      {activeTab === "searchengines" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Google Outdated Content Tool */}
          <div className="panel-card p-5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="status-pill pill-cyan text-[10px]">Google Search</span>
              <h3 className="font-bold text-sm text-slate-100">Outdated Content Removal</h3>
              <p className="text-xs text-[var(--text-muted)]">
                Use when a broker or site has already removed your phone number, but Google still displays your number in search snippet previews or cache.
              </p>
              <ol className="list-decimal list-inside text-xs text-slate-300 space-y-1.5 pt-2 bg-slate-900/60 p-3 rounded border border-slate-800">
                <li>Verify the live page no longer shows your phone number.</li>
                <li>Copy the exact URL of the search result.</li>
                <li>Submit the URL to Google Search Console Outdated Content Tool.</li>
                <li>Google re-crawls the page and purges snippet text within 24–48 hours.</li>
              </ol>
            </div>
            <a
              href="https://search.google.com/search-console/remove-outdated-content"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary text-xs py-2 px-3 w-full"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Launch Google Outdated Tool
            </a>
          </div>

          {/* Google PII Removal (Personal Contact Removal) */}
          <div className="panel-card p-5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="status-pill pill-emerald text-[10px]">Google Policy</span>
              <h3 className="font-bold text-sm text-slate-100">Personal Info (PII) Removal</h3>
              <p className="text-xs text-[var(--text-muted)]">
                Direct removal of search results that expose personal contact info, doxxing content, or phone numbers that pose predatory or harassment risks.
              </p>
              <ol className="list-decimal list-inside text-xs text-slate-300 space-y-1.5 pt-2 bg-slate-900/60 p-3 rounded border border-slate-800">
                <li>Open Google's "Results about you" or PII removal request form.</li>
                <li>Select "Personal info, like phone number or address".</li>
                <li>Provide the offending search URL and your contact details.</li>
                <li>Google review team evaluates and de-indexes the specific URL query globally.</li>
              </ol>
            </div>
            <a
              href="https://support.google.com/websearch/troubleshooter/3111061"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary text-xs py-2 px-3 w-full"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Launch Google PII Removal Form
            </a>
          </div>

          {/* Bing Content Removal */}
          <div className="panel-card p-5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="status-pill pill-amber text-[10px]">Microsoft Bing</span>
              <h3 className="font-bold text-sm text-slate-100">Bing Cache & Snippet Purge</h3>
              <p className="text-xs text-[var(--text-muted)]">
                Purges outdated cache versions and search previews across Bing and Yahoo Search for pages where your number was removed.
              </p>
              <ol className="list-decimal list-inside text-xs text-slate-300 space-y-1.5 pt-2 bg-slate-900/60 p-3 rounded border border-slate-800">
                <li>Sign in to Bing Webmaster Tools Content Removal.</li>
                <li>Enter the exact URL of the outdated page.</li>
                <li>Enter a keyword from the old cache (e.g. your phone number).</li>
                <li>Bing clears the cached snapshot within 24–72 hours.</li>
              </ol>
            </div>
            <a
              href="https://www.bing.com/webmasters/help/bing-content-removal-tool-cb6c11ec"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary text-xs py-2 px-3 w-full"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Launch Bing Removal Tool
            </a>
          </div>
        </div>
      )}
    </div>
  );
};
