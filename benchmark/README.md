# Common Benchmark Evaluator (B1)

Shared, architecture-neutral evaluation harness for comparing **KAG**,
**HybridRAG** and **NativeRAG** on Vietnamese legal question answering.

> **Status**
>
> * **B1 — evaluation protocol, schemas, evaluator, metrics, unit tests: complete.**
> * **B2 — benchmark construction (the question set itself): NOT YET DONE.**
> * **B3 — benchmark freeze: NOT YET DONE.**
>
> No benchmark question set exists in this directory yet. Nothing here has been
> run against any of the three systems, and no result in this repository was
> produced by this evaluator.

---

## 1. What this is, and what it is not

This package defines **how a comparison is scored**, not what is being scored.
It contains:

* the evaluation protocol (what counts as a correct retrieval, answer, citation
  or refusal),
* two JSON schemas — one for the benchmark dataset, one for a system's output,
* a single shared evaluator every system is scored by, byte-identically,
* metric definitions with explicit formulas and directions,
* unit tests on tiny synthetic data.

It does **not** contain: benchmark questions, gold answers for real legal texts,
system runners, retrievers, generators, prompts, or any result.

## 2. Why the gold truth is architecture-neutral

The three systems chunk, index and retrieve differently. KAG works over a
knowledge graph with its own chunk and node ids; HybridRAG and NativeRAG use
vector stores with their own ids. **A chunk id of any one system can never be
the gold truth of a comparison between all three** — scoring against KAG chunk
ids would mean asking the other two systems to reproduce KAG's segmentation.

The gold truth is therefore expressed in the vocabulary of the law itself:

```
document → article → clause → point → evidence text → gold claim
```

`benchmark_schema.json` actively **rejects** dataset files that carry
system-internal identifiers. `evaluator/models.py` enforces the same list at
load time (`FORBIDDEN_DATASET_KEYS`), so a legacy `gold_chunks.json`-shaped file
cannot be loaded as common gold truth even by accident. The legacy KAG-only
evaluator under `kag/solver/` is untouched and keeps working on its own terms;
it is simply not this.

## 3. Directory layout

```
benchmark/
  README.md                     this file
  benchmark_schema.json         dataset contract (architecture-neutral gold truth)
  system_output_schema.json     what a system must emit to be scored
  evaluator/
    normalization.py            text/marker/number/location normalization
    models.py                   dataset + output parsing, forbidden-key rejection
    evidence_matching.py        structural → text → judge support routes
    retrieval_metrics.py        Evidence Recall, Context Precision, Hit@k, MRR
    answer_metrics.py           Hit Rate, Hit All, Claim P/R/F1
    grounding_metrics.py        Faithfulness, Hallucination Rate, retrieval gap
    citation_metrics.py         Document/Article accuracy, Citation P/R
    abstention_metrics.py       Correct Abstention, False Answer Rate
    aggregate.py                micro / macro-by-category / bootstrap CI
    judge.py                    vendor-free semantic-judge abstraction
    evaluate.py                 orchestration + CLI
  adapters/
    citation_parser.py          the one citation parser all three adapters use
  tests/                        offline unit tests on synthetic data
```

The evaluator lives **outside** `kag/` on purpose and imports none of `kag`,
`hybridRAG` or `nativeRAG`. `tests/test_isolation.py` enforces that
structurally, and also that the package depends on the standard library only.

## 4. Dataset contract (`benchmark_schema.json`)

One item per question:

| field | required | meaning |
|---|---|---|
| `id` | yes | unique question id |
| `question` | yes | the question text |
| `category` | yes | free-form label; macro averaging groups by it |
| `answerable` | yes | `false` = the corpus genuinely cannot answer this |
| `gold_evidence[]` | for answerable items | `{document_id, text, article, clause, point, required, evidence_id}` |
| `gold_markers[]` | optional | strings the answer must contain (amounts, durations, sanctions) |
| `gold_claims[]` | optional | atomic statements the answer should express |
| `source_url`, `source_name`, `notes`, `verification_status` | optional | provenance, for auditing |

