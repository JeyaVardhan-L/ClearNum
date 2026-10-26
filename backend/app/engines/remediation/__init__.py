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
    get_state_color_token,
    InvalidStateTransitionError,
)
from backend.app.engines.remediation.templates import (
    GeneratedTemplate,
    generate_ccpa_opt_out,
    generate_gdpr_erasure,
    generate_tcpa_ftc_complaint,
    generate_trai_1909_complaint,
    generate_merchant_unsubscribe,
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

__all__ = [
    "REMEDIATION_REGISTRY",
    "RemediationSource",
    "lookup_source_by_url",
    "get_all_sources",
    "ActionState",
    "validate_transition",
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
]
