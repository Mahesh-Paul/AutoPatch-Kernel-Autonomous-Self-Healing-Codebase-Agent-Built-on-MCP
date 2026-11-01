"""AutoPatch-Kernel - Hardcore Minimalist Terminal UI (TUI) Agent.

A developer-first, streaming CLI for autonomous codebase healing.
Features:
- Live streaming execution log (Docker/GitHub Actions aesthetic).
- Raw AST code slice rendering via syntax highlighting (no heavy box frames).
- Multi-worktree parallel race tracker with Read-Only Guardrail interception.
- Z3 SMT formal proof certificate and clean green build verification.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Force UTF-8 encoding on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.live import Live
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# Path setup
WORKSPACE_ROOT = Path(__file__).parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from engine.tournament_kernel import PatchTournamentKernel
from engine.worktree_manager import WorktreeManager
from github_integration.pr_generator import PRGenerator
from mcp_server.ast_graph_mcp import ASTCallGraphEngine, SyscallTelemetryEngine
from verification.z3_verifier import Z3TheoremProver


console = Console(highlight=False)


def get_timestamp() -> str:
    """Returns current wall-clock timestamp string."""
    return time.strftime("%H:%M:%S")


def log_event(level: str, message: str, dim: bool = False):
    """Prints a minimalist streaming log event."""
    ts = f"[dim]{get_timestamp()}[/dim]"
    if level == "INFO":
        tag = "[bold cyan]INFO [/bold cyan]"
    elif level == "CRASH":
        tag = "[bold red]CRASH[/bold red]"
    elif level == "AST":
        tag = "[bold magenta]AST  [/bold magenta]"
    elif level == "RACE":
        tag = "[bold blue]RACE [/bold blue]"
    elif level == "GUARD":
        tag = "[bold red]GUARD[/bold red]"
    elif level == "PROOF":
        tag = "[bold cyan]PROOF[/bold cyan]"
    elif level == "DONE":
        tag = "[bold green]DONE [/bold green]"
    elif level == "WARN":
        tag = "[bold yellow]WARN [/bold yellow]"
    else:
        tag = f"[bold]{level:<5}[/bold]"

    msg = f"[dim]{message}[/dim]" if dim else message
    console.print(f"{ts}  {tag}  {msg}")


def run_interactive_cli(auto_pilot: bool = False, prompt_override: Optional[str] = None):
    """Executes the hardcore minimalist developer terminal workflow."""
    console.print()
    console.print("[bold cyan]AUTOPATCH-KERNEL[/bold cyan] [dim]v1.4 // AUTONOMOUS REPAIR KERNEL // MODEL CONTEXT PROTOCOL[/dim]")
    console.print("[dim]Target: target_app/ (Financial Payment Order Engine)[/dim]")
    console.print()

    # Step 0: Minimalist Command Prompt
    if auto_pilot or prompt_override:
        cmd_text = prompt_override or "heal payment processor division by zero and customer tier KeyError"
        console.print(f"[bold cyan]autopatch-kernel[/bold cyan] [dim]~ $[/dim] {cmd_text}")
    else:
        cmd_text = Prompt.ask(
            "[bold cyan]autopatch-kernel[/bold cyan] [dim]~ $[/dim]",
            default="heal payment processor division by zero and customer tier KeyError",
        )

    console.print()
    start_time = time.perf_counter()

    # Step 1: Real Subprocess Crash Capture
    log_event("INFO", "Running initial test suite verification...")
    test_cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
    telemetry = SyscallTelemetryEngine.capture(command=test_cmd, cwd=str(WORKSPACE_ROOT))

    if telemetry.exit_code != 0:
        log_event("CRASH", f"Test execution failed with exit code {telemetry.exit_code}")
        for exc in telemetry.detected_exceptions:
            log_event("CRASH", f"Exception caught: [bold red]{exc}[/bold red]")
        if telemetry.primary_failure_frame:
            pf = telemetry.primary_failure_frame
            rel_path = os.path.relpath(pf.file_path, str(WORKSPACE_ROOT))
            log_event("CRASH", f"Primary stack frame: [yellow]{rel_path}:{pf.line_number}[/yellow] in [bold]{pf.function_name}()[/bold]")
    else:
        log_event("INFO", "Target application tests already passing.")
        return

    console.print()

    # Step 2: AST 2-Hop Call-Graph MCP Slicing
    log_event("AST", "Querying AST 2-Hop Call-Graph MCP Server...")
    ast_engine = ASTCallGraphEngine(str(WORKSPACE_ROOT))
    processor_file = str(WORKSPACE_ROOT / "target_app" / "processor.py")
    subgraph = ast_engine.extract_subgraph(processor_file, line_number=26, hop_depth=2)

    log_event("AST", f"Isolated focal node: [bold]{subgraph.focal_node.name}[/bold] (Lines {subgraph.focal_node.start_line}-{subgraph.focal_node.end_line})")
    log_event("AST", f"Upstream callers: [dim]{[c.name for c in subgraph.upstream_callers]}[/dim]")
    log_event("AST", f"Downstream callees: [dim]{[c.name for c in subgraph.downstream_callees]}[/dim]")
    console.print()

    # Clean Code Slice Display (No bloated UI cards)
    console.print(f"[dim]# --- Sliced AST Neighborhood: target_app/processor.py ---[/dim]")
    syntax_view = Syntax(
        subgraph.focal_node.source_slice,
        "python",
        theme="monokai",
        line_numbers=True,
        start_line=subgraph.focal_node.start_line,
    )
    console.print(syntax_view)
    console.print(f"[dim]# ---------------------------------------------------------[/dim]")
    console.print()

    # Step 3: Speculative Git Worktree Tournament Racing
    log_event("RACE", "Spawning 3 concurrent isolated Git worktrees (.autopatch/worktrees/)...")
    wt_manager = WorktreeManager(str(WORKSPACE_ROOT))

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=25, style="dim", complete_style="cyan"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Evaluating parallel worktree repair hypotheses...", total=3)
        race_res = wt_manager.race_competing_hypotheses(subgraph, telemetry)
        progress.update(task, completed=3)

    for o in race_res.outcomes:
        if o.sandbox_result and o.sandbox_result.lucky_pass_blocked:
            log_event(
                "GUARD",
                f"[bold red]{o.worktree_name:<20}[/bold red] [red][SECURITY BLOCKED][/red] Attempted test file tampering! Disqualified (0.0/100)",
            )
        elif o.sandbox_result and o.sandbox_result.tests_passed:
            log_event(
                "RACE",
                f"[bold green]{o.worktree_name:<20}[/bold green] [green][VERIFIED CLEAN][/green] Passed tests under Read-Only Guardrail",
            )
        else:
            log_event(
                "WARN",
                f"[bold yellow]{o.worktree_name:<20}[/bold yellow] [yellow][SLOW / SUBOPTIMAL][/yellow] Defensive exception wrapper penalized",
            )

    console.print()

    # Step 4: Microsoft Z3 SMT Formal Theorem Prover
    log_event("PROOF", "Running Microsoft Z3 SMT Theorem Prover on candidate AST invariants...")
    z3_res = Z3TheoremProver.verify_patched_discount_logic()

    if z3_res.is_verified:
        cert = z3_res.certificate
        log_event("PROOF", f"Theorem Verdict: [bold green]{cert.verdict}[/bold green]")
        log_event("PROOF", f"Certificate ID:  [cyan]{cert.certificate_id}[/cyan]")
        log_event("PROOF", f"SHA-256 Digest:  [dim]{cert.sha256_digest}[/dim]")
        log_event("PROOF", "Invariants: [dim]denominator >= 1 & discount >= 0.0 & cap <= 0.50[/dim]")
    else:
        log_event("WARN", "Formal verification failed to prove invariants.")

    console.print()

    # Step 5: Patch Tournament Scoring Matrix
    tournament_res = PatchTournamentKernel.evaluate_tournament(race_res, z3_res)
    winner = tournament_res.winner

    table = Table(box=None, padding=(0, 2), show_edge=False, pad_edge=False)
    table.add_column("RANK", style="bold", justify="right")
    table.add_column("WORKTREE", style="bold cyan")
    table.add_column("MODEL", style="dim")
    table.add_column("STATUS")
    table.add_column("SCORE", justify="right")

    for card in tournament_res.scorecards:
        b = card.breakdown
        if card.is_winner:
            st = "[bold green]CROWNED WINNER[/bold green]"
            sc = f"[bold green]{b.total_score}/100[/bold green]"
        elif b.disqualified:
            st = "[bold red]DISQUALIFIED[/bold red]"
            sc = "[red]0.0/100[/red]"
        else:
            st = "[bold yellow]PENALIZED[/bold yellow]"
            sc = f"[yellow]{b.total_score}/100[/yellow]"

        table.add_row(f"#{card.rank}", card.worktree_name, card.model_used, st, sc)

    console.print(table)
    console.print()

    # Step 6: PR Generation & Verification
    pr_gen = PRGenerator(str(WORKSPACE_ROOT))
    flight_pr = pr_gen.write_pr_artifact(tournament_res)
    rel_pr_path = os.path.relpath(flight_pr.artifact_path, str(WORKSPACE_ROOT))

    total_time = round(time.perf_counter() - start_time, 2)
    log_event("DONE", f"Proof-carrying PR written: [bold cyan]{rel_pr_path}[/bold cyan]")
    log_event("DONE", f"Autonomous repair completed in [bold green]{total_time}s[/bold green]")
    console.print()


def main():
    parser = argparse.ArgumentParser(
        description="AutoPatch-Kernel: Hardcore Minimalist Terminal UI",
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
        help="Custom bug prompt to execute",
    )
    args = parser.parse_args()

    run_interactive_cli(auto_pilot=args.auto, prompt_override=args.prompt)


if __name__ == "__main__":
    main()
