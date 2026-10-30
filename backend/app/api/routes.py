"""FastAPI routes for NumberShield platform."""

import os
import uuid
from pathlib import Path
from typing import List, Optional, Set, Dict, Tuple
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from urllib.parse import urlparse

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection, init_db, purge_all_data, utc_now_iso, get_purge_impact
from backend.app.core.security import compute_phone_hmac, mask_phone_number
from backend.app.core.canonical_url import canonicalize_url
from backend.app.core.ssrf import safe_fetch_url
from backend.app.engines.discovery import parse_and_normalize, match_phone_in_text
from backend.app.engines.discovery.matcher import format_evidence_requirement, EXAMPLE_PATTERN
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
    SearchConsent,
    ProviderDisclosureItem,
    SearchPrivacyDisclosureResponse,
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
    PurgeRequest,
    PurgeStatusResponse,
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
    if req.region.upper() == "IN" or op_name or circ_desc or matched_brand or req.sender.startswith("+91"):
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
        confidence_disclaimer="Probabilistic route inference based on TRAI DLT header allocations. DLT headers indicate the licensed telecom route, but do not provide cryptographic authentication or guarantee message authenticity. Attackers can forge headers or register shell businesses.",
        statutory_deadline_info="TRAI TCCCPR 2018 Regulation 25 mandates filing UCC complaints within 72 hours (3 days) of receipt. Access providers are statutorily required to complete investigations within 7 working days, but enforcement depends on carrier verification.",
        dpdp_status_note="Under Section 6(4) and Section 12 of the DPDP Act 2023, Data Principals have statutory rights to revoke consent and demand erasure. Note: Data Protection Board of India rules and active adjudication frameworks are in the process of notification by the Central Government.",
    )



# --- 2. Discovery Engine ---

