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
| `gold_evidence[]` | for answerable items | `{document_id, article, clause, point, text, required, evidence_id}` |
| `gold_markers[]` | optional | strings the answer must contain (amounts, durations, sanctions) |
| `gold_claims[]` | optional | atomic statements the answer should express |
| `source_url`, `source_name`, `notes`, `verification_status` | optional | provenance, for auditing |

`required: false` marks supporting-but-not-mandatory evidence; recall is
reported both over all gold evidence and over required evidence only.

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

## 6. Metric catalogue

Retrieval (`retrieval_metrics.py`):

| metric | direction | formula |
|---|---|---|
| `evidence_recall` | ↑ | supported gold evidence / all gold evidence |
| `evidence_recall_required` | ↑ | same, over required evidence only |
| `context_precision` | ↑ | contexts supporting some gold evidence / all contexts |
| `hit@k` | ↑ | 1 if some context in the top *k* supports required evidence |
| `mrr` | ↑ | 1 / rank of first supporting context, else 0 |
| `evidence_recall@Ntok` | ↑ | Evidence Recall using only the top-ranked contexts that fit an *N*-token budget |

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

Two rules make this safe:

* A **declared location mismatch is a hard negative.** Điều 52 text offered for
  Điều 53 evidence is rejected, and the judge cannot rescue it
  (`SupportMethod.LOCATION_MISMATCH`). Right answer, wrong pointer is a distinct
  failure that the citation metrics report separately.
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
  --budgets 2000,4000 \
  --judge null
```

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
  retrieval gap into a fake hallucination.
* `claim_*`, `faithfulness` and `hallucination_rate` need claim extraction. With
  the default `NullJudge` and no adapter-supplied `answer_claims`, they are
  reported as unavailable, not as 0.
* Clause- and point-level accuracy are diagnostics: most items are not authored
  to require that depth.
* Token counting uses a tokenizer-free estimate (`max(words, ceil(chars/4))`),
  injectable via `EvaluationConfig.token_counter`. Budget comparisons are
  therefore consistent across systems but not identical to a specific model's
  tokenizer.
