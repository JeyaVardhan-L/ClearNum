"""FastAPI routes for NumberShield platform."""

import os
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from urllib.parse import urlparse

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection, init_db, purge_all_data, utc_now_iso
from backend.app.core.security import compute_phone_hmac, mask_phone_number
from backend.app.core.ssrf import safe_fetch_url
from backend.app.engines.discovery import parse_and_normalize, match_phone_in_text
from backend.app.engines.discovery.providers import (
    SearXNGProvider,
    DuckDuckGoProvider,
    WikimediaProvider,
    HackerNewsProvider,
    WaybackProvider,
    generate_manual_dorks,
    ProviderResult,
    ProviderStatus,
)
from backend.app.engines.discovery.local_parsers import (
    parse_mbox_file,
    parse_sms_backup_file,
    analyze_single_sms,
)
from backend.app.engines.remediation import (
    lookup_source_by_url,
    get_all_sources,
    validate_transition,
    ActionState,
    InvalidStateTransitionError,
    EVIDENCE_RULES,
    generate_ccpa_opt_out,
    generate_gdpr_erasure,
    generate_tcpa_ftc_complaint,
    generate_trai_1909_complaint,
    generate_merchant_unsubscribe,
    generate_dpdp_act_notice,
    get_all_dnd_guides,
    get_search_removal_guides,
    get_all_indian_sources,
    get_inventory_summary,
    get_sources_by_category,
)
from backend.app.engines.discovery.india_telecom import (
    decode_dlt_sender,
    generate_trai_1909_complaint as gen_trai_1909,
    generate_chakshu_escalation,
    generate_dpdp_revocation_notice,
)
from backend.app.engines.prevention import (
    record_spam_incident,
    list_spam_incidents,
    analyze_spam_campaigns,
    verify_exposure_url,
    calculate_metrics,
)
from backend.app.api.schemas import (
    PhoneParseRequest,
    PhoneParseResponse,
    ScanRequest,
    ScanResponse,
    DiscoveredExposureItem,
    ProviderOutcomeItem,
    ManualDorkItem,
    TransitionActionRequest,
    GenerateTemplateRequest,
    GenerateTemplateResponse,
    RescanVerificationRequest,
    RescanVerificationResponse,
    SpamIncidentRequest,
    PurgeResponse,
    AnalyzeSMSRequest,
    AnalyzeSMSResponse,
    IndianSourceTargetItem,
    InventorySummaryResponse,
)

router = APIRouter(prefix="/api")


# --- 1. Identity & Normalization ---

@router.post("/identity/parse", response_model=PhoneParseResponse)
def parse_phone_endpoint(req: PhoneParseRequest):
    norm = parse_and_normalize(req.phone_number, req.default_region)
    return PhoneParseResponse(
        is_valid=norm.is_valid,
        is_possible=norm.is_possible,
        e164=norm.e164,
        international=norm.international,
        national=norm.national,
        country_code=norm.country_code,
        region_code=norm.region_code,
        location_desc=norm.location_desc,
        carrier_name=norm.carrier_name,
        line_type=norm.line_type,
        masked_display=norm.masked_display,
        hmac_id=norm.hmac_id,
        search_queries=norm.search_queries,
    )

