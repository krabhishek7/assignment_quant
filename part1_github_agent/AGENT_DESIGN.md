### GitHub Agent – Design

**Goal**: For a list of GitHub profiles, fetch repository metadata and analyze developer activity trends. Produce per-developer JSON reports and a cross-developer summary CSV, including a fresh integrity_token on each run.

### Inputs
- `developers.csv`: columns include at least `name`, `username`, `profile_url`.
- Optional `GITHUB_TOKEN` via env or `--token` flag to increase rate limits.

### Outputs
- `outputs/<username>.json`: normalized repository dataset and derived metrics.
- `outputs/summary.csv`: one row per developer with key metrics.
- Integrity token: unique UUID v4 recorded in every JSON and in `summary.csv`.

### Key Metrics
- Total repositories analyzed
- Total stars, forks
- Primary languages distribution (by repo language)
- Last activity timestamps (repo `pushed_at` and `updated_at`)
- Recent activity (repos updated in last 30/90 days)
- Activity timeline: count of repo updates grouped by month

### Architecture
1. CSV Loader parses `developers.csv` and validates minimal columns.
2. GitHub Client fetches `users/{username}/repos` with pagination and optional token.
3. Analyzer computes metrics and trends from repo metadata only (no heavy commit crawling), minimizing rate usage.
4. Writer serializes per-developer JSON and an aggregated summary CSV.

### Rate Limits & Resilience
- Unauthenticated: ~60 req/hr; authenticated: ~5k req/hr.
- Pagination handled via `Link` header; `per_page=100` to reduce calls.
- Backoff: simple sleep on 403 rate-limit responses using `X-RateLimit-Reset` when available.
- Network robustness: retries on transient 5xx with jitter.

### Data Schema (per developer JSON)
```
{
  "integrity_token": "uuid4",
  "generated_at": "ISO-8601",
  "developer": {"name": str, "username": str, "profile_url": str},
  "metrics": {
    "repo_count": int,
    "total_stars": int,
    "total_forks": int,
    "languages": {language: count},
    "recent_activity": {"updated_last_30d": int, "updated_last_90d": int},
    "last_pushed_at": "ISO-8601|null",
    "last_updated_at": "ISO-8601|null",
    "monthly_update_counts": {"YYYY-MM": int}
  },
  "repos": [
    {
      "name": str,
      "html_url": str,
      "description": str|null,
      "language": str|null,
      "stargazers_count": int,
      "forks_count": int,
      "open_issues_count": int,
      "created_at": "ISO-8601",
      "updated_at": "ISO-8601",
      "pushed_at": "ISO-8601"
    }
  ]
}
```

### Ethical Use & Originality
- The agent performs read-only public data access and respects rate limits.
- `integrity_token` changes every run to link outputs to execution.

### Runbook
- CLI: `python github_agent.py --input developers.csv --out outputs --token $GITHUB_TOKEN`
- Artifacts are deterministic given GitHub state at runtime (aside from token).


