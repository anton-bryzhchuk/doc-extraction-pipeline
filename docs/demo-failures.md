# Demo: the validation layer catches bad extractions

Each mock profile injects a realistic extraction failure. This table shows
how the deterministic validation + routing layer handled it. The key column
is **wrongly auto-approved** -- a wrong value that slipped through (must be 0).

**Result:** all handled ✅

| Profile | Injected failure | Auto-approved | Needs review | Failed | Wrongly auto-approved |
|---------|------------------|---------------|--------------|--------|-----------------------|
| `noisy` | misread/missing fields -> routed to needs_review | 21 | 9 | 0 | **0** |
| `hallucinating` | invented wrong total -> arithmetic check fails -> needs_review | 18 | 12 | 0 | **0** |
| `malformed` | invalid JSON -> fails after retries -> status failed | 21 | 0 | 9 | **0** |

