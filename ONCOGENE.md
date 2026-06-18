# ONCOGENE: Self-Propagating Errors in Agentic Workflows

## Preface

The wrong cache fix documented in `AUTOPSY_CACHE_FIX.md` was not simply a bug. Bugs
are expressed in code, found, patched. This error was expressed in the guidance layer —
the documents that direct agent behavior — and it behaved differently from any code bug:
it replicated, spread to new documents, actively generated its own implementation
pathway, and survived multiple independent review passes while appearing validated at
each one.

That behavior has a better model than "documentation error." It is oncogenic.

This document develops that model, not as metaphor but as a structural description of
a failure class that is specific to agentic workflows and has no direct equivalent in
human engineering teams.

---

## I. Proto-Oncogene vs. Oncogene

In molecular biology, an **oncogene** is a mutated form of a normal gene — a
**proto-oncogene** — whose ordinary function is cell growth and division. The mutation
does not introduce foreign material. It takes a functional, necessary mechanism and
makes it pathological by removing the off-switch.

In an agentic workflow, the proto-oncogene is the practice of writing investigation
documents for future agents. This is correct and necessary. Without it, every new agent
session re-derives from scratch, wasting compute and losing accumulated context.
Investigation documents are the off-switch for redundant work.

The mutation is subtle: the document not only records findings but encodes proposed
fixes as settled facts, and instructs future agents not to re-investigate. The
normal, useful mechanism of knowledge transfer becomes pathological because it now
actively suppresses correction of its own errors.

**The proto-oncogene:** "Write investigation findings into handoff documents."

**The oncogenic mutation:** "Encode proposed fixes as verified facts; add 'do not
re-derive' to prevent redundant work."

The second instruction is locally reasonable at every instance it is written. The
combination is what creates the driver mutation.

---

## II. The Mutation Event

The specific mutation in this codebase occurred at a single inference step:

> "Two consecutive calls where the 200-word query would retrieve nearly identical
> passages (stable clinical topic) may still produce different 500-char hashes and
> trigger a redundant fetch. The cache key shifts faster than the underlying query
> changes."

This conflated two distinct claims:
- **Semantic:** consecutive windows retrieve similar clinical passages (may be true)
- **Deterministic:** consecutive windows produce the same hash (always false)

The inference was locally coherent — it identified a real internal inconsistency
(hash window ≠ query window) and proposed to resolve it. The error was invisible
without tracing the calling convention backward to the frontend trigger mechanism,
which this analysis did not do.

Every subsequent agent that read the resulting document inherited this inference as
a finding, not a hypothesis. They had no reason to trace the calling convention
because the document said the investigation was complete.

---

## III. Tumor Suppressor Genes

Oncogenes express unchecked when **tumor suppressor genes** are absent. In cellular
biology, suppressors are checkpoints: they verify that conditions for division are met
before allowing the cell to proceed. Without them, a single driver mutation is
sufficient to initiate uncontrolled growth.

In an agentic workflow, the suppressors are:

**Cross-layer tracing.** Any fix to a function must trace its callers and their data
sources. The cache fix required tracing `prefetch_rag_context` ← `handle_realtime_analysis_with_retry`
← `handle_segment_analysis` ← the HTTP request ← the frontend trigger mechanism ←
the transcript window construction. The analysis stopped at the function boundary.
The suppressor was absent.

**A falsifiable success criterion.** The fix should have been: "apply this change;
measure `cache_hit` rate over a 5-minute session at 130 wpm; if rate is < 10%, the
fix is wrong." Instead, the criterion was: "assert that `context_cache_hit` appears
in the response JSON." This passes whether or not the cache ever hits. The suppressor
was absent.

**A test in the production scenario.** The test spec appended 5 words to a 250-word
transcript and asserted the hash was unchanged. The production trigger threshold is 8
words. The test was written below the activation threshold of the bug it was meant to
catch. The suppressor was present in form, absent in function.

**Running the tests.** The test spec was committed without execution. A test that would
have failed on its own assertions was treated as validation. The suppressor was absent.

When all four suppressors are absent simultaneously, a single driver mutation is
sufficient to propagate indefinitely.

---

## IV. Metastasis: Spread to New Tissues

A localized tumor can be excised. A metastatic cancer has seeded distant sites; 
removing the primary does not clear the disease.

The cache fix began in one document (`CACHE_ANALYSIS_REPORT.md`) and metastasized
to five:

```
CACHE_ANALYSIS_REPORT.md          ← primary tumor
        ↓ "dedicated session bootstrap for implementing the cache fixes"
cache.md                           ← liver metastasis (implementation instructions)
        ↓ "Fix the RAG cache key (hash the last-200-word...)"
technical.md                       ← lung metastasis (project roadmap)
        ↓ "cache key fix (last-200-word hash)"
UNIT_TESTING_SPEC.md               ← bone metastasis (test specifications)
        ↓ "Option C3 — Increase window size"
TherAssist-AgentHandoff.md         ← brain metastasis (read by every incoming agent)
```

