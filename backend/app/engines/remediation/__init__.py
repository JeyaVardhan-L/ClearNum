"""Remediation Engine package."""
from backend.app.engines.remediation.registry import (
    REMEDIATION_REGISTRY,
    RemediationSource,
    lookup_source_by_url,
    get_all_sources,
)
from backend.app.engines.remediation.lifecycle import (
    ActionState,
    validate_transition,
    normalize_state,
    get_state_color_token,
    InvalidStateTransitionError,
    EVIDENCE_RULES,
)
from backend.app.engines.remediation.templates import (
    GeneratedTemplate,
    generate_ccpa_opt_out,
    generate_gdpr_erasure,
    generate_tcpa_ftc_complaint,
    generate_trai_1909_complaint,
    generate_merchant_unsubscribe,
    generate_dpdp_act_notice,
)
from backend.app.engines.remediation.search_removal import (
    SearchRemovalGuide,
    get_search_removal_guides,
)
from backend.app.engines.remediation.dnd_guides import (
    DNDCountryGuide,
    get_dnd_guide_for_country,
    get_all_dnd_guides,
)
from backend.app.engines.remediation.india_registry import (
    INDIAN_SOURCE_INVENTORY,
    IndianSourceTarget,
    get_all_indian_sources,
    get_sources_by_category,
    get_inventory_summary,
    get_indian_source_by_id,
)
from backend.app.engines.remediation.deadlines import (
    DeadlineInfo,
    calculate_remediation_deadline,
)

__all__ = [
    "REMEDIATION_REGISTRY",
    "RemediationSource",
    "lookup_source_by_url",
    "get_all_sources",
    "INDIAN_SOURCE_INVENTORY",
    "IndianSourceTarget",
    "get_all_indian_sources",
    "get_sources_by_category",
    "get_inventory_summary",
    "get_indian_source_by_id",
    "ActionState",
    "validate_transition",
    "normalize_state",
    "get_state_color_token",
    "InvalidStateTransitionError",
    "GeneratedTemplate",
    "generate_ccpa_opt_out",
    "generate_gdpr_erasure",
    "generate_tcpa_ftc_complaint",
    "generate_trai_1909_complaint",
    "generate_merchant_unsubscribe",
    "SearchRemovalGuide",
    "get_search_removal_guides",
    "DNDCountryGuide",
    "get_dnd_guide_for_country",
    "get_all_dnd_guides",
    "DeadlineInfo",
    "calculate_remediation_deadline",
]
