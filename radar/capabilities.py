"""Small, dependency-free capability contracts and registry for Radar Core.

Concrete providers are registered by an application composition root. Core never
imports provider implementations or discovers arbitrary Python modules itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional, Protocol, Tuple


CAPABILITY_API_VERSION = 1
_RESULT_STATUSES = {"succeeded", "partial", "skipped", "unavailable", "failed"}


class CapabilityError(ValueError):
    """Base error for capability contract and registry failures."""


class CapabilityRegistrationError(CapabilityError):
    """A capability cannot be registered under the current API contract."""


class CapabilityNotFoundError(CapabilityError):
    """No registered capability matches the requested identity."""


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Stable identity and compatibility declaration for one capability."""

    name: str
    kind: str
    version: str
    api_version: int = CAPABILITY_API_VERSION
    description: str = ""

    def __post_init__(self) -> None:
        for field_name in ("name", "kind", "version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise CapabilityRegistrationError(
                    "%s must be a non-empty string" % field_name
                )
        if self.api_version != CAPABILITY_API_VERSION:
            raise CapabilityRegistrationError(
                "unsupported capability API version: %r" % self.api_version
            )
        if not isinstance(self.description, str):
            raise CapabilityRegistrationError("description must be a string")


@dataclass(frozen=True)
class CapabilityContext:
    """Explicit input boundary passed from Core to a capability."""

    operation: str
    workspace_id: Optional[str] = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise CapabilityError("operation must be a non-empty string")
        if self.workspace_id is not None and (
            not isinstance(self.workspace_id, str) or not self.workspace_id.strip()
        ):
            raise CapabilityError("workspace_id must be a non-empty string or None")
        if not isinstance(self.inputs, Mapping) or not isinstance(self.parameters, Mapping):
            raise CapabilityError("inputs and parameters must be mappings")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True)
class CapabilityResult:
    """Normalized outcome; failures never masquerade as empty successful results."""

    status: str
    records: Tuple[Mapping[str, Any], ...] = ()
    warnings: Tuple[Mapping[str, Any], ...] = ()
    error: Optional[Mapping[str, Any]] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in _RESULT_STATUSES:
            raise CapabilityError("invalid capability result status: %r" % self.status)
        if self.status == "failed" and not self.error:
            raise CapabilityError("failed result requires an error object")
        if self.status != "failed" and self.error is not None:
            raise CapabilityError("only failed results may contain an error object")
        for name in ("records", "warnings"):
            value = getattr(self, name)
            if not isinstance(value, (list, tuple)):
                raise CapabilityError("%s must be a list or tuple" % name)
            if any(not isinstance(item, Mapping) for item in value):
                raise CapabilityError("%s entries must be mappings" % name)
            object.__setattr__(self, name, tuple(MappingProxyType(dict(x)) for x in value))
        if self.error is not None:
            if not isinstance(self.error, Mapping):
                raise CapabilityError("error must be a mapping")
            object.__setattr__(self, "error", MappingProxyType(dict(self.error)))
        if not isinstance(self.metadata, Mapping):
            raise CapabilityError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class Capability(Protocol):
    """Structural interface implemented by source, parser, and domain providers."""

    @property
    def descriptor(self) -> CapabilityDescriptor:
        ...

    def execute(self, context: CapabilityContext) -> CapabilityResult:
        ...


class CapabilityRegistry:
    """Explicit in-process registry; no entry-point scanning or implicit imports."""

    def __init__(self, api_version: int = CAPABILITY_API_VERSION) -> None:
        if api_version != CAPABILITY_API_VERSION:
            raise CapabilityRegistrationError(
                "registry API version %r is not supported" % api_version
            )
        self.api_version = api_version
        self._capabilities = {}

    def register(self, capability: Capability) -> None:
        descriptor = getattr(capability, "descriptor", None)
        execute = getattr(capability, "execute", None)
        if not isinstance(descriptor, CapabilityDescriptor) or not callable(execute):
            raise CapabilityRegistrationError(
                "capability must expose a CapabilityDescriptor and execute(context)"
            )
        if descriptor.api_version != self.api_version:
            raise CapabilityRegistrationError("capability API version mismatch")
        key = (descriptor.kind, descriptor.name)
        if key in self._capabilities:
            raise CapabilityRegistrationError(
                "capability already registered: %s/%s" % key
            )
        self._capabilities[key] = capability

    def get(self, name: str, kind: Optional[str] = None) -> Capability:
        matches = [
            capability for (registered_kind, registered_name), capability
            in self._capabilities.items()
            if registered_name == name and (kind is None or registered_kind == kind)
        ]
        if len(matches) != 1:
            if not matches:
                raise CapabilityNotFoundError("capability not found: %s" % name)
            raise CapabilityError(
                "capability name is ambiguous; specify kind: %s" % name
            )
        return matches[0]

    def list(self, kind: Optional[str] = None) -> Tuple[CapabilityDescriptor, ...]:
        descriptors = [
            capability.descriptor for (registered_kind, _), capability
            in self._capabilities.items()
            if kind is None or registered_kind == kind
        ]
        return tuple(sorted(descriptors, key=lambda item: (item.kind, item.name)))

    def execute(
        self,
        name: str,
        context: CapabilityContext,
        kind: Optional[str] = None,
    ) -> CapabilityResult:
        try:
            capability = self.get(name, kind=kind)
        except CapabilityNotFoundError:
            return CapabilityResult(
                status="unavailable",
                warnings=({
                    "code": "capability_not_registered",
                    "capability": name,
                },),
            )
        try:
            result = capability.execute(context)
        except Exception as exc:
            # Do not copy exception text into persisted results: it may contain secrets.
            return CapabilityResult(
                status="failed",
                error={
                    "code": "capability_execution_failed",
                    "exception_type": type(exc).__name__,
                },
            )
        if not isinstance(result, CapabilityResult):
            return CapabilityResult(
                status="failed",
                error={"code": "invalid_capability_result", "exception_type": "TypeError"},
            )
        return result
