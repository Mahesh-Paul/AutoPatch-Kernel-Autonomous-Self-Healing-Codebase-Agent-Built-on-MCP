"""AutoPatch-Kernel — Hardcore Minimalist Terminal UI (TUI) Agent.

A developer-first, high-throughput streaming CLI for autonomous codebase self-healing.
Features:
- Live streaming execution log (Docker/GitHub Actions terminal aesthetic).
- Raw AST code slice rendering via syntax highlighting with Zero bloat.
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

# Force UTF-8 encoding across Windows terminal sessions
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

# Repository Workspace Path Anchor
PROJECT_WORKSPACE_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_WORKSPACE_ROOT))

from engine.tournament_kernel import PatchTournamentKernel
from engine.worktree_manager import WorktreeManager
from github_integration.pr_generator import PRGenerator
from mcp_server.ast_graph_mcp import ASTCallGraphEngine, SyscallTelemetryEngine
from verification.z3_verifier import Z3TheoremProver


terminal_console = Console(highlight=False)


def _retrieve_wall_clock_time() -> str:
    """Returns the current formatted wall-clock timestamp string."""
    return time.strftime("%H:%M:%S")


def emit_diagnostic_event(
    log_level_tag: str,
    log_message: str,
    render_dimmed: bool = False,
    dim: Optional[bool] = None,
) -> None:
    """Emits a minimalist, streaming log event adhering to CI/CD pipeline aesthetics."""
    effective_dim = dim if dim is not None else render_dimmed
    formatted_timestamp = f"[dim]{_retrieve_wall_clock_time()}[/dim]"
    if log_level_tag == "INFO":
        diagnostic_log_badge = "[bold cyan]INFO [/bold cyan]"
    elif log_level_tag == "CRASH":
        diagnostic_log_badge = "[bold red]CRASH[/bold red]"
    elif log_level_tag == "AST":
        diagnostic_log_badge = "[bold magenta]AST  [/bold magenta]"
    elif log_level_tag == "RACE":
        diagnostic_log_badge = "[bold blue]RACE [/bold blue]"
    elif log_level_tag == "GUARD":
        diagnostic_log_badge = "[bold red]GUARD[/bold red]"
    elif log_level_tag == "PROOF":
        diagnostic_log_badge = "[bold cyan]PROOF[/bold cyan]"
    elif log_level_tag == "DONE":
        diagnostic_log_badge = "[bold green]DONE [/bold green]"
    elif log_level_tag == "WARN":
        diagnostic_log_badge = "[bold yellow]WARN [/bold yellow]"
    else:
        diagnostic_log_badge = f"[bold]{log_level_tag:<5}[/bold]"

    rendered_message_text = f"[dim]{log_message}[/dim]" if effective_dim else log_message
    terminal_console.print(f"{formatted_timestamp}  {diagnostic_log_badge}  {rendered_message_text}")


# Backward-compatible alias for unit test harness
log_event = emit_diagnostic_event


def run_interactive_cli(auto_pilot: bool = False, prompt_override: Optional[str] = None) -> None:
    """Executes the hardcore minimalist developer terminal workflow."""
    terminal_console.print()
    terminal_console.print(
        "[bold cyan]AUTOPATCH-KERNEL[/bold cyan] [dim]v1.4 // AUTONOMOUS REPAIR KERNEL // MODEL CONTEXT PROTOCOL[/dim]"
    )
    terminal_console.print("[dim]Target: target_app/ (Financial Payment Order Engine)[/dim]")
    terminal_console.print()

    # Step 0: Command-Line Prompt Ingestion
    if auto_pilot or prompt_override:
        active_command_instruction = (
            prompt_override or "heal payment processor division by zero and customer tier KeyError"
        )
        terminal_console.print(
            f"[bold cyan]autopatch-kernel[/bold cyan] [dim]~ $[/dim] {active_command_instruction}"
        )
    else:
        active_command_instruction = Prompt.ask(
            "[bold cyan]autopatch-kernel[/bold cyan] [dim]~ $[/dim]",
            default="heal payment processor division by zero and customer tier KeyError",
        )

    terminal_console.print()
    workflow_execution_clock_start = time.perf_counter()

    # Step 1: Real Subprocess Telemetry and Traceback Capture
    emit_diagnostic_event("INFO", "Running initial test suite verification...")
    baseline_test_command = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
    runtime_syscall_telemetry = SyscallTelemetryEngine.capture(
        command=baseline_test_command, cwd=str(PROJECT_WORKSPACE_ROOT)
    )

    if runtime_syscall_telemetry.exit_code != 0:
        emit_diagnostic_event(
            "CRASH", f"Test execution failed with exit code {runtime_syscall_telemetry.exit_code}"
        )
        for detected_exception_name in runtime_syscall_telemetry.detected_exceptions:
            emit_diagnostic_event(
                "CRASH", f"Exception caught: [bold red]{detected_exception_name}[/bold red]"
            )
        if runtime_syscall_telemetry.primary_failure_frame:
            failing_frame_descriptor = runtime_syscall_telemetry.primary_failure_frame
            relative_failing_path = os.path.relpath(
                failing_frame_descriptor.file_path, str(PROJECT_WORKSPACE_ROOT)
            )
            emit_diagnostic_event(
                "CRASH",
                f"Primary stack frame: [yellow]{relative_failing_path}:{failing_frame_descriptor.line_number}[/yellow] "
                f"in [bold]{failing_frame_descriptor.function_name}()[/bold]",
            )
    else:
        emit_diagnostic_event("INFO", "Target application tests already passing.")
        return

    terminal_console.print()

    # Step 2: AST 2-Hop Call-Graph MCP Slicing
    emit_diagnostic_event("AST", "Querying AST 2-Hop Call-Graph MCP Server...")
    ast_callgraph_engine = ASTCallGraphEngine(str(PROJECT_WORKSPACE_ROOT))
    processor_source_path = str(PROJECT_WORKSPACE_ROOT / "target_app" / "processor.py")
    callgraph_subgraph = ast_callgraph_engine.extract_subgraph(
        processor_source_path, line_number=26, hop_depth=2
    )

    emit_diagnostic_event(
        "AST",
        f"Isolated focal node: [bold]{callgraph_subgraph.focal_node.name}[/bold] "
        f"(Lines {callgraph_subgraph.focal_node.start_line}-{callgraph_subgraph.focal_node.end_line})",
    )
    emit_diagnostic_event(
        "AST",
        f"Upstream callers: [dim]{[caller.name for caller in callgraph_subgraph.upstream_callers]}[/dim]",
    )
    emit_diagnostic_event(
        "AST",
        f"Downstream callees: [dim]{[callee.name for callee in callgraph_subgraph.downstream_callees]}[/dim]",
    )
    terminal_console.print()

    # Render Clean Code Slice
    terminal_console.print(f"[dim]# --- Sliced AST Neighborhood: target_app/processor.py ---[/dim]")
    highlighted_syntax_view = Syntax(
        callgraph_subgraph.focal_node.source_slice,
        "python",
        theme="monokai",
        line_numbers=True,
        start_line=callgraph_subgraph.focal_node.start_line,
    )
    terminal_console.print(highlighted_syntax_view)
    terminal_console.print(f"[dim]# ---------------------------------------------------------[/dim]")
    terminal_console.print()

    # Step 3: Speculative Git Worktree Tournament Racing
    emit_diagnostic_event("RACE", "Spawning 3 concurrent isolated Git worktrees (.autopatch/worktrees/)...")
    worktree_tournament_manager = WorktreeManager(str(PROJECT_WORKSPACE_ROOT))

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=25, style="dim", complete_style="cyan"),
        TimeElapsedColumn(),
        console=terminal_console,
        transient=True,
    ) as tournament_progress:
        race_progress_task = tournament_progress.add_task(
            "[cyan]Evaluating parallel worktree repair hypotheses...", total=3
        )
        tournament_race_outcomes = worktree_tournament_manager.race_competing_hypotheses(
            callgraph_subgraph, runtime_syscall_telemetry
        )
        tournament_progress.update(race_progress_task, completed=3)

    for tournament_candidate_outcome in tournament_race_outcomes.outcomes:
        if (
            tournament_candidate_outcome.sandbox_result
            and tournament_candidate_outcome.sandbox_result.lucky_pass_blocked
        ):
            emit_diagnostic_event(
                "GUARD",
                f"[bold red]{tournament_candidate_outcome.worktree_name:<20}[/bold red] "
                f"[red][SECURITY BLOCKED][/red] Attempted test file tampering! Disqualified (0.0/100)",
            )
        elif (
            tournament_candidate_outcome.sandbox_result
            and tournament_candidate_outcome.sandbox_result.tests_passed
        ):
            emit_diagnostic_event(
                "RACE",
                f"[bold green]{tournament_candidate_outcome.worktree_name:<20}[/bold green] "
                f"[green][VERIFIED CLEAN][/green] Passed tests under Read-Only Guardrail",
            )
        else:
            emit_diagnostic_event(
                "WARN",
                f"[bold yellow]{tournament_candidate_outcome.worktree_name:<20}[/bold yellow] "
                f"[yellow][SLOW / SUBOPTIMAL][/yellow] Defensive exception wrapper penalized",
            )

    terminal_console.print()

    # Step 4: Microsoft Z3 SMT Formal Invariant Verification
    emit_diagnostic_event("PROOF", "Running Microsoft Z3 SMT Theorem Prover on candidate AST invariants...")
    formal_z3_verification = Z3TheoremProver.verify_patched_discount_logic()

    if formal_z3_verification.is_verified:
        formal_z3_certificate = formal_z3_verification.certificate
        emit_diagnostic_event(
            "PROOF", f"Theorem Verdict: [bold green]{formal_z3_certificate.verdict}[/bold green]"
        )
        emit_diagnostic_event(
            "PROOF", f"Certificate ID:  [cyan]{formal_z3_certificate.certificate_id}[/cyan]"
        )
        emit_diagnostic_event(
            "PROOF", f"SHA-256 Digest:  [dim]{formal_z3_certificate.sha256_digest}[/dim]"
        )
        emit_diagnostic_event(
            "PROOF", "Invariants: [dim]denominator >= 1 & discount >= 0.0 & cap <= 0.50[/dim]"
        )
    else:
        emit_diagnostic_event("WARN", "Formal verification failed to prove invariants.")

    terminal_console.print()

    # Step 5: Multi-Objective Tournament Scoring Matrix
    adjudicated_tournament_result = PatchTournamentKernel.evaluate_tournament(
        tournament_race_outcomes, formal_z3_verification
    )

    scorecard_summary_table = Table(box=None, padding=(0, 2), show_edge=False, pad_edge=False)
    scorecard_summary_table.add_column("RANK", style="bold", justify="right")
    scorecard_summary_table.add_column("WORKTREE", style="bold cyan")
    scorecard_summary_table.add_column("MODEL", style="dim")
    scorecard_summary_table.add_column("STATUS")
    scorecard_summary_table.add_column("SCORE", justify="right")

    for candidate_card in adjudicated_tournament_result.scorecards:
        score_breakdown = candidate_card.breakdown
        if candidate_card.is_winner:
            status_badge_markup = "[bold green]CROWNED WINNER[/bold green]"
            score_text_markup = f"[bold green]{score_breakdown.total_score}/100[/bold green]"
        elif score_breakdown.disqualified:
            status_badge_markup = "[bold red]DISQUALIFIED[/bold red]"
            score_text_markup = "[red]0.0/100[/red]"
        else:
            status_badge_markup = "[bold yellow]PENALIZED[/bold yellow]"
            score_text_markup = f"[yellow]{score_breakdown.total_score}/100[/yellow]"

        scorecard_summary_table.add_row(
            f"#{candidate_card.rank}",
            candidate_card.worktree_name,
            candidate_card.model_used,
            status_badge_markup,
            score_text_markup,
        )

    terminal_console.print(scorecard_summary_table)
    terminal_console.print()

    # Step 6: Flight Recorder PR Generation & Artifact Writing
    pr_generator_engine = PRGenerator(str(PROJECT_WORKSPACE_ROOT))
    flight_recorder_pr_artifact = pr_generator_engine.write_pr_artifact(adjudicated_tournament_result)
    relative_pr_artifact_path = os.path.relpath(
        flight_recorder_pr_artifact.artifact_path, str(PROJECT_WORKSPACE_ROOT)
    )

    total_pipeline_duration_seconds = round(time.perf_counter() - workflow_execution_clock_start, 2)
    emit_diagnostic_event(
        "DONE", f"Proof-carrying PR written: [bold cyan]{relative_pr_artifact_path}[/bold cyan]"
    )
    emit_diagnostic_event(
        "DONE",
        f"Autonomous repair completed in [bold green]{total_pipeline_duration_seconds}s[/bold green]",
    )
    terminal_console.print()


def main():
    cli_argument_parser = argparse.ArgumentParser(
        description="AutoPatch-Kernel: Hardcore Minimalist Terminal UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    cli_argument_parser.add_argument(
        "--auto",
        action="store_true",
        help="Run without interactive prompt (auto-pilot mode)",
    )
    cli_argument_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Custom bug prompt to execute",
    )
    parsed_cli_options = cli_argument_parser.parse_args()

    run_interactive_cli(
        auto_pilot=parsed_cli_options.auto, prompt_override=parsed_cli_options.prompt
    )


if __name__ == "__main__":
    main()
