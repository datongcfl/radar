import unittest

from radar.capabilities import (
    CAPABILITY_API_VERSION,
    CapabilityContext,
    CapabilityDescriptor,
    CapabilityRegistry,
    CapabilityRegistrationError,
    CapabilityResult,
)


class StubCapability:
    def __init__(self, name="github", kind="source", result=None, error=None):
        self._descriptor = CapabilityDescriptor(
            name=name, kind=kind, version="1.0.0", description="test provider"
        )
        self.result = result or CapabilityResult(status="succeeded")
        self.error = error
        self.contexts = []

    @property
    def descriptor(self):
        return self._descriptor

    def execute(self, context):
        self.contexts.append(context)
        if self.error:
            raise self.error
        return self.result


class TestCapabilityRegistry(unittest.TestCase):
    def test_register_and_list_capabilities_deterministically(self):
        registry = CapabilityRegistry()
        registry.register(StubCapability("web", "source"))
        registry.register(StubCapability("pdf", "parser"))
        registry.register(StubCapability("github", "source"))
        self.assertEqual(
            [(item.kind, item.name) for item in registry.list()],
            [("parser", "pdf"), ("source", "github"), ("source", "web")],
        )
        self.assertEqual([x.name for x in registry.list("source")], ["github", "web"])

    def test_duplicate_registration_is_rejected(self):
        registry = CapabilityRegistry()
        registry.register(StubCapability())
        with self.assertRaises(CapabilityRegistrationError):
            registry.register(StubCapability())

    def test_incompatible_api_version_is_rejected(self):
        with self.assertRaises(CapabilityRegistrationError):
            CapabilityDescriptor("bad", "source", "1.0", api_version=99)

    def test_capability_contract_is_required(self):
        with self.assertRaises(CapabilityRegistrationError):
            CapabilityRegistry().register(object())

    def test_ambiguous_names_require_kind(self):
        registry = CapabilityRegistry()
        registry.register(StubCapability("common", "source"))
        registry.register(StubCapability("common", "parser"))
        with self.assertRaises(ValueError):
            registry.get("common")
        self.assertEqual(registry.get("common", "parser").descriptor.kind, "parser")

    def test_execute_passes_explicit_context(self):
        registry = CapabilityRegistry()
        capability = StubCapability(result=CapabilityResult(
            status="partial", records=({"asset_id": "ast_1"},),
            warnings=({"code": "rate_limited"},),
        ))
        registry.register(capability)
        context = CapabilityContext(
            operation="discover", workspace_id="ws_demo",
            inputs={"query": "procurement"}, parameters={"limit": 5},
        )
        result = registry.execute("github", context, kind="source")
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.records[0]["asset_id"], "ast_1")
        self.assertIs(capability.contexts[0], context)

    def test_missing_capability_is_explicitly_unavailable(self):
        result = CapabilityRegistry().execute(
            "pdf", CapabilityContext(operation="parse"), kind="parser"
        )
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.warnings[0]["code"], "capability_not_registered")

    def test_provider_exception_is_isolated_without_leaking_message(self):
        registry = CapabilityRegistry()
        registry.register(StubCapability(error=RuntimeError("token=secret-value")))
        result = registry.execute(
            "github", CapabilityContext(operation="discover"), kind="source"
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "capability_execution_failed")
        self.assertNotIn("secret-value", str(result.error))

    def test_failed_result_requires_error(self):
        with self.assertRaises(ValueError):
            CapabilityResult(status="failed")

    def test_success_result_cannot_carry_error(self):
        with self.assertRaises(ValueError):
            CapabilityResult(status="succeeded", error={"code": "bad"})

    def test_context_mappings_are_read_only(self):
        source = {"query": "before"}
        context = CapabilityContext(operation="discover", inputs=source)
        source["query"] = "after"
        self.assertEqual(context.inputs["query"], "before")
        with self.assertRaises(TypeError):
            context.inputs["query"] = "mutate"

    def test_registry_api_version_is_fixed(self):
        with self.assertRaises(CapabilityRegistrationError):
            CapabilityRegistry(api_version=CAPABILITY_API_VERSION + 1)


if __name__ == "__main__":
    unittest.main()
