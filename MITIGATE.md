# Mitigating LLM-Induced Documentation Drift

## What This Document Is

A standing protocol for this project to prevent the class of failure documented in
`AUTOPSY_CACHE_FIX.md`: an LLM analysis pass produces a locally coherent but globally
wrong conclusion, encodes it into authoritative-looking documents, and subsequent
agents treat those documents as settled ground truth. The error then propagates into
roadmaps, session bootstraps, and test specs — surviving indefinitely because every
document downstream instructs agents not to re-derive.

This is not a hypothetical risk. It happened once in this codebase and produced a wrong
fix that was scheduled in `technical.md`, implemented as Task 1 in `backend/cache.md`,
codified in test specs, and endorsed by at least three independent review passes before
the error was caught.

---

## Preliminary Risk Assessment by Effort Level

### `/effort high` — Parallelization amplifies document poisoning

High-effort sessions run multiple agents simultaneously against the same context
window. This is the stated mechanism: parallelization + sophisticated prompt
engineering + high context utilization. The risk profile is different from iterative
single-agent work, and in some ways worse:

| Property | Effect on drift risk |
|---|---|
| Multiple agents reading the same flawed document simultaneously | N agents reach the same wrong conclusion independently — creates the appearance of consensus without providing it |
| Authoritative-looking output at each layer | Each pass produces well-structured analysis that is harder to question than a throwaway comment |
| "Investigation complete — do not re-derive" language | Standard handoff language for high-effort sessions; becomes a propagation mechanism for errors |
| High context utilization | More sophisticated documents, more elaborate wrong fixes, more layers of cross-references that all agree |
| Deep intra-session parallelism | An adversarial reviewer and a proposing agent can't be truly independent if they read the same prior-session documents |

**The specific failure mode for `/effort high`:** a single wrong inference in Session N
gets document coverage within that session (because multiple sub-agents elaborate it),
becomes "prior analysis" for Session N+1, and arrives pre-endorsed.

### `/effort medium` — Iteration without auditing compounds errors

Medium-effort sessions are typically sequential: one agent, one pass, incremental
improvements. The risk profile is lower amplitude but more insidious:

| Property | Effect on drift risk |
|---|---|
| Each pass builds on prior output | Wrong assumptions accumulate silently — each layer is consistent with the layer below it |
| Less context overhead | Simpler documents, less elaborate wrong fixes — but also less visibility into cross-layer dependencies |
| No adversarial reviewer | Nobody checks whether the thing being improved is worth improving |
| "Improve the cache" task framing | Agent reads `cache.md`, sees a detailed implementation plan, implements it without checking if the plan is correct |

**The specific failure mode for `/effort medium`:** a wrong fix gets implemented as
described, passes structural DOD checks (the field exists in the response), and is
committed. The wrong fix is now in production code and future agents work around it
rather than questioning it.

---

## The Anatomy of This Failure Class

Six conditions, all present in the cache fix case, are sufficient for a wrong LLM
conclusion to become permanent in a codebase:

1. **Local coherence**: The fix is correct when analyzed within the function it touches.
   Cross-layer analysis (tracing callers, tracing data sources) is required to see the
   flaw.

2. **A plausible-sounding mechanism**: "Align the hash with the query" sounds like a
   consistency improvement. The semantic/deterministic confusion (similar passages vs.
   same hash) is not obvious on inspection.

3. **Authoritative document language**: "Investigation complete", "settled facts",
   "do not re-derive" — standard handoff efficiency language that accidentally blocks
   error correction.

4. **A structural DOD that passes without the fix working**: "Assert that
   `context_cache_hit` appears in the response" passes whether cache hits ever occur
   or not. The wrong fix can be declared done.

5. **Test specs written under the same false premise**: The tests were designed to
   confirm the fix, not to validate it. They would have failed on execution — but they
   were never run before the spec was committed.

6. **No observable success criterion**: The metric "cache hit rate > 50%" appeared in
   `technical.md` but was not wired to any automated measurement. It was aspirational,
   not falsifiable.

---

## Protocol: Document Classification

Not all documents carry the same forward risk. Apply these labels explicitly:

| Label | Meaning | What agents may do with it |
|---|---|---|
| `FINDING` | An observed fact about code behavior | Trust and cite |
| `HYPOTHESIS` | A proposed explanation for a finding | Must be verified before acting |
| `PROPOSED FIX` | A concrete change that may resolve a finding | Must be validated against the finding's success criterion before committing |
| `VERIFIED FIX` | A proposed fix whose observable criterion was met | May be implemented |
| `SUPERSEDED` | Prior content known to be wrong | Must not be acted on; update or mark explicitly |