@router.post("/discovery/analyze-sms", response_model=AnalyzeSMSResponse)
def analyze_sms_endpoint(req: AnalyzeSMSRequest):
    sender_info = analyze_single_sms(req.sender, req.message_body, req.region)
    complaint_sms = None
    merchant_notice = None
    dpdp_notice = None
    chakshu_url = None
    chakshu_instructions = None
    circle_desc = None
    operator_name = None
    dnd_portal_url = None
    grievance_email = None
    customer_care_phone = None

    # Decode DLT sender header
    op_name, circ_desc, matched_brand = decode_dlt_sender(req.sender)
    if op_name:
        operator_name = op_name
    if circ_desc:
        circle_desc = circ_desc

    if matched_brand:
        brand_name = matched_brand.brand_name
        category = matched_brand.category
        dnd_portal_url = matched_brand.dnd_url
        grievance_email = matched_brand.grievance_email
        customer_care_phone = matched_brand.customer_care_phone
    else:
        brand_name = sender_info.brand_name
        category = sender_info.category

    # TRAI 1909 & Chakshu escalation
    if req.region.upper() == "IN":
        trai_data = gen_trai_1909(req.sender, req.message_body)
        complaint_sms = trai_data["formal_syntax"]

        chakshu_data = generate_chakshu_escalation(req.sender, req.message_body)
        chakshu_url = chakshu_data["portal_url"]
        chakshu_instructions = chakshu_data["instructions"]

    # DPDP Act 2023 Statutory Consent Revocation Notice
    user_masked = mask_phone_number(req.user_phone) if req.user_phone else "[Registered Subscriber Mobile]"
    if matched_brand:
        dpdp_notice = generate_dpdp_revocation_notice(matched_brand, user_masked)
        merchant_notice = (
            f"FORMAL NOTICE OF WITHDRAWAL OF CONSENT / STATUTORY DO-NOT-CALL DEMAND\n"
            f"To: {matched_brand.brand_name} Grievance & Compliance Team ({matched_brand.grievance_email or 'grievance'})\n\n"
            f"Please immediately suppress telephone number {user_masked} from all active marketing, promotional, "
            f"and affiliated calling databases under Section 6(4) of the Digital Personal Data Protection Act, 2023 "
            f"and TRAI Telecom Commercial Communications Customer Preference Regulations (TCCCPR 2018)."
        )
    elif brand_name:
        merchant_notice = (
            f"FORMAL NOTICE OF WITHDRAWAL OF CONSENT / STATUTORY DO-NOT-CALL DEMAND\n"
            f"To: {brand_name} Privacy & Compliance Team\n\n"
            f"Please immediately suppress my telephone number ({user_masked}) from all marketing, promotional, "
            f"and affiliated third-party databases under Section 6(4) of the Digital Personal Data Protection Act, 2023."
        )

    return AnalyzeSMSResponse(
        sender=sender_info.sender_number,
        category=category,
        brand_name=brand_name,
        dlt_prefix=sender_info.dlt_prefix,
        telecom_circle=circle_desc,
        access_provider=operator_name,
        is_shortcode=sender_info.is_shortcode,
        has_opt_out_keyword=sender_info.has_opt_out_keyword,
        opt_out_command=sender_info.opt_out_command,
        recommended_action=sender_info.recommended_action,
        complaint_sms=complaint_sms,
        chakshu_portal_url=chakshu_url,
        chakshu_instructions=chakshu_instructions,
        merchant_notice=merchant_notice,
        dpdp_notice=dpdp_notice,
        dnd_portal_url=dnd_portal_url,
        grievance_email=grievance_email,
        customer_care_phone=customer_care_phone,
    )



# --- 2. Discovery Engine ---

