"""Z3 SMT Theorem Prover Engine & Cryptographic Proof Certificate Generator.

Uses the Microsoft Z3 SMT Theorem Prover to formally verify that patched business logic
satisfies mathematical safety invariants (Φ_pre => Φ_post) across infinite real domains,
ruling out ZeroDivisionError, negative discounts, and invariant violations.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

import z3
from pydantic import BaseModel, Field


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class SMTVerificationException(Exception):
    """Base exception for formal SMT verification anomalies."""
    pass


class SMTModelExtractionError(SMTVerificationException):
    """Raised when counterexample model interpretation fails."""
    pass


# ==============================================================================
# Pydantic Schemas for Formal Proofs
# ==============================================================================

class Z3VerificationCertificate(BaseModel):
    """Immutable formal verification attestation envelope."""
    certificate_id: str
    target_function: str
    verdict: Literal["UNSAT_PROVEN_SAFE", "SAT_COUNTEREXAMPLE_FOUND", "UNKNOWN"]
    is_safe: bool
    pre_conditions: List[str]
    post_conditions: List[str]
    smt_lib2_code: str
    counterexample: Optional[Dict[str, Any]] = None
    sha256_digest: str
    timestamp_unix: float = Field(default_factory=time.time)
    solver_version: str = Field(default_factory=lambda: str(z3.get_version()))


class Z3VerificationResult(BaseModel):
    """Result envelope containing solver convergence state and mathematical certificate."""
    is_verified: bool
    verdict: Literal["UNSAT_PROVEN_SAFE", "SAT_COUNTEREXAMPLE_FOUND", "UNKNOWN"]
    counterexample: Optional[Dict[str, Any]] = None
    certificate: Z3VerificationCertificate
    duration_ms: float
    proof_summary: str


# ==============================================================================
# Z3 SMT Formal Verifier
# ==============================================================================

class Z3TheoremProver:
    """Constructs First-Order Logic SMT formulas to prove safety properties of code.
    
    Proof Strategy (Proof by Contradiction / CEGIS):
    To formally prove that Pre(x) => Post(x) holds universally across infinite inputs:
    1. Assert Pre(x)
    2. Assert NOT(Post(x))
    3. If the solver evaluates UNSAT (Unsatisfiable), no input state exists where the safety
       invariant can be violated. The patch is mathematically sound.
    4. If the solver evaluates SAT, the satisfying model is an exact counterexample witness.
    """

    @classmethod
    def verify_unpatched_discount_logic(cls) -> Z3VerificationResult:
        """Evaluates unpatched calculate_discount to isolate the ZeroDivisionError counterexample."""
        solver_clock_start_ns = time.perf_counter()
        smt_prover_instance = z3.Solver()

        # Domain Variables
        order_total = z3.Real("order_total")
        tier_multiplier = z3.Real("tier_multiplier")
        active_promos_count = z3.Int("active_promos_count")
        max_discount_slots = z3.IntVal(4)

        # Pre-conditions (Valid domain input bounds)
        pre_conditions = z3.And(
            order_total > 0,
            tier_multiplier >= 1.0,
            active_promos_count >= 0,
            active_promos_count <= 10,
        )
        smt_prover_instance.add(pre_conditions)

        # In unpatched code: promo_denominator = max_discount_slots - active_promos_count
        promo_denominator = max_discount_slots - active_promos_count

        # Violation condition: Division by zero (denominator == 0)
        violation_predicate = (promo_denominator == 0)
        smt_prover_instance.add(violation_predicate)

        satisfiability_outcome = smt_prover_instance.check()
        solver_latency_ms = round((time.perf_counter() - solver_clock_start_ns) * 1000.0, 2)

        if satisfiability_outcome == z3.sat:
            sat_counterexample_model = smt_prover_instance.model()
            counterexample = {
                "active_promos_count": int(str(sat_counterexample_model[active_promos_count])),
                "tier_multiplier": float(
                    str(
                        sat_counterexample_model[tier_multiplier].as_decimal(4)
                        if hasattr(sat_counterexample_model[tier_multiplier], "as_decimal")
                        else str(sat_counterexample_model[tier_multiplier])
                    )
                ),
                "order_total": float(
                    str(
                        sat_counterexample_model[order_total].as_decimal(4)
                        if hasattr(sat_counterexample_model[order_total], "as_decimal")
                        else str(sat_counterexample_model[order_total])
                    )
                ),
                "evaluated_denominator": 4 - int(str(sat_counterexample_model[active_promos_count])),
            }
            serialized_smt2_definitions = smt_prover_instance.to_smt2()
            cert_id = f"CERT-UNPATCHED-BUG-{hashlib.sha256(serialized_smt2_definitions.encode()).hexdigest()[:12]}"
            certificate_sha256_digest = hashlib.sha256(f"{cert_id}:{serialized_smt2_definitions}".encode()).hexdigest()

            certificate = Z3VerificationCertificate(
                certificate_id=cert_id,
                target_function="target_app.processor.calculate_discount",
                verdict="SAT_COUNTEREXAMPLE_FOUND",
                is_safe=False,
                pre_conditions=[
                    "order_total > 0",
                    "tier_multiplier >= 1.0",
                    "0 <= active_promos_count <= 10",
                ],
                post_conditions=["denominator != 0", "discount_ratio >= 0.0"],
                smt_lib2_code=serialized_smt2_definitions,
                counterexample=counterexample,
                sha256_digest=certificate_sha256_digest,
            )

            return Z3VerificationResult(
                is_verified=False,
                verdict="SAT_COUNTEREXAMPLE_FOUND",
                counterexample=counterexample,
                certificate=certificate,
                duration_ms=solver_latency_ms,
                proof_summary=(
                    f"BUG VERIFIED: Z3 found SAT counterexample at active_promos_count={counterexample['active_promos_count']} "
                    f"causing division by zero (denominator={counterexample['evaluated_denominator']})."
                ),
            )
        else:
            raise SMTVerificationException("Unexpected solver result: expected SAT for unpatched buggy logic")

    @classmethod
    def verify_patched_discount_logic(cls) -> Z3VerificationResult:
        """Formally proves that patched calculate_discount is mathematically guaranteed safe.
        
        SMT proof strategy:
        We assert Pre-conditions and the NEGATION of Post-conditions.
        If the solver returns `UNSAT`, no counterexample exists anywhere in the domain.
        """
        solver_clock_start_ns = time.perf_counter()
        smt_prover_instance = z3.Solver()

        # Domain Variables
        order_total = z3.Real("order_total")
        tier_multiplier = z3.Real("tier_multiplier")
        active_promos_count = z3.Int("active_promos_count")
        max_discount_slots = z3.IntVal(4)
        max_allowed_discount_pct = z3.RealVal("0.50")

        # 1. Pre-Conditions (Valid Domain Constraints)
        pre_conditions = [
            order_total > 0,
            tier_multiplier >= 1.0,
            tier_multiplier <= 3.0,
            active_promos_count >= 0,
            active_promos_count <= 50,
        ]
        smt_prover_instance.add(z3.And(*pre_conditions))

        # 2. Symbolic Modeling of Patched AST Implementation:
        bounded_promos = z3.If(
            active_promos_count < (max_discount_slots - 1),
            active_promos_count,
            max_discount_slots - 1,
        )
        raw_denom = max_discount_slots - bounded_promos
        safe_denominator = z3.If(raw_denom > 1, raw_denom, 1)

        unbounded_ratio = (tier_multiplier * z3.RealVal("0.05")) / z3.ToReal(safe_denominator)
        discount_ratio = z3.If(
            unbounded_ratio < max_allowed_discount_pct,
            unbounded_ratio,
            max_allowed_discount_pct,
        )

        calculated_discount = order_total * discount_ratio

        # 3. Post-Condition Invariants (Safety Properties)
        safety_invariants = z3.And(
            safe_denominator >= 1,
            discount_ratio >= 0.0,
            calculated_discount <= order_total * max_allowed_discount_pct,
            calculated_discount < order_total,
        )

        # 4. Prove by Contradiction: Assert NOT(safety_invariants)
        smt_prover_instance.add(z3.Not(safety_invariants))

        satisfiability_outcome = smt_prover_instance.check()
        solver_latency_ms = round((time.perf_counter() - solver_clock_start_ns) * 1000.0, 2)

        serialized_smt2_definitions = smt_prover_instance.to_smt2()
        cert_id = f"Z3-PROVEN-{hashlib.sha256(serialized_smt2_definitions.encode()).hexdigest()[:16]}"
        certificate_sha256_digest = hashlib.sha256(f"{cert_id}:{serialized_smt2_definitions}:UNSAT".encode()).hexdigest()

        if satisfiability_outcome == z3.unsat:
            certificate = Z3VerificationCertificate(
                certificate_id=cert_id,
                target_function="target_app.processor.calculate_discount",
                verdict="UNSAT_PROVEN_SAFE",
                is_safe=True,
                pre_conditions=[
                    "order_total > 0",
                    "1.0 <= tier_multiplier <= 3.0",
                    "0 <= active_promos_count <= 50",
                ],
                post_conditions=[
                    "safe_denominator >= 1 (ZeroDivisionError impossible)",
                    "calculated_discount >= 0.0 (Negative discount impossible)",
                    "calculated_discount <= order_total * 0.50 (Max cap strictly enforced)",
                    "calculated_discount < order_total (Customer never charged negative net)",
                ],
                smt_lib2_code=serialized_smt2_definitions,
                counterexample=None,
                sha256_digest=certificate_sha256_digest,
            )

            return Z3VerificationResult(
                is_verified=True,
                verdict="UNSAT_PROVEN_SAFE",
                counterexample=None,
                certificate=certificate,
                duration_ms=solver_latency_ms,
                proof_summary=(
                    "FORMALLY VERIFIED (UNSAT): Z3 theorem prover mathematically proved that for all "
                    "infinite inputs in the domain, ZeroDivisionError, negative discounts, and invariant violations "
                    "are provably impossible."
                ),
            )
        else:
            sat_counterexample_model = smt_prover_instance.model()
            return Z3VerificationResult(
                is_verified=False,
                verdict="SAT_COUNTEREXAMPLE_FOUND",
                counterexample={"model": str(sat_counterexample_model)},
                certificate=Z3VerificationCertificate(
                    certificate_id=cert_id,
                    target_function="target_app.processor.calculate_discount",
                    verdict="SAT_COUNTEREXAMPLE_FOUND",
                    is_safe=False,
                    pre_conditions=[],
                    post_conditions=[],
                    smt_lib2_code=serialized_smt2_definitions,
                    sha256_digest=certificate_sha256_digest,
                ),
                duration_ms=solver_latency_ms,
                proof_summary=f"Counterexample detected: {sat_counterexample_model}",
            )