Documents in this project that carry `PROPOSED FIX` content without a `VERIFIED` marker
should be treated as hypotheses, not instructions.

---

## Protocol: Required Elements for Any Cache/Performance Fix Document

Before a performance fix (cache, latency, token cost) is written into a session
bootstrap or roadmap item, the document must include all four of these:

### 1. The observable metric and its baseline

```
Metric: _diagnostics.grounding.prefetch.cache_hit == true
Baseline: 0% of realtime responses (as of 2026-06-06)
Target: ≥ 40% over a 5-minute session at normal conversational pace (~130 wpm)
```

Without a baseline and a measurable target, "fix the cache" cannot be declared done
and cannot be falsified.

### 2. A cross-layer trace

Any fix to a backend function must trace the calling path back to the data source.
For `prefetch_rag_context`, the required trace is:

```
frontend trigger → transcript window construction → HTTP payload → 
format_transcript_segment → transcript_text growth pattern → hash input
```

A fix proposed without this trace is local analysis only and must be labeled
`HYPOTHESIS`.

### 3. A falsifiability condition

The document must state under what observable conditions the fix is wrong:

```
This fix is wrong if, after applying it, cache_hit remains < 10% over a 
5-minute session at 130 wpm. If that occurs, the TTL is still the wrong 
mechanism and Option 3 (background prefetch) is required.
```

### 4. A test that would fail if the fix doesn't work

The test must not be written under the same assumption as the fix. It must test
the production scenario — the trigger threshold and speaking pace — not an
idealized scenario with minimal input.

For the cache: "append 8 words (the actual trigger threshold) and assert cache hit"
is the correct test. "Append 5 words and assert hash unchanged" is wrong because
it tests below the trigger threshold and the assertion was false.

---

## Protocol: "Do Not Re-Derive" Language

The phrase "investigation complete — do not re-derive" is useful for avoiding
redundant work. It is dangerous when the investigation contained an error.

**Replace it with:**

```
Investigation complete as of [date]. Findings are in [document].
If a proposed fix in this document appears inconsistent with the code behavior
you observe, the finding may be correct but the fix may be wrong — check
AUTOPSY_CACHE_FIX.md for the known failure mode before implementing.
```

The key change: separate "the finding is settled" from "the fix is settled."
Findings are observations. Fixes are hypotheses until validated.

---

## Protocol: Adversarial Review for `/effort high` Sessions

When a high-effort session produces a proposed fix to a caching, latency, or
cost-optimization system, one agent in that session must be given only the
following context:
- The function being fixed
- The production trigger mechanism (how often is this called, what changes between calls)
- The success metric

It must NOT be given:
- The prior session's analysis documents
- The proposed fix
- Any framing as "improving" an existing approach

If the adversarial agent reaches the same conclusion independently, the fix has
stronger standing. If it reaches a different conclusion, both conclusions must be
resolved before the fix is implemented.

This is not standard practice — it is reserved for fixes to systems where a wrong
implementation is observable only at production conversational pace, not in unit
tests or casual smoke testing.

---

## Specific Known-Wrong Fixes for This Codebase

The following proposed changes have been analyzed and confirmed incorrect.
Do not implement them regardless of what prior documents say:

| Fix | Why it's wrong | Correct alternative |
|---|---|---|
| Hash `transcript_text[-200 words]` instead of `[-500 chars]` for RAG cache | Both windows include the tail of a growing string; the hash changes on every trigger either way | Remove the hash check entirely; use TTL only |
| Hash `transcript_text[-5000:]` for RAG cache | Same structural problem; larger window, same result | Remove the hash check entirely |
| Extend `RAG_CACHE_TTL_SECONDS` to 90 without removing hash | TTL is gated behind hash check; if hash always fails, TTL value is irrelevant | Remove hash check first; then TTL extension matters |

---

## Verification Checkpoint for Session Bootstraps

Before using a document as a session bootstrap for implementing a fix, verify:

- [ ] The DOD includes a measurable metric, not just structural compliance
- [ ] The proposed code change has a cross-layer trace (not just local function analysis)  
- [ ] At least one test exercises the production-pace scenario (not idealized input)
- [ ] "Investigation complete" language distinguishes findings from fixes
- [ ] No test in the spec would pass if the fix doesn't actually work

If any of these are missing, add them before giving the document to an implementation
agent. A missing item means the fix could be implemented incorrectly and declared done.
