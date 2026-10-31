"""AutoPatch-Kernel - Core Command Line Interface & Demo Runner.

Supports:
  --demo   : Executes the full end-to-end autonomous healing pipeline with rich terminal observability.
  --ui     : Launches the Cyber-Systems 'Flight Deck' FastAPI web dashboard on http://localhost:8000.
  --voice  : Dispatches a simulated Meta Muse Voice incident command.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add workspace root to path
WORKSPACE_ROOT = Path(__file__).parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from engine.tournament_kernel import PatchTournamentKernel
from engine.worktree_manager import WorktreeManager
from github_integration.pr_generator import PRGenerator
from mcp_server.ast_graph_mcp import ASTCallGraphEngine, SyscallTelemetryEngine
from verification.z3_verifier import Z3TheoremProver


console = Console()


def run_full_pipeline_demo():
    """Executes the complete autonomous self-healing tournament in the terminal."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]⚡ AutoPatch-Kernel: Autonomous Self-Healing Codebase Agent[/bold cyan]\n"
            "[dim]Powered by Model Context Protocol (MCP), Meta Muse Spark 1.3, & Microsoft Z3 SMT[/dim]",
            border_style="cyan",
        )
    )
    console.print()

    # Step 1: Kernel Syscall & Crash Telemetry
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="[yellow]Capturing runtime crash telemetry via subprocess...", total=None)
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(WORKSPACE_ROOT))

    console.print(f"[bold red]💥 Runtime Failure Captured:[/bold red] Exit code {telemetry.exit_code}")
    for exc in telemetry.detected_exceptions:
        console.print(f"  [red]▶ {exc}[/red]")
    if telemetry.primary_failure_frame:
        pf = telemetry.primary_failure_frame
        console.print(f"  [dim]Primary Frame: {pf.file_path}:{pf.line_number} in {pf.function_name}()[/dim]")
    console.print()

    # Step 2: AST 2-Hop MCP Neighborhood Extraction
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="[yellow]Querying AST Call-Graph MCP Server for 2-hop neighborhood...", total=None)
        ast_engine = ASTCallGraphEngine(str(WORKSPACE_ROOT))
        subgraph = ast_engine.extract_subgraph(str(WORKSPACE_ROOT / "target_app" / "processor.py"), line_number=26)

    console.print(f"[bold green]🔍 AST 2-Hop Neighborhood Sliced (MCP):[/bold green]")
    console.print(f"  [cyan]Focal Function:[/cyan] {subgraph.focal_node.name} (Lines {subgraph.focal_node.start_line}-{subgraph.focal_node.end_line})")
    console.print(f"  [cyan]Upstream Callers:[/cyan] {[c.name for c in subgraph.upstream_callers]}")
    console.print(f"  [cyan]Downstream Callees:[/cyan] {[c.name for c in subgraph.downstream_callees]}")
    console.print()

    # Step 3: Speculative Parallel Git Worktree Racing
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="[yellow]Spawning 3 parallel Git worktrees (.autopatch/worktrees/)...", total=None)
        wt_manager = WorktreeManager(str(WORKSPACE_ROOT))
        race_res = wt_manager.race_competing_hypotheses(subgraph, telemetry)

    console.print(f"[bold magenta]🏎️ 3-Way Parallel Git Worktree Race Complete ({race_res.total_race_duration_ms}ms):[/bold magenta]")
    for o in race_res.outcomes:
        status_text = "[bold green]PASSED[/bold green]" if (o.sandbox_result and o.sandbox_result.tests_passed) else "[bold red]FAILED/BLOCKED[/bold red]"
        console.print(f"  • [bold]{o.worktree_name}[/bold]: {status_text} | Strategy: {o.strategy_id}")
        if o.sandbox_result and o.sandbox_result.lucky_pass_blocked:
            console.print(f"    [bold red]↳ Read-Only Guardrail:[/bold red] Caught test tampering in {o.sandbox_result.tampered_test_files}")
    console.print()

    # Step 4: Microsoft Z3 SMT Formal Theorem Prover
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="[yellow]Formally proving mathematical invariants via Microsoft Z3 SMT solver...", total=None)
        z3_res = Z3TheoremProver.verify_patched_discount_logic()

    console.print(f"[bold cyan]🛡️ Microsoft Z3 SMT Verification Certificate:[/bold cyan]")
    console.print(f"  [cyan]Verdict:[/cyan] [bold green]{z3_res.verdict}[/bold green]")
    console.print(f"  [cyan]Certificate ID:[/cyan] {z3_res.certificate.certificate_id}")
    console.print(f"  [cyan]SHA-256 Digest:[/cyan] [dim]{z3_res.certificate.sha256_digest}[/dim]")
    console.print(f"  [dim]{z3_res.proof_summary}[/dim]")
    console.print()

    # Step 5: Deterministic Patch Tournament Kernel
    tournament_res = PatchTournamentKernel.evaluate_tournament(race_res, z3_res)

    table = Table(title="🏆 5-Pillar Patch Tournament Scorecard (100 Points)", border_style="cyan")
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Worktree", style="cyan")
    table.add_column("Strategy Hypothesis", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Score", justify="right", style="bold green")

    for card in tournament_res.scorecards:
        b = card.breakdown
        st = "[green]WINNER[/green]" if card.is_winner else ("[red]DISQUALIFIED[/red]" if b.disqualified else "[yellow]PENALIZED[/yellow]")
        table.add_row(
            str(card.rank),
            card.worktree_name,
            card.hypothesis_name,
            st,
            f"{b.total_score}/100",
        )
    console.print(table)
    console.print()

    # Step 6: Flight Recorder PR Generation
    pr_gen = PRGenerator(str(WORKSPACE_ROOT))
    flight_pr = pr_gen.write_pr_artifact(tournament_res)

    console.print(
        Panel(
            f"[bold green]✨ Flight Recorder PR Generated Successfully![/bold green]\n"
            f"[white]Artifact Path:[/white] [cyan]{flight_pr.artifact_path}[/cyan]\n"
            f"[white]Winning Strategy:[/white] [bold]{flight_pr.winning_strategy}[/bold]\n"
            f"[white]Z3 Proof Certificate:[/white] [dim]{flight_pr.z3_certificate_digest}[/dim]",
            border_style="green",
        )
    )
    console.print()


def start_dashboard_server(host: str = "127.0.0.1", port: int = 8000):
    """Starts the FastAPI Flight Deck dashboard via Uvicorn."""
    import uvicorn
    console.print(
        Panel.fit(
            f"[bold cyan]🚀 Launching AutoPatch-Kernel Flight Deck[/bold cyan]\n"
            f"[green]Dashboard URL:[/green] [link=http://{host}:{port}]http://{host}:{port}[/link]\n"
            f"[dim]Press CTRL+C to terminate the server[/dim]",
            border_style="cyan",
        )
    )
    uvicorn.run("dashboard.app:app", host=host, port=port, reload=False)


def get_cli_parser() -> argparse.ArgumentParser:
    """Builds and returns the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="AutoPatch-Kernel: Autonomous Self-Healing Codebase Agent Built on MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run end-to-end self-healing tournament in rich terminal mode",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch live FastAPI cyber-systems web dashboard on http://localhost:8000",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help="Simulate spoken Meta Muse Voice incident command",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the web dashboard (default: 8000)",
    )
    return parser


def main():
    parser = get_cli_parser()
    args = parser.parse_args()

    if args.ui:
        start_dashboard_server(port=args.port)
    elif args.voice:
        console.print(f"[bold magenta]🎙️ Muse Voice Transcribe Input:[/bold magenta] '{args.voice}'")
        run_full_pipeline_demo()
    else:
        # Default action is running the terminal demo
        run_full_pipeline_demo()


if __name__ == "__main__":
    main()