Each metastatic site independently directs agents toward the wrong fix. Correcting
the primary (`CACHE_ANALYSIS_REPORT.md`) without clearing all metastases leaves live
tumor. An agent reading only `TherAssist-AgentHandoff.md` in a new session would
re-derive Option C3 from that document alone, even after the primary was corrected.

Metastasis is what makes this error class expensive to clear. It is not enough to
correct the document where the error originated. Every document that cited it, quoted
it, or implemented its conclusions must be found and corrected or the error regenerates.

---

## V. Angiogenesis: The Error Builds Its Own Infrastructure

A tumor does not grow passively. It signals surrounding tissue to grow blood vessels
toward it — **angiogenesis** — creating the supply chain it needs to expand.

The cache fix was angiogenic. `CACHE_ANALYSIS_REPORT.md` contained not just the error
but an explicit list of implementation steps, a DOD checklist, and a pointer to a
dedicated session bootstrap. `cache.md` was created specifically to provide the
infrastructure to implement the fix: code snippets, test specs, file locations,
line numbers. The error actively organized its own implementation pathway.

This is distinct from a passive documentation mistake. The error generated:
- A session bootstrap that would direct an agent to open `main.py` at line 569 and
  make a specific change
- A test file specification that would confirm the change was correct
- A DOD checklist that would allow the task to be marked complete
- A roadmap entry that would schedule the task in a project timeline

An agent handed `cache.md` with the instruction "implement the fixes" had no mechanism
to resist. The document was complete, internally consistent, and referenced by two
other authoritative documents. The error had built everything it needed to survive
implementation.

---

## VI. Tumor Heterogeneity: Multiple Variants of the Same Mutation

Mature tumors are not genetically uniform. Different cells carry different versions of
the driver mutation — **tumor heterogeneity** — which is why treatment that targets
one variant can fail when another variant is present.

The cache error exhibited heterogeneity across its metastatic sites:

| Document | Variant |
|---|---|
| Original code (`main.py:569`) | `hash(transcript_text[-500:])` |
| `CACHE_ANALYSIS_REPORT.md` | `hash(query_text)` where `query_text = last 200 words` |
| `TherAssist-AgentHandoff.md` | `hash(transcript[-5000:])` |

These are three distinct expressions of the same underlying mutation: a window-based
hash over the tail of a growing transcript string. Each variant produces different
specific code but the same runtime behavior — hash changes on every trigger, cache hits
are zero.

The heterogeneity matters because each variant is sufficient to regenerate the others.
An agent that encounters only the `[-5000:]` variant can independently derive the
`[-200 words]` variant as a "refinement." The error has multiple independent seeds,
any one of which is sufficient to restart the propagation chain.

---

## VII. Hereditary vs. Sporadic Expression

