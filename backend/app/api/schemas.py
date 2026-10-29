"""Pydantic request and response schemas for NumberShield / ClearNum API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PhoneParseRequest(BaseModel):
    phone_number: str = Field(..., description="Raw phone number input string")
    default_region: str = Field("IN", description="Default ISO 2-letter country code (defaults to IN for India)")


class PhoneParseResponse(BaseModel):
    is_valid: bool
    is_possible: bool
    e164: str
    international: str
    national: str
    country_code: int
    region_code: str
    location_desc: str
    carrier_name: str
    line_type: str
    masked_display: str
    hmac_id: str
    search_queries: List[str]


class ScanRequest(BaseModel):
    phone_number: str
    default_region: str = "IN"
    providers: List[str] = Field(default_factory=lambda: ["searxng", "duckduckgo", "wikimedia", "hackernews"])
    target_urls: Optional[List[str]] = Field(default_factory=list, description="Optional user-supplied URLs to scan")


class DiscoveredExposureItem(BaseModel):
    id: str
    source_id: str
    url: str
    domain: str
    title: str
    match_type: str
    confidence: float
    snippet: str
    discovered_at: str
    last_checked_at: str
    remediation_status: Optional[str] = None
    official_removal_url: Optional[str] = None
    match_rationale: Optional[str] = None


class ProviderOutcomeItem(BaseModel):
    provider_id: str
    status: str
    result_count: int
    duration_ms: int
    retryable: bool
    diagnostic: str
    last_successful_check: Optional[str] = None


class ScanResponse(BaseModel):
    identity_hmac: str
    masked_phone: str
    total_found: int
    exposures: List[DiscoveredExposureItem]
    manual_dorks_count: int
    provider_outcomes: List[ProviderOutcomeItem] = Field(default_factory=list)
    scan_status: str = Field(default="complete", description="'complete', 'partial_failure', or 'all_failed'")


class ManualDorkItem(BaseModel):
    engine_name: str
    category: str
    query_text: str
    search_url: str
    purpose: str


class TransitionActionRequest(BaseModel):
    action_id: Optional[str] = None
    exposure_id: str
    identity_hmac: str
    next_state: str  # "VERIFIED", "SUBMITTED", "ACKNOWLEDGED", "REJECTED", "VERIFIED_REMOVED", etc.
    submission_ref: Optional[str] = None
    notes: Optional[str] = None


class GenerateTemplateRequest(BaseModel):
    template_type: str  # "CCPA_DELETE", "GDPR_ERASURE", "TCPA_COMPLAINT", "TRAI_1909", "MERCHANT_UNSUBSCRIBE", "DPDP_ACT_2023"
    phone_number: str
    default_region: str = "IN"
    recipient_name: Optional[str] = "Data Broker Privacy Team"
    target_url: Optional[str] = None
    violator_number: Optional[str] = None
    incident_date: Optional[str] = None
    call_description: Optional[str] = None


class GenerateTemplateResponse(BaseModel):
    template_type: str
    title: str
    subject_line: str
    body_markdown: str


class RescanVerificationRequest(BaseModel):
    exposure_id: str
    url: str
    phone_number: str
    default_region: str = "IN"


class RescanVerificationResponse(BaseModel):
    url: str
    status: str
    http_status_code: Optional[int]
    evidence_notes: str
    verified_at: str


class SpamIncidentRequest(BaseModel):
    identity_hmac: str
    sender_number: str
    channel: str = "CALL"
    category: str = "ROBOCALL"
    spoof_suspected: bool = False
    campaign_summary: str = ""


class PurgeRequest(BaseModel):
    confirm: bool = Field(default=False, description="Must be explicitly set to True to execute purge")
    confirmation_code: str = Field(default="", description="Must be exactly 'PURGE' to confirm deletion")


class PurgeStatusResponse(BaseModel):
    database_path: str
    database_exists: bool
    database_size_bytes: int
    key_path: str
    key_exists: bool
    is_default_database: bool
    record_counts: Dict[str, int]
    total_records: int
    allowed_to_purge: bool
    reason: str = ""
    warning: str


class PurgeResponse(BaseModel):
    success: bool
    message: str
    database_path: str = ""
    key_path: str = ""
    tables_dropped: List[str] = []
    records_deleted: Dict[str, int] = {}
    key_deleted: bool = False
    files_unlinked: List[str] = []
    errors: List[str] = []
    purged_at: str


class AnalyzeSMSRequest(BaseModel):
    sender: str = Field(..., description="Sender header or telephone number (e.g. VM-HDFCBK, AD-SWIGGY)")
    message_body: str = Field(default="", description="Optional SMS message body text")
    region: str = Field(default="IN", description="Jurisdiction code (defaults to IN)")
    user_phone: Optional[str] = Field(default="", description="Optional user phone number for complaint generation")


class AnalyzeSMSResponse(BaseModel):
    sender: str
    category: str
    brand_name: str
    dlt_prefix: str
    telecom_circle: Optional[str] = None
    access_provider: Optional[str] = None
    is_shortcode: bool
    has_opt_out_keyword: bool
    opt_out_command: str
    recommended_action: str
    complaint_sms: Optional[str] = None
    chakshu_portal_url: Optional[str] = None
    chakshu_instructions: Optional[List[str]] = None
    merchant_notice: Optional[str] = None
    dpdp_notice: Optional[str] = None
    dnd_portal_url: Optional[str] = None
    grievance_email: Optional[str] = None
    customer_care_phone: Optional[str] = None
    confidence_disclaimer: Optional[str] = None
    statutory_deadline_info: Optional[str] = None
    dpdp_status_note: Optional[str] = None


class IndianSourceTargetItem(BaseModel):
    source_id: str
    name: str
    official_url: str
    category: str
    category_label: str
    execution_type: str
    verification_status: str
    access_restrictions: str
    lookup_method: str
    can_match_phone: bool
    evidence_attribution: str
    last_verified_at: str
    implementation_status: str
    known_limitations: str
    instructions: List[str]
    statutory_rights: List[str]
    grievance_email: Optional[str] = None
    customer_care_phone: Optional[str] = None
    domains: List[str]


class InventorySummaryResponse(BaseModel):
    total_sources: int
    by_category: Dict[str, int]
    by_execution_type: Dict[str, int]
    by_verification_status: Dict[str, int]
    last_verified: str