@router.post("/discovery/scan", response_model=ScanResponse)
async def scan_discovery_endpoint(req: ScanRequest):
    norm = parse_and_normalize(req.phone_number, req.default_region)
    if not norm.is_possible:
        raise HTTPException(status_code=400, detail="Provided phone number is not a possible telephone sequence.")

    # Record identity in local DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hmac_id) DO NOTHING
    """, (
        str(uuid.uuid4()),
        norm.hmac_id,
        norm.masked_display,
        str(norm.country_code),
        norm.carrier_name,
        norm.line_type,
        utc_now_iso(),
    ))
    conn.commit()

    all_provider_results: List[ProviderResult] = []
    provider_outcomes: List[ProviderOutcomeItem] = []

    # Run chosen providers
    provider_factories = {
        "searxng": (SearXNGProvider, 12),
        "duckduckgo": (DuckDuckGoProvider, 12),
        "wikimedia": (WikimediaProvider, 10),
        "hackernews": (HackerNewsProvider, 10),
        "wayback": (WaybackProvider, 10),
    }

    for p_id in req.providers:
        if p_id in provider_factories:
            cls_factory, max_r = provider_factories[p_id]
            provider_inst = cls_factory()
            res = await provider_inst.search(norm, max_results=max_r)
            all_provider_results.extend(res)
            if res.outcome:
                provider_outcomes.append(ProviderOutcomeItem(
                    provider_id=res.outcome.provider_id,
                    status=res.outcome.status.value,
                    result_count=res.outcome.result_count,
                    duration_ms=res.outcome.duration_ms,
                    retryable=res.outcome.retryable,
                    diagnostic=res.outcome.diagnostic,
                    last_successful_check=res.outcome.last_successful_check,
                ))

    # Process user-supplied target URLs safely with SSRF protection
    if req.target_urls:
        for custom_url in req.target_urls:
            clean_custom = custom_url.strip()
            if not clean_custom.startswith(("http://", "https://")):
                continue
            try:
                status_code, content, _ = await safe_fetch_url(clean_custom)
                if status_code == 200:
                    match_res = match_phone_in_text(content, norm)
                    if match_res.matched:
                        parsed_u = urlparse(clean_custom)
                        all_provider_results.append(ProviderResult.from_url_and_title(
                            url=clean_custom,
                            title=f"Custom Target [{parsed_u.netloc}]",
                            snippet=match_res.snippet,
                            provider_id="user_target",
                        ))
            except Exception:
                pass

    # Process and deduplicate results
    seen_urls = set()
    discovered_items: List[DiscoveredExposureItem] = []
    now_iso = utc_now_iso()

    for item in all_provider_results:
        clean_url = item.url.split("#")[0].strip()
        if not clean_url or clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        # Context match evaluation
        match_eval = match_phone_in_text(f"{item.title} {item.snippet}", norm)
        match_type = match_eval.match_type if match_eval.matched else "PROBABLE"
        confidence = match_eval.confidence if match_eval.matched else 0.75
        snippet = match_eval.snippet if match_eval.snippet else (item.snippet or item.title)

        parsed = urlparse(clean_url)
        domain = parsed.netloc.lower().replace("www.", "")

        # Look up remediation source
        rem_source = lookup_source_by_url(clean_url)
        source_id = rem_source.source_id if rem_source else "generic_web"
        official_removal_url = rem_source.official_removal_url if rem_source else None

        cursor.execute("SELECT id FROM exposures WHERE identity_hmac = ? AND url = ?", (norm.hmac_id, clean_url))
        existing_exp = cursor.fetchone()

        if existing_exp:
            exposure_id = existing_exp["id"]
            cursor.execute("""
                UPDATE exposures
                SET last_checked_at = ?, snippet = ?, confidence = ?, match_type = ?
                WHERE id = ?
            """, (now_iso, snippet, confidence, match_type, exposure_id))
        else:
            exposure_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO exposures (
                    id, identity_hmac, source_id, url, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exposure_id,
                norm.hmac_id,
                source_id,
                clean_url,
                domain,
                item.title,
                match_type,
                confidence,
                snippet,
                now_iso,
                now_iso,
            ))

        # Check existing remediation action
        cursor.execute("SELECT id, status, official_url FROM remediation_actions WHERE exposure_id = ?", (exposure_id,))
        act_row = cursor.fetchone()

        if not act_row:
            action_id = str(uuid.uuid4())
            rem_status = "ACTION_AVAILABLE" if rem_source else "DISCOVERED"
            cursor.execute("""
                INSERT INTO remediation_actions (
                    id, exposure_id, identity_hmac, source_id, status, official_url, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action_id,
                exposure_id,
                norm.hmac_id,
                source_id,
                rem_status,
                official_removal_url,
                "Discovered via search provider",
                now_iso,
            ))
        else:
            rem_status = act_row["status"]
            official_removal_url = act_row["official_url"]

        discovered_items.append(DiscoveredExposureItem(
            id=exposure_id,
            source_id=source_id,
            url=clean_url,
            domain=domain,
            title=item.title,
            match_type=match_type,
            confidence=confidence,
            snippet=snippet,
            discovered_at=now_iso,
            last_checked_at=now_iso,
            remediation_status=rem_status,
            official_removal_url=official_removal_url,
        ))

    conn.commit()
    conn.close()

    dorks = generate_manual_dorks(norm)

    # Calculate overall scan status
    healthy_count = sum(1 for p in provider_outcomes if getattr(p, "status", "") in ("healthy", ProviderStatus.HEALTHY))
    if not provider_outcomes or healthy_count == len(provider_outcomes):
        scan_status = "complete"
    elif healthy_count == 0:
        scan_status = "all_failed"
    else:
        scan_status = "partial_failure"

    return ScanResponse(
        identity_hmac=norm.hmac_id,
        masked_phone=norm.masked_display,
        total_found=len(discovered_items),
        exposures=discovered_items,
        manual_dorks_count=len(dorks),
        provider_outcomes=provider_outcomes,
        scan_status=scan_status,
    )


