### AI Tools & Research Intern Assignment – Submission

Hi! I built and demoed two lightweight agents with a focus on clarity, determinism, and interview-readiness. Everything is stdlib-only, reproducible, and includes an integrity_token that changes each run.

### What this project does
- Part 1 – GitHub Agent: Given developer usernames, fetches repository metadata from GitHub and analyzes activity trends (stars, forks, languages, recency, monthly timeline). Outputs per-developer JSON plus a cross-developer `summary.csv`.
- Part 2 – Signal Discovery Agent: Reads resume-like CSV text and extracts skills, education, and domain keywords, mapping them into normalized categories. Outputs per-row JSON plus `signals.csv`.

### Why I designed it this way
- Stdlib-only: zero setup friction for interview/demo; easy to audit.
- Deterministic metrics: simple, explainable trend analysis from repo metadata (no heavy commit crawling) to respect rate limits and time.
- Integrity token: fresh UUID per run to tie artifacts to execution and support originality checks.
- Resilience: pagination, basic retry/backoff, optional token for higher limits; optional `--no-verify-ssl` to work around macOS cert issues during live demos.

### How to run (Quickstart)
```bash
# Part 1 – GitHub Agent
python part1_github_agent/github_agent.py \
  --input part1_github_agent/developers.csv \
  --out part1_github_agent/outputs \
  [--token "$GITHUB_TOKEN"] [--since-days 90] [--no-verify-ssl]

# Part 2 – Signal Discovery Agent
python part2_signal_discovery/signal_extractor.py \
  --input github_profiles_dataset.csv \
  --out part2_signal_discovery/outputs
```

Tips:
- Set `GITHUB_TOKEN` to raise API limits during the interview.
- Use `--no-verify-ssl` only if your macOS local cert store causes SSL errors.

### Repository structure
```
part1_github_agent/
  AGENT_DESIGN.md
  README.md
  github_agent.py
  developers.csv
  outputs/
part2_signal_discovery/
  RESEARCH.md
  AGENT.md
  README.md
  requirements.txt
  signal_extractor.py
  outputs/
video_link.md
```

