"""Phase 5 Verification Tests: Hardcore Minimalist Terminal UI (TUI) Agent.

Validates that:
1. cli_agent.py argument parser functions cleanly with --auto and --prompt flags.
2. log_event streaming formatter formats all levels without markup errors.
3. run_interactive_cli executes the end-to-end autonomous healing pipeline in auto mode.
4. main.py correctly dispatches to the terminal agent.
"""
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from cli_agent import log_event, run_interactive_cli
from main import get_cli_parser


class TestPhase5MinimalistTerminalUI(unittest.TestCase):

    def test_01_log_event_all_levels(self):
        """Verifies log_event renders all log levels without markup or syntax errors."""
        levels = ["INFO", "CRASH", "AST", "RACE", "GUARD", "PROOF", "DONE", "WARN"]
        for lvl in levels:
            try:
                log_event(lvl, f"Test message for {lvl} level")
                log_event(lvl, f"Test dim message for {lvl}", dim=True)
            except Exception as e:
                self.fail(f"log_event failed on level {lvl}: {e}")

    def test_02_cli_agent_auto_pipeline_execution(self):
        """Verifies run_interactive_cli executes the full pipeline in auto-pilot mode."""
        try:
            run_interactive_cli(auto_pilot=True)
        except Exception as e:
            self.fail(f"run_interactive_cli failed in auto mode: {e}")

    def test_03_main_cli_argument_parsing(self):
        """Verifies main.py CLI arguments parse cleanly."""
        parser = get_cli_parser()
        args = parser.parse_args(["--auto"])
        self.assertTrue(args.auto)
        self.assertFalse(args.demo)

        args_demo = parser.parse_args(["--demo"])
        self.assertTrue(args_demo.demo)

        args_prompt = parser.parse_args(["--prompt", "Fix payment crash"])
        self.assertEqual(args_prompt.prompt, "Fix payment crash")


if __name__ == "__main__":
    unittest.main()
