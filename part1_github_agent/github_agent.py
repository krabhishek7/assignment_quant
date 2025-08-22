from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import ssl

try:
    import urllib.request as ulreq
    import urllib.error as ulerr
    from urllib.parse import urlparse, parse_qs, urlunparse
except Exception as exc: 
    print(f"Failed to import urllib: {exc}", file=sys.stderr)
    raise


GITHUB_API_ROOT = "https://api.github.com"


@dataclass
class Developer:
    name: str
    username: str
    profile_url: str


def read_developers_csv(path: str) -> List[Developer]:
    developers: List[Developer] = []
    with open(path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"name", "username", "profile_url"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"Input CSV missing required columns: {sorted(missing)}. Present: {reader.fieldnames}"
            )
        for row in reader:
            name = (row.get("name") or "").strip()
            username = (row.get("username") or "").strip()
            profile_url = (row.get("profile_url") or "").strip()
            if not username:
                # attempt to derive from profile_url
                try:
                    parsed = urlparse(profile_url)
                    if parsed.netloc.endswith("github.com"):
                        parts = parsed.path.strip("/").split("/")
                        if parts and parts[0]:
                            username = parts[0]
                except Exception:
                    pass
            if not username:
                continue
            developers.append(Developer(name=name or username, username=username, profile_url=profile_url))
    return developers


def build_headers(token: Optional[str]) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "qa-assignment-github-agent",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def http_get_json(url: str, headers: Dict[str, str], retries: int = 3, sleep_seconds: float = 1.0, ssl_context: Optional[ssl.SSLContext] = None) -> Tuple[object, Dict[str, str]]:
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        req = ulreq.Request(url, headers=headers, method="GET")
        try:
            with ulreq.urlopen(req, timeout=30, context=ssl_context) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset)
                data = json.loads(body)
                # Extract relevant headers (for pagination, rate limiting)
                hdrs = {k: v for k, v in resp.headers.items()}
                return data, hdrs
        except ulerr.HTTPError as e:
            # Rate limit handling
            if e.code == 403:
                reset = e.headers.get("X-RateLimit-Reset")
                if reset and reset.isdigit():
                    reset_epoch = int(reset)
                    now = int(time.time())
                    wait = max(0, reset_epoch - now) + 1
                    print(f"Rate limited. Sleeping {wait}s until reset...", file=sys.stderr)
                    time.sleep(min(wait, 60)) 
                    last_err = e
                    continue
            if 500 <= e.code < 600 and attempt < retries:
                time.sleep(sleep_seconds * (attempt + 1))
                last_err = e
                continue
            raise
        except ulerr.URLError as e:
            last_err = e
            if attempt < retries:
                time.sleep(sleep_seconds * (attempt + 1))
                continue
            raise
        except Exception as e:  # pragma: no cover
            last_err = e
            if attempt < retries:
                time.sleep(sleep_seconds * (attempt + 1))
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("GET failed without exception")


def paginate_repos(username: str, headers: Dict[str, str], ssl_context: Optional[ssl.SSLContext]) -> Iterable[dict]:
    url = f"{GITHUB_API_ROOT}/users/{username}/repos?per_page=100&type=owner&sort=updated"
    while url:
        data, resp_headers = http_get_json(url, headers, ssl_context=ssl_context)
        if not isinstance(data, list):
            break
        for item in data:
            yield item
        link_header = resp_headers.get("Link") or resp_headers.get("link")
        url = None
        if link_header:
            # Example: <https://api.github.com/user/123/repos?page=2>; rel="next", <...>; rel="last"
            parts = [p.strip() for p in link_header.split(",")]
            for p in parts:
                if "rel=\"next\"" in p:
                    start = p.find("<")
                    end = p.find(">", start + 1)
                    if start != -1 and end != -1:
                        url = p[start + 1 : end]
                        break