@router.get("/discovery/exposures", response_model=List[DiscoveredExposureItem])
def list_exposures_endpoint(identity_hmac: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.source_id, e.url, e.domain, e.title, e.match_type, e.confidence, e.snippet,
               e.discovered_at, e.last_checked_at, r.status as remediation_status, r.official_url as official_removal_url
        FROM exposures e
        LEFT JOIN remediation_actions r ON r.exposure_id = e.id
        WHERE e.identity_hmac = ?
        ORDER BY e.discovered_at DESC
    """, (identity_hmac,))
    rows = cursor.fetchall()
    conn.close()

    return [
        DiscoveredExposureItem(
            id=r["id"],
            source_id=r["source_id"],
            url=r["url"],
            domain=r["domain"],
            title=r["title"] or r["domain"],
            match_type=r["match_type"],
            confidence=r["confidence"],
            snippet=r["snippet"] or "",
            discovered_at=r["discovered_at"],
            last_checked_at=r["last_checked_at"],
            remediation_status=r["remediation_status"] or "DISCOVERED",
            official_removal_url=r["official_removal_url"],
        )
        for r in rows
    ]


@router.get("/discovery/manual-dorks", response_model=List[ManualDorkItem])
def get_manual_dorks_endpoint(phone_number: str, default_region: str = "US"):
    norm = parse_and_normalize(phone_number, default_region)
    dorks = generate_manual_dorks(norm)
    return [
        ManualDorkItem(
            engine_name=d.engine_name,
            category=d.category,
            query_text=d.query_text,
            search_url=d.search_url,
            purpose=d.purpose,
        )
        for d in dorks
    ]


# --- 3. Remediation Hub ---

@router.get("/remediation/sources")
def list_remediation_sources_endpoint():
    sources = get_all_sources()
    return [
        {
            "source_id": s.source_id,
            "name": s.name,
            "category": s.category,
            "domains": s.domains,
            "official_removal_url": s.official_removal_url,
            "removal_method": s.removal_method,
            "instructions": s.instructions,
            "processing_time_estimate": s.processing_time_estimate,
            "requires_email_confirmation": s.requires_email_confirmation,
            "requires_phone_call": s.requires_phone_call,
            "statutory_rights": s.statutory_rights,
            "contact_email": s.contact_email,
            "notes": s.notes,
            "execution_type": getattr(s, "execution_type", None) or s.removal_method,
            "verification_status": getattr(s, "verification_status", None) or "accessible_manual",
            "lookup_method": getattr(s, "lookup_method", None) or "Direct web lookup",
            "can_match_phone": getattr(s, "can_match_phone", True),
            "evidence_attribution": getattr(s, "evidence_attribution", None) or "Web presence",
            "last_verified_at": getattr(s, "last_verified_at", None) or "2026-10-29T11:00:00Z",
        }
        for s in sources
    ]


@router.get("/remediation/india-inventory", response_model=List[IndianSourceTargetItem])
def get_india_inventory_endpoint():
    """Returns the complete curated inventory of 110+ distinct Indian source targets."""
    return [
        IndianSourceTargetItem(
            source_id=t.source_id,
            name=t.name,
            official_url=t.official_url,
            category=t.category,
            category_label=t.category_label,
            execution_type=t.execution_type,
            verification_status=t.verification_status,
            access_restrictions=t.access_restrictions,
            lookup_method=t.lookup_method,
            can_match_phone=t.can_match_phone,
            evidence_attribution=t.evidence_attribution,
            last_verified_at=t.last_verified_at,
            implementation_status=t.implementation_status,
            known_limitations=t.known_limitations,
            instructions=t.instructions,
            statutory_rights=t.statutory_rights,
            grievance_email=t.grievance_email,
            customer_care_phone=t.customer_care_phone,
            domains=t.domains,
        )
        for t in get_all_indian_sources()
    ]


@router.get("/remediation/india-inventory/summary", response_model=InventorySummaryResponse)
def get_india_inventory_summary_endpoint():
    """Returns exact source counts across all 10 categories, execution types, and verification statuses."""
    summary = get_inventory_summary()
    return InventorySummaryResponse(
        total_sources=summary["total_sources"],
        by_category=summary["by_category"],
        by_execution_type=summary["by_execution_type"],
        by_verification_status=summary["by_verification_status"],
        last_verified=summary["last_verified"],
    )


@router.post("/remediation/transition")
def transition_action_endpoint(req: TransitionActionRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get current status
    cursor.execute("""
        SELECT id, status FROM remediation_actions
        WHERE exposure_id = ? AND identity_hmac = ?
    """, (req.exposure_id, req.identity_hmac))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Remediation action not found for exposure.")

    current_status = row["status"]
    action_id = row["id"]

    try:
        validate_transition(current_status, req.next_state)
    except InvalidStateTransitionError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

    now_iso = utc_now_iso()
    cursor.execute("""
        UPDATE remediation_actions
        SET status = ?, submission_ref = COALESCE(?, submission_ref),
            notes = COALESCE(?, notes), updated_at = ?
        WHERE id = ?
    """, (req.next_state, req.submission_ref, req.notes, now_iso, action_id))

    # Log immutable state transition into action_audit_log
    audit_id = str(uuid.uuid4())
    evidence_rule = EVIDENCE_RULES.get(req.next_state)
    ev_type = evidence_rule.required_evidence_type if evidence_rule else "USER_TRANSITION"
    ev_notes = req.notes or (f"Submission reference: {req.submission_ref}" if req.submission_ref else "User initiated transition")
    cursor.execute("""
        INSERT INTO action_audit_log (
            id, action_id, identity_hmac, from_state, to_state, evidence_type, evidence_notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        audit_id,
        action_id,
        req.identity_hmac,
        current_status,
        req.next_state,
        ev_type,
        ev_notes,
        now_iso,
    ))

    conn.commit()
    conn.close()

    return {"success": True, "action_id": action_id, "new_status": req.next_state, "updated_at": now_iso}


