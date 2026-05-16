"""Singapore lead-enrichment workflow implementation.

The MCP tool remains registered in `hubspot_nurtureany_server.py`; this module
keeps the SG-specific orchestration and row-shaping logic separate from the
HubSpot transport and scope facade.
"""

from __future__ import annotations

from typing import Any


def build_singapore_lead_enrichment_plan(
    slack_user_email: str,
    *,
    deps: dict[str, Any],
    owner_email: str | None = None,
    company_ids: list[str] | None = None,
    limit: int | None = None,
    batch_size: int | None = None,
    phone_stale_after_days: int | None = None,
    output_mode: str = "full",
) -> dict[str, Any]:
    """Build a review-first SG lead-enrichment plan for HubSpot companies before WhatsApp nurture."""

    country = deps["country"]
    scope = deps["caller_scope"](slack_user_email)
    if scope["kind"] == "blocked":
        return deps["blocked"]("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
    if country not in scope.get("countries", ()):
        return deps["blocked"](
            "Singapore lead enrichment requires Singapore scope.",
            deps["scope_response"](scope, []),
        )

    requested_limit = deps["bounded_int"](
        limit,
        default=deps["default_limit"],
        maximum=deps["max_limit"],
    )
    requested_batch_size = deps["bounded_int"](
        batch_size,
        default=deps["default_batch_size"],
        maximum=deps["default_batch_size"],
    )
    requested_stale_days = deps["bounded_int"](
        phone_stale_after_days,
        default=deps["phone_stale_after_days"],
        maximum=3650,
    )
    requested_output_mode = str(output_mode or "full").strip().lower()
    if requested_output_mode not in {"full", "compact"}:
        requested_output_mode = "full"
    target_owner_id, target_owner_email = deps["target_owner_id_for_scope"](scope, owner_email)
    metadata: dict[str, Any]
    skipped_company_ids: list[dict[str, str]] = []

    if company_ids:
        input_ids = [str(company_id or "").strip() for company_id in company_ids if str(company_id or "").strip()]
        selected_companies = []
        for company_id in input_ids[:requested_limit]:
            company = deps["get_company"](company_id)
            access_reason = _access_reason(company, scope, target_owner_id, deps)
            if access_reason:
                skipped_company_ids.append({"company_id": company_id, "reason": access_reason})
                continue
            selected_companies.append(company)
        metadata = {
            "total": len(input_ids),
            "requested_limit": requested_limit,
            "returned_count": len(selected_companies),
            "has_more": len(input_ids) > requested_limit,
            "truncated": len(input_ids) > requested_limit,
            "skipped_company_ids": skipped_company_ids,
            "explicit_company_ids": True,
        }
    else:
        data = deps["company_search"](
            deps["target_filters"]([country], target_owner_id),
            requested_limit,
            maximum=deps["max_limit"],
        )
        selected_companies = data.get("results", [])
        metadata = {**deps["search_metadata"](data), "explicit_company_ids": False}

    company_ids_for_contacts = [str(company.get("id") or "") for company in selected_companies if company.get("id")]
    contact_index = deps["batch_association_ids"]("companies", "contacts", company_ids_for_contacts)
    raw_contacts_by_id = {
        str(contact.get("id") or ""): contact
        for contact in deps["batch_read"](
            "contacts",
            sorted({contact_id for ids in contact_index.values() for contact_id in ids}),
            deps["contact_properties"],
        )
        if contact.get("id")
    }

    rows = []
    for company in selected_companies:
        company_id = str(company.get("id") or "")
        safe_contacts = [
            deps["safe_contact"](raw_contacts_by_id[contact_id], requested_stale_days)
            for contact_id in contact_index.get(company_id, [])
            if contact_id in raw_contacts_by_id
        ]
        rows.append(_row(company, safe_contacts, len(contact_index.get(company_id, [])), requested_stale_days, deps))

    buckets_config = deps["buckets"]
    rows.sort(
        key=lambda row: (
            buckets_config.index(row["gap_bucket"])
            if row.get("gap_bucket") in buckets_config
            else 99,
            -row.get("priority_score", 0),
            str(row.get("name") or ""),
        )
    )
    buckets = {bucket: [] for bucket in buckets_config}
    for row in rows:
        bucket_row = _bucket_row(row)
        buckets.setdefault(row["gap_bucket"], []).append(bucket_row)
        for secondary_bucket in row.get("secondary_buckets", []):
            buckets.setdefault(secondary_bucket, []).append(bucket_row)

    whatsapp_ready = [
        _whatsapp_batch_row(row)
        for row in rows
        if row.get("gap_bucket") == "nurture_ready" and not row.get("do_not_contact")
    ][:requested_batch_size]
    buckets["ready_for_whatsapp_batch"] = [_bucket_row(row) for row in rows if row.get("gap_bucket") == "nurture_ready"][
        :requested_batch_size
    ]

    account_rows = [_compact_account_row(row) for row in rows] if requested_output_mode == "compact" else rows
    answer = {
        "accounts": account_rows,
        "output_mode": requested_output_mode,
        "top_priority_accounts": [_compact_account_row(row) for row in rows[: min(10, len(rows))]],
        "buckets": buckets,
        "ready_for_whatsapp_batch": {
            "account_count": len(whatsapp_ready),
            "batch_size": requested_batch_size,
            "draft_only": True,
            "no_auto_send": True,
            "kns_framework": "Knowledge / Network / Support",
            "accounts": whatsapp_ready,
        },
        "pilot_contract": {
            "ownership_policy": "Fixed AE account ownership is unchanged; owner_email scopes the plan but never reassigns accounts.",
            "pilot_size": "Start with 20-30 priority accounts before scaling.",
            "cost_mode": "capped_effective",
            "cost_mode_policy": "Optimize for cost per usable AE handoff, not lowest cash spend. Paid steps run only when a real coverage gap remains.",
            "khai_role": "Research, classify persona, verify company/title/duplicate/source, and hand off High/Medium confidence contacts.",
            "ae_role": "Use the contact, validate commercial relevance through outreach, and update validation status within 3 working days.",
            "ae_validation_options": ["valid", "wrong_person", "left_company", "no_response", "not_attempted"],
            "definition_of_done_where_possible": [
                "1 verified decision maker",
                "1 champion/influencer or operating contact",
                "at least 3 usable contacts",
                "persona type captured",
                "source captured",
                "confidence level captured",
                "AE next action clear",
            ],
        },
        "provider_waterfall_policy": _global_provider_waterfall_policy(deps),
        "field_contract": {
            "phone_statuses": sorted(deps["phone_statuses"]),
            "phone_sources": sorted(deps["phone_sources"]),
            "truecaller_v1_policy": "Manual lookup/callability evidence only; no automated reverse lookup, scraping, or bulk enrichment.",
            "prospeo_v1_1_policy": "Prospeo is a measured paid-provider pilot candidate only; no adapter, no auto-write, no bulk export, and no raw phone in default Slack summaries.",
        },
        "source_ladder": list(deps["source_ladder"]),
        "counts": {
            "account_count": len(rows),
            "nurture_ready": len(buckets["nurture_ready"]),
            "missing_associated_contact": len(buckets["missing_associated_contact"]),
            "missing_decision_maker": len(buckets["missing_decision_maker"]),
            "missing_verified_phone": len(buckets["missing_verified_phone"]),
            "hubspot_rollup_mismatch": len(buckets["hubspot_rollup_mismatch"]),
            "needs_paid_reveal": len(buckets["needs_paid_reveal"]),
            "needs_manual_truecaller_check": len(buckets["needs_manual_truecaller_check"]),
            "ready_for_whatsapp_batch": len(whatsapp_ready),
        },
    }
    result_truncated = bool(metadata.get("truncated"))
    return {
        "answer": answer,
        "source": "HubSpot Singapore companies, associated contact buying roles, NurtureAny phone-verification fields, and review-first enrichment ladder",
        "scope": deps["scope_response"](
            scope,
            [country],
            target_owner_id,
            target_owner_email,
        ),
        **metadata,
        "confidence": "needs-check" if result_truncated or any(row.get("gap_bucket") != "nurture_ready" for row in rows) else "verified",
        "caveat": deps["coverage_caveat"](
            metadata,
            "Plan is read-only. It returns HubSpot writeback previews and WhatsApp talking points only; no HubSpot mutation, paid Lusha/Prospeo reveal, Truecaller automation, WhatsApp send, or raw HubSpot phone exposure was performed.",
        ),
    }


def _access_reason(
    company: dict[str, Any],
    scope: dict[str, Any],
    target_owner_id: str | None,
    deps: dict[str, Any],
) -> str:
    props = company.get("properties", {})
    if props.get("company_country") != deps["country"]:
        return "not_singapore_company"
    if deps["country"] not in scope.get("countries", ()):
        return "caller_missing_singapore_scope"
    company_owner_id = str(props.get("hubspot_owner_id") or "")
    if target_owner_id and company_owner_id != str(target_owner_id):
        return "outside_selected_owner_scope"
    if scope.get("kind") in {"admin", "manager"}:
        return ""
    if scope.get("kind") == "ae" and company_owner_id == str(scope.get("owner_id") or ""):
        return ""
    return "outside_caller_owner_scope"


def _row(
    company: dict[str, Any],
    safe_contacts: list[dict[str, Any]],
    associated_contact_count: int,
    phone_stale_after_days: int,
    deps: dict[str, Any],
) -> dict[str, Any]:
    props = company.get("properties", {})
    company_summary = deps["summarize_company_with_contacts"](company, safe_contacts, associated_contact_count)
    coverage = deps["coverage"](props, safe_contacts)
    phone_summary = _phone_summary(safe_contacts, phone_stale_after_days)
    slots = _stakeholder_slots(safe_contacts, deps)
    mismatch_notes = _rollup_mismatch_notes(company_summary, safe_contacts, phone_summary)
    gap_bucket, secondary_buckets = _gap_bucket(company_summary, coverage, phone_summary, mismatch_notes)
    recommended_next_source = _recommended_next_source(gap_bucket, company_summary, coverage, phone_summary, slots)
    pilot_flags = _pilot_flags(coverage, slots)
    provider_policy = _row_provider_waterfall_policy(
        gap_bucket,
        recommended_next_source,
        company_summary,
        coverage,
        phone_summary,
        secondary_buckets,
        deps,
    )
    row = {
        "company_id": company_summary.get("company_id"),
        "hubspot_scoped": True,
        "scope_source": deps["scope_source"],
        "name": company_summary.get("name"),
        "domain": company_summary.get("domain"),
        "domain_source": company_summary.get("domain_source"),
        "domain_required_for_exa": recommended_next_source == "exa_people_candidate_discovery",
        "domain_warning": ""
        if company_summary.get("domain")
        else "HubSpot domain and website are both empty; Exa input needs a manual domain before people-candidate search.",
        "country": company_summary.get("country"),
        "owner_id": company_summary.get("owner_id"),
        "owner_email": company_summary.get("owner_email"),
        "owner_name": company_summary.get("owner_name"),
        "is_target_account": str(props.get("hs_is_target_account") or "").strip().lower() == "true",
        "account_status": company_summary.get("account_status"),
        "industry": company_summary.get("industry"),
        "headcount": company_summary.get("headcount"),
        "current_tools": company_summary.get("current_tools"),
        "associated_contact_count": associated_contact_count,
        "verified_decision_maker_count": coverage.get("verified_decision_maker_count"),
        "role_inferred_decision_maker_candidate_count": coverage.get("role_inferred_decision_maker_candidate_count"),
        "usable_contact_count": coverage.get("usable_contact_count"),
        "minimum_ready_state": {
            "has_associated_contact": associated_contact_count >= 1,
            "has_verified_decision_maker": coverage.get("verified_decision_maker_count", 0) >= 1,
            "has_verified_phone": phone_summary.get("verified_phone_count", 0) >= 1,
        },
        "preferred_sg_ready_state": {
            "has_distinct_decision_maker_and_operating_contact": slots.get("distinct_contact_slots"),
            "has_champion_influencer_or_operating_contact": bool(slots.get("champion_influencer")),
            "has_three_usable_contacts_where_possible": coverage.get("usable_contact_count", 0) >= 3,
        },
        "stakeholder_slots": slots,
        "ranked_people_candidates": _rank_people_candidates(safe_contacts, deps),
        "phone_verification_summary": phone_summary,
        "hubspot_mismatch_notes": mismatch_notes,
        "pilot_flags": pilot_flags,
        "gap_bucket": gap_bucket,
        "secondary_buckets": secondary_buckets,
        "recommended_next_source": recommended_next_source,
        "provider_waterfall_policy": provider_policy,
        "recommended_next_action": _next_action(gap_bucket, recommended_next_source, pilot_flags),
        "hubspot_writeback_preview": _writeback_preview(company_summary, slots, phone_summary, gap_bucket),
        "handoff_note": _handoff_note(company_summary, gap_bucket, recommended_next_source, pilot_flags, deps),
        "whatsapp_readiness": {
            "ready": gap_bucket == "nurture_ready",
            "draft_only": True,
            "no_auto_send": True,
        },
        "confidence": "needs-check" if gap_bucket != "nurture_ready" or pilot_flags else "verified",
        **deps["score_company"](company_summary),
    }
    return row


def _global_provider_waterfall_policy(deps: dict[str, Any]) -> dict[str, Any]:
    return {
        "cost_mode": "capped_effective",
        "optimization_target": "lowest reasonable cost per usable AE outcome, not lowest possible spend",
        "pilot_budget_default": "under_100_usd_monthly_unless_changed",
        "run_rules": [
            "Use HubSpot and existing activity/history before any external provider.",
            "Use Tavily public research for company, careers, and SG job-board signals before paid contact reveal.",
            "Use Exa for public people candidates when stakeholder coverage is still missing.",
            "Use Lusha and Prospeo in a controlled parallel pilot only when a real paid contact-data gap remains.",
            "Stop once minimum readiness is met: associated contact, verified decision maker, and fresh called_connected phone verification.",
            "Provider candidates never count as verified decision makers or verified phones until HubSpot/call verification rules pass.",
        ],
        "provider_jobs": list(deps["provider_jobs"]),
        "paid_parallel_test": {
            "providers": ["lusha", "prospeo"],
            "status": "pilot_contract_only",
            "requires": [
                "scoped HubSpot company IDs",
                "explicit approval marker before reveal",
                "cost or credit report",
                "selected contacts only",
                "no raw phone in default Slack summaries",
            ],
            "prospeo_status": "V1.1 provider candidate; no MCP adapter is enabled in this change.",
        },
        "metrics_to_track": list(deps["pilot_metrics"]),
        "unbrowse_policy": "Out of scope for this workflow because the safety model avoids automated gated, social, or shadow-API access for prospect enrichment.",
    }


def _contact_sort_label(contact: dict[str, Any]) -> str:
    return " ".join(
        str(contact.get(key) or "")
        for key in ("display_name", "persona", "buying_role", "channel_fit", "contact_confidence")
    ).strip()


def _contact_confidence_rank(contact: dict[str, Any]) -> int:
    confidence = str(contact.get("contact_confidence") or "").strip().lower()
    if confidence == "high":
        return 0
    if confidence == "medium":
        return 1
    if contact.get("is_verified_decision_maker"):
        return 1
    if contact.get("is_role_inferred_decision_maker"):
        return 2
    if confidence == "low":
        return 4
    return 3


def _operating_contact_priority(contact: dict[str, Any], deps: dict[str, Any]) -> tuple[int, str]:
    text = deps["normalized_words"](_contact_sort_label(contact))
    role = str(contact.get("buying_role") or "").strip().upper()
    if "CHAMPION" in role:
        return (0, "champion")
    if "INFLUENCER" in role:
        return (1, "influencer")
    if ("hr" in text or "people" in text) and ("director" in text or "manager" in text or "head" in text):
        return (2, "hr_people")
    if ("ops" in text or "operations" in text) and ("director" in text or "manager" in text or "head" in text):
        return (3, "operations")
    if "area manager" in text:
        return (4, "area_manager")
    if "outlet manager" in text:
        return (5, "outlet_manager")
    if any(marker in text for marker in ("finance manager", "payroll manager", "admin manager")):
        return (6, "finance_payroll_admin")
    return (99, "")


def _rank_people_candidates(contacts: list[dict[str, Any]], deps: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = []
    for contact in contacts:
        priority, persona_type = _operating_contact_priority(contact, deps)
        candidate = {
            "contact_id": contact.get("contact_id"),
            "display_name": contact.get("display_name"),
            "persona": contact.get("persona"),
            "buying_role": contact.get("buying_role"),
            "persona_type": "decision_maker"
            if contact.get("is_verified_decision_maker") or contact.get("is_role_inferred_decision_maker")
            else persona_type or "associated_contact",
            "decision_maker_status": "verified"
            if contact.get("is_verified_decision_maker")
            else "needs-check"
            if contact.get("is_role_inferred_decision_maker")
            else "",
            "phone_verification_status": contact.get("phone_verification_status"),
            "phone_verification_source": contact.get("phone_verification_source"),
            "phone_verified_at": contact.get("phone_verified_at"),
            "phone_available": bool(contact.get("phone_available")),
            "is_phone_verified": bool(contact.get("is_phone_verified")),
            "contact_confidence": contact.get("contact_confidence") or "needs-check",
            "source": "HubSpot associated contact fields",
            "ae_validation_status": "not_attempted",
        }
        ranked.append(
            {
                **candidate,
                "_sort": (
                    0 if contact.get("is_verified_decision_maker") else 1 if contact.get("is_role_inferred_decision_maker") else 2,
                    priority,
                    _contact_confidence_rank(contact),
                    str(contact.get("display_name") or ""),
                ),
            }
        )
    ranked.sort(key=lambda item: item["_sort"])
    for item in ranked:
        item.pop("_sort", None)
    return ranked


def _stakeholder_slots(contacts: list[dict[str, Any]], deps: dict[str, Any]) -> dict[str, Any]:
    ranked = _rank_people_candidates(contacts, deps)
    decision_maker = next((item for item in ranked if item.get("decision_maker_status") == "verified"), None)
    if decision_maker is None:
        decision_maker = next((item for item in ranked if item.get("decision_maker_status") == "needs-check"), None)
    operating_candidates = [
        item
        for item in ranked
        if item.get("persona_type") in {"champion", "influencer", "hr_people", "operations", "area_manager", "outlet_manager", "finance_payroll_admin"}
    ]
    operating_contact = None
    if operating_candidates:
        if decision_maker:
            operating_contact = next(
                (item for item in operating_candidates if item.get("contact_id") != decision_maker.get("contact_id")),
                operating_candidates[0],
            )
        else:
            operating_contact = operating_candidates[0]
    return {
        "decision_maker": decision_maker,
        "operating_contact": operating_contact,
        "champion_influencer": operating_contact,
        "distinct_contact_slots": bool(
            decision_maker and operating_contact and decision_maker.get("contact_id") != operating_contact.get("contact_id")
        ),
    }


def _row_provider_waterfall_policy(
    gap_bucket: str,
    recommended_next_source: str,
    company_summary: dict[str, Any],
    coverage: dict[str, Any],
    phone_summary: dict[str, Any],
    secondary_buckets: list[str],
    deps: dict[str, Any],
) -> dict[str, Any]:
    paid_step_allowed = recommended_next_source == "lusha_prospeo_parallel_search_pilot" or "needs_paid_reveal" in secondary_buckets
    minimum_ready = (
        coverage.get("associated_contact_count", 0) >= 1
        and coverage.get("verified_decision_maker_count", 0) >= 1
        and phone_summary.get("verified_phone_count", 0) >= 1
    )
    return {
        "cost_mode": "capped_effective",
        "next_step": recommended_next_source,
        "why": _provider_policy_reason(
            gap_bucket,
            recommended_next_source,
            company_summary,
            coverage,
            phone_summary,
        ),
        "run_condition_met": not minimum_ready,
        "paid_step_allowed": paid_step_allowed,
        "paid_parallel_test": {
            "eligible": paid_step_allowed,
            "providers": ["lusha", "prospeo"] if paid_step_allowed else [],
            "guardrail": "Run only with approval, cost/credit reporting, selected contacts, and no raw-phone Slack summary.",
        },
        "stop_condition": "Stop paid provider work once minimum readiness is met or once AE marks the handoff not useful.",
        "verification_rule": "Provider output remains candidate evidence; verified decision maker requires hs_buying_role=DECISION_MAKER and verified phone requires called_connected within freshness window.",
        "metrics_to_track": list(deps["pilot_metrics"]),
    }


def _provider_policy_reason(
    gap_bucket: str,
    recommended_next_source: str,
    company_summary: dict[str, Any],
    coverage: dict[str, Any],
    phone_summary: dict[str, Any],
) -> str:
    if recommended_next_source == "hubspot_field_diagnostic":
        return "HubSpot fields disagree; fixing the source-of-truth record is cheaper and more accurate than prospecting more."
    if recommended_next_source == "tavily_public_company_job_board_research":
        return "The account lacks usable associated-contact coverage; use low-cost public company and job-board evidence before people/contact providers."
    if recommended_next_source == "exa_people_candidate_discovery":
        return "The account has some contact/account context but still lacks a verified decision maker; search public people candidates before contact reveal."
    if recommended_next_source == "manual_truecaller_call_outcome":
        return "A callable candidate or stale phone exists; manual callability check and call outcome are needed before spending reveal credits."
    if recommended_next_source == "lusha_prospeo_parallel_search_pilot":
        return "The account has a verified decision-maker path but lacks fresh callable phone coverage; compare paid providers only for this real gap."
    if recommended_next_source == "whatsapp_batch_draft":
        return "Minimum readiness is met; no paid enrichment is needed before draft-only nurture talking points."
    if company_summary.get("associated_contact_count", 0) < 1 or coverage.get("associated_contact_count", 0) < 1:
        return "No associated contact coverage is visible."
    if phone_summary.get("verified_phone_count", 0) < 1:
        return "Phone verification coverage is missing."
    return f"Next source follows SG enrichment gap bucket {gap_bucket}."


def _phone_summary(contacts: list[dict[str, Any]], phone_stale_after_days: int) -> dict[str, Any]:
    verified = [contact for contact in contacts if contact.get("is_phone_verified")]
    candidates = [contact for contact in contacts if contact.get("phone_available")]
    stale = [contact for contact in contacts if contact.get("phone_verification_status") == "stale"]
    truecaller_manual = [
        contact
        for contact in contacts
        if contact.get("phone_verification_source") == "truecaller_manual_lookup"
        and not contact.get("is_phone_verified")
    ]
    status_counts: dict[str, int] = {}
    for contact in contacts:
        status = str(contact.get("phone_verification_status") or "not_checked")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "verified_phone_count": len(verified),
        "phone_candidate_count": len(candidates),
        "stale_phone_count": len(stale),
        "manual_truecaller_needs_call_count": len(truecaller_manual),
        "status_counts": status_counts,
        "phone_stale_after_days": phone_stale_after_days,
        "redaction_policy": "Raw phone numbers are omitted from Slack-facing output.",
        "truecaller_policy": "truecaller_manual_lookup is candidate evidence only unless paired with called_connected phone verification status.",
    }


def _rollup_mismatch_notes(
    company_summary: dict[str, Any],
    contacts: list[dict[str, Any]],
    phone_summary: dict[str, Any],
) -> list[dict[str, str]]:
    coverage = company_summary.get("decision_maker_coverage") or {}
    notes = []
    if coverage.get("decision_maker_count_from_hubspot_property", 0) > 0 and not any(
        contact.get("is_verified_decision_maker") for contact in contacts
    ):
        notes.append(
            {
                "reason": "company_rollup_has_decision_maker_but_associated_contacts_missing_decision_maker_role",
                "field_level_reason": "HubSpot company hs_num_decision_makers > 0 but returned associated contacts do not include hs_buying_role=DECISION_MAKER.",
                "rep_action": "Fix the associated contact buying-role field if the DM exists; otherwise treat the company rollup as stale and keep prospecting.",
            }
        )
    for issue in coverage.get("issues", []):
        if issue == "company_rollup_has_decision_maker_but_no_associated_contact_returned":
            notes.append(
                {
                    "reason": issue,
                    "field_level_reason": "HubSpot company hs_num_decision_makers > 0 but no associated contacts were returned with hs_buying_role=DECISION_MAKER.",
                    "rep_action": "Fix HubSpot association/buying role if the DM exists; keep prospecting if the rollup is stale.",
                }
            )
        elif issue == "buying_role_contacts_exist_but_none_are_decision_maker":
            notes.append(
                {
                    "reason": issue,
                    "field_level_reason": "HubSpot company hs_num_contacts_with_buying_roles > 0 but returned associated contacts do not include hs_buying_role=DECISION_MAKER.",
                    "rep_action": "Check whether persona/champion/influencer was tagged instead of the actual decision-maker field.",
                }
            )
    if contacts and phone_summary.get("verified_phone_count", 0) < 1:
        notes.append(
            {
                "reason": "associated_contacts_exist_but_no_verified_phone_status",
                "field_level_reason": "Associated contacts exist, but none have nurtureany_phone_verification_status=called_connected within the freshness window.",
                "rep_action": "Verify by call/manual lookup and update NurtureAny phone verification fields after outreach.",
            }
        )
    for contact in contacts:
        if (
            contact.get("phone_verification_source") == "truecaller_manual_lookup"
            and contact.get("phone_verification_status") != "called_connected"
        ):
            notes.append(
                {
                    "reason": "truecaller_manual_lookup_not_verified_call",
                    "field_level_reason": "nurtureany_phone_verification_source=truecaller_manual_lookup without nurtureany_phone_verification_status=called_connected.",
                    "rep_action": "Treat as callable candidate only until an actual call outcome or approved verification note confirms it.",
                }
            )
            break
    return notes


def _gap_bucket(
    company_summary: dict[str, Any],
    coverage: dict[str, Any],
    phone_summary: dict[str, Any],
    mismatch_notes: list[dict[str, str]],
) -> tuple[str, list[str]]:
    secondary: list[str] = []
    if any(
        note.get("reason")
        in {
            "company_rollup_has_decision_maker_but_no_associated_contact_returned",
            "company_rollup_has_decision_maker_but_associated_contacts_missing_decision_maker_role",
            "buying_role_contacts_exist_but_none_are_decision_maker",
        }
        for note in mismatch_notes
    ):
        return "hubspot_rollup_mismatch", secondary
    if coverage.get("associated_contact_count", 0) < 1:
        return "missing_associated_contact", secondary
    if coverage.get("verified_decision_maker_count", 0) < 1:
        return "missing_decision_maker", secondary
    if phone_summary.get("verified_phone_count", 0) < 1:
        if phone_summary.get("stale_phone_count", 0):
            return "missing_verified_phone", secondary
        if phone_summary.get("manual_truecaller_needs_call_count", 0) or phone_summary.get("phone_candidate_count", 0):
            return "needs_manual_truecaller_check", secondary
        if company_summary.get("associated_contact_count", 0) >= 1:
            secondary.append("needs_paid_reveal")
        return "missing_verified_phone", secondary
    return "nurture_ready", secondary


def _recommended_next_source(
    gap_bucket: str,
    company_summary: dict[str, Any],
    coverage: dict[str, Any],
    phone_summary: dict[str, Any],
    slots: dict[str, Any],
) -> str:
    if gap_bucket == "hubspot_rollup_mismatch":
        return "hubspot_field_diagnostic"
    if gap_bucket == "missing_associated_contact":
        return "tavily_public_company_job_board_research"
    if gap_bucket == "missing_decision_maker":
        return "exa_people_candidate_discovery"
    if gap_bucket == "needs_manual_truecaller_check":
        return "manual_truecaller_call_outcome"
    if gap_bucket == "missing_verified_phone":
        if phone_summary.get("stale_phone_count", 0) or phone_summary.get("phone_candidate_count", 0):
            return "manual_truecaller_call_outcome"
        return "lusha_prospeo_parallel_search_pilot" if coverage.get("associated_contact_count", 0) else "tavily_public_company_job_board_research"
    if gap_bucket == "nurture_ready":
        return "whatsapp_batch_draft"
    return "hubspot"


def _pilot_flags(coverage: dict[str, Any], slots: dict[str, Any]) -> list[str]:
    flags = []
    if not slots.get("champion_influencer"):
        flags.append("missing_champion_influencer_or_operating_contact")
    if coverage.get("usable_contact_count", 0) < 3:
        flags.append("below_three_usable_contacts_where_possible")
    return flags


def _next_action(gap_bucket: str, recommended_next_source: str, pilot_flags: list[str]) -> str:
    if gap_bucket == "hubspot_rollup_mismatch":
        return "Fix the exact HubSpot field mismatch before prospecting more contacts."
    if gap_bucket == "missing_associated_contact":
        return "Run Tavily/public company and SG job-board research first; then classify High/Medium/Low before any HubSpot writeback."
    if gap_bucket == "missing_decision_maker":
        return "Use Exa people candidates and gatekeeper calls to verify the boss/owner/director decision maker; title inference stays needs-check."
    if gap_bucket == "needs_manual_truecaller_check":
        return "Manual Truecaller/callability check and actual call outcome before marking phone verified."
    if gap_bucket == "missing_verified_phone":
        if recommended_next_source == "lusha_prospeo_parallel_search_pilot":
            return "Run a controlled Lusha + Prospeo paid-provider pilot only with approval, then verify by actual call outcome."
        return "Find or reveal a callable number only with approval, then verify by actual call outcome."
    if pilot_flags:
        return "Ready for nurture minimums; still improve pilot coverage flags before scaling if time allows."
    return "Ready for WhatsApp talking-point drafting; no send without approval."


def _writeback_preview(
    company_summary: dict[str, Any],
    slots: dict[str, Any],
    phone_summary: dict[str, Any],
    gap_bucket: str,
) -> dict[str, Any]:
    actions = []
    decision_maker = slots.get("decision_maker") or {}
    if decision_maker and decision_maker.get("decision_maker_status") == "needs-check":
        actions.append(
            {
                "object_type": "contact",
                "contact_id": decision_maker.get("contact_id"),
                "condition": "Only after call verification confirms decision authority.",
                "properties": {"hs_buying_role": "DECISION_MAKER"},
            }
        )
    if gap_bucket in {"needs_manual_truecaller_check", "missing_verified_phone"}:
        actions.append(
            {
                "object_type": "contact",
                "condition": "Only after manual lookup/call outcome is complete; raw HubSpot phone fields stay out of this SG-plan Slack output.",
                "properties": {
                    "nurtureany_phone_verification_status": "called_connected | wrong_number | unreachable | no_answer | do_not_contact",
                    "nurtureany_phone_verified_at": "YYYY-MM-DD",
                    "nurtureany_phone_verified_by": "AE email",
                    "nurtureany_phone_verification_source": "manual_call | truecaller_manual_lookup | lusha_reveal | apollo_manual | prospeo_manual",
                    "nurtureany_phone_verification_notes": "short safe note, no raw number",
                },
            }
        )
    return {
        "will_mutate_hubspot": False,
        "company_id": company_summary.get("company_id"),
        "actions": actions,
        "phone_summary": phone_summary,
    }


def _handoff_note(
    company_summary: dict[str, Any],
    gap_bucket: str,
    recommended_next_source: str,
    pilot_flags: list[str],
    deps: dict[str, Any],
) -> str:
    flags = f" Pilot flags: {', '.join(pilot_flags)}." if pilot_flags else ""
    return deps["short_text"](
        f"{company_summary.get('name')}: {gap_bucket}; next source {recommended_next_source}. "
        "Khai researches/classifies; AE validates through outreach within 3 working days."
        f"{flags}",
        320,
    )


def _bucket_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": row.get("company_id"),
        "name": row.get("name"),
        "domain": row.get("domain"),
        "owner_email": row.get("owner_email"),
        "gap_bucket": row.get("gap_bucket"),
        "recommended_next_source": row.get("recommended_next_source"),
        "associated_contact_count": row.get("associated_contact_count"),
        "verified_decision_maker_count": row.get("verified_decision_maker_count"),
        "verified_phone_count": row.get("phone_verification_summary", {}).get("verified_phone_count"),
        "provider_waterfall_next_step": (row.get("provider_waterfall_policy") or {}).get("next_step"),
        "paid_step_allowed": (row.get("provider_waterfall_policy") or {}).get("paid_step_allowed", False),
        "pilot_flags": row.get("pilot_flags", []),
    }


