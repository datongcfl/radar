"""GitHub repository search exposed through the Radar source capability contract.

This adapter preserves the existing metadata-only semantics. It does not claim
that repository metadata is code/document evidence.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .adapters import collect_github
from .capabilities import (
    CapabilityContext,
    CapabilityDescriptor,
    CapabilityResult,
)


class GithubSourceCapability:
    """Adapter around the existing GitHub search implementation."""

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="github",
            kind="source",
            version="1.0.0",
            description="GitHub repository metadata discovery",
        )

    @staticmethod
    def _safe_warning(message: Any, token: Any) -> str:
        text = str(message or "GitHub query warning")[:300]
        if token:
            text = text.replace(str(token), "[REDACTED]")
        text = re.sub(
            r"(?i)(authorization\s*:\s*bearer\s+)\S+",
            r"\1[REDACTED]",
            text,
        )
        return text

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        if context.operation != "discover":
            return CapabilityResult(
                status="failed",
                error={"code": "unsupported_operation"},
            )
        pack = context.inputs.get("pack")
        if not isinstance(pack, Mapping):
            return CapabilityResult(
                status="failed",
                error={"code": "invalid_pack_input"},
            )
        limit = context.parameters.get("limit_per_query", 3)
        max_queries = context.parameters.get("max_queries", 3)
        token = context.parameters.get("token")
        if (not isinstance(limit, int) or isinstance(limit, bool)
                or not 1 <= limit <= 10):
            return CapabilityResult(
                status="failed",
                error={"code": "invalid_limit_per_query"},
            )
        if (not isinstance(max_queries, int) or isinstance(max_queries, bool)
                or not 0 <= max_queries <= 100):
            return CapabilityResult(
                status="failed",
                error={"code": "invalid_max_queries"},
            )
        if token is not None and not isinstance(token, str):
            return CapabilityResult(
                status="failed",
                error={"code": "invalid_token_type"},
            )

        try:
            records, raw_warnings = collect_github(
                pack,
                limit_per_query=limit,
                max_queries=max_queries,
                token=token,
            )
        except Exception as exc:
            return CapabilityResult(
                status="failed",
                error={
                    "code": "github_adapter_exception",
                    "exception_type": type(exc).__name__,
                },
            )

        warnings = tuple(
            {"code": "github_query_warning",
             "message": self._safe_warning(item, token)}
            for item in raw_warnings
        )
        if warnings and records:
            status = "partial"
        elif warnings:
            status = "failed"
        else:
            status = "succeeded"
        error = (
            {"code": "github_search_failed"}
            if status == "failed" else None
        )
        return CapabilityResult(
            status=status,
            records=tuple(records),
            warnings=warnings,
            error=error,
            metadata={
                "provider": "github",
                "evidence_level": "metadata",
                "records_are_repository_metadata": True,
            },
        )
