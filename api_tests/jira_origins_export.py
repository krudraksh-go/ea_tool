import csv
import sys
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

import requests

# Reuse Jira config from existing script
try:
    from jira_api import JIRA_BASE_URL, headers
except Exception as import_error:  # pragma: no cover
    print(f"Failed to import Jira configuration from jira_api.py: {import_error}")
    sys.exit(1)


JQL = (
    'project = GreyMatter AND issuetype = "Engineering Analysis"'
)


def fetch_issues(jql: str, max_results: int = 100) -> List[Dict]:
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    start_at = 0
    issues: List[Dict] = []

    while True:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            # Only fetch Origins to minimize payload size
            "fields": ["customfield_11401"],
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        try:
            resp.raise_for_status()
        except Exception as http_error:
            # Provide actionable diagnostics and exit
            print(f"HTTP error while querying Jira (startAt={start_at}): {http_error}")
            try:
                print(f"Response body: {resp.text[:500]}")
            except Exception:
                pass
            sys.exit(2)

        data = resp.json()
        issues_page = data.get("issues", [])
        issues.extend(issues_page)

        total = int(data.get("total", 0))
        if start_at + max_results >= total:
            break
        start_at += max_results

    return issues


def extract_origins_value(origins_field) -> List[str]:
    values: List[str] = []
    if origins_field is None:
        return values

    if isinstance(origins_field, list):
        for origin in origins_field:
            if isinstance(origin, dict):
                value = origin.get("value") or origin.get("name") or str(origin)
            else:
                value = str(origin)
            if value is not None:
                normalized = value.strip()
                if normalized:
                    values.append(normalized)
    elif isinstance(origins_field, dict):
        value = origins_field.get("value") or origins_field.get("name") or str(origins_field)
        if value is not None:
            normalized = value.strip()
            if normalized:
                values.append(normalized)
    else:
        normalized = str(origins_field).strip()
        if normalized:
            values.append(normalized)

    return values


def collect_unique_origins(issues: List[Dict]) -> Tuple[Set[str], Counter]:
    unique: Set[str] = set()
    counts: Counter = Counter()

    for issue in issues:
        fields: Dict = issue.get("fields", {})
        raw = fields.get("customfield_11401")
        values = extract_origins_value(raw)
        for val in values:
            unique.add(val)
            counts[val] += 1

    return unique, counts


def save_origins_to_csv(origins_counts: Counter, filename: str = "jira_origins.csv") -> None:
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["origin", "count"])
        for origin, count in sorted(origins_counts.items(), key=lambda x: (-x[1], x[0].lower())):
            writer.writerow([origin, count])


def main() -> None:
    print("🔍 Fetching Engineering Analysis tickets to extract Origins...")
    issues = fetch_issues(JQL)
    print(f"✅ Retrieved {len(issues)} issues")

    unique, counts = collect_unique_origins(issues)
    print(f"🧭 Found {len(unique)} unique Origins values")

    save_origins_to_csv(counts, filename="jira_origins.csv")
    print("📄 Saved unique Origins and counts to jira_origins.csv")

    # Also print the list to stdout for quick verification
    if unique:
        print("\nTop Origins (by frequency):")
        for origin, count in counts.most_common(20):
            print(f" - {origin}: {count}")


if __name__ == "__main__":
    main()