def _compact_account_row(row: dict[str, Any]) -> dict[str, Any]:
    phone_summary = row.get("phone_verification_summary") or {}
    return {
        "company_id": row.get("company_id"),
        "name": row.get("name"),
        "domain": row.get("domain"),
        "domain_source": row.get("domain_source"),
        "domain_warning": row.get("domain_warning"),
        "owner_email": row.get("owner_email"),
        "gap_bucket": row.get("gap_bucket"),
        "secondary_buckets": row.get("secondary_buckets", []),
        "associated_contact_count": row.get("associated_contact_count"),
        "verified_decision_maker_count": row.get("verified_decision_maker_count"),
        "usable_contact_count": row.get("usable_contact_count"),
        "verified_phone_count": phone_summary.get("verified_phone_count"),
        "stale_phone_count": phone_summary.get("stale_phone_count"),
        "recommended_next_source": row.get("recommended_next_source"),
        "provider_waterfall_policy": row.get("provider_waterfall_policy"),
        "hubspot_mismatch_notes": row.get("hubspot_mismatch_notes", [])[:2],
        "pilot_flags": row.get("pilot_flags", []),
        "handoff_note": row.get("handoff_note"),
        "whatsapp_ready": (row.get("whatsapp_readiness") or {}).get("ready", False),
        "confidence": row.get("confidence"),
    }


def _whatsapp_batch_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": row.get("company_id"),
        "name": row.get("name"),
        "owner_email": row.get("owner_email"),
        "draft_only": True,
        "no_auto_send": True,
        "talking_points": [
            {
                "kns": "Knowledge",
                "angle": "salary benchmarking and labour-market context for F&B/retail teams",
                "question": "Worth comparing how your team is thinking about wage pressure this month?",
            },
            {
                "kns": "Network",
                "angle": "event invites, peer matching, talent matching, future-speaker sourcing, and collaboration opportunities",
                "question": "Want me to suggest a few relevant events, peers, hiring/talent matches, future speakers, or collaboration angles for AE review?",
            },
            {
                "kns": "Support",
                "angle": "speaker, venue, simple-meal, or outlet-support asks when the opportunity is real",
                "question": "Would it be useful if we support your venue, feature you as a speaker, or bring a small peer meal to your outlet?",
            },
        ],
        "name_drop_policy": "Use find_sales_case_studies or approved material registry before naming a customer; otherwise keep the angle generic.",
    }