`required: false` marks supporting-but-not-mandatory evidence; recall is
reported both over all gold evidence and over required evidence only.

### Labelling convention for gold evidence

Inside one evidence entry, `document_id` and `text` are **mandatory**, `article`
is strongly expected, and `clause` / `point` are optional labels:

* **`text` is mandatory** because it is the only support route every system can
  reach. A system whose adapter reports rich metadata (KAG can often name the
  clause) would otherwise be matched structurally while a system that can name
  only the document (HybridRAG, frequently) would end up undecided on the very
  same passage. Verbatim text puts all three on the same footing.
* **The comparison is scored at the article.** A wrong document or a wrong
  article is a hard negative nothing can overturn; see §7.
* **`clause` and `point` are recorded for error analysis, never for scoring.**
  Write them when you know them — they make failure analysis far sharper — but
  they cannot make a system lose a point, because the three systems label
  clauses at different granularities and penalising the one that declares a
  clause would simply reverse the unfairness.

`gold_claims[]` is optional and B2 does not need it: every headline metric is
decidable without it.

## 5. System output contract (`system_output_schema.json`)

One record per question, per system:

```json
{
  "question_id": "…",
  "system": "kag | hybridrag | nativerag",
  "answer": "…",
  "retrieved_contexts": [
    {"rank": 1, "document_id": "…", "article": "53", "clause": "3",
     "point": "b", "text": "…", "score": null}
  ],
  "citations": [{"document_id": "…", "article": "53", "clause": "3", "point": "b"}],
  "latency_ms": 1234,
  "error": null
}
```

`rank` is 1-based and defaults to list position. `score` is optional and
nullable, and **is never compared across architectures** — a graph traversal
score and a cosine similarity are not the same quantity. `error` marks a failed
run: its metrics become *unavailable*, never zero. `answer_claims` may be
supplied by an adapter to skip judge-side claim extraction.

### Citation contract

`citations[]` is **what the answer text says**, extracted by
`adapters/citation_parser.py`, and nothing else. In particular an adapter may
not build it from `retrieved_contexts`, from chunk metadata, or from any other
channel. This is not hypothetical: `nativeRAG/rag_core/engine.py::generate`
returns the retrieved documents under the name `citations`, so copying that
field across would make NativeRAG's Citation Recall equal to its retrieval
recall for free, without the answer pointing at anything.

All three prompts already require an inline Vietnamese prose citation
(`khoản 2 Điều 8 Nghị định 13/2023/NĐ-CP`), which is the only channel the three
have in common, so that is the only thing parsed. KAG's
`<reference id="chunk:1_2">` tags index its own trace log rather than a legal
location and are ignored. A citation naming no document inherits the nearest
document mentioned before it — the same rule for every system.

The loader cannot enforce this, so it watches for it: when an output's
citations mirror its retrieved contexts exactly (three or more, identical
location sets), the report carries a note saying so. It is a note and not a
rejection, because citing exactly what you retrieved is legitimate.

## 6. Metric catalogue

Retrieval (`retrieval_metrics.py`):

| metric | direction | formula |
|---|---|---|
| `evidence_recall` | ↑ | supported gold evidence / all gold evidence |
| `evidence_recall@k` | ↑ | same, over the top *k* contexts only (`k = 5` in the main table) |
| `evidence_recall_required` | ↑ | same, over required evidence only |
| `context_precision` | ↑ | contexts supporting some gold evidence / all contexts |
| `hit@k` | ↑ | 1 if some context in the top *k* supports required evidence |
| `mrr` | ↑ | 1 / rank of first supporting context, else 0 |
| `evidence_recall@Ntok` | ↑ | Evidence Recall using only the top-ranked contexts that fit an *N*-token budget |

