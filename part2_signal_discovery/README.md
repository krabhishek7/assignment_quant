Part 2 – Signal Discovery Agent

Extracts skills, education, and domain keywords from resume-like CSV text.

Quickstart:
```bash
python part2_signal_discovery/signal_extractor.py \
  --input github_profiles_dataset.csv \
  --out part2_signal_discovery/outputs \
  [--enrich-with-github --github-outputs part1_github_agent/outputs]
```

Outputs:
- `signals.csv`: one row per input record with normalized features
- `<row_index>.json`: detailed extraction per record including integrity_token

No external dependencies required.

### What it does
- Auto-detects text fields (bio/summary/experience) and concatenates them per row.
- Uses rule-based dictionaries/regex to extract skills (bucketed), education levels, and domain keywords.
- Consolidates into a primary domain, emits per-row JSON and `signals.csv` with an integrity_token.

### Why these choices
- Deterministic, zero-dependency extraction is dependable in interviews and easy to reason about.
- Provides a strong baseline that can be incrementally improved with NLP/LLM later.

### How to present
- Run the CLI; open `outputs/signals.csv` to show primary_domain, education_levels, and skill_buckets.
- Open one `X.json` to demonstrate the structured signals and integrity_token.
- Discuss how dictionaries can be extended or swapped for ML.

### Enrichment
- Use `--enrich-with-github` to leverage Part 1 outputs: repo languages are added as skills, and repo text boosts domain keyword counts. This reduces empty fields when bios are sparse.

### Trade-offs & extensions
- May miss variants and nuanced phrasing; mitigated with alias lists and case-insensitive matches.
- Extensions: add fuzzy matching, spaCy/HF models, or LLM prompting; include confidence scoring.


