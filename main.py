"""AutoPatch-Kernel - Hardcore Developer Terminal Entry Point.

100% CLI / TUI Autonomous Self-Healing Codebase Agent built on Model Context Protocol (MCP).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Path setup
WORKSPACE_ROOT = Path(__file__).parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from cli_agent import run_interactive_cli


def get_cli_parser() -> argparse.ArgumentParser:
    """CLI Argument Parser for AutoPatch-Kernel."""
    parser = argparse.ArgumentParser(
        description="AutoPatch-Kernel: Autonomous Self-Healing Codebase Agent Built on MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run without interactive prompt (auto-pilot mode)",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Custom bug description to triage and heal",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Alias for auto-pilot demo execution",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the live web dashboard on http://127.0.0.1:8050",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port for the web dashboard (default: 8050)",
    )
    return parser


def main():
    parser = get_cli_parser()
    args = parser.parse_args()

    if args.ui:
        import uvicorn
        print(f"\n[AutoPatch-Kernel] Launching web dashboard on http://127.0.0.1:{args.port}\n")
        uvicorn.run("dashboard.app:app", host="127.0.0.1", port=args.port, reload=False)
    else:
        auto_mode = args.auto or args.demo
        run_interactive_cli(auto_pilot=auto_mode, prompt_override=args.prompt)


if __name__ == "__main__":
    main()
