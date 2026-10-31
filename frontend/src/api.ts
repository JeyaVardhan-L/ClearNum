/**
 * ClearNum API Client.
 * Connects to localhost backend (defaults to /api or http://127.0.0.1:8765/api).
 * India-first architecture.
 */

import type {
  PhoneParseResult,
  DiscoveredExposure,
  ProviderOutcome,
  RemediationSource,
  IndianSourceTarget,
  InventorySummary,
  ManualDorkItem,
  SpamIncident,
  CampaignGroup,
  ExposureMetrics,
  DNDCountryGuide,
  SearchRemovalGuide,
  GeneratedTemplate,
  PrepareRemediationResult,
  SubmitRemediationResult,
  RemediationHistory,
  AnalyzeSmsResult,
  PurgeStatusResponse,
  PurgeResponse,
  SearchPrivacyDisclosureResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

export async function parsePhone(phoneNumber: string, defaultRegion: string = "IN"): Promise<PhoneParseResult> {
  const res = await fetch(`${API_BASE}/identity/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: phoneNumber, default_region: defaultRegion }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSearchPrivacyDisclosure(
  phoneNumber: string,
  defaultRegion: string = "IN"
): Promise<SearchPrivacyDisclosureResponse> {
  const params = new URLSearchParams({ phone_number: phoneNumber, default_region: defaultRegion });
  const res = await fetch(`${API_BASE}/discovery/disclosure?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function scanDiscovery(
  phoneNumber: string,
  defaultRegion: string = "IN",
  providers: string[] = ["searxng", "duckduckgo"],
  targetUrls: string[] = [],
  consent?: { granted: boolean; confirmed_providers?: string[] }
): Promise<{
  identity_hmac: string;
  masked_phone: string;
  exposures: DiscoveredExposure[];
  total_found: number;
  manual_dorks_count?: number;
  provider_outcomes?: ProviderOutcome[];
  scan_status?: "complete" | "partial_failure" | "all_failed";
  consent_granted?: boolean;
  external_search_conducted?: boolean;
  privacy_notice?: string;
}> {
  const res = await fetch(`${API_BASE}/discovery/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      phone_number: phoneNumber,
      default_region: defaultRegion,
      providers,
      target_urls: targetUrls,
      consent: consent || { granted: false },
      external_search_consent: consent?.granted || false,
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

export async function getManualDorks(phoneNumber: string, defaultRegion: string = "IN"): Promise<ManualDorkItem[]> {
  const params = new URLSearchParams({ phone_number: phoneNumber, default_region: defaultRegion });
  const res = await fetch(`${API_BASE}/discovery/manual-dorks?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function analyzeSmsMessage(
  sender: string,
  messageBody: string = "",
  region: string = "IN",
  userPhone: string = ""
): Promise<AnalyzeSmsResult> {
  const res = await fetch(`${API_BASE}/discovery/analyze-sms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sender,
      message_body: messageBody,
      region,
      user_phone: userPhone,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRemediationSources(): Promise<RemediationSource[]> {
  const res = await fetch(`${API_BASE}/remediation/sources`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getIndiaInventory(): Promise<IndianSourceTarget[]> {
  const res = await fetch(`${API_BASE}/remediation/india-inventory`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getIndiaInventorySummary(): Promise<InventorySummary> {
  const res = await fetch(`${API_BASE}/remediation/india-inventory/summary`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function transitionAction(
  exposureId: string,
  identityHmac: string,
  nextState: string,
  submissionRef?: string,
  notes?: string
): Promise<{ success: boolean; new_status: string; action_id?: string; updated_at?: string }> {
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
export const transitionRemediationState = transitionAction;

export async function generateLegalTemplate(
  templateType: string,
  phoneNumber: string,
  defaultRegion: string = "IN",
  recipientName?: string,
  targetUrl?: string,
  violatorNumber?: string,
  incidentDate?: string,
  callDescription?: string,
  exposureId?: string,
  identityHmac?: string
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
      incident_date: incidentDate,
      call_description: callDescription,
      exposure_id: exposureId,
      identity_hmac: identityHmac,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function prepareRemediationRequest(params: {
  exposureId: string;
  identityHmac: string;
  requestType: string;
  submissionChannel?: string;
  recipientName?: string;
  targetUrl?: string;
  notes?: string;
  expectedResponseDate?: string;
  followUpDate?: string;
  deadlineBasis?: string;
}): Promise<PrepareRemediationResult> {
  const res = await fetch(`${API_BASE}/remediation/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exposure_id: params.exposureId,
      identity_hmac: params.identityHmac,
      request_type: params.requestType,
      submission_channel: params.submissionChannel || "WEB_FORM",
      recipient_name: params.recipientName,
      target_url: params.targetUrl,
      notes: params.notes,
      expected_response_date: params.expectedResponseDate,
      follow_up_date: params.followUpDate,
      deadline_basis: params.deadlineBasis || "NONE",
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitRemediationRequest(params: {
  exposureId: string;
  identityHmac: string;
  submissionChannel: string;
  submissionRef?: string;
  notes?: string;
  submittedAt?: string;
  expectedResponseDate?: string;
  followUpDate?: string;
  deadlineBasis?: string;
}): Promise<SubmitRemediationResult> {
  const res = await fetch(`${API_BASE}/remediation/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exposure_id: params.exposureId,
      identity_hmac: params.identityHmac,
      submission_channel: params.submissionChannel,
      submission_ref: params.submissionRef,
      notes: params.notes,
      submitted_at: params.submittedAt,
      expected_response_date: params.expectedResponseDate,
      follow_up_date: params.followUpDate,
      deadline_basis: params.deadlineBasis || "NONE",
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRemediationHistory(
  exposureId: string,
  identityHmac: string
): Promise<RemediationHistory> {
  const res = await fetch(`${API_BASE}/remediation/history/${encodeURIComponent(exposureId)}`, {
    headers: {
      "X-Identity-HMAC": identityHmac,
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function verifyExposure(
  exposureId: string,
  url: string,
  phoneNumber: string,
  defaultRegion: string = "IN"
): Promise<{
  url: string;
  status: string;
  http_status_code?: number;
  evidence_notes: string;
  verified_at: string;
  outcome?: string;
  final_url?: string;
  content_hash?: string;
  evidence_origin?: string;
  soft_404_detected?: boolean;
  reappeared?: boolean;
}> {
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
export const rescanVerifyUrl = verifyExposure;

export async function getDndGuides(): Promise<{ telecom_guides: DNDCountryGuide[]; search_removal_guides: SearchRemovalGuide[] }> {
  const res = await fetch(`${API_BASE}/prevention/dnd-guides`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export const getDNDGuides = getDndGuides;

export async function getSearchRemovalGuides(): Promise<SearchRemovalGuide[]> {
  const data = await getDndGuides();
  return data.search_removal_guides || [];
}

export async function recordSpam(
  identityHmac: string,
  senderNumber: string,
  channel: string = "CALL",
  category: string = "ROBOCALL",
  spoofSuspected: boolean = false,
  campaignSummary: string = ""
): Promise<{ success: boolean; incident_id: string; reported_at: string }> {
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
export const logSpamIncident = recordSpam;

export async function getSpamIncidents(identityHmac: string): Promise<{ incidents: SpamIncident[]; campaigns: CampaignGroup[] }> {
  const res = await fetch(`${API_BASE}/prevention/incidents?identity_hmac=${encodeURIComponent(identityHmac)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSpamCampaigns(identityHmac: string): Promise<CampaignGroup[]> {
  const data = await getSpamIncidents(identityHmac);
  return data.campaigns || [];
}

export async function getMetrics(identityHmac: string): Promise<ExposureMetrics> {
  const res = await fetch(`${API_BASE}/prevention/metrics?identity_hmac=${encodeURIComponent(identityHmac)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export const getExposureMetrics = getMetrics;

export async function getPurgeStatus(): Promise<PurgeStatusResponse> {
  const res = await fetch(`${API_BASE}/privacy/purge/status`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function purgeData(confirmationCode: string = "PURGE"): Promise<PurgeResponse> {
  const res = await fetch(`${API_BASE}/privacy/purge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      confirm: true,
      confirmation_code: confirmationCode,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export const purgeAllData = purgeData;

export async function exportAuditReport(identityHmac: string): Promise<any> {
  const res = await fetch(`${API_BASE}/privacy/export?identity_hmac=${encodeURIComponent(identityHmac)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function loadSyntheticDemo(): Promise<{
  success: boolean;
  message: string;
  identity_hmac: string;
  masked_phone: string;
  exposures_count: number;
}> {
  const res = await fetch(`${API_BASE}/demo/synthetic`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadMboxFile(
  file: File,
  identityHmac: string = "",
  phoneNumber: string = "",
  defaultRegion: string = "US"
) {
  const formData = new FormData();
  formData.append("file", file);
  if (identityHmac) formData.append("identity_hmac", identityHmac);
  if (phoneNumber) formData.append("phone_number", phoneNumber);
  if (defaultRegion) formData.append("default_region", defaultRegion);
  const res = await fetch(`${API_BASE}/import/mbox`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadSmsFile(
  file: File,
  identityHmac: string = "",
  phoneNumber: string = "",
  defaultRegion: string = "US"
) {
  const formData = new FormData();
  formData.append("file", file);
  if (identityHmac) formData.append("identity_hmac", identityHmac);
  if (phoneNumber) formData.append("phone_number", phoneNumber);
  if (defaultRegion) formData.append("default_region", defaultRegion);
  const res = await fetch(`${API_BASE}/import/sms`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
