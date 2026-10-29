import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { ScanConsole } from "./components/ScanConsole";
import { ExposuresView } from "./components/ExposuresView";
import { RemediationHub } from "./components/RemediationHub";
import { PreventionView } from "./components/PreventionView";
import { VerificationAudit } from "./components/VerificationAudit";
import type {
  PhoneParseResult,
  DiscoveredExposure,
} from "./types";
import {
  parsePhone,
  getExposures,
  loadSyntheticDemo,
  purgeData,
} from "./api";
import { CheckCircle2, AlertCircle, Info } from "lucide-react";

export function App() {
  const [activeTab, setActiveTab] = useState<string>("scan");
  const [currentIdentity, setCurrentIdentity] = useState<PhoneParseResult | null>(null);
  const [exposures, setExposures] = useState<DiscoveredExposure[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<{ message: string; type: "success" | "info" | "error" } | null>(null);

  // Initialize with default demo parse on mount
  useEffect(() => {
    async function initDefault() {
      try {
        const parsed = await parsePhone("+918106833178", "IN");
        setCurrentIdentity(parsed);
        const expList = await getExposures(parsed.hmac_id).catch(() => []);
        setExposures(expList);
      } catch {
        // Backend may be starting up
      }
    }
    initDefault();
  }, []);

  const showToast = (message: string, type: "success" | "info" | "error" = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const refreshData = async (identity = currentIdentity) => {
    if (!identity?.hmac_id) return;
    try {
      const expList = await getExposures(identity.hmac_id);
      setExposures(expList);
    } catch (err) {
      console.error("Failed to refresh data", err);
    }
  };

  const handleScanComplete = async (identity: PhoneParseResult) => {
    setCurrentIdentity(identity);
    await refreshData(identity);
    showToast(`Scan complete for ${identity.masked_display}. Discovered exposures loaded.`, "success");
    setActiveTab("exposures");
  };

  const handleLoadDemo = async () => {
    try {
      await loadSyntheticDemo();
      const parsed = await parsePhone("+14155552671", "US");
      setCurrentIdentity(parsed);
      await refreshData(parsed);
      showToast(
        `Synthetic scenario loaded: 5 realistic data broker exposures and spam syndicates initialized.`,
        "success"
      );
      setActiveTab("exposures");
    } catch (err: any) {
      showToast(`Failed to load demo scenario: ${err.message}`, "error");
    }
  };

  const handlePurge = async () => {
    const input = window.prompt("Type PURGE to permanently destroy all local data records and HMAC key:");
    if (input !== "PURGE") {
      if (input !== null) {
        showToast("Purge cancelled: confirmation code 'PURGE' was not entered.", "info");
      }
      return;
    }
    try {
      const res = await purgeData("PURGE");
      setCurrentIdentity(null);
      setExposures([]);
      showToast(res.message || "All local records and HMAC keys have been erased.", "info");
      setActiveTab("scan");
    } catch (err: any) {
      showToast(`Purge failed: ${err.message}`, "error");
    }
  };

  const handleOpenRemediation = (sourceId?: string) => {
    setSelectedSourceId(sourceId);
    setActiveTab("remediation");
  };

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-app)] text-[var(--text-main)]">
      {/* Universal Sticky Top Navbar */}
      <Navbar
        currentIdentity={currentIdentity}
        onLoadDemo={handleLoadDemo}
        onPurge={handlePurge}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      {/* Toast Alert */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2.5 px-4 py-3 rounded-lg border shadow-xl text-xs font-semibold backdrop-blur-md transition-all animate-bounce bg-slate-900/90 text-slate-100 border-slate-700">
          {toast.type === "success" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
          {toast.type === "error" && <AlertCircle className="w-4 h-4 text-rose-400" />}
          {toast.type === "info" && <Info className="w-4 h-4 text-sky-400" />}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Main Workspace */}
      <main className="container-shell flex-1 py-6">
        {activeTab === "scan" && (
          <ScanConsole
            currentIdentity={currentIdentity}
            onScanComplete={handleScanComplete}
            onOpenRemediation={() => setActiveTab("remediation")}
          />
        )}

        {activeTab === "exposures" && (
          <ExposuresView
            exposures={exposures}
            currentIdentity={currentIdentity}
            onRefresh={() => refreshData()}
            onOpenRemediation={handleOpenRemediation}
            onNavigateToScan={() => setActiveTab("scan")}
            onLoadDemo={handleLoadDemo}
          />
        )}

        {activeTab === "remediation" && (
          <RemediationHub
            currentIdentity={currentIdentity}
            selectedSourceId={selectedSourceId}
          />
        )}

        {activeTab === "prevention" && (
          <PreventionView currentIdentity={currentIdentity} />
        )}

        {activeTab === "audit" && (
          <VerificationAudit
            currentIdentity={currentIdentity}
            onPurgeComplete={() => {
              setCurrentIdentity(null);
              setExposures([]);
              showToast("Zero-trace purge executed successfully.", "info");
              setActiveTab("scan");
            }}
          />
        )}
      </main>

      {/* Calm Localhost Footer */}
      <footer className="border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] py-4 text-xs text-[var(--text-dim)]">
        <div className="container-shell flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
            <span>Localhost Server Active: <code className="font-mono text-slate-300">127.0.0.1:8765</code></span>
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Zero Remote Telemetry</span>
            <span>•</span>
            <span>256-Bit Keyed HMAC</span>
            <span>•</span>
            <span>Apache 2.0 Open Source</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