The two `@` suffixes mean different things and the `tok` suffix is what tells
them apart: `evidence_recall@5` cuts the list at five contexts,
`evidence_recall@2000tok` cuts it at a 2000-token context budget.

Answer (`answer_metrics.py`): `hit_rate` ↑ (fraction of gold markers found),
`hit_all` ↑ (all-or-nothing over markers), `claim_precision` / `claim_recall` /
`claim_f1` ↑.

Grounding (`grounding_metrics.py`): `faithfulness` ↑ (claims supported by *that
system's own* retrieved contexts), `hallucination_rate` ↓ (claims unsupported or
contradicted per gold), `retrieval_gap_rate` ↓ (claims true per gold that the
system's own retriever never surfaced), `unsupported_claim_rate` ↓.

Citation (`citation_metrics.py`): `document_accuracy` ↑, `article_accuracy` ↑,
`clause_accuracy` / `point_accuracy` ↑ (diagnostic), `citation_precision` ↑,
`citation_recall` ↑.

Unanswerable (`abstention_metrics.py`): `correct_abstention` ↑,
`false_answer_rate` ↓, `unsupported_claim_rate` ↓.

Operational: `latency_ms` ↓, `error_rate` ↓.

### The paper profile

Everything above is computed and lands in `per_question`. Only a small profile
is *reported*, and the rule for being in it is that the number must be
decidable on a run with no judge at all:

| headline (`PRIMARY_METRICS`) | error analysis (`DIAGNOSTIC_METRICS`) |
|---|---|
| `evidence_recall` | `mrr` |
| `evidence_recall@5` | `hit@5` |
| `evidence_recall@2000tok` | `context_precision` |
| `hit_rate` | `citation_precision` |
| `hit_all` | `citation_document_accuracy` |
| `citation_article_accuracy` | `error_rate` |
| `citation_recall` | |
| `correct_abstention` | |
| `latency_ms` ↓ | |

Computed, kept in `per_question`, not printed in either table:
`citation_clause_accuracy`, `citation_point_accuracy`,
`evidence_recall_required`, `hit@1`, `hit@3`, `hit@10`, `first_relevant_rank`,
`n_undecided`, `n_unavailable`.

Computed but off the publication path until a calibrated judge exists (see §9):
`claim_precision`, `claim_recall`, `claim_f1`, `faithfulness`,
`hallucination_rate`, `retrieval_gap_rate`, `unsupported_claim_rate`,
`false_answer_rate`. The code that computes them is untouched, so switching
them back on is a change to one list in `evaluate.py`.

`k = 5` and the 2000-token budget are fixed in advance and identical for all
three systems; both are written into `report["config"]`. Reading several
cut-offs and reporting the best one per system would be tuning on the test set.

**There is no overall score.** Retrieval quality, answer correctness,
grounding, citation accuracy and abstention behaviour trade off against each
other; averaging them would hide the one thing a reader wants to know, which is
*which* capability is weak. `aggregate.py` refuses to synthesise one, and the
printed report has no total line.

### Faithfulness and Hallucination Rate are not complements

`hallucination_rate` is **not** `1 - faithfulness`. Each claim in an answer
lands in exactly one bucket:

| bucket | faithfulness | hallucination |
|---|---|---|
| supported by the system's own context | counts | — |
| true per gold, absent from context (**retrieval gap**) | — | — |
| unsupported or contradicted per gold | — | counts |
| undecided (no route could decide) | — | — |

A system whose generator is sound but whose retriever is starving it loses
faithfulness without being accused of fabricating. Collapsing the two would
report a retrieval failure as a hallucination, which is the fastest way to make
a RAG comparison say the wrong thing.

## 7. How a context or claim is judged to support evidence

`evidence_matching.py` tries three routes, in order:

1. **structural** — the declared legal location matches (document → article →
   clause → point, as deep as both sides declare);
2. **text** — the evidence text is contained in the context, or token coverage
   reaches the policy threshold (0.8 by default);
3. **judge** — semantic entailment, only if a judge is configured.

Three rules make this safe:

* A **declared mismatch at the scoring depth is a hard negative.** The scoring
  depth is `("document", "article")` — `MatchingPolicy.hard_negative_levels`,
  frozen into `report["config"]["policy"]`. Điều 52 text offered for Điều 53
  evidence is rejected and the judge cannot rescue it
  (`SupportMethod.LOCATION_MISMATCH`). Right answer, wrong pointer is a distinct
  failure that the citation metrics report separately.
* **A clause or point mismatch decides nothing.** It is recorded in
  `soft_mismatch` for error analysis and then handed to the text route — the
  same route a context that declares no clause at all already takes. Without
  this, a system that labels a multi-clause chunk by its first clause would
  fail hard while a system that declares no clause would be rescued by text:
  declaring more would score worse than declaring less, which is the reverse of
  the asymmetry the harness exists to remove.
* **Undecided is not False.** When no route can decide, support is `None`; the
  claim leaves both numerators and is counted in `n_undecided`.

## 8. Normalization policy

`normalization.py` is deliberately separate and deliberately conservative. It
does: Unicode NFC, markdown stripping, whitespace collapsing, thousand-separator
tolerance (`100.000.000` ≡ `100 000 000 đồng`), and diacritic folding **only**
on structural labels (`Điều`, `Khoản`, `Điểm`).

It does **not** merge things that differ in law:

* `Điều 13` ≠ `Điều 31` (no digit reordering),
* `30,5%` ≠ `305%` (separator stripping applies inside digit groups only),
* `330/2026/NĐ-CP` ≠ `331/2026/NĐ-CP` (document numbers are never merged),
* negation is preserved (`không bị xử phạt` ≠ `bị xử phạt`),
* money units and rates are preserved (`triệu` ≠ `tỷ`).

Two profiles exist: `TEXT_PROFILE` for prose comparison, `MARKER_PROFILE`
(whitespace-free) for substring marker matching. Both are unit-tested directly.

## 9. Deterministic metrics vs judge-dependent metrics

| deterministic | judge-dependent (falls back to deterministic first) |
|---|---|
| structural evidence matching, `hit@k`, `mrr`, `hit_rate`, `hit_all`, citation accuracies, abstention cue detection | paraphrase-level evidence support, claim precision/recall, faithfulness, hallucination, contradiction detection, citation entailment, unclear-phrasing abstention |

`judge.py` defines a `Judge` interface with **no vendor and no model name
anywhere**. Three judges ship, all offline: `NullJudge` (default — answers
UNKNOWN to everything, so judge-dependent metrics report `None` rather than a
fabricated 0), `RuleBasedJudge` (lexical, deterministic), `ScriptedJudge` (fixed
answers, for tests and frozen replays). A real LLM judge is an adapter written
outside this package.

**The CLI can only build `NullJudge`.** `RuleBasedJudge` is importable — it is a
useful stand-in in unit tests — but it is not a `--judge` choice, because it
never returns CONTRADICTED. Every number it produces is therefore biased in one
direction (`hallucination_rate` drifts towards 0) while looking complete on the
page, and a complete-looking wrong number is worse than a missing one.

Conditions a judge must meet before any judge-dependent metric goes into the
paper:

1. **Independent of all three systems under test.** A judge that shares a
   generator with one of the contestants is that contestant marking its own
   work.
2. **A purpose-written Vietnamese legal prompt.** Do not port KAG's upstream
   `JudgerPrompt`: it is a Chinese-language few-shot prompt on medical
   multiple-choice questions, and upstream `getBenchMark` defaults to letting
   the system judge itself.
3. **Calibration against human labels** — at minimum 50 human-labelled pairs,
   with the agreement reported next to the results.
4. **A frozen `JudgeConfig`** (model, version, temperature 0, prompt version,
   seed) whose `fingerprint()` is published with the numbers.

Until all four hold, the judge-dependent metrics stay out of both tables and
the comparison rests on the deterministic profile in §6.

`JudgeConfig` freezes a judge for publication — model, model version,
temperature (0), prompt version, seed — and its `fingerprint()` goes into the
report so two runs can be told apart. **B1 calls no API; the whole test suite
runs offline.**

## 10. `None` is not zero

Every metric may be `None`, and each `None` is labelled:

* `not_applicable` — the ground truth does not pose that question (no
  abstention score for an answerable item, no Evidence Recall for an item with
  no gold evidence, no clause accuracy when neither side declares a clause);
* `unavailable` — it does pose the question, but the run could not answer it
  (the system errored, or a judge-dependent metric ran with a judge that decides
  nothing).

Aggregation counts `n`, `n_not_applicable` and `n_unavailable` separately, and a
question with no system output at all is **excluded from every mean** rather
than scored 0 — a crashed run must not be able to look like a wrong answer.

## 11. Aggregation and confidence intervals

* **micro** — plain mean over every question with a real value.
* **macro** — mean over categories of each category's micro mean, so a large
  category cannot swamp a small one. Categories are read from the dataset;
  neither the category list nor the dataset size is hard-coded anywhere.
* **95% CI** — percentile bootstrap over the pooled per-question values, with a
  configurable sample count and a fixed seed (`BootstrapConfig`). A fresh
  `random.Random(seed)` is created per call, so results do not depend on global
  random state: same seed and same inputs give identical bounds. Fewer than two
  values yields `(None, None)` instead of a degenerate interval.
* The CI belongs to **micro only**. Macro is not bootstrapped, because doing it
  honestly needs stratified resampling within categories, which is not
  implemented.

## 12. Running it

```bash
python -m benchmark.evaluator.evaluate \
  --dataset  <benchmark dataset>.json \
  --system-output <one system's outputs>.json \
  --out report.json \
  --k 1,3,5,10 \
  --budgets 2000 \
  --judge null
```

`--k` must include 5 and `--budgets` must include 2000, or the main table loses
a headline row. Both default to exactly that, and `--judge null` is the only
judge the CLI offers.

Tests:

```bash
python -m pytest benchmark/tests -q
```

Fairness rules for an actual comparison, once B2/B3 exist: run every system
through **this** evaluator with the **same** dataset file, the same `--k`, the
same `--budgets`, the same judge configuration and the same bootstrap seed, and
publish that configuration next to the numbers. Comparing budgeted Evidence
Recall at an equal context-token budget is what keeps a system that dumps 8k
tokens of context from looking better than one that retrieves 500 useful ones.

## 13. Known limits

* `RuleBasedJudge` never reports a contradiction; telling contradiction apart
  from absence needs a real entailment model, and guessing would turn a
  retrieval gap into a fake hallucination. That is why it is not a CLI choice.
* `claim_*`, `faithfulness` and `hallucination_rate` need claim extraction. With
  the default `NullJudge` and no adapter-supplied `answer_claims`, they are
  reported as unavailable, not as 0 — and they are off the publication path
  until §9's four conditions are met.
* Clause- and point-level agreement is diagnostic only. The comparison cannot
  currently distinguish "retrieved the right article, wrong clause" from
  "retrieved the right clause" when the evidence text matches; buying that
  distinction back would require every system's adapter to label clauses at the
  same granularity, which is exactly the assumption this harness refuses.
* The citation parser reads prose citations only. A citation whose article is
  named before its document inherits the nearest document mentioned *before*
  it; a list such as "Điều 8 và Điều 9 Nghị định X" therefore attaches the
  document to Điều 9 and leaves Điều 8 without one. The rule is identical for
  all three systems, which is what matters for a comparison, but it is not the
  rule a human reader would apply.
* Token counting uses a tokenizer-free estimate (`max(words, ceil(chars/4))`),
  injectable via `EvaluationConfig.token_counter`. Budget comparisons are
  therefore consistent across systems but not identical to a specific model's
  tokenizer.
