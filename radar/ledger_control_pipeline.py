"""Orchestrate provenance-backed ledger controls in a deterministic pipeline."""
from __future__ import annotations

from typing import Any, Iterable

from .ledger_effects import LedgerEffectError, validate_ledger_effects
from .ledger_aggregator import LedgerAggregationError, aggregate_ledger_effects
from .ledger_vouchers import LedgerVoucherError, validate_gl_vouchers
from .ledger_reconciliation import (
    LedgerReconciliationError, reconcile_inventory_gl,
)


class LedgerControlPipelineError(ValueError):
    """Invalid input or failed stage in the ledger control pipeline."""


def run_ledger_control_pipeline(
        ledger_effects: Iterable[dict[str, Any]],
        evidence_records: Iterable[dict[str, Any]],
        extraction_manifests: Iterable[dict[str, Any]],
        aggregation_rules: Iterable[dict[str, Any]],
        reconciliation_tolerance: Any = "0.01",
        voucher_tolerance: Any = "0") -> dict[str, Any]:
    """Run validation -> voucher controls -> aggregation -> reconciliation.

    The function deliberately accepts explicit source records, extraction
    manifests, and aggregation rules. It does not infer missing periods,
    account mappings, valuation, or manifest completeness. Every downstream
    stage receives only ledger rows accepted by the provenance validator.
    """
    rows = list(ledger_effects)
    evidence = list(evidence_records)
    manifests = list(extraction_manifests)
    rules = list(aggregation_rules)

    try:
        validation = validate_ledger_effects(rows, evidence)
    except LedgerEffectError as exc:
        raise LedgerControlPipelineError("ledger effect validation failed: %s" % exc)

    accepted = validation["ledger_effects"]
    accepted_gl = [row for row in accepted if row["ledger_kind"] == "general_ledger"]
    try:
        vouchers = validate_gl_vouchers(
            accepted_gl, manifests, evidence, tolerance=voucher_tolerance)
    except LedgerVoucherError as exc:
        raise LedgerControlPipelineError("GL voucher validation failed: %s" % exc)

    try:
        aggregations = aggregate_ledger_effects(accepted, evidence, rules)
    except LedgerAggregationError as exc:
        raise LedgerControlPipelineError("ledger aggregation failed: %s" % exc)

    stock_groups = [group for result in aggregations for group in result["results"]
                    if group["ledger_kind"] == "stock"]
    gl_groups = [group for result in aggregations for group in result["results"]
                 if group["ledger_kind"] == "general_ledger"]
    try:
        reconciliation = reconcile_inventory_gl(
            stock_groups, gl_groups, tolerance=reconciliation_tolerance)
    except LedgerReconciliationError as exc:
        raise LedgerControlPipelineError("inventory/GL reconciliation failed: %s" % exc)

    return {
        "schema_version": 1,
        "validation": validation,
        "vouchers": vouchers,
        "aggregations": aggregations,
        "reconciliation": reconciliation,
        "summary": {
            "ledger_effects_accepted": validation["summary"]["accepted"],
            "ledger_effects_skipped": validation["summary"]["skipped"],
            "vouchers_balanced": vouchers["summary"]["balanced"],
            "vouchers_unbalanced": vouchers["summary"]["unbalanced"],
            "vouchers_unresolved": vouchers["summary"]["unresolved"],
            "aggregates": sum(item["summary"]["groups"] for item in aggregations),
            "reconciliations_matched": reconciliation["summary"]["matched"],
            "reconciliations_mismatched": reconciliation["summary"]["mismatched"],
            "reconciliations_unresolved": reconciliation["summary"]["unresolved"],
        },
        "policy": {
            "stages_run_in_order": [
                "ledger_effect_validation", "voucher_completeness_and_balance",
                "ledger_aggregation", "inventory_gl_reconciliation"],
            "downstream_stages_receive_only_accepted_ledger_effects": True,
            "missing_source_facts_are_never_inferred": True,
            "voucher_balance_requires_explicit_complete_extract_manifest": True,
            "account_mapping_and_aggregation_dimensions_are_explicit": True,
            "computed_results_are_not_business_assessments": True,
        },
    }