@router.get("/discovery/disclosure", response_model=SearchPrivacyDisclosureResponse)
@router.post("/discovery/disclosure", response_model=SearchPrivacyDisclosureResponse)
def get_search_disclosure_endpoint(
    phone_number: str = Query(""),
    default_region: str = Query("IN"),
):
    """Provides transparent disclosure of which external search providers receive the phone number,
    the exact query sent, data transmission mechanism, purpose, and privacy implications.
    Defaults to ASSISTED_MANUAL_SEARCH with zero external data transmission."""
    norm = parse_and_normalize(phone_number, default_region) if phone_number else None
    phone_display = norm.e164 if (norm and norm.e164) else phone_number
    masked = norm.masked_display if (norm and norm.masked_display) else mask_phone_number(phone_number)
    digits = norm.digits_only if norm else re.sub(r"\D", "", phone_number)

    providers_info = [
        ProviderDisclosureItem(
            provider_id="duckduckgo",
            provider_name="DuckDuckGo HTML",
            endpoint="https://html.duckduckgo.com/html/",
            exact_query_sent=f'"{phone_display}"',
            masked_query_preview=f'"{masked}"',
            data_transmitted="Telephone string sent via HTTPS POST in form payload.",
            purpose="Searches open web text, public classifieds, and directories for exact phone matches.",
            privacy_risk="DuckDuckGo receives your unmasked phone query in its server web access logs.",
        ),
        ProviderDisclosureItem(
            provider_id="searxng",
            provider_name="SearXNG Meta-Search",
            endpoint="http://127.0.0.1:8080/search (or configured instance)",
            exact_query_sent=f'"{phone_display}"',
            masked_query_preview=f'"{masked}"',
            data_transmitted="Telephone string sent via HTTP/HTTPS GET parameter.",
            purpose="Aggregates search indices across multiple search engines with local privacy proxying.",
            privacy_risk="SearXNG instance receives query. Local instances preserve privacy; public instances log incoming requests.",
        ),
        ProviderDisclosureItem(
            provider_id="wayback",
            provider_name="Internet Archive (Wayback CDX)",
            endpoint="https://web.archive.org/cdx/search/cdx",
            exact_query_sent=f"*{digits}*",
            masked_query_preview=f"*•••{digits[-4:] if len(digits) >= 4 else ''}*",
            data_transmitted="Wildcard URL pattern sent via HTTPS GET query.",
            purpose="Scans historical archived URL paths (pastebins, text dumps) for matching telephone digits.",
            privacy_risk="Internet Archive servers log incoming CDX search queries.",
        ),
        ProviderDisclosureItem(
            provider_id="wikimedia",
            provider_name="Wikimedia / Wikipedia API",
            endpoint="https://en.wikipedia.org/w/api.php",
            exact_query_sent=phone_display,
            masked_query_preview=masked,
            data_transmitted="Telephone string sent via HTTPS GET to MediaWiki search API.",
            purpose="Checks public Wikipedia talk pages, user profiles, and open leaks for unauthorized phone listings.",
            privacy_risk="Wikimedia Foundation server logs capture search queries.",
        ),
        ProviderDisclosureItem(
            provider_id="hackernews",
            provider_name="Hacker News (Algolia API)",
            endpoint="https://hn.algolia.com/api/v1/search",
            exact_query_sent=phone_display,
            masked_query_preview=masked,
            data_transmitted="Telephone string sent via HTTPS GET to Algolia search API.",
            purpose="Checks public Hacker News discussions, Ask HN hiring threads, and comments for exposed phone contact.",
            privacy_risk="Algolia cloud search servers log API queries.",
        ),
    ]

    return SearchPrivacyDisclosureResponse(
        identity_hmac=norm.hmac_id if norm else "",
        masked_phone=masked,
        default_mode="ASSISTED_MANUAL_SEARCH",
        notice=(
            "Privacy Notice: External search engines process queries on third-party servers. "
            "To prevent transmitting your phone number over external networks, ClearNum defaults to Assisted Manual Search, "
            "which generates site-specific dorks that you execute in your own local browser without sending data through our backend. "
            "You may explicitly authorize automated querying on a per-provider basis below."
        ),
        providers=providers_info,
    )


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

    # Enforce Privacy-First Consent Guard:
    # External providers are strictly NOT contacted unless the user explicitly opts in.
    consent_granted = False
    authorized_providers = set()
    if req.consent and req.consent.granted:
        consent_granted = True
        authorized_providers = set(req.consent.confirmed_providers) if req.consent.confirmed_providers else set(req.providers)
    elif req.external_search_consent:
        consent_granted = True
        authorized_providers = set(req.providers)

    all_provider_results: List[ProviderResult] = []
    provider_outcomes: List[ProviderOutcomeItem] = []

    if not consent_granted:
        # PRIVACY-FIRST DEFAULT: Zero external transmission without explicit consent
        for p_id in req.providers:
            provider_outcomes.append(ProviderOutcomeItem(
                provider_id=p_id,
                status="unconfigured",
                result_count=0,
                duration_ms=0,
                retryable=False,
                diagnostic="External search skipped: requires explicit user opt-in consent to protect phone privacy. Use Assisted Manual Search Dorks below.",
            ))
    else:
        # Run only authorized providers
        provider_factories = {
            "searxng": (SearXNGProvider, 12),
            "duckduckgo": (DuckDuckGoProvider, 12),
            "wikimedia": (WikimediaProvider, 10),
            "hackernews": (HackerNewsProvider, 10),
            "wayback": (WaybackProvider, 10),
        }

        for p_id in req.providers:
            if p_id in authorized_providers and p_id in provider_factories:
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
                            evidence_origin="FETCHED_PAGE",
                        ))
            except Exception:
                pass

    # Process and deduplicate results by canonical URL
    seen_canonical_in_request: Set[str] = set()
    discovered_items_by_canonical: Dict[str, DiscoveredExposureItem] = {}
    now_iso = utc_now_iso()

    for item in all_provider_results:
        raw_url = (item.url or "").strip()
        if not raw_url:
            continue

        # 1. Safe Canonicalization & Malformed URL Rejection
        canonical_url = canonicalize_url(raw_url)
        if not canonical_url:
            # Safely reject malformed, unsupported, or non-http/https URLs
            continue

        clean_url = raw_url.split("#")[0].strip()
        item_evidence_origin = getattr(item, "evidence_origin", "SEARCH_SNIPPET") or "UNKNOWN"

        # Context match evaluation with explicit evidence origin
        match_eval = match_phone_in_text(f"{item.title} {item.snippet}", norm, evidence_origin=item_evidence_origin)

        # 2. Fail safely if matcher output is missing or malformed; never invent confidence or classification
        if not match_eval or not hasattr(match_eval, "match_type"):
            continue

        # 3. Strict False-Positive Rejection:
        # Never allow rejected patterns (invoices, transaction IDs, dates, UUIDs) to become exposures
        if match_eval.match_type == "FALSE_POSITIVE" or getattr(match_eval, "match_classification", "") == "FALSE_POSITIVE":
            continue

        # 4. Non-matches: Do not silently turn matched=False into a positive match
        if not match_eval.matched:
            continue

        # 5. Valid match types only (EXACT, PROBABLE) - never promote inconclusive or weak local fragments to exposures
        if match_eval.match_type not in ("EXACT", "PROBABLE") or match_eval.match_classification == "INCONCLUSIVE":
            continue

        match_type = match_eval.match_type
        confidence = match_eval.confidence
        snippet = match_eval.snippet if match_eval.snippet else (item.snippet or item.title)

        parsed = urlparse(canonical_url)
        domain = parsed.netloc.lower().replace("www.", "")

        # Look up remediation source
        rem_source = lookup_source_by_url(canonical_url) or lookup_source_by_url(clean_url)
        source_id = rem_source.source_id if rem_source else "generic_web"
        official_removal_url = rem_source.official_removal_url if rem_source else None

        # Check deduplication within the current scan request batch:
        if canonical_url in seen_canonical_in_request:
            # Same canonical page returned by multiple providers in the same scan run
            cursor.execute("""
                SELECT id, confidence, snippet, match_type, evidence_origin, discovered_at FROM exposures
                WHERE identity_hmac = ? AND (canonical_url = ? OR url = ?)
            """, (norm.hmac_id, canonical_url, clean_url))
            existing_row = cursor.fetchone()
            if existing_row:
                exp_id = existing_row["id"]
                new_conf = max(float(existing_row["confidence"]), float(confidence))
                better_snippet = snippet if len(snippet) > len(existing_row["snippet"] or "") else existing_row["snippet"]
                best_match_type = match_type if confidence >= float(existing_row["confidence"]) else existing_row["match_type"]
                cur_orig = existing_row["evidence_origin"] or "UNKNOWN"
                promoted_orig = "FETCHED_PAGE" if item_evidence_origin == "FETCHED_PAGE" else (cur_orig if cur_orig != "UNKNOWN" else item_evidence_origin)
                cursor.execute("""
                    UPDATE exposures
                    SET last_checked_at = ?, confidence = ?, snippet = ?, match_type = ?, evidence_origin = ?
                    WHERE id = ?
                """, (now_iso, new_conf, better_snippet, best_match_type, promoted_orig, exp_id))

                # Update provider provenance in remediation_actions notes
                cursor.execute("SELECT id, notes FROM remediation_actions WHERE exposure_id = ?", (exp_id,))
                act_row = cursor.fetchone()
                if act_row:
                    cur_notes = act_row["notes"] or ""
                    p_id = item.provider_id or "search"
                    if p_id not in cur_notes:
                        updated_notes = f"{cur_notes}, {p_id}" if cur_notes else f"Discovered via {p_id} search"
                        cursor.execute("UPDATE remediation_actions SET notes = ?, updated_at = ? WHERE id = ?", (updated_notes, now_iso, act_row["id"]))

                if canonical_url in discovered_items_by_canonical:
                    item_ref = discovered_items_by_canonical[canonical_url]
                    item_ref.confidence = new_conf
                    item_ref.snippet = better_snippet
                    item_ref.last_checked_at = now_iso
            continue

        seen_canonical_in_request.add(canonical_url)

        # Check database for existing exposure by (identity_hmac, canonical_url) or fallback (identity_hmac, url)
        cursor.execute("""
            SELECT id, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
            FROM exposures
            WHERE identity_hmac = ? AND (canonical_url = ? OR url = ?)
        """, (norm.hmac_id, canonical_url, clean_url))
        existing_exp = cursor.fetchone()

        if existing_exp:
            exposure_id = existing_exp["id"]
            discovered_at = existing_exp["discovered_at"]
            # A later discovery updates last_checked_at without destroying original discovered_at evidence
            new_conf = max(float(existing_exp["confidence"]), float(confidence))
            better_snippet = snippet if len(snippet) > len(existing_exp["snippet"] or "") else existing_exp["snippet"]
            best_match_type = match_type if confidence >= float(existing_exp["confidence"]) else existing_exp["match_type"]
            cur_orig = existing_exp["evidence_origin"] or "UNKNOWN"
            promoted_orig = "FETCHED_PAGE" if item_evidence_origin == "FETCHED_PAGE" else (cur_orig if cur_orig != "UNKNOWN" else item_evidence_origin)
            cursor.execute("""
                UPDATE exposures
                SET last_checked_at = ?, canonical_url = ?, evidence_origin = ?, snippet = ?, confidence = ?, match_type = ?
                WHERE id = ?
            """, (now_iso, canonical_url, promoted_orig, better_snippet, new_conf, best_match_type, exposure_id))
            final_evidence_origin = promoted_orig
            provider_status = "RECORDED"
        else:
            exposure_id = str(uuid.uuid4())
            discovered_at = now_iso
            final_evidence_origin = item_evidence_origin
            cursor.execute("""
                INSERT INTO exposures (
                    id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exposure_id,
                norm.hmac_id,
                source_id,
                clean_url,
                canonical_url,
                final_evidence_origin,
                domain,
                item.title,
                match_type,
                confidence,
                snippet,
                discovered_at,
                now_iso,
            ))
            provider_status = "NEW"

        # Check / update remediation action and preserve provider provenance
        cursor.execute("SELECT id, status, official_url, notes FROM remediation_actions WHERE exposure_id = ?", (exposure_id,))
        act_row = cursor.fetchone()
        p_id = item.provider_id or "search"

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
                f"Discovered via {p_id} search",
                now_iso,
            ))
        else:
            rem_status = act_row["status"]
            official_removal_url = act_row["official_url"]
            cur_notes = act_row["notes"] or ""
            if p_id not in cur_notes:
                updated_notes = f"{cur_notes}, {p_id}" if cur_notes else f"Discovered via {p_id} search"
                cursor.execute("""
                    UPDATE remediation_actions
                    SET notes = ?, updated_at = ?
                    WHERE id = ?
                """, (updated_notes, now_iso, act_row["id"]))

        matched_repr = match_eval.matched_text if match_eval.matched_text else norm.masked_display
        match_class = getattr(match_eval, "match_classification", "POSSIBLE_MATCH")
        conf_expl = getattr(match_eval, "confidence_explanation", "") or "Matched target telephone number."
        is_ex = getattr(match_eval, "is_example_or_test", False)
        matched_tier = getattr(match_eval, "matched_tier", "NONE")
        verif_req = getattr(match_eval, "verification_requirement", "")

        item_obj = DiscoveredExposureItem(
            id=exposure_id,
            source_id=source_id,
            url=clean_url,
            domain=domain,
            title=item.title,
            match_type=match_type,
            confidence=confidence,
            snippet=snippet,
            discovered_at=discovered_at,
            last_checked_at=now_iso,
            remediation_status=rem_status,
            official_removal_url=official_removal_url,
            canonical_url=canonical_url,
            evidence_origin=final_evidence_origin,
            matched_representation=matched_repr,
            match_classification=match_class,
            confidence_explanation=conf_expl,
            provider_status=provider_status,
            is_example_or_test=is_ex,
            matched_tier=matched_tier,
            verification_requirement=verif_req,
        )
        discovered_items_by_canonical[canonical_url] = item_obj

    discovered_items = list(discovered_items_by_canonical.values())

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

    privacy_notice = (
        "External search executed across authorized providers."
        if consent_granted
        else "Privacy-first default: external search skipped without explicit consent. Assisted manual search dorks generated below for zero-leakage local inspection."
    )

    return ScanResponse(
        identity_hmac=norm.hmac_id,
        masked_phone=norm.masked_display,
        total_found=len(discovered_items),
        exposures=discovered_items,
        manual_dorks_count=len(dorks),
        provider_outcomes=provider_outcomes,
        scan_status=scan_status,
        consent_granted=consent_granted,
        external_search_conducted=bool(consent_granted and all_provider_results),
        privacy_notice=privacy_notice,
    )


@router.get("/discovery/exposures", response_model=List[DiscoveredExposureItem])
def list_exposures_endpoint(identity_hmac: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.source_id, e.url, e.canonical_url, e.evidence_origin, e.domain, e.title, e.match_type, e.confidence, e.snippet,
               e.discovered_at, e.last_checked_at, r.status as remediation_status, r.official_url as official_removal_url
        FROM exposures e
        LEFT JOIN remediation_actions r ON r.exposure_id = e.id
        WHERE e.identity_hmac = ?
        ORDER BY e.discovered_at DESC
    """, (identity_hmac,))
    rows = cursor.fetchall()
    conn.close()

    def _classify_stored_record(m_type: str, conf: float, ev_orig: str = "UNKNOWN", snip: str = "") -> Tuple[str, str, str, str]:
        origin_req = format_evidence_requirement(ev_orig)
        has_example = bool(EXAMPLE_PATTERN.search(snip or ""))

        if m_type == "EXACT":
            if conf <= 0.75 or has_example:
                m_class = "INCIDENTAL_MENTION"
                tier = "EXACT_CANONICAL"
                core = "Exact telephone representation appears in documentation or test fixture context."
            else:
                m_class = "CONFIRMED_MATCH"
                tier = "EXACT_CANONICAL"
                core = "Exact verified telephone representation in plausible contact context."
        elif m_type == "PROBABLE":
            if conf <= 0.75 or has_example:
                m_class = "INCIDENTAL_MENTION"
                tier = "UNFORMATTED_DIGITS"
                core = "Continuous digit sequence matching telephone length without explicit contact label."
            elif conf <= 0.80:
                m_class = "POSSIBLE_MATCH"
                tier = "UNFORMATTED_DIGITS"
                core = "Continuous digit sequence appearing alongside explicit telephone/contact keywords."
            else:
                m_class = "POSSIBLE_MATCH"
                tier = "SPACED_NATIONAL"
                core = "Spaced national telephone format matching local numbering plan."
        elif m_type == "WEAK":
            m_class = "INCONCLUSIVE"
            tier = "LOCAL_FRAGMENT"
            core = "Ambiguous local digit sequence lacking area code or explicit telephone designation."
        elif m_type == "FALSE_POSITIVE":
            m_class = "FALSE_POSITIVE"
            tier = "NONE"
            core = "Digit sequence identified as invoice, transaction ID, date, or UUID."
            return m_class, core, tier, "Candidate discarded as false positive; no exposure created."
        else:
            m_class = "INCONCLUSIVE"
            tier = "NONE"
            core = "Stored exposure record with inconclusive match status."

        full_expl = f"{core} {origin_req}"
        return m_class, full_expl, tier, origin_req

    items = []
    for r in rows:
        canon_u = r["canonical_url"] if ("canonical_url" in r.keys() and r["canonical_url"]) else (canonicalize_url(r["url"]) or r["url"])
        ev_orig = r["evidence_origin"] if ("evidence_origin" in r.keys() and r["evidence_origin"]) else "UNKNOWN"
        snip = r["snippet"] or ""
        match_class, conf_expl, tier, verif_req = _classify_stored_record(r["match_type"], float(r["confidence"]), ev_orig, snip)
        items.append(
            DiscoveredExposureItem(
                id=r["id"],
                source_id=r["source_id"],
                url=r["url"],
                domain=r["domain"],
                title=r["title"] or r["domain"],
                match_type=r["match_type"],
                confidence=r["confidence"],
                snippet=snip,
                discovered_at=r["discovered_at"],
                last_checked_at=r["last_checked_at"],
                remediation_status=r["remediation_status"] or "DISCOVERED",
                official_removal_url=r["official_removal_url"],
                canonical_url=canon_u,
                evidence_origin=ev_orig,
                matched_representation=None,
                match_classification=match_class,
                confidence_explanation=conf_expl,
                provider_status="RECORDED",
                is_example_or_test=False,
                matched_tier=tier,
                verification_requirement=verif_req,
            )
        )
    return items


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
            "capability_category": s.capability_category,
            "capability_description": s.capability_description,
            "truth_notice": s.truth_notice,
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
            capability_category=t.capability_category,
            capability_description=t.capability_description,
            truth_notice=t.truth_notice,
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

