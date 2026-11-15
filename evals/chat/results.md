# Chat agent evaluation

Generated 2026-11-15T23:56:26+00:00 by `make eval` ([run_eval.py](run_eval.py)) on [golden.jsonl](golden.jsonl): 52 questions (rules, history, stats). Retrieval: hybrid (vector + full-text) (982 embedded chunks), searched as the agent does (rules questions filtered to FIA documents).

| Metric | Score | Target |
|---|---|---|
| Retrieval hit@5 (rules + history) | 84% | 70% |
| … rules (FIA) | 76% | |
| … history (Wikipedia, summaries) | 93% | |
| Stats answers that used `query_stats` | 100% | 95% |
| Answer correctness (key facts), 51 answered | 96% | |
| … history | 87% | |
| … rules | 100% | |
| … stats | 100% | |

Retrieval misses: hist-12, rules-06, rules-09, rules-15, rules-16.  
Wrong answers: hist-05, hist-12.  
Unanswered (providers busy): rules-06.