def iso_to_dt(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def analyze_repos(repos: List[dict], since_days: int = 90) -> Dict[str, object]:
    total_stars = 0
    total_forks = 0
    languages = Counter()
    last_pushed_at: Optional[dt.datetime] = None
    last_updated_at: Optional[dt.datetime] = None
    monthly_update_counts: Dict[str, int] = defaultdict(int)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=since_days)
    updated_last_30d = 0
    updated_last_90d = 0

    for repo in repos:
        total_stars += int(repo.get("stargazers_count") or 0)
        total_forks += int(repo.get("forks_count") or 0)
        lang = repo.get("language")
        if lang:
            languages[lang] += 1
        pushed = iso_to_dt(repo.get("pushed_at"))
        updated = iso_to_dt(repo.get("updated_at"))
        if pushed and (last_pushed_at is None or pushed > last_pushed_at):
            last_pushed_at = pushed
        if updated and (last_updated_at is None or updated > last_updated_at):
            last_updated_at = updated
        # Monthly timeline by updated_at
        if updated:
            ym = updated.strftime("%Y-%m")
            monthly_update_counts[ym] += 1
            if updated >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30):
                updated_last_30d += 1
            if updated >= cutoff:
                updated_last_90d += 1

    metrics = {
        "repo_count": len(repos),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "languages": dict(languages.most_common()),
        "recent_activity": {
            "updated_last_30d": updated_last_30d,
            "updated_last_90d": updated_last_90d,
        },
        "last_pushed_at": last_pushed_at.isoformat() if last_pushed_at else None,
        "last_updated_at": last_updated_at.isoformat() if last_updated_at else None,
        "monthly_update_counts": dict(sorted(monthly_update_counts.items())),
    }
    return metrics


def normalize_repo(repo: dict) -> dict:
    return {
        "name": repo.get("name"),
        "html_url": repo.get("html_url"),
        "description": repo.get("description"),
        "language": repo.get("language"),
        "stargazers_count": int(repo.get("stargazers_count") or 0),
        "forks_count": int(repo.get("forks_count") or 0),
        "open_issues_count": int(repo.get("open_issues_count") or 0),
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
    }


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, obj: object) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_summary_csv(path: str, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def run(input_csv: str, out_dir: str, token: Optional[str], since_days: int, no_verify_ssl: bool) -> None:
    ensure_dir(out_dir)
    developers = read_developers_csv(input_csv)
    headers = build_headers(token)
    integrity_token = str(uuid.uuid4())
    summary_rows: List[Dict[str, object]] = []
    ssl_context: Optional[ssl.SSLContext]
    if no_verify_ssl or os.getenv("GITHUB_SSL_NO_VERIFY") == "1":
        ssl_context = ssl._create_unverified_context()  # type: ignore[attr-defined]
    else:
        ssl_context = ssl.create_default_context()

    for dev in developers:
        print(f"Processing {dev.username}...")
        repos = [normalize_repo(r) for r in paginate_repos(dev.username, headers, ssl_context)]
        metrics = analyze_repos(repos, since_days=since_days)
        report = {
            "integrity_token": integrity_token,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "developer": {
                "name": dev.name,
                "username": dev.username,
                "profile_url": dev.profile_url,
            },
            "metrics": metrics,
            "repos": repos,
        }
        write_json(os.path.join(out_dir, f"{dev.username}.json"), report)
        summary_rows.append(
            {
                "integrity_token": integrity_token,
                "name": dev.name,
                "username": dev.username,
                "profile_url": dev.profile_url,
                "repo_count": metrics["repo_count"],
                "total_stars": metrics["total_stars"],
                "total_forks": metrics["total_forks"],
                "updated_last_30d": metrics["recent_activity"]["updated_last_30d"],
                "updated_last_90d": metrics["recent_activity"]["updated_last_90d"],
                "last_updated_at": metrics["last_updated_at"],
            }
        )

    write_summary_csv(os.path.join(out_dir, "summary.csv"), summary_rows)
    print(f"Integrity token: {integrity_token}")
    print(f"Wrote {len(summary_rows)} reports to: {out_dir}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GitHub Agent: analyze developer repo activity")
    parser.add_argument("--input", required=True, help="Path to developers.csv")
    parser.add_argument("--out", required=True, help="Output directory for reports")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN"), help="GitHub token (or set GITHUB_TOKEN)")
    parser.add_argument("--since-days", type=int, default=90, help="Window for recent activity metrics")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification (for local environments with cert issues)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        run(args.input, args.out, args.token, args.since_days, args.no_verify_ssl)
        return 0
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