@router.post("/remediation/template", response_model=GenerateTemplateResponse)
def generate_template_endpoint(req: GenerateTemplateRequest):
    norm = parse_and_normalize(req.phone_number, req.default_region)
    t_type = req.template_type.upper()

    if t_type in ("CCPA_DELETE", "CCPA_DELETION"):
        tpl = generate_ccpa_opt_out(norm, req.recipient_name or "Data Broker Privacy Team", req.target_url)
    elif t_type in ("GDPR_ERASURE", "GDPR_DELETE"):
        tpl = generate_gdpr_erasure(norm, req.recipient_name or "Data Protection Officer", req.target_url)
    elif t_type in ("TCPA_COMPLAINT", "TCPA_REVOCATION"):
        tpl = generate_tcpa_ftc_complaint(
            norm,
            req.violator_number or "[Unknown Caller ID]",
            req.incident_date or utc_now_iso(),
            req.call_description or "Unsolicited prerecorded marketing robocall",
        )
    elif t_type in ("TRAI_1909", "TRAI_COMMERCIAL"):
        tpl = generate_trai_1909_complaint(
            norm,
            req.violator_number or "9876543210",
            req.incident_date or "24/10/26",
            "14:30",
        )
    elif t_type in ("MERCHANT_UNSUBSCRIBE", "MERCHANT_OPTOUT"):
        tpl = generate_merchant_unsubscribe(norm, req.recipient_name or "Company Operations")
    elif t_type in ("DPDP_ACT_2023", "DPDP_NOTICE", "DPDP"):
        tpl = generate_dpdp_act_notice(
            norm,
            req.recipient_name or "Grievance Officer",
            target_url=req.target_url,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown template type: {req.template_type}")

    return GenerateTemplateResponse(
        template_type=tpl.template_type,
        title=tpl.title,
        subject_line=tpl.subject_line,
        body_markdown=tpl.body_markdown,
    )


@router.post("/remediation/verify", response_model=RescanVerificationResponse)
async def verify_exposure_endpoint(req: RescanVerificationRequest):
    norm = parse_and_normalize(req.phone_number, req.default_region)
    outcome = await verify_exposure_url(
        exposure_id=req.exposure_id,
        url=req.url,
        phone=norm,
        update_database=True,
    )
    return RescanVerificationResponse(
        url=outcome.url,
        status=outcome.status,
        http_status_code=outcome.http_status_code,
        evidence_notes=outcome.evidence_notes,
        verified_at=outcome.verified_at,
    )


# --- 4. User-Authorized Local File Imports ---

@router.post("/import/mbox")
async def import_mbox_endpoint(
    file: UploadFile = File(...),
    phone_number: str = Form(""),
    default_region: str = Form("US"),
):
    norm = parse_and_normalize(phone_number, default_region) if phone_number else None
    temp_dir = settings.db_path.parent / "temp_imports"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"import_{uuid.uuid4().hex}.mbox"

    try:
        content = await file.read()
        temp_path.write_bytes(content)
        subs = parse_mbox_file(temp_path, phone=norm, max_emails=250)
        
        # Save subscriptions to DB if identity exists
        if norm and norm.hmac_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            now_iso = utc_now_iso()
            for s in subs:
                sub_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO subscriptions (
                        id, identity_hmac, sender_name, sender_contact, channel, unsubscribe_method, unsubscribe_target, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sub_id,
                    norm.hmac_id,
                    s.sender_name,
                    s.sender_contact,
                    s.channel,
                    s.unsubscribe_method,
                    s.unsubscribe_target,
                    "ACTIVE",
                    now_iso,
                ))
            conn.commit()
            conn.close()

        return {
            "success": True,
            "filename": file.filename,
            "discovered_subscriptions_count": len(subs),
            "subscriptions": [
                {
                    "sender_name": s.sender_name,
                    "sender_contact": s.sender_contact,
                    "channel": s.channel,
                    "unsubscribe_method": s.unsubscribe_method,
                    "unsubscribe_target": s.unsubscribe_target,
                    "phone_exposed": s.phone_exposed,
                    "evidence_snippet": s.evidence_snippet,
                }
                for s in subs
            ],
        }
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


