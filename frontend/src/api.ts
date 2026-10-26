/**
 * NumberShield API Client.
 * Connects to localhost backend (defaults to /api or http://127.0.0.1:8765/api).
 */

import type {
  PhoneParseResult,
  DiscoveredExposure,
  RemediationSource,
  ManualDorkItem,
  SpamIncident,
  CampaignGroup,
  ExposureMetrics,
  DNDCountryGuide,
  SearchRemovalGuide,
  GeneratedTemplate,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

export async function parsePhone(phoneNumber: string, defaultRegion: string = "US"): Promise<PhoneParseResult> {
  const res = await fetch(`${API_BASE}/identity/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: phoneNumber, default_region: defaultRegion }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function scanDiscovery(
  phoneNumber: string,
  defaultRegion: string = "US",
  providers: string[] = ["searxng", "duckduckgo"],
  targetUrls: string[] = []
): Promise<{ identity_hmac: string; masked_phone: string; exposures: DiscoveredExposure[]; total_found: number }> {
  const res = await fetch(`${API_BASE}/discovery/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      phone_number: phoneNumber,
      default_region: defaultRegion,
      providers,
      target_urls: targetUrls,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExposures(identityHmac: string): Promise<DiscoveredExposure[]> {
  const res = await fetch(`${API_BASE}/discovery/exposures?identity_hmac=${encodeURIComponent(identityHmac)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getManualDorks(phoneNumber: string, defaultRegion: string = "US"): Promise<ManualDorkItem[]> {
  const res = await fetch(
    `${API_BASE}/discovery/manual-dorks?phone_number=${encodeURIComponent(phoneNumber)}&default_region=${encodeURIComponent(defaultRegion)}`
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRemediationSources(): Promise<RemediationSource[]> {
  const res = await fetch(`${API_BASE}/remediation/sources`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function transitionAction(
  exposureId: string,
  identityHmac: string,
  nextState: string,
  submissionRef?: string,
  notes?: string
): Promise<{ success: boolean; new_status: string }> {
  const res = await fetch(`${API_BASE}/remediation/transition`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exposure_id: exposureId,
      identity_hmac: identityHmac,
      next_state: nextState,
      submission_ref: submissionRef,
      notes: notes,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateLegalTemplate(
  templateType: string,
  phoneNumber: string,
  defaultRegion: string = "US",
  recipientName: string = "Data Broker Privacy Team",
  targetUrl?: string,
  violatorNumber?: string
): Promise<GeneratedTemplate> {
  const res = await fetch(`${API_BASE}/remediation/template`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      template_type: templateType,
      phone_number: phoneNumber,
      default_region: defaultRegion,
      recipient_name: recipientName,
      target_url: targetUrl,
      violator_number: violatorNumber,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function verifyExposure(
  exposureId: string,
  url: string,
  phoneNumber: string,
  defaultRegion: string = "US"
): Promise<{ url: string; status: string; http_status_code?: number; evidence_notes: string; verified_at: string }> {
  const res = await fetch(`${API_BASE}/remediation/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exposure_id: exposureId,
      url,
      phone_number: phoneNumber,
      default_region: defaultRegion,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadMboxFile(file: File, phoneNumber: string = ""): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("phone_number", phoneNumber);
  const res = await fetch(`${API_BASE}/import/mbox`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadSmsFile(file: File, identityHmac: string = ""): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("identity_hmac", identityHmac);
  const res = await fetch(`${API_BASE}/import/sms`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function recordSpam(
  identityHmac: string,
  senderNumber: string,
  channel: string = "CALL",
  category: string = "ROBOCALL",
  spoofSuspected: boolean = false,
  campaignSummary: string = ""
): Promise<any> {
  const res = await fetch(`${API_BASE}/prevention/incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      identity_hmac: identityHmac,
      sender_number: senderNumber,
      channel,
      category,
      spoof_suspected: spoofSuspected,
      campaign_summary: campaignSummary,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSpamIncidents(identityHmac: string): Promise<{ incidents: SpamIncident[]; campaigns: CampaignGroup[] }> {
  const res = await fetch(`${API_BASE}/prevention/incidents?identity_hmac=${encodeURIComponent(identityHmac)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMetrics(identityHmac: string): Promise<ExposureMetrics> {
  const res = await fetch(`${API_BASE}/prevention/metrics?identity_hmac=${encodeURIComponent(identityHmac)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDndGuides(): Promise<{ telecom_guides: DNDCountryGuide[]; search_removal_guides: SearchRemovalGuide[] }> {
  const res = await fetch(`${API_BASE}/prevention/dnd-guides`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function exportAuditReport(identityHmac: string): Promise<any> {
  const res = await fetch(`${API_BASE}/privacy/export?identity_hmac=${encodeURIComponent(identityHmac)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function purgeData(): Promise<any> {
  const res = await fetch(`${API_BASE}/privacy/purge`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function loadSyntheticDemo(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/synthetic`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
