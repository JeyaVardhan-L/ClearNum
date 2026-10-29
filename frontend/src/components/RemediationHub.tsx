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

  const copyToClipboard = (text: string, type: "body" | "subject") => {
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
    const content = `# ${generatedTemplate.title}\n\n**SUBJECT:** ${generatedTemplate.subject_line}\n\n---\n\n${generatedTemplate.body_markdown}`;
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
      <div className="card p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] flex items-center justify-center text-[var(--pixel-green)]">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-main)]">Remediation Hub</h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Curated official opt-out procedures, statutory legal templates, and search removal workflows.
            </p>
          </div>
        </div>

        {/* Sub-tab Navigation */}
        <div className="flex items-center gap-1 bg-[var(--bg-app)] p-1 rounded-lg border border-[var(--border-subtle)] self-start md:self-center">
          <button
            onClick={() => setActiveTab("directory")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "directory"
                ? "bg-[var(--pixel-green)] text-[#022c22] font-bold shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                : "text-[var(--text-muted)] hover:text-[var(--text-main)]"
            }`}
          >
            Broker Directory ({sources.length})
          </button>
          <button
            onClick={() => setActiveTab("templates")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "templates"
                ? "bg-[var(--pixel-green)] text-[#022c22] font-bold shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                : "text-[var(--text-muted)] hover:text-[var(--text-main)]"
            }`}
          >
            Legal Notice Generator
          </button>
          <button
            onClick={() => setActiveTab("searchengines")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "searchengines"
                ? "bg-[var(--pixel-green)] text-[#022c22] font-bold shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                : "text-[var(--text-muted)] hover:text-[var(--text-main)]"
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
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 card p-3">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 text-[var(--text-dim)] absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search brokers (e.g. FastPeopleSearch, Whitepages, Radaris)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-field pl-8 py-1.5 text-xs"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-[var(--text-dim)]" />
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
            <div className="text-center py-12 text-xs text-[var(--text-dim)]">
              Loading broker registry...
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredSources.map((source) => (
                <div
                  key={source.source_id}
                  className={`card p-4 space-y-3 flex flex-col justify-between ${
                    selectedSourceId === source.source_id ? "border-[var(--pixel-green)]" : ""
                  }`}
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-bold text-[var(--text-main)]">{source.name}</h3>
                        <span className="text-[11px] text-[var(--pixel-cyan)] font-medium">
                          {source.category}
                        </span>
                      </div>
                      <span className="status-pill pill-pixel-purple text-[9px] flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {source.processing_time_estimate}
                      </span>
                    </div>

                    {/* Domains */}
                    <div className="flex flex-wrap gap-1">
                      {source.domains.map((d) => (
                        <span
                          key={d}
                          className="font-mono text-[10px] bg-[var(--bg-app)] px-2 py-0.5 rounded border border-[var(--border-subtle)] text-[var(--text-muted)]"
                        >
                          {d}
                        </span>
                      ))}
                    </div>

                    {/* Badges for requirements and rights */}
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {source.requires_email_confirmation && (
                        <span className="status-pill pill-pixel-yellow text-[9px]">
                          <Mail className="w-2.5 h-2.5" /> Email Confirm Required
                        </span>
                      )}
                      {source.requires_phone_call && (
                        <span className="status-pill pill-pixel-red text-[9px]">
                          <Phone className="w-2.5 h-2.5" /> Phone Call Required
                        </span>
                      )}
                      {source.statutory_rights.map((r) => (
                        <span key={r} className="status-pill pill-pixel-cyan text-[9px]">
                          {r}
                        </span>
                      ))}
                    </div>

                    {/* Instructions */}
                    <div className="bg-[var(--bg-app)] p-3 rounded-lg border border-[var(--border-subtle)] text-xs space-y-1.5">
                      <div className="text-[10px] font-bold text-[var(--pixel-green)] uppercase tracking-wider">
                        Opt-Out Procedure:
                      </div>
                      <ol className="list-decimal list-inside space-y-1 text-[11px] text-[var(--text-muted)] leading-relaxed">
                        {source.instructions.map((step, idx) => (
                          <li key={idx}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="pt-2.5 border-t border-[var(--border-subtle)] flex items-center justify-between gap-2">
                    {/* Pre-fill clipboard helper */}
                    {currentIdentity && (
                      <button
                        onClick={() => {
                          const val = currentIdentity.e164 || currentIdentity.masked_display;
                          navigator.clipboard.writeText(val);
                          setCopiedPreFill(source.source_id);
                          setTimeout(() => setCopiedPreFill(null), 2000);
                        }}
                        className="btn btn-secondary text-xs py-1.5 px-2.5"
                        title="Copy phone format to clipboard for pasting into broker opt-out form"
                      >
                        {copiedPreFill === source.source_id ? (
                          <Check className="w-3 h-3 text-[var(--pixel-green)]" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        <span className="hidden sm:inline">Copy Phone</span>
                      </button>
                    )}

                    <a
                      href={source.official_removal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-primary text-xs py-1.5 px-3 flex-1 flex items-center justify-center gap-1.5"
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
            <div className="card p-5 space-y-4">
              <div>
                <h3 className="text-sm font-bold text-[var(--text-main)] flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[var(--pixel-green)]" />
                  Statutory Notice Configuration
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-1 leading-relaxed">
                  Draft legally enforceable privacy rights demands citing specific consumer protection statutes.
                </p>
              </div>

              {templateError && (
                <div className="p-3 rounded-md border border-rose-500/40 bg-rose-950/20 text-xs text-rose-400">
                  {templateError}
                </div>
              )}

              <form onSubmit={handleGenerateTemplate} className="space-y-3.5">
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
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
                  <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
                    Recipient Company / Privacy Officer
                  </label>
                  <input
                    type="text"
                    value={recipientName}
                    onChange={(e) => setRecipientName(e.target.value)}
                    className="input-field text-xs"
                    placeholder="e.g. FastPeopleSearch Legal Team, Acme Corp Marketing"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
                    Specific Listing URL (Optional)
                  </label>
                  <input
                    type="text"
                    value={targetUrl}
                    onChange={(e) => setTargetUrl(e.target.value)}
                    className="input-field text-xs font-mono"
                    placeholder="https://www.broker.com/people/j-doe/..."
                  />
                </div>

                {(templateType === "TCPA_REVOCATION" || templateType === "TRAI_COMMERCIAL") && (
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] block mb-1 uppercase tracking-wider">
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
                  className="btn btn-primary w-full py-2.5 mt-2 text-xs"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>
                    {isGenerating ? "Compiling Statutory Citations..." : "Generate Privacy Rights Notice"}
                  </span>
                </button>
              </form>
            </div>

            <div className="card p-4 space-y-2 border-slate-800 bg-[#0c1424]">
              <div className="text-xs font-bold text-amber-400 flex items-center gap-1.5 uppercase tracking-wider">
                <AlertCircle className="w-3.5 h-3.5" /> Statutory Deadlines
              </div>
              <ul className="list-disc list-inside space-y-1.5 text-xs text-[var(--text-muted)] leading-relaxed">
                <li>
                  <strong className="text-[var(--text-main)]">CCPA/CPRA:</strong> 45 calendar days to confirm deletion (Civil Code § 1798.105).
                </li>
                <li>
                  <strong className="text-[var(--text-main)]">GDPR:</strong> 1 month standard window under Article 12(3).
                </li>
                <li>
                  <strong className="text-[var(--text-main)]">TCPA:</strong> Immediate internal DNC recording; up to $500–$1,500 statutory damages per willful violation.
                </li>
                <li>
                  <strong className="text-[var(--text-main)]">TRAI 1909:</strong> Commercial sender blacklisting within 7 business days under TCCCPR 2018.
                </li>
              </ul>
            </div>
          </div>

          {/* Notice Preview Column */}
          <div className="lg:col-span-7">
            {generatedTemplate ? (
              <div className="card p-5 space-y-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-3">
                  <div>
                    <span className="kicker-tag text-[9px]">{generatedTemplate.template_type}</span>
                    <h3 className="text-sm font-bold text-[var(--text-main)] mt-1">
                      {generatedTemplate.title}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => copyToClipboard(generatedTemplate.body_markdown, "body")}
                      className="btn btn-secondary text-xs py-1.5 px-3"
                    >
                      {copiedTemplate ? (
                        <>
                          <Check className="w-3 h-3 text-[var(--pixel-green)]" />
                          <span>Copied Body</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy Notice</span>
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleDownloadMarkdown}
                      className="btn btn-secondary text-xs py-1.5 px-3"
                      title="Download as Markdown"
                    >
                      <Download className="w-3 h-3" />
                      <span>.md</span>
                    </button>
                  </div>
                </div>

                {/* Subject line box */}
                <div className="bg-[var(--bg-app)] p-3 rounded-lg border border-[var(--border-subtle)] flex items-center justify-between gap-2 text-xs">
                  <div className="truncate">
                    <span className="text-[var(--text-dim)] font-bold mr-2 uppercase tracking-wider">
                      Subject:
                    </span>
                    <span className="font-mono text-[var(--text-main)]">
                      {generatedTemplate.subject_line}
                    </span>
                  </div>
                  <button
                    onClick={() => copyToClipboard(generatedTemplate.subject_line, "subject")}
                    className="text-[var(--text-dim)] hover:text-[var(--pixel-green)] text-xs px-2 py-1 rounded bg-[var(--bg-surface)]"
                    title="Copy subject line"
                  >
                    {copiedSubject ? (
                      <Check className="w-3 h-3 text-[var(--pixel-green)]" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>

                {/* Formatted body display */}
                <div className="bg-[var(--bg-app)] p-4 rounded-lg border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-main)] whitespace-pre-wrap max-h-[500px] overflow-y-auto leading-relaxed">
                  {generatedTemplate.body_markdown}
                </div>
              </div>
            ) : (
              <div className="card p-12 text-center space-y-3">
                <FileText className="w-10 h-10 text-[var(--text-dim)] mx-auto" />
                <h4 className="text-sm font-bold text-[var(--text-main)]">NO NOTICE GENERATED YET</h4>
                <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto leading-relaxed">
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
          <div className="card p-5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="status-pill pill-pixel-cyan text-[9px]">Google Search</span>
              <h3 className="text-sm font-bold text-[var(--text-main)]">Outdated Content Removal</h3>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Use when a broker or site has already removed your phone number, but Google still displays your number in search snippet previews or cache.
              </p>
              <ol className="list-decimal list-inside text-xs text-[var(--text-muted)] space-y-1 pt-2 bg-[var(--bg-app)] p-3 rounded-lg border border-[var(--border-subtle)] leading-relaxed">
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
              className="btn btn-primary text-xs py-2 px-3 w-full"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Launch Google Outdated Tool
            </a>
          </div>

          {/* Google PII Removal (Personal Contact Removal) */}
          <div className="card p-5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="status-pill pill-pixel-green text-[9px]">Google Policy</span>
              <h3 className="text-sm font-bold text-[var(--text-main)]">Personal Info (PII) Removal</h3>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Direct removal of search results that expose personal contact info, doxxing content, or phone numbers that pose predatory or harassment risks.
              </p>
              <ol className="list-decimal list-inside text-xs text-[var(--text-muted)] space-y-1 pt-2 bg-[var(--bg-app)] p-3 rounded-lg border border-[var(--border-subtle)] leading-relaxed">
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
              className="btn btn-primary text-xs py-2 px-3 w-full"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Launch Google PII Removal Form
            </a>
          </div>

          {/* Bing Content Removal */}
          <div className="card p-5 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="status-pill pill-pixel-yellow text-[9px]">Microsoft Bing</span>
              <h3 className="text-sm font-bold text-[var(--text-main)]">Bing Cache & Snippet Purge</h3>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Purges outdated cache versions and search previews across Bing and Yahoo Search for pages where your number was removed.
              </p>
              <ol className="list-decimal list-inside text-xs text-[var(--text-muted)] space-y-1 pt-2 bg-[var(--bg-app)] p-3 rounded-lg border border-[var(--border-subtle)] leading-relaxed">
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
              className="btn btn-primary text-xs py-2 px-3 w-full"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Launch Bing Removal Tool
            </a>
          </div>
        </div>
      )}
    </div>
  );
};

export default RemediationHub;