@router.post("/import/sms")
async def import_sms_endpoint(
    file: UploadFile = File(...),
    identity_hmac: str = Form(""),
):
    temp_dir = settings.db_path.parent / "temp_imports"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"sms_{uuid.uuid4().hex}_{file.filename}"

    try:
        content = await file.read()
        temp_path.write_bytes(content)
        senders = parse_sms_backup_file(temp_path, max_records=500)

        return {
            "success": True,
            "filename": file.filename,
            "senders_count": len(senders),
            "senders": [
                {
                    "sender_number": s.sender_number,
                    "is_shortcode": s.is_shortcode,
                    "message_count": s.message_count,
                    "has_opt_out_keyword": s.has_opt_out_keyword,
                    "opt_out_command": s.opt_out_command,
                    "sample_body": s.sample_body,
                    "category": s.category,
                    "brand_name": s.brand_name,
                    "dlt_prefix": s.dlt_prefix,
                    "recommended_action": s.recommended_action,
                }
                for s in senders
            ],
        }
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


@router.get("/subscriptions")
def list_subscriptions_endpoint(identity_hmac: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, identity_hmac, sender_name, sender_contact, channel, unsubscribe_method, unsubscribe_target, status, created_at
        FROM subscriptions
        WHERE identity_hmac = ?
        ORDER BY created_at DESC
    """, (identity_hmac,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- 5. Prevention & Spam Log ---

@router.post("/prevention/incidents")
def record_incident_endpoint(req: SpamIncidentRequest):
    rec = record_spam_incident(
        identity_hmac=req.identity_hmac,
        sender_number=req.sender_number,
        channel=req.channel,
        category=req.category,
        spoof_suspected=req.spoof_suspected,
        campaign_summary=req.campaign_summary,
    )
    return {"success": True, "incident_id": rec.id, "reported_at": rec.reported_at}


@router.get("/prevention/incidents")
def list_incidents_endpoint(identity_hmac: str):
    incidents = list_spam_incidents(identity_hmac)
    campaigns = analyze_spam_campaigns(incidents)
    return {
        "incidents": [
            {
                "id": i.id,
                "sender_number": i.sender_number,
                "channel": i.channel,
                "category": i.category,
                "spoof_suspected": i.spoof_suspected,
                "campaign_summary": i.campaign_summary,
                "reported_at": i.reported_at,
            }
            for i in incidents
        ],
        "campaigns": [
            {
                "campaign_name": c.campaign_name,
                "incident_count": c.incident_count,
                "sender_numbers": c.sender_numbers,
                "channels": c.channels,
                "sample_pitches": c.sample_pitches,
                "spoof_percentage": c.spoof_percentage,
            }
            for c in campaigns
        ],
    }


@router.get("/prevention/metrics")
def get_metrics_endpoint(identity_hmac: str):
    m = calculate_metrics(identity_hmac)
    return {
        "total_exposures": m.total_exposures,
        "verified_removed": m.verified_removed,
        "pending_actions": m.pending_actions,
        "submitted_actions": m.submitted_actions,
        "action_available": m.action_available,
        "rejected_matches": m.rejected_matches,
        "active_subscriptions": m.active_subscriptions,
        "total_spam_incidents": m.total_spam_incidents,
        "removal_success_rate": m.removal_success_rate,
        "exposure_by_source": m.exposure_by_source,
        "incidents_by_category": m.incidents_by_category,
    }


@router.get("/prevention/dnd-guides")
def list_dnd_guides_endpoint():
    guides = get_all_dnd_guides()
    search_guides = get_search_removal_guides()
    return {
        "telecom_guides": [
            {
                "country_code": g.country_code,
                "country_name": g.country_name,
                "registry_name": g.registry_name,
                "official_website": g.official_website,
                "statutory_window": g.statutory_window,
                "how_to_register": g.how_to_register,
                "carrier_spam_forwarding_code": g.carrier_spam_forwarding_code,
                "carrier_forwarding_instructions": g.carrier_forwarding_instructions,
                "how_to_file_complaint": g.how_to_file_complaint,
                "legal_basis": g.legal_basis,
            }
            for g in guides
        ],
        "search_removal_guides": [
            {
                "engine": sg.engine,
                "workflow_name": sg.workflow_name,
                "portal_url": sg.portal_url,
                "applicability": sg.applicability,
                "prerequisites": sg.prerequisites,
                "steps": sg.steps,
                "estimated_turnaround": sg.estimated_turnaround,
            }
            for sg in search_guides
        ],
    }


# --- 6. Privacy & Purge ---

@router.post("/privacy/purge", response_model=PurgeResponse)
def purge_endpoint():
    purge_all_data()
    return PurgeResponse(
        success=True,
        message="Cryptographic purge complete. All database tables and HMAC keys have been zero-wiped and reset.",
        purged_at=utc_now_iso(),
    )


@router.get("/privacy/export")
def export_audit_endpoint(identity_hmac: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM identities WHERE hmac_id = ?", (identity_hmac,))
    identity = cursor.fetchone()
    if not identity:
        conn.close()
        raise HTTPException(status_code=404, detail="Identity not found.")

    cursor.execute("""
        SELECT e.url, e.domain, e.title, e.match_type, e.confidence, e.snippet, e.discovered_at,
               r.status as remediation_status, r.submission_ref, r.verified_at, r.notes
        FROM exposures e
        LEFT JOIN remediation_actions r ON r.exposure_id = e.id
        WHERE e.identity_hmac = ?
    """, (identity_hmac,))
    exposures = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM subscriptions WHERE identity_hmac = ?", (identity_hmac,))
    subscriptions = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM spam_incidents WHERE identity_hmac = ?", (identity_hmac,))
    incidents = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT id, action_id, from_state, to_state, evidence_type, evidence_notes, created_at
        FROM action_audit_log
        WHERE identity_hmac = ?
        ORDER BY created_at ASC
    """, (identity_hmac,))
    audit_trail = [dict(r) for r in cursor.fetchall()]
    conn.close()

    metrics = calculate_metrics(identity_hmac)

    return {
        "report_title": "NumberShield Privacy Audit & Exposure Report",
        "exported_at": utc_now_iso(),
        "masked_phone": identity["masked_phone"],
        "identity_hmac": identity["hmac_id"],
        "telephony_metadata": {
            "country_code": identity["country_code"],
            "carrier_name": identity["carrier_name"],
            "line_type": identity["line_type"],
        },
        "metrics": {
            "total_exposures": metrics.total_exposures,
            "verified_removed": metrics.verified_removed,
            "submitted_actions": metrics.submitted_actions,
            "action_available": metrics.action_available,
            "removal_success_rate": f"{metrics.removal_success_rate}%",
        },
        "exposures": exposures,
        "subscriptions": subscriptions,
        "spam_incidents": incidents,
        "audit_trail": audit_trail,
    }


