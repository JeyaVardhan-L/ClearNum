import React from "react";
import { Shield, Trash2, Play, Lock } from "lucide-react";
import type { PhoneParseResult } from "../types";

interface NavbarProps {
  currentIdentity: PhoneParseResult | null;
  onLoadDemo: () => void;
  onPurge: () => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentIdentity,
  onLoadDemo,
  onPurge,
  activeTab,
  setActiveTab,
}) => {
  return (
    <header className="border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] sticky top-0 z-40">
      <div className="container-shell flex items-center justify-between h-16">
        {/* Brand */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab("scan")}>
          <div className="w-9 h-9 rounded-lg bg-sky-950/80 border border-sky-800 flex items-center justify-center text-sky-400 shadow-sm">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight text-slate-100">NumberShield</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800">
                v1.0 Local
              </span>
            </div>
            <p className="text-xs text-[var(--text-dim)]">Open-Source Phone Privacy & Remediation</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 bg-[var(--bg-app)] p-1 rounded-lg border border-[var(--border-subtle)]">
          {[
            { id: "scan", label: "Scan & Dorks" },
            { id: "exposures", label: "Exposures" },
            { id: "remediation", label: "Remediation Hub" },
            { id: "prevention", label: "Spam & DND" },
            { id: "audit", label: "Verify & Audit" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === tab.id
                  ? "bg-[var(--bg-elevated)] text-sky-400 shadow-sm border border-[var(--border-strong)]"
                  : "text-[var(--text-muted)] hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Identity & Actions */}
        <div className="flex items-center gap-3">
          {currentIdentity ? (
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-md bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-mono text-slate-200">{currentIdentity.masked_display}</span>
              <span className="text-[10px] text-slate-400 bg-slate-800 px-1 rounded">HMAC</span>
            </div>
          ) : null}

          <button
            onClick={onLoadDemo}
            className="btn-secondary text-xs py-1.5 px-3"
            title="Load synthetic scenario with realistic data brokers and spam reports"
          >
            <Play className="w-3.5 h-3.5 text-sky-400" />
            <span className="hidden sm:inline">Load Demo</span>
          </button>

          <button
            onClick={onPurge}
            className="btn-danger text-xs py-1.5 px-2.5"
            title="Zero-trace cryptographic wipe of all local records"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Purge</span>
          </button>
        </div>
      </div>

      {/* Mobile Sub-Navigation Bar */}
      <div className="flex md:hidden border-t border-[var(--border-subtle)] px-3 py-2 overflow-x-auto gap-1.5 bg-[var(--bg-app)]">
        {[
          { id: "scan", label: "Scan & Dorks" },
          { id: "exposures", label: "Exposures" },
          { id: "remediation", label: "Remediation Hub" },
          { id: "prevention", label: "Spam & DND" },
          { id: "audit", label: "Verify & Audit" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-2.5 py-1 rounded text-xs font-semibold whitespace-nowrap transition-all ${
              activeTab === tab.id
                ? "bg-[var(--bg-elevated)] text-sky-400 border border-[var(--border-strong)]"
                : "text-[var(--text-muted)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </header>
  );
};
