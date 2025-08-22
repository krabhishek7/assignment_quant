### Signal Discovery Agent – Design

Reads a resumes dataset (CSV), extracts skills, education, and domain keywords from text columns (e.g., Bio/Experience), and maps them to normalized categories. Outputs per-candidate JSON and a consolidated CSV with key features, with a fresh integrity_token per run.

Pipeline:
1. Load CSV; select text fields (auto-detect: columns containing "bio", "summary", "experience", case-insensitive).
2. Preprocess: lowercase, normalize whitespace, keep alphanumerics and select symbols.
3. Extractors: dictionary/regex matchers for skills, education, domain keywords.
4. Normalizer: map to canonical categories.
5. Writer: emit `<row_id>.json` and `signals.csv`.

CLI:
```bash
python part2_signal_discovery/signal_extractor.py --input github_profiles_dataset.csv --out part2_signal_discovery/outputs
```