# --- 7. Synthetic Demo Scenario Loader ---

@router.post("/demo/synthetic")
def load_synthetic_scenario_endpoint():
    """Loads a realistic synthetic scenario for testing and verification without using real data."""
    init_db()
    # Use standard fictional number
    synthetic_phone = "+14155552671"
    norm = parse_and_normalize(synthetic_phone, "US")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = utc_now_iso()

    # Identity
    cursor.execute("""
        INSERT INTO identities (id, hmac_id, masked_phone, country_code, carrier_name, line_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hmac_id) DO NOTHING
    """, (
        str(uuid.uuid4()),
        norm.hmac_id,
        norm.masked_display,
        "1",
        "Pacific Bell (Fictional)",
        "MOBILE",
        now_iso,
    ))

    # Synthetic Exposures across data brokers & search
    fixtures = [
        (
            "fastpeoplesearch",
            "https://www.fastpeoplesearch.com/p/synthetic-jane-doe",
            "fastpeoplesearch.com",
            "Jane Doe - (415) 555-2671 - San Francisco, CA | FastPeopleSearch",
            "EXACT",
            1.0,
            "...Phone Numbers: (415) 555-2671 (Current Mobile) | Past Addresses: Market St, SF...",
            "SUBMITTED",
            "https://www.fastpeoplesearch.com/removal",
            "FPS-REF-89412",
            "Submitted removal form; waiting on 48h confirmation.",
        ),
        (
            "truepeoplesearch",
            "https://www.truepeoplesearch.com/find/person/px8924192",
            "truepeoplesearch.com",
            "Jane Doe Phone & Address - San Francisco | TruePeopleSearch",
            "EXACT",
            1.0,
            "...Primary Contact: +1 415-555-2671 Wireless line...",
            "VERIFIED_REMOVED",
            "https://www.truepeoplesearch.com/removal",
            "TPS-CONF-2041",
            "Rescan verified HTTP 404. Profile successfully suppressed.",
        ),
        (
            "whitepages",
            "https://www.whitepages.com/name/Jane-Doe/San-Francisco-CA/102941",
            "whitepages.com",
            "Jane Doe in San Francisco, CA | Whitepages Record",
            "EXACT",
            0.95,
            "...Landline/Mobile: 415-555-2671...",
            "ACTION_AVAILABLE",
            "https://www.whitepages.com/suppression-requests",
            None,
            "Official suppression portal available.",
        ),
        (
            "github",
            "https://github.com/synthetic-user/test-repo/blob/main/config.sample.env",
            "github.com",
            "synthetic-user/test-repo config.sample.env",
            "EXACT",
            0.9,
            "SUPPORT_CONTACT_PHONE=+14155552671\nALERT_SMS_GATEWAY=true",
            "ACTION_AVAILABLE",
            "https://support.github.com/contact/private-information",
            None,
            "Found hardcoded in open-source repository commit.",
        ),
        (
            "generic_web",
            "https://example-classifieds-archive.org/posts/84210",
            "example-classifieds-archive.org",
            "Moving Sale Furniture - 2024 Archive",
            "PROBABLE",
            0.8,
            "Call or text 415.555.2671 for pickup details. Cash only.",
            "DISCOVERED",
            None,
            None,
            "Public forum archive mention.",
        ),
    ]

    for source_id, url, domain, title, match_type, conf, snippet, status, rem_url, sub_ref, notes in fixtures:
        cursor.execute("SELECT id FROM exposures WHERE identity_hmac = ? AND url = ?", (norm.hmac_id, url))
        row = cursor.fetchone()
        if row:
            exp_id = row[0]
            cursor.execute(
                "UPDATE exposures SET last_checked_at = ?, snippet = ?, confidence = ? WHERE id = ?",
                (now_iso, snippet, conf, exp_id),
            )
        else:
            exp_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO exposures (
                    id, identity_hmac, source_id, url, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (exp_id, norm.hmac_id, source_id, url, domain, title, match_type, conf, snippet, now_iso, now_iso))

        cursor.execute("SELECT id FROM remediation_actions WHERE exposure_id = ?", (exp_id,))
        act_row = cursor.fetchone()
        if act_row:
            cursor.execute("""
                UPDATE remediation_actions
                SET status = ?, official_url = ?, submission_ref = ?, notes = ?, updated_at = ?
                WHERE id = ?
            """, (status, rem_url, sub_ref, notes, now_iso, act_row[0]))
        else:
            act_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO remediation_actions (
                    id, exposure_id, identity_hmac, source_id, status, official_url, submission_ref, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (act_id, exp_id, norm.hmac_id, source_id, status, rem_url, sub_ref, notes, now_iso))

    # Synthetic Spam Incidents
    incidents = [
        ("18005550199", "CALL", "ROBOCALL", 1, "Your auto warranty is about to expire, press 1 to renew."),
        ("18885550144", "CALL", "ROBOCALL", 1, "Affordable Health insurance open enrollment deadline."),
        ("4155559988", "CALL", "LIVE_AGENT", 1, "Neighbor spoofing - solar energy panel sales pitch."),
        ("223344", "SMS", "MARKETING_SMS", 0, "Exclusive 50% discount coupon. Reply STOP to cancel."),
    ]
    for sender, ch, cat, spoof, pitch in incidents:
        cursor.execute("""
            INSERT INTO spam_incidents (
                id, identity_hmac, sender_number, channel, category, spoof_suspected, campaign_summary, reported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), norm.hmac_id, sender, ch, cat, spoof, pitch, now_iso))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "Synthetic scenario successfully loaded.",
        "identity_hmac": norm.hmac_id,
        "masked_phone": norm.masked_display,
        "synthetic_phone": synthetic_phone,
    }
