/**
 * ClearNum TypeScript Data Definitions (India-First Architecture)
 */

export interface PhoneParseResult {
  is_valid: boolean;
  is_possible: boolean;
  e164: string;
  international: string;
  national: string;
  country_code: number;
  region_code: string;
  location_desc: string;
  carrier_name: string;
  line_type: string;
  masked_display: string;
  hmac_id: string;
  search_queries: string[];
  raw_input?: string;
}

export interface ProviderOutcome {
  provider_id: string;
  status: "healthy" | "rate_limited" | "unreachable" | "unconfigured" | "malformed_response" | "unsupported";
  result_count: number;
  duration_ms: number;
  retryable: boolean;
  diagnostic: string;
  last_successful_check?: string;
}

export interface DiscoveredExposure {
  id: string;
  source_id: string;
  url: string;
  domain: string;
  title: string;
  match_type: "EXACT" | "PROBABLE" | "WEAK" | "FALSE_POSITIVE";
  confidence: number;
  snippet: string;
  discovered_at: string;
  last_checked_at: string;
  remediation_status: string;
  official_removal_url?: string;
  match_rationale?: string;
  canonical_url?: string;
  matched_representation?: string;
  match_classification?: "CONFIRMED_MATCH" | "POSSIBLE_MATCH" | "INCIDENTAL_MENTION" | "INCONCLUSIVE" | "FALSE_POSITIVE";
  confidence_explanation?: string;
  provider_status?: string;
  is_example_or_test?: boolean;
}

export interface ProviderDisclosureItem {
  provider_id: string;
  provider_name: string;
  endpoint: string;
  exact_query_sent: string;
  masked_query_preview: string;
  data_transmitted: string;
  purpose: string;
  privacy_risk: string;
}

export interface SearchPrivacyDisclosureResponse {
  identity_hmac: string;
  masked_phone: string;
  default_mode: string;
  notice: string;
  providers: ProviderDisclosureItem[];
}

export interface RemediationSource {
  source_id: string;
  name: string;
  category: string;
  domains: string[];
  official_removal_url: string;
  removal_method: string;
  instructions: string[];
  processing_time_estimate: string;
  requires_email_confirmation: boolean;
  requires_phone_call: boolean;
  statutory_rights: string[];
  contact_email?: string;
  notes?: string;
  execution_type?: string;
  verification_status?: string;
  lookup_method?: string;
  can_match_phone?: boolean;
  evidence_attribution?: string;
  last_verified_at?: string;
  capability_category?: string;
  capability_description?: string;
  truth_notice?: string;
}

export interface IndianSourceTarget {
  source_id: string;
  name: string;
  official_url: string;
  category: string;
  category_label: string;
  execution_type: string;
  verification_status: string;
  access_restrictions: string;
  lookup_method: string;
  can_match_phone: boolean;
  evidence_attribution: string;
  last_verified_at: string;
  implementation_status: string;
  known_limitations: string;
  instructions: string[];
  statutory_rights: string[];
  grievance_email?: string;
  customer_care_phone?: string;
  domains: string[];
  capability_category?: string;
  capability_description?: string;
  truth_notice?: string;
}

export interface InventorySummary {
  total_sources: number;
  by_category: Record<string, number>;
  by_execution_type: Record<string, number>;
  by_verification_status: Record<string, number>;
  last_verified: string;
}

export interface ManualDorkItem {
  engine_name: string;
  category: string;
  query_text: string;
  search_url: string;
  purpose: string;
}

export interface SpamIncident {
  id: string;
  sender_number: string;
  channel: string;
  category: string;
  spoof_suspected: boolean;
  campaign_summary: string;
  reported_at: string;
}

export interface CampaignGroup {
  campaign_name: string;
  incident_count: number;
  sender_numbers: string[];
  channels: string[];
  sample_pitches: string[];
  spoof_percentage: number;
}

export interface ExposureMetrics {
  total_exposures: number;
  verified_removed: number;
  pending_actions: number;
  submitted_actions: number;
  action_available: number;
  rejected_matches: number;
  active_subscriptions: number;
  total_spam_incidents: number;
  removal_success_rate: number;
  exposure_by_source: Record<string, number>;
  incidents_by_category: Record<string, number>;
}

export interface DNDCountryGuide {
  country_code: string;
  country_name: string;
  registry_name: string;
  official_website: string;
  statutory_window: string;
  how_to_register: string[];
  carrier_spam_forwarding_code?: string;
  carrier_forwarding_instructions: string;
  how_to_file_complaint: string[];
  legal_basis: string;
}

export interface SearchRemovalGuide {
  engine: string;
  workflow_name: string;
  portal_url: string;
  applicability: string;
  prerequisites: string[];
  steps: string[];
  estimated_turnaround: string;
}

export interface GeneratedTemplate {
  template_type: string;
  title: string;
  subject_line: string;
  body_markdown: string;
}

export interface DiscoveredSMSSender {
  sender_number: string;
  is_shortcode: boolean;
  message_count: number;
  has_opt_out_keyword: boolean;
  opt_out_command: string;
  sample_body: string;
  category: string;
  brand_name?: string;
  dlt_prefix?: string;
  recommended_action?: string;
}

export interface AnalyzeSmsResult {
  sender: string;
  category: string;
  brand_name: string;
  dlt_prefix: string;
  telecom_circle?: string;
  access_provider?: string;
  is_shortcode: boolean;
  has_opt_out_keyword: boolean;
  opt_out_command: string;
  recommended_action: string;
  complaint_sms?: string;
  chakshu_portal_url?: string;
  chakshu_instructions?: string[];
  merchant_notice?: string;
  dpdp_notice?: string;
  dnd_portal_url?: string;
  grievance_email?: string;
  customer_care_phone?: string;
  confidence_disclaimer?: string;
  statutory_deadline_info?: string;
  dpdp_status_note?: string;
}

export interface PurgeStatusResponse {
  database_path: string;
  database_exists: boolean;
  database_size_bytes: number;
  key_path: string;
  key_exists: boolean;
  is_default_database: boolean;
  record_counts: Record<string, number>;
  total_records: number;
  allowed_to_purge: boolean;
  validation_reason: string;
  warning: string;
}

export interface PurgeResponse {
  success: boolean;
  message: string;
  database_path: string;
  key_path: string;
  tables_dropped: string[];
  records_deleted: Record<string, number>;
  key_deleted: boolean;
  files_unlinked: string[];
  errors: string[];
  purged_at: string;
}