@router.get("/privacy/purge/status", response_model=PurgeStatusResponse)
def purge_status_endpoint():
    """Returns pre-purge impact metadata, record counts, and target paths."""
    impact = get_purge_impact()
    return PurgeStatusResponse(
        database_path=impact["database_path"],
        database_exists=impact["database_exists"],
        database_size_bytes=impact["database_size_bytes"],
        key_path=impact["key_path"],
        key_exists=impact["key_exists"],
        is_default_database=impact["is_default_database"],
        record_counts=impact["record_counts"],
        total_records=impact["total_records"],
        allowed_to_purge=impact["allowed_to_purge"],
        reason=impact["reason"],
        warning=impact["warning"],
    )


@router.post("/privacy/purge", response_model=PurgeResponse)
def purge_endpoint(req: PurgeRequest):
    """Executes a confirmed purge of the local database and HMAC secret key."""
    if not req.confirm or req.confirmation_code.strip() != "PURGE":
        raise HTTPException(
            status_code=400,
            detail="Purge cancelled: explicit confirmation code 'PURGE' required."
        )

    res = purge_all_data(confirmed=req.confirm, confirmation_code=req.confirmation_code)
    if not res["success"] and "Refused" in res["message"]:
        raise HTTPException(status_code=403, detail=res["message"])

    return PurgeResponse(
        success=res["success"],
        message=res["message"],
        database_path=res["database_path"],
        key_path=res["key_path"],
        tables_dropped=res["tables_dropped"],
        records_deleted=res["records_deleted"],
        key_deleted=res["key_deleted"],
        files_unlinked=res["files_unlinked"],
        errors=res["errors"],
        purged_at=res["purged_at"],
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
        canon_url = canonicalize_url(url) or url
        cursor.execute("SELECT id FROM exposures WHERE identity_hmac = ? AND (canonical_url = ? OR url = ?)", (norm.hmac_id, canon_url, url))
        row = cursor.fetchone()
        if row:
            exp_id = row[0]
            cursor.execute(
                "UPDATE exposures SET last_checked_at = ?, snippet = ?, confidence = ?, canonical_url = ? WHERE id = ?",
                (now_iso, snippet, conf, canon_url, exp_id),
            )
        else:
            exp_id = str(uuid.uuid4())
            # Assign realistic evidence origins across fixtures
            f_origin = "ARCHIVED_SNAPSHOT" if "archive" in url or "archive" in source_id else ("FETCHED_PAGE" if "github" in source_id or "pastebin" in source_id else "SEARCH_SNIPPET")
            cursor.execute("""
                INSERT INTO exposures (
                    id, identity_hmac, source_id, url, canonical_url, evidence_origin, domain, title, match_type, confidence, snippet, discovered_at, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (exp_id, norm.hmac_id, source_id, url, canon_url, f_origin, domain, title, match_type, conf, snippet, now_iso, now_iso))

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
