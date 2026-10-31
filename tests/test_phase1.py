"""Phase 1 Verification Tests: AST 2-Hop Call-Graph MCP & Crash Telemetry.

Validates that:
1. Syscall & crash telemetry accurately captures failing stack frames and exceptions.
2. AST 2-Hop engine extracts exact focal function, upstream callers, and downstream callees
   across target_app/processor.py and target_app/validators.py.
3. Model Context Protocol (MCP) server conforms strictly to tool execution specifications.
"""
import os
import sys
import unittest
from pathlib import Path

# Ensure root directory is on PYTHONPATH
WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from mcp_server.ast_graph_mcp import (
    ASTCallGraphEngine,
    SyscallTelemetryEngine,
    AutoPatchMCPServer,
)


class TestPhase1ASTAndTelemetry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = WORKSPACE_ROOT
        cls.ast_engine = ASTCallGraphEngine(str(cls.workspace))
        cls.mcp_server = AutoPatchMCPServer(str(cls.workspace))

    def test_01_syscall_telemetry_captures_runtime_crash(self):
        """Verifies that SyscallTelemetryEngine detects ZeroDivisionError and KeyError

        from the failing target_app test suite, accurately parsing stack frames.
        """
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(self.workspace))

        self.assertNotEqual(telemetry.exit_code, 0, "Failing test suite must return non-zero exit code")
        self.assertGreater(telemetry.duration_ms, 0.0)

        # Check detected exceptions
        exceptions_str = " ".join(telemetry.detected_exceptions)
        self.assertTrue(
            "ZeroDivisionError" in exceptions_str or "KeyError" in exceptions_str,
            f"Expected ZeroDivisionError or KeyError, got: {telemetry.detected_exceptions}",
        )

        # Check stack frames parsing
        self.assertGreater(len(telemetry.failing_frames), 0, "Should extract at least one stack frame")
        self.assertIsNotNone(telemetry.primary_failure_frame, "Should isolate primary failing frame")

        primary = telemetry.primary_failure_frame
        self.assertTrue(
            "processor.py" in primary.file_path or "validators.py" in primary.file_path,
            f"Primary failure frame should be in target_app, got: {primary.file_path}",
        )

    def test_02_ast_2hop_isolates_focal_and_upstream_caller(self):
        """Verifies that given the crash coordinate at calculate_discount, the AST engine:

        1. Identifies focal function calculate_discount in processor.py
        2. Discovers process_payment_order as its upstream caller
        3. Extracts the surgical source code slice without full file dumps
        """
        processor_file = str(self.workspace / "target_app" / "processor.py")
        # Line 26 is inside calculate_discount
        subgraph = self.ast_engine.extract_subgraph(
            file_path=processor_file, line_number=26, hop_depth=2
        )

        # Verify Focal Node
        self.assertEqual(subgraph.focal_node.name, "calculate_discount")
        self.assertIn("def calculate_discount", subgraph.focal_node.source_slice)
        self.assertLessEqual(subgraph.focal_node.start_line, 26)
        self.assertGreaterEqual(subgraph.focal_node.end_line, 26)

        # Verify Upstream Caller (process_payment_order invokes calculate_discount)
        upstream_names = [c.name for c in subgraph.upstream_callers]
        self.assertIn(
            "process_payment_order",
            upstream_names,
            f"Expected process_payment_order in upstream callers, got: {upstream_names}",
        )

        # Verify Module Imports are extracted
        self.assertTrue(
            any("validators" in imp for imp in subgraph.module_imports),
            f"Expected validators in imports, got: {subgraph.module_imports}",
        )

    def test_03_ast_2hop_isolates_downstream_callees_across_files(self):
        """Verifies that given line coordinate inside process_payment_order, the AST engine:

        Discovers downstream callees across multi-file boundaries (validate_order_schema,
        extract_tier_multiplier, calculate_tax_bracket in validators.py, and calculate_discount).
        """
        processor_file = str(self.workspace / "target_app" / "processor.py")
        # Line 45 is inside process_payment_order
        subgraph = self.ast_engine.extract_subgraph(
            file_path=processor_file, line_number=45, hop_depth=2
        )

        self.assertEqual(subgraph.focal_node.name, "process_payment_order")

        downstream_names = [c.name for c in subgraph.downstream_callees]
        # Must cross file boundary into validators.py
        self.assertIn("validate_order_schema", downstream_names)
        self.assertIn("extract_tier_multiplier", downstream_names)
        self.assertIn("calculate_tax_bracket", downstream_names)
        self.assertIn("calculate_discount", downstream_names)

        # Verify files of callees
        callee_files = [Path(c.file_path).name for c in subgraph.downstream_callees]
        self.assertIn("validators.py", callee_files)
        self.assertIn("processor.py", callee_files)

    def test_04_mcp_server_protocol_execution(self):
        """Verifies MCP server tool discovery and execution dispatch conformance."""
        tools = self.mcp_server.get_tool_definitions()
        tool_names = [t["name"] for t in tools]
        self.assertIn("extract_ast_subgraph", tool_names)
        self.assertIn("capture_syscall_telemetry", tool_names)

        # Test tool invocation via MCP dispatch
        args = {
            "file_path": str(self.workspace / "target_app" / "processor.py"),
            "line_number": 26,
            "hop_depth": 2,
        }
        result = self.mcp_server.execute_tool("extract_ast_subgraph", args)
        self.assertIn("focal_node", result)
        self.assertEqual(result["focal_node"]["name"], "calculate_discount")
        self.assertIn("upstream_callers", result)
        self.assertGreater(result["total_nodes_in_neighborhood"], 1)


if __name__ == "__main__":
    unittest.main()

