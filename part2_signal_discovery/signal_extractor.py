#!/usr/bin/env python3
"""
Signal Discovery Agent: extracts skills, education, and domain keywords from CSV text fields.
Stdlib-only, deterministic rules. Includes integrity_token per run.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_rows(csv_path: str) -> List[dict]:
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def select_text_fields(fieldnames: List[str]) -> List[str]:
    names = [n.lower() for n in fieldnames]
    candidates = []
    for i, n in enumerate(names):
        if any(key in n for key in ["bio", "summary", "experience", "description", "about"]):
            candidates.append(fieldnames[i])
    # Fallback: if nothing matched, use all non-URL-ish text-like columns
    if not candidates:
        for i, n in enumerate(names):
            if not any(key in n for key in ["url", "http", "https", "email", "image", "avatar", "stats"]):
                candidates.append(fieldnames[i])
    return candidates


ALIAS_SKILLS = {
    # languages
    "python": "Programming Languages",
    "java": "Programming Languages",
    "c++": "Programming Languages",
    "c#": "Programming Languages",
    "javascript": "Programming Languages",
    "typescript": "Programming Languages",
    "go": "Programming Languages",
    "rust": "Programming Languages",
    "scala": "Programming Languages",
    "sql": "Programming Languages",
    # frameworks & libs
    "pytorch": "ML Frameworks",
    "tensorflow": "ML Frameworks",
    "scikit-learn": "ML Frameworks",
    "sklearn": "ML Frameworks",
    "keras": "ML Frameworks",
    "xgboost": "ML Frameworks",
    "lightgbm": "ML Frameworks",
    "numpy": "Data Libraries",
    "pandas": "Data Libraries",
    "matplotlib": "Data Visualization",
    "seaborn": "Data Visualization",
    # cloud
    "aws": "Cloud",
    "gcp": "Cloud",
    "azure": "Cloud",
    # data eng
    "spark": "Data Engineering",
    "hadoop": "Data Engineering",
    "kafka": "Data Engineering",
    "airflow": "Data Engineering",
}


EDUCATION_KEYWORDS = {
    "phd": "Doctorate",
    "doctor": "Doctorate",
    "m.s": "Masters",
    "ms": "Masters",
    "mtech": "Masters",
    "m.tech": "Masters",
    "m.sc": "Masters",
    "btech": "Bachelors",
    "b.tech": "Bachelors",
    "b.e": "Bachelors",
    "be ": "Bachelors",
    "b.sc": "Bachelors",
}


DOMAIN_KEYWORDS = {
    "trading": "Finance",
    "quant": "Finance",
    "algorithmic": "Finance",
    "algotrading": "Finance",
    "backend": "Software Engineering",
    "frontend": "Software Engineering",
    "fullstack": "Software Engineering",
    "data engineer": "Data",
    "data science": "Data",
    "ml": "AI/ML",
    "ai": "AI/ML",
    "research": "Research",
}


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_skills(text: str) -> Dict[str, List[str]]:
    text_l = normalize_text(text)
    found_by_bucket: Dict[str, set] = defaultdict(set)
    for alias, bucket in ALIAS_SKILLS.items():
        if alias in text_l:
            found_by_bucket[bucket].add(alias)
    return {bucket: sorted(list(vals)) for bucket, vals in found_by_bucket.items()}


def extract_education(text: str) -> List[str]:
    text_l = normalize_text(text)
    edu = set()
    for key, bucket in EDUCATION_KEYWORDS.items():
        if key in text_l:
            edu.add(bucket)
    return sorted(list(edu))


def extract_domains(text: str) -> Dict[str, int]:
    text_l = normalize_text(text)
    counts: Dict[str, int] = defaultdict(int)
    for key, bucket in DOMAIN_KEYWORDS.items():
        if key in text_l:
            counts[bucket] += text_l.count(key)
    return dict(counts)


def consolidate_signals(skills: Dict[str, List[str]], education: List[str], domains: Dict[str, int]) -> Dict[str, object]:
    top_domain = None
    if domains:
        top_domain = max(domains.items(), key=lambda kv: kv[1])[0]
    return {
        "education": education,
        "skills": skills,
        "domain_counts": domains,
        "primary_domain": top_domain,
    }


def parse_github_username_from_row(row: dict) -> Optional[str]:
    # Try common columns first
    candidates = []
    for key in row.keys():
        k = (key or "").lower()
        if "github" in k:
            candidates.append(key)
        if "repos url" in k:
            candidates.append(key)
    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for c in candidates:
        if c not in seen:
            ordered.append(c)
            seen.add(c)
    for col in ordered:
        val = (row.get(col) or "").strip()
        if not val:
            continue
        try:
            parsed = urlparse(val)
            if parsed.netloc.endswith("github.com"):
                parts = parsed.path.strip("/").split("/")
                if parts and parts[0]:
                    return parts[0]
        except Exception:
            continue
    return None


def enrich_from_github_outputs(username: str, outputs_dir: str) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    """Return (skills_delta, domain_counts_delta) using Part 1 outputs if available.
    - Adds repo languages into skills bucket "Programming Languages".
    - Scans repo names/descriptions for domain keywords to boost domain counts.
    """
    path = os.path.join(outputs_dir, f"{username}.json")
    if not os.path.exists(path):
        return {}, {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        skills_delta: Dict[str, List[str]] = {}
        domain_delta: Dict[str, int] = defaultdict(int)
        # Languages from metrics
        langs = list((data.get("metrics") or {}).get("languages", {}).keys())
        if langs:
            skills_delta["Programming Languages"] = sorted(set(langs))
        # Scan repo text for domain keywords
        repos = data.get("repos") or []
        for r in repos:
            text = f"{r.get('name') or ''} {r.get('description') or ''}".lower()
            for key, bucket in DOMAIN_KEYWORDS.items():
                if key in text:
                    domain_delta[bucket] += text.count(key)
        return skills_delta, dict(domain_delta)
    except Exception:
        return {}, {}


def write_json(path: str, obj: object) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_signals_csv(path: str, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def run(input_csv: str, out_dir: str, enrich_with_github: bool = False, github_outputs_dir: Optional[str] = None) -> None:
    ensure_dir(out_dir)
    rows = load_rows(input_csv)
    if not rows:
        print("No rows found in input", file=sys.stderr)
        return
    integrity_token = str(uuid.uuid4())
    fieldnames = list(rows[0].keys())
    text_fields = select_text_fields(fieldnames)
    summary_rows: List[Dict[str, object]] = []

    for idx, row in enumerate(rows):
        text_parts = [str(row.get(f) or "") for f in text_fields]
        combined = " \n ".join(text_parts)
        skills = extract_skills(combined)
        education = extract_education(combined)
        domains = extract_domains(combined)
        enriched = False
        if enrich_with_github:
            username = parse_github_username_from_row(row)
            if username and github_outputs_dir:
                skills_delta, domain_delta = enrich_from_github_outputs(username, github_outputs_dir)
                if skills_delta:
                    for bucket, vals in skills_delta.items():
                        existing = set(skills.get(bucket, []))
                        skills[bucket] = sorted(existing.union(set(vals)))
                if domain_delta:
                    for bucket, inc in domain_delta.items():
                        domains[bucket] = domains.get(bucket, 0) + int(inc)
                enriched = bool(skills_delta or domain_delta)
        consolidated = consolidate_signals(skills, education, domains)
        # Backfill primary_domain if still empty but we have some skills
        if not consolidated["primary_domain"] and consolidated["skills"]:
            consolidated["primary_domain"] = "Software Engineering"
        record = {
            "integrity_token": integrity_token,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "row_index": idx,
            "source_fields": text_fields,
            "signals": consolidated,
            "enriched_with_github": enriched,
        }
        write_json(os.path.join(out_dir, f"{idx}.json"), record)
        summary_rows.append(
            {
                "integrity_token": integrity_token,
                "row_index": idx,
                "primary_domain": consolidated["primary_domain"],
                "education_levels": ";".join(consolidated["education"]),
                "skill_buckets": ";".join(sorted(consolidated["skills"].keys())),
                "skill_terms_count": sum(len(v) for v in consolidated["skills"].values()),
                "enriched_with_github": "yes" if enriched else "no",
            }
        )

    write_signals_csv(os.path.join(out_dir, "signals.csv"), summary_rows)
    print(f"Integrity token: {integrity_token}")
    print(f"Processed {len(rows)} rows → {out_dir}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Signal Discovery Agent")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--enrich-with-github", action="store_true", help="Enrich using Part 1 outputs if available")
    parser.add_argument("--github-outputs", default="part1_github_agent/outputs", help="Path to Part 1 outputs directory")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        run(args.input, args.out, enrich_with_github=args.enrich_with_github, github_outputs_dir=args.github_outputs)
        return 0
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


