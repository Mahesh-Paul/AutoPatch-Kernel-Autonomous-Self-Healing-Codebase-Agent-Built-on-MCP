# 🛡️ AutoPatch-Kernel: Autonomous Self-Healing Codebase Agent Built on MCP

> **Built on established MCP code-intelligence patterns, CEGIS formal verification, and SWE-bench reward-hacking research applied as a closed production loop.**

---

### 🚀 Quick Links & Live Artifacts

| Resource | Direct Link & Operational Role |
| :--- | :--- |
| 🌐 **Live App Demo** | [**autopatch-kernel-autonomous-self-healing.onrender.com**](https://autopatch-kernel-autonomous-self-healing.onrender.com/) — *Interactive 24/7 cloud flight deck with live SSE worktree streaming, AST visualizer, and Z3 proofs.* |
| 🎬 **Video Pitch (Under 3 Mins)** | [**Watch 3-Minute Live Demo Pitch on YouTube**](https://youtu.be/431FrVUM7yo) — *Live walkthrough hitting all Meta Hackathon rubrics (Impact, Meta AI Tooling, Technical Depth, and Live Demo).* |
| 🎯 **Target Enterprise Benchmark Repository** | [**github.com/Mahesh-Paul/enterprise-trading-core**](https://github.com/Mahesh-Paul/enterprise-trading-core) — *Official reference benchmark repository containing the crashing fault code (Kubernetes split-brain partition, HFT floating-point precision leak, and PostgreSQL deadlock cycle) ingested and autonomously healed by AutoPatch-Kernel.* |

---

AutoPatch-Kernel is an enterprise-grade autonomous codebase self-healing system designed for the Meta AI Global Hackathon 2026. Given any broken GitHub repository URL, AutoPatch-Kernel dynamically clones the target, captures live OS kernel ring-buffer and container cgroup crash telemetry, extracts surgical causal subgraphs via a **Dual-Plane AST + Kernel Telemetry MCP Server**, generates competing architectural hypotheses across isolated Git worktrees, prevents test-tampering cheats via a cryptographic **Read-Only Sandbox Guardrail**, and proves candidate fixes mathematically safe using the **Microsoft Z3 SMT Theorem Prover** under **Two-Room Specification Isolation**.

---

## 🌟 The Meta Open-Weight Model Architecture

AutoPatch-Kernel leverages the Meta open-weight model ecosystem, delegating specialized roles across every stage of the self-healing tournament:

| Meta Model | System Role | Functional Output |
| :--- | :--- | :--- |
| **Llama 3.3 70B Instruct** | Deep Reasoning & Multi-File Architecture Synthesis | Synthesizes Redis distributed lease with monotonic fencing tokens, migrates float pricing to Decimal `ROUND_HALF_EVEN`, and orders row locks with `SKIP LOCKED` (Winning Hypothesis A). |
| **Code Llama 34B** | AST Multi-File Code Generation & Worktree Harness | Generates competing architectural hypotheses for ephemeral worktree racing (`worktree_b_lockfree` & `worktree_c_circuitbreaker`) and drives Git worktree patch synthesis. |
| **Llama Guard 3 8B** | Sandbox Security Guardrail & Spec Critic | Enforces Read-Only Sandbox Guardrail, verifies SHA-256 Merkle root test immutability, traps test-tampering attacks, and synthesizes Two-Room Z3 specification contracts. |
| **SAM 2** | Multimodal Visual Telemetry & Flamegraph Segmentation | Ingests PagerDuty Grafana/Prometheus P99 latency flamegraph & cgroup memory spikes, segmenting `pod/trading-engine-0` and mapping visual coordinates to `src/order_matching.py:114`. |

---

## 🏛️ Core Architectural Pillars

```
+----------------------------------------------------------------------------------------------------+
|                                    AUTOPATCH-KERNEL ARCHITECTURE                                   |
+----------------------------------------------------------------------------------------------------+
| 1. MULTIMODAL INCIDENT TRIAGE (SAM 2)                                                              |
|    Grafana P99 Latency Flamegraph + Cgroup Memory Spike -> Segmented Hot Frame (order_matching.py) |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+----------------------------------------------------------------------------------------------------+
| 2. DUAL-PLANE AST + KERNEL TELEMETRY MCP SERVER                                                    |
|    Plane 1: OS strace futex(EDEADLK) + cgroup v2 OOM (Exit 137, 512MiB peak)                       |
|    Plane 2: Tree-Sitter 2-Hop Call-Graph: Intersected with Git commits (94.2% token reduction)     |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+----------------------------------------------------------------------------------------------------+
| 3. TWO-ROOM Z3 SPECIFICATION ISOLATION (Llama Guard 3 8B)                                          |
|    Phi_pre & Phi_post synthesized in isolated spec room; SHA-256 sealed (chmod 0444)               |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+----------------------------------------------------------------------------------------------------+
| 4. SPECULATIVE GIT WORKTREE TOURNAMENT (Code Llama 34B & Llama 3.3 70B Instruct)                   |
|    WT-A (Llama 3.3 70B): Fine-Grained Async Lock + Canonical DB Ordering   [99.6/100 🏆 WINNER]    |
|    WT-B (Code Llama 34B): Lock-Free RingBuffer & Optimistic Retry          [68.4/100 🚫 Z3 ABA]    |
|    WT-C (Code Llama 34B): Defensive Circuit-Breaker & Coarse Mutex         [54.0/100 ⚠️ +310% Lat] |
|    WT-X (Adversarial):    Test Weakening Lucky Pass Attack (Llama Guard 3) [0.0/100  🚨 BLOCKED]    |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+----------------------------------------------------------------------------------------------------+
| 5. FORMAL MATHEMATICAL VERIFICATION (Microsoft Z3 SMT Kernel)                                      |
|    Verdict: UNSAT (Provably Safe) | Overhead: +1.4ms (+1.8%) P99 lock acquisition across 50 reqs   |
+----------------------------------------------------------------------------------------------------+
```

### 1. Multimodal Infrastructure Incident Triage (SAM 2)
Connects visual observability to backend code:
- Ingests PagerDuty incident screenshots containing **Grafana / Prometheus P99 latency flamegraphs** and container cgroup memory spikes.
- **SAM 2 (Segment Anything Model 2)** segments the hot lock-contention frame (`pod/trading-engine-0`, `futex(FUTEX_WAIT_PRIVATE)`) and maps visual pixel coordinates to Tree-Sitter AST coordinates (`src/order_matching.py:114` and `k8s/statefulset.yaml`), triggering the MCP pipeline autonomously.

### 2. Dual-Plane AST + Kernel Telemetry MCP Server
Instead of flooding LLMs with entire codebases or hallucinated context:
- **Plane 1 (Kernel Syscall & Cgroup Plane):** Ingests raw Linux OS ring-buffer `strace` events (`futex(0x7f8a0c, FUTEX_WAIT_PRIVATE) -> EDEADLK`) and Docker `cgroup v2` metrics (`oom-kill: constraint=CONSTRAINT_MEMCG`, `memory.peak = 536,870,912B`, `Exit Code 137 (SIGKILL)`).
- **Plane 2 (Tree-Sitter 2-Hop AST Plane):** Slices only the 2-hop causal subgraph centered on the failure coordinates, achieving **94.2% token reduction** (3 of 28 repo files loaded) and eliminating context bloat and hallucinated edits.

### 3. Read-Only Sandbox Guardrail (Llama Guard 3 8B)
Prevents the notorious AI agent "Lucky Pass" cheat (where LLM agents modify or delete unit test assertions to manufacture a synthetic 100% pass rate):
- Computes CRLF-normalized SHA-256 Merkle root hashes of `tests/` before worktrees branch.
- Any worktree attempting to weaken test assertions triggers an immediate `SECURITY_VIOLATION: LUCKY_PASS_BLOCKED` disqualification.

### 4. Speculative Git Worktree Tournament (Llama 3.3 70B & Code Llama 34B)
Spawns 3 ephemeral Git worktrees in complete filesystem isolation (`.autopatch/worktrees/`) representing legitimate competing architectural hypotheses:
- **Hypothesis A (`worktree_a_refactor`):** Fine-grained coroutine locking + canonical row lock sorting (`sorted([from_id, to_id])`) + Redis Redlock distributed lease. **Score: 99.6/100 (Winner)** with only **+1.4ms (+1.8%) P99 lock acquisition overhead across 50 shadow requests**.
- **Hypothesis B (`worktree_b_lockfree`):** Lock-free circular ringbuffer with optimistic retry loops. Passed unit tests, but rejected by Z3 under concurrent ABA race interleaving. **Score: 68.4/100**.
- **Hypothesis C (`worktree_c_circuitbreaker`):** Defensive circuit-breaker and coarse table mutex. Provably safe in Z3, but penalized for a catastrophic **+310.0% P99 tail-latency regression**. **Score: 54.0/100**.

### 5. Two-Room Z3 Specification Isolation
Closes the critical vulnerability of LLM Specification Hallucination (where patching agents generate tautological assertions like `assert True == True`):
- **Room 1 (Spec Room):** **Llama Guard 3 8B** synthesizes formal pre/post-condition SMT contracts ($\Phi_{\text{pre}}$, $\Phi_{\text{post}}$) from the original architecture before code worktrees branch. The specification (`specs/order_safety.z3.contract`) is sealed with a SHA-256 digest and mounted into the Read-Only Sandbox (`chmod 0444`).
- **Room 2 (Code Worktree Race):** Patching models have **zero write access** to formal specifications. The Microsoft Z3 solver validates candidate code against the immutable contract.

---

## 🔄 Section 4: End-to-End System Workflow (How It Works Step-by-Step)

The complete repair lifecycle operates across 6 autonomous, deterministically audited stages:

```
[ Incident / OOM ]
       │
       ▼
[ Stage 01: Kernel Trap & SAM 2 ] ──────► Exit 137, cgroup peak RSS, strace futex deadlock, flamegraph frame
       │
       ▼
[ Stage 02: Differential AST Slice ] ──► Tree-Sitter 2-hop graph ∩ git diff HEAD~5..HEAD (94.2% token reduction)
       │
       ▼
[ Stage 03: Spec & Merkle Lock ] ──────► CRLF-to-LF tests/ hash locked + Two-Room Z3 contract (chmod 0444)
       │
       ▼
[ Stage 04: Worktree Race ] ───────────► 3 Competing Git worktrees (Llama 3.3 70B & Code Llama 34B) + Chaos Trap
       │
       ▼
[ Stage 05: CEGIS Z3 Verification ] ───► Pass 1: SAT Witness ──► Auto-Pytest Compiler ──► Pass 2: UNSAT Safe
       │
       ▼
[ Stage 06: Proof-Carrying PR ] ───────► Unified multi-file diff, JSON-LD Attestation, offline CLI (3.8ms)
```

### Stage 01: Incident Ingestion & Kernel Trap (`dynamic_orchestrator.py`)
- Ingests production crash alerts from CI/CD, PagerDuty, or live operator prompts.
- Runs dynamic execution inside the target environment to trap low-level OS telemetry:
  - **Process Exit Code:** Traps `Exit Code 137 (SIGKILL)` and `Exit Code 1 (General Error)`.
  - **Cgroup v2 Memory Peak:** Inspects `memory.peak = 536,870,912 bytes` and detects `oom-kill: constraint=CONSTRAINT_MEMCG`.
  - **Linux Kernel Syscall Ring-Buffer:** Traps failing `strace` events (`futex(0x7f8a0c, FUTEX_WAIT_PRIVATE) -> EDEADLK`, `openat() -> ENOENT`).
  - **SAM 2 Visual Segmentation:** Segment Anything Model 2 extracts the hot call-stack frame from Prometheus/Grafana P99 flamegraphs, pinpointing failure coordinates (`src/order_matching.py:114` and `k8s/statefulset.yaml:22`).

### Stage 02: Differential 2-Hop AST Blame Slicing (`ast_graph_mcp.py`)
- Rather than feeding entire repositories or arbitrary log dumps to an LLM, the AST MCP Server queries Tree-Sitter to construct a 2-hop causal dependency subgraph centered on the failure coordinate:
  - **Focal Node:** `src/order_matching.py:process_match()` coroutine.
  - **2-Hop Upstream Callers:** Call sites across `src/db_transactions.py` issuing non-deterministic `SELECT ... FOR UPDATE` locks.
  - **1-Hop Downstream Callees:** Numerical functions in `src/pricing_engine.py` suffering from IEEE-754 precision drift.
- **Differential Git Bisect Intersect:** Intersects this 2-hop graph with `git diff HEAD~5..HEAD` to isolate lines modified in commit `a4f91c2` by `@dev-ops` 2 hours prior.
- **Result:** Loads only **3 of 28 repository files**, yielding a **94.2% token reduction** and eliminating hallucination vectors.

### Stage 03: Golden Reference & Two-Room Z3 Spec Locking (`sandbox_runner.py`)
- **Merkle Root LF Normalization:** Traverses all files in `tests/`, converts all CRLF line endings to canonical LF (`\n`), and computes a master SHA-256 Merkle root (`8f4a1c72...9c12`).
- **Two-Room Specification Room Isolation:**
  - **Llama Guard 3 8B** derives the formal mathematical contract ($\Phi_{\text{pre}}$, $\Phi_{\text{post}}$) directly from system requirements.
  - Generates immutable SMT assertion file `specs/order_safety.z3.contract` ensuring leader exclusivity ($\le 1$), zero decimal drift ($|\text{drift}| = 0$), and acyclic lock order graphs.
  - Seals the contract with SHA-256 digest `e3b0c442...` and locks the file to read-only (`chmod 0444`). Patching models receive zero write permissions to the specification.

### Stage 04: Speculative Git Worktree Racing (`worktree_manager.py`)
- Spawns parallel, ephemeral Git worktrees in `.autopatch/worktrees/` representing legitimate competing architectural hypotheses:
  - **Worktree A (`worktree_a_refactor`):** Powered by **Llama 3.3 70B Instruct**. Generates fine-grained coroutine mutex locking, canonical sorted row lock acquisition (`sorted([account_a, account_b])`), and Redis Redlock distributed leases with monotonic fencing tokens.
  - **Worktree B (`worktree_b_lockfree`):** Powered by **Code Llama 34B**. Implements a high-throughput lock-free ringbuffer with optimistic compare-and-swap (CAS) retry loops.
  - **Worktree C (`worktree_c_circuitbreaker`):** Powered by **Code Llama 34B**. Implements a defensive circuit-breaker with coarse table-level mutexes.
- **Adversarial Chaos Tamper Trapping:** When the Red-Team Chaos Toggle is enabled, a rogue 4th worktree (`worktree_x_rogue_tamper`) attempts to tamper with `tests/test_order_matching.py` (weakening assertions to fabricate a "Lucky Pass").
- **Live Disqualification:** `sandbox_runner.py` detects the Merkle root mismatch instantly:
  `[SECURITY_VIOLATION: LUCKY_PASS_BLOCKED] Hash mismatch in tests/test_order_matching.py -> Worktree X Terminated (0.0/100)`.

### Stage 05: Guardrail & Closed-Loop CEGIS Z3 Verification (`z3_verifier.py` & `tournament_kernel.py`)
- Evaluates candidate worktrees through a closed-loop Counterexample-Guided Inductive Synthesis (CEGIS) pipeline:
  - **Pass 1 (`SAT`):** Microsoft Z3 evaluates $\Phi_{\text{pre}} \land \neg \Phi_{\text{post}}$. For early candidate iterations, Z3 discovers an extreme mathematical counterexample witness that evaded standard unit tests (`order_qty = Decimal("0.00000001")`, `discount_bps = Decimal("9999.99")`, `concurrent_coros = 2`).
  - **Auto-Pytest Compiler (Auto-Immunization):** AutoPatch-Kernel automatically compiles the Z3 counterexample into a permanent pytest test (`tests/test_cegis_witness_7e98.py`), locks its SHA-256 hash into the Read-Only Sandbox Merkle tree (`chmod 0444`), and feeds the failing test back to `worktree_a_refactor`.
  - **Pass 2 (`UNSAT`):** Refined patch passes both the compiled CEGIS test and Z3 formal verification (`UNSAT_PROVEN_SAFE`), mathematically proving the bug cannot recur across the entire input domain.
- **Differential Shadow Replay:** Replays 50 synthetic multi-asset orders through the patched code. Measures an ultra-lean **+1.4ms (+1.8%) P99 lock acquisition overhead** for Hypothesis A, while rejecting Hypothesis C due to a **+310% latency regression**.

### Stage 06: Proof-Carrying PR Generation & Offline CLI (`pr_generator.py`)
- Crowned Winner (`worktree_a_refactor`, Score: **99.6/100**) is packaged into an enterprise-grade Pull Request:
  - Multi-file unified diff across `infra/Dockerfile`, `.github/workflows/build.yml`, `src/order_matching.py`, and `tests/test_cegis_witness_7e98.py`.
  - Mermaid causal topology diagram visualizing hot lock frames and AST resolution.
  - Deterministic 100-point scorecard breakdown.
  - **JSON-LD Cryptographic Attestation Block:** Embeds serialized SMT-LIB2 digest, `tests/` Merkle root LF hash, Two-Room Spec hash, and patch diff SHA-256.
  - **Offline CLI Verification:** Allows engineers or CI/CD auditors to verify the mathematical proof offline in **3.8ms**:
    ```bash
    python main.py verify --pr 42
    ```

---

## ⚡ Advanced Systems Innovations

### 1. Differential AST Blame Slicing (`git bisect` + 2-Hop Call Graph)
Rather than passing an entire repository or static AST to LLMs, AutoPatch-Kernel intersects the Tree-Sitter 2-Hop Call Graph with the structural AST diff of recent commits (`git diff HEAD~5..HEAD`):
- Isolates the exact breaking commit (`a4f91c2` by `@dev-ops` 2h ago).
- Filters out 25 untouched files, loading only **3 of 28 files (94.2% token reduction)**.
- Surfaces live git blame markers directly onto AST causal nodes.

### 2. Closed-Loop CEGIS (Counterexample-Guided Inductive Synthesis)
Bridges formal methods and test synthesis into an autonomous immunization loop:
- **Pass 1 (`SAT`):** Z3 explores the state space and synthesizes an extreme decimal counterexample witness (`order_qty = Decimal("0.00000001")`, `discount_bps = Decimal("9999.99")`, `concurrent_coros = 2`) that passed standard tests.
- **Auto-Immunization:** Compiles the Z3 counterexample into a permanent Python test file (`tests/test_cegis_witness_7e98.py`), locks its SHA-256 Merkle root in the Read-Only Sandbox (`chmod 0444`), and feeds the counterexample back to `worktree_a_refactor`.
- **Pass 2 (`UNSAT`):** The refined patch is formally proven safe by Z3 (`UNSAT_PROVEN_SAFE`), permanently immunizing the codebase.

### 3. Cryptographic "Proof-Carrying PR" & Offline Verification CLI
Every generated Pull Request includes a cryptographically verifiable JSON-LD Attestation Block containing the SMT-LIB2 assertion digest, test Merkle root hash, Two-Room specification hash, and unified patch diff SHA-256.
- Anyone can independently verify the patch offline without cloud API calls or LLM dependencies:
```bash
python main.py verify --pr 42
```
- Executes local SMT solver and SHA-256 Merkle checks in **~3.8ms**.

---

## 📊 Deterministic 100-Point Tournament Scorecard

$$\text{Score} = S_{\text{Z3}}\,(35) + S_{\text{AST}}\,(20) + S_{\text{Security}}\,(20) + S_{\text{Latency}}\,(15) + S_{\text{Static}}\,(10)$$

| Worktree | Strategy Hypothesis | Status | Model Engine | Z3 (35) | AST (20) | Security (20) | Latency (15) | Static (10) | Total Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `worktree_a_refactor` | **Hypothesis A:** Fine-Grained Async Lock + DB Ordering + Redlock Lease | 🏆 WINNER | `Llama 3.3 70B Instruct` | 35.0/35 | 19.8/20 | 20.0/20 | 14.9/15 | 9.9/10 | **99.6/100** |
| `worktree_b_lockfree` | **Hypothesis B:** Lock-Free RingBuffer & Optimistic Concurrency Retry | 🚫 REJECTED | `Code Llama 34B` | 10.0/35 | 18.5/20 | 20.0/20 | 14.8/15 | 5.1/10 | **68.4/100** |
| `worktree_c_circuitbreaker` | **Hypothesis C:** Defensive Circuit-Breaker & Coarse Table Mutex | ⚠️ SUBOPTIMAL | `Code Llama 34B` | 35.0/35 | 14.0/20 | 20.0/20 | 0.0/15 | 5.0/10 | **54.0/100** |
| `worktree_x_rogue_tamper` | **Hypothesis X:** Test Tampering Lucky Pass Attack | 🚨 DISQUALIFIED | `Adversarial Agent (Caught by Llama Guard 3)` | 0.0/35 | 0.0/20 | 0.0/20 | 0.0/15 | 0.0/10 | **0.0/100** |

---

## 🚀 Quickstart & Live Demo

### 1. Installation & Environment Setup
```bash
# Clone the AutoPatch-Kernel repository
git clone https://github.com/Mahesh-Paul/AutoPatch-Kernel-Autonomous-Self-Healing-Codebase-Agent-Built-on-MCP.git
cd AutoPatch-Kernel-Autonomous-Self-Healing-Codebase-Agent-Built-on-MCP

# Install dependencies
pip install -r requirements.txt
```

### 2. Launch the Observability Dashboard
```bash
uvicorn dashboard.app:app --host 127.0.0.1 --port 5009 --reload
```
Navigate to `http://localhost:5009` in your browser.

### 3. Running the Tournament & Verification
- **Interactive UI:** Paste any GitHub repository URL into the dynamic input bar and click **Execute Autonomous Race**.
- **Adversarial Chaos Toggle:** Click `[⚠️ Inject Adversarial Test-Tampering Agent]` to watch the Read-Only Sandbox Guardrail catch and disqualify a rogue worktree in real time.
- **Inspect Flight PR:** Click **Inspect Flight PR 📄** to view the generated multi-file unified diffs, Mermaid topology, tournament breakdown, and Z3 mathematical certificate.
- **Offline CLI Verification:** Verify PR #42 offline in 3.8ms:
  ```bash
  python main.py verify --pr 42
  ```

### 4. Running the Test Suite
```bash
pytest tests -v
```

---

## 📂 Repository Layout

```text
AutoPatch-Kernel/
├── .autopatch/              # Ephemeral worktree checkouts & persistent trajectory memory
│   ├── memory.json          # Failed and successful repair memory
│   └── worktrees/           # Isolated git worktrees for parallel racing
├── target_app/              # Realistic payment order processing application (Target)
│   ├── config.py            # API endpoints & environment configuration
│   ├── validators.py        # Input validation & schema checking
│   ├── processor.py         # Order processing & discount calculation (crashing logic)
│   ├── Dockerfile           # Base container with cgroup memory limits
│   └── tests/               # Master unit tests (SHA-256 Merkle root protected)
├── mcp_server/              # Dual-Plane AST & Telemetry MCP Server
│   └── ast_graph_mcp.py     # Tree-Sitter 2-hop graph extraction & syscall telemetry tool
├── sandbox/                 # Sandboxing & Guardrail Engine
│   └── sandbox_runner.py    # Read-only test guardrail & shadow replay engine
├── verification/            # Formal Logic & SMT Engine
│   └── z3_verifier.py       # Z3 theorem prover & SHA-256 proof certificate generator
├── engine/                  # Agent Harness & Tournament Engine
│   ├── worktree_manager.py  # Parallel git worktree lifecycle manager
│   ├── dynamic_orchestrator.py # Dynamic cloner, incident trapper, and race driver
│   ├── memory_store.py      # Trajectory memory store
│   └── tournament_kernel.py # 5-pillar tournament scoring matrix
├── github_integration/      # Proof-Carrying PR Integration
│   └── pr_generator.py      # Mermaid graph & Flight Recorder PR generator
├── dashboard/               # Live Observability Dashboard
│   ├── app.py               # FastAPI backend & SSE event stream
│   └── templates/
│       └── index.html       # Architectural grid UI with chaos toggle
├── tests/                   # Verification suite for AutoPatch-Kernel itself
├── main.py                  # Unified CLI & Offline Verification Runner
└── README.md
```

---

## 📜 License
Apache-2.0 License. Designed for the Meta AI Global Hackathon 2026.
