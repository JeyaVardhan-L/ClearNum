import React from "react";
import { Shield, Trash2, Play, Lock, Zap, Bug } from "lucide-react";
import type { PhoneParseResult } from "../types";

interface NavbarProps {
  currentIdentity: PhoneParseResult | null;
  onLoadDemo: () => void;
  onPurge: () => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const tabs = [
  { id: "scan", label: "Scan & Dorks", icon: Bug },
  { id: "exposures", label: "Exposures", icon: Zap },
  { id: "remediation", label: "Remediation Hub", icon: Shield },
  { id: "prevention", label: "Spam & DND", icon: Lock },
  { id: "audit", label: "Verify & Audit", icon: Trash2 },
] as const;

export const Navbar: React.FC<NavbarProps> = ({
  currentIdentity,
  onLoadDemo,
  onPurge,
  activeTab,
  setActiveTab,
}) => {
  return (
    <header className="border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] sticky top-0 z-40">
      <div className="container-shell flex flex-wrap items-center justify-between gap-y-2.5 gap-x-3 py-2.5 md:py-0 md:h-16">
        {/* Brand (Order 1 on both mobile & desktop) */}
        <div
          className="brand-mark shrink-0 cursor-pointer order-1 md:order-1"
          onClick={() => setActiveTab("scan")}
        >
          <div className="brand-icon">
            <Shield className="w-5 h-5 text-[var(--pixel-green)]" />
          </div>
          <div>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <span className="brand-title">ClearNum</span>
              <span className="font-mono text-xs text-slate-300 font-semibold tracking-tight">NumberShield</span>
              <span className="kicker-tag text-[10px]">v1.0 Local</span>
            </div>
            <p className="font-mono-ui text-[11px] text-[var(--text-muted)] mt-0.5 hidden sm:block">
              Open-Source Phone Privacy & Remediation
            </p>
          </div>
        </div>

        {/* Identity & Actions (Order 2 on mobile to sit beside brand; Order 3 on desktop to sit at the end) */}
        <div className="flex items-center gap-2 sm:gap-2.5 shrink-0 order-2 md:order-3">
          {currentIdentity ? (
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-input)] whitespace-nowrap shrink-0">
              <Lock className="w-3.5 h-3.5 text-[var(--pixel-green)]" />
              <span className="font-mono-ui text-xs text-[var(--text-main)] whitespace-nowrap">
                {currentIdentity.masked_display}
              </span>
              <span className="kicker-tag text-[9px] px-1.5 py-0.5">
                HMAC
              </span>
            </div>
          ) : null}

          <button
            onClick={onLoadDemo}
            className="btn btn-secondary text-xs py-1.5 px-2.5 sm:px-3 shrink-0"
            title="Load synthetic scenario with realistic data brokers and spam reports"
          >
            <Play className="w-3.5 h-3.5 text-[var(--pixel-green)]" />
            <span>Load Demo</span>
          </button>

          <button
            onClick={onPurge}
            className="btn btn-pixel danger text-xs py-1.5 px-2.5 sm:px-3 shrink-0"
            title="Zero-trace cryptographic wipe of all local records"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Purge</span>
          </button>
        </div>

        {/* The Single Unified Navigation Bar (<nav>) (Order 3 on mobile to drop to row 2; Order 2 on desktop to sit in the middle) */}
        <nav className="flex items-center overflow-x-auto gap-1.5 md:gap-1 bg-[var(--bg-app)] p-1 rounded-lg border border-[var(--border-subtle)] w-full md:w-auto shrink-0 order-3 md:order-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 md:gap-2 px-2.5 md:px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all shrink-0 ${
                  isActive
                    ? "bg-[var(--pixel-green)] text-[#022c22] font-bold shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--bg-card)]"
                }`}
                title={tab.label}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};

export default Navbar;