In oncology, cancers are classified as **hereditary** (germline mutation present in
every cell from conception) or **sporadic** (mutation arises in a specific cell during
the organism's lifetime).

This error class has both modes.

**Sporadic expression** occurs when an LLM performs local analysis of a function,
misses a cross-layer dependency, and generates a locally coherent wrong conclusion
independently — with no exposure to prior wrong documents. The codebase structure
itself is sufficient to produce the error because the calling convention is not visible
at the function level. Every new agent that analyzes `prefetch_rag_context` in
isolation is at risk of sporadic expression.

**Hereditary expression** occurs when the error is in the germline — documents that
are always loaded into agent context. `TherAssist-AgentHandoff.md` is the germline
document for this project: every agent session that uses it inherits the Option C3
variant. Even if `CACHE_ANALYSIS_REPORT.md` is never read, the germline document
transmits the mutation.

Hereditary expression is more dangerous because it is structural, not contingent. The
error does not need to be re-derived; it is delivered. Clearing hereditary expression
requires editing the germline document — which is what the correction to
`TherAssist-AgentHandoff.md` in this session accomplished.

Sporadic expression cannot be eliminated entirely. It can only be suppressed by
reinstating the tumor suppressor mechanisms: cross-layer tracing requirements,
falsifiable success criteria, production-scenario tests.

---

## VIII. Recurrence After Treatment

The corrections applied in this session addressed both the primary tumor and all five
metastatic sites. But recurrence is possible under two conditions:

**Incomplete clearance.** If any document in the project still contains an uncorrected
reference to the wrong fix — a cached export, a linked document not found in this
search, a comment in code — that residual tissue can regenerate the tumor in a future
session. Clearance is only as complete as the search was thorough.

**Re-mutation from sporadic expression.** Even with all documents corrected, a future
agent performing local analysis of `prefetch_rag_context` may independently re-derive
the wrong fix. The codebase structure that produced the original sporadic mutation
still exists. The only protection is the tumor suppressor mechanism: the known-wrong
fixes table in `MITIGATE.md` must be in the context of any agent performing cache
analysis, and the cross-layer tracing requirement must be enforced.

`MITIGATE.md` functions as a **maintenance therapy** protocol — not a cure, but a
standing suppression regime that prevents recurrence by keeping the tumor suppressors
active across sessions.

---

## IX. Why This Failure Class Is Specific to Agentic Workflows

Human engineering teams have natural defenses against this failure mode that agentic
workflows lack:

**Shared memory across sessions.** A human engineer who proposes a wrong fix, has it
rejected, and is corrected, carries that correction into future work. An LLM agent
has no persistent memory across sessions. The correction must be encoded externally —
in documents — or it is lost. This means the correction exists in the same medium as
the error, and is subject to the same propagation dynamics.

**Social friction as a correction mechanism.** In a human team, a proposed fix that
doesn't produce observable results generates questions. "Did the cache hit rate
improve after your change?" is a natural conversation. In an agentic workflow, the
agent that implements the fix is not the agent that observes the outcome. The
implementing agent marks the DOD complete and terminates. The observation gap is
structural.

**Localized authority.** When a human senior engineer writes an investigation report,
they carry contextual credibility that helps other engineers calibrate how much to
trust specific claims. An LLM-generated document carries uniform formatting and tone
regardless of whether the underlying reasoning is correct. There is no signal in the
presentation layer that distinguishes a well-traced analysis from a locally-coherent
error. This is the mechanism by which "investigation complete — do not re-derive"
functions as a suppressor of correction rather than a signal to inspect more carefully.

**The absence of boredom.** Human engineers notice when they keep fixing the same bug.
The repetition is itself a signal that the fix is wrong. An LLM agent encountering the
same cache fix recommendation for the fourth time has no such signal. It processes the
recommendation fresh, without the pattern-matching that would make repetition suspicious.

These absences are not defects in specific models — they are structural properties of
the workflow architecture. They apply to any LLM-based agentic system that uses
document-based handoffs between sessions.

---

## X. The Taxonomy of Oncogenic Errors

Not all documentation errors are oncogenic. The specific properties that make an error
oncogenic rather than merely wrong:

| Property | Oncogenic | Merely wrong |
|---|---|---|
| Location | Guidance/instruction layer | Code or data layer |
| Replication mechanism | Cited by downstream documents that agents are instructed to read | Found in a file that may or may not be read |
| Suppressor bypass | "Do not re-derive" / "investigation complete" language | No explicit instruction not to check |
| Self-infrastructure | Generates its own implementation plan, test specs, DOD | Exists passively |
| Heterogeneity | Multiple variants across documents, each sufficient to regenerate others | Single expression point |
| Hereditary transmission | In germline document (always-loaded context) | In non-essential document |

An error with three or more of these properties is oncogenic: it will survive correction
of any single site and regenerate from residual expression.

The cache fix had all six.

---

## XI. Suppression Protocol Summary

The full suppression regime across this project's documents:

| Suppressor | Mechanism | Where encoded |
|---|---|---|
| Cross-layer tracing | Any cache/performance fix must trace the calling convention to the data source | `MITIGATE.md` §Required Elements |
| Falsifiable success criterion | Observable metric + baseline + target required before implementation | `MITIGATE.md` §Required Elements |
| Production-scenario test | Tests must exercise the trigger threshold, not idealized input | `MITIGATE.md` §Required Elements |
| Known-wrong fixes table | Explicit list of confirmed-wrong changes with explanations | `MITIGATE.md` §Known-Wrong Fixes |
| Adversarial review | High-effort sessions: one agent with no prior-session context | `MITIGATE.md` §Adversarial Review |
| Germline correction | `TherAssist-AgentHandoff.md` Option C3 struck and marked incorrect | `TherAssist-AgentHandoff.md` |
| Corrected propagation chain | All five metastatic documents corrected with explicit wrong-fix warnings | `cache.md`, `CACHE_ANALYSIS_REPORT.md`, `technical.md`, `UNIT_TESTING_SPEC.md`, `TherAssist-AgentHandoff.md` |

Suppression is only effective while these documents remain in the context of agents
performing cache work. If a session is initialized with a subset of project documents
that excludes `MITIGATE.md` and `AUTOPSY_CACHE_FIX.md`, sporadic re-expression is
possible. Session bootstraps for any work touching `prefetch_rag_context` should
explicitly include both.
