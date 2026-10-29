"""Pydantic request and response schemas for NumberShield API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PhoneParseRequest(BaseModel):
    phone_number: str = Field(..., description="Raw phone number input string")
    default_region: str = Field("US", description="Default ISO 2-letter country code if missing prefix")


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
    default_region: str = "US"
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
    template_type: str  # "CCPA_DELETE", "GDPR_ERASURE", "TCPA_COMPLAINT", "TRAI_1909", "MERCHANT_UNSUBSCRIBE"
    phone_number: str
    default_region: str = "US"
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
    default_region: str = "US"


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


class PurgeResponse(BaseModel):
    success: bool
    message: str
    purged_at: str


class AnalyzeSMSRequest(BaseModel):
    sender: str = Field(..., description="Sender header or telephone number (e.g. VM-HDFCBK, AD-SWIGGY)")
    message_body: str = Field(default="", description="Optional SMS message body text")
    region: str = Field(default="IN", description="Jurisdiction code (e.g. IN, US, GB)")
    user_phone: Optional[str] = Field(default="", description="Optional user phone number for complaint generation")


class AnalyzeSMSResponse(BaseModel):
    sender: str
    category: str
    brand_name: str
    dlt_prefix: str
    is_shortcode: bool
    has_opt_out_keyword: bool
    opt_out_command: str
    recommended_action: str
    complaint_sms: Optional[str] = None
    merchant_notice: Optional[str] = None
