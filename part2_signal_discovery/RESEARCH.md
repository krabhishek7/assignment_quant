### Signal Discovery Research Notes

Objective: Extract skills, education, and keywords from semi-structured resume-like text, then map to normalized categories for downstream ranking.

Approach chosen for this assignment: lightweight, deterministic, rule-based extractor with dictionaries and regexes to avoid heavyweight dependencies. Can be augmented with LLM prompts later.

Key signals considered:
- Skills: programming languages, frameworks, data tools, cloud, ML/AI.
- Education: degree keywords (B.Tech, B.E., M.S., Ph.D), institutions.
- Keywords: finance/trading, backend/data eng, research, roles.

Normalization:
- Map raw tokens to canonical buckets (e.g., "PyTorch" -> "ML Frameworks").
- Lowercase, trim, deduplicate; use simple lemmatization via suffix rules (no external NLP libs).

Limitations and mitigations:
- Rule-based can miss variants; mitigate with alias lists and case-insensitive matching.
- Ambiguity in short bios; fallback to keyword presence counts.

Ethics and originality:
- Read-only processing of provided text.
- `integrity_token` included per run to trace artifacts.


