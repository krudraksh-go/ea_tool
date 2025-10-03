import requests
import csv
from tqdm import tqdm

# ==============================
# Jira Setup
# ==============================
JIRA_BASE_URL = "https://work.greyorange.com/jira"
API_TOKEN = "NjQzMTc1MzM3NjQ0On0fuL/A6sogWMfDPEUaHhPJAUV/"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}

# ==============================
# JQL for search
# ==============================
JQL = """
project = GreyMatter 
AND issuetype = "Engineering Analysis" 
AND statusCategory in (Done) 
AND created >= 2025-01-01
"""

# ==============================
# Step 1: Fetch matching issues
# ==============================
def fetch_issues(jql, max_results=100):
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    start_at = 0
    issues = []

    print("🔍 Querying Jira issues...")
    while True:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": ["key", "summary", "status", "resolution", "created", "resolutiondate", "customfield_12345", "versions", "customfield_11401", "priority", "customfield_11017", "comment"],  # Replace customfield_12345 with the field ID for "analysis", customfield_11401 appears to be Origins, customfield_11017 is SLA category
            "expand": ["changelog"]
        }
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        issues.extend(data.get("issues", []))
        print(f"   ➡️ Retrieved {len(issues)}/{data['total']} issues")

        if start_at + max_results >= data["total"]:
            break
        start_at += max_results

    return issues

# ==============================
# Step 2: Extract rows (base + all changes)
# ==============================
def extract_rows(issue):
    rows = []
    fields = issue["fields"]

    # Extract Affects Versions
    affects_versions = []
    if fields.get("versions"):
        affects_versions = [version.get("name") for version in fields["versions"]]
    affects_versions_str = ", ".join(affects_versions) if affects_versions else None
    
    # Extract Origins
    origins = None
    if fields.get("customfield_11401"):
        # Origins can be a single object or array depending on field configuration
        origins_field = fields["customfield_11401"]
        if isinstance(origins_field, list):
            # Handle list of strings or objects
            origins_list = []
            for origin in origins_field:
                if isinstance(origin, dict):
                    origins_list.append(origin.get("value", str(origin)))
                else:
                    origins_list.append(str(origin))
            origins = ", ".join(origins_list)
        elif isinstance(origins_field, dict):
            origins = origins_field.get("value", str(origins_field))
        else:
            origins = str(origins_field)

    # Extract Priority
    priority = None
    if fields.get("priority"):
        priority = fields["priority"]["name"]

    # Extract SLA Category
    sla_category = None
    if fields.get("customfield_11017"):
        # SLA category can be a single object or string depending on field configuration
        sla_field = fields["customfield_11017"]
        if isinstance(sla_field, dict):
            sla_category = sla_field.get("value", str(sla_field))
        else:
            sla_category = str(sla_field)

    base_info = {
        "key": issue["key"],
        "summary": fields.get("summary"),
        "status": fields["status"]["name"] if fields.get("status") else None,
        "resolution": fields["resolution"]["name"] if fields.get("resolution") else None,
        "created": fields.get("created"),
        "resolved": fields.get("resolutiondate"),
        "analysis": fields.get("customfield_12345"),  # Replace with correct field ID for "analysis"
        "affects_versions": affects_versions_str,
        "origins": origins,
        "priority": priority,
        "sla_category": sla_category,
    }

    # Add base row
    rows.append({
        "row_type": "base",
        **base_info,
        "field_changed": None,
        "from_value": None,
        "to_value": None,
        "changed_at": None,
        "changed_by": None,
        "comment_body": None,
        "comment_author": None,
        "comment_created": None
    })

    # Add rows for all field changes
    for history in issue.get("changelog", {}).get("histories", []):
        change_timestamp = history.get("created")
        change_author = history.get("author", {}).get("displayName")
        
        for item in history.get("items", []):
            field_name = item.get("field")
            from_value = item.get("fromString")
            to_value = item.get("toString")
            
            # For some fields, use the field ID if fieldId is available
            field_id = item.get("fieldId")
            if field_id and not from_value and not to_value:
                from_value = item.get("from")
                to_value = item.get("to")
            
            rows.append({
                "row_type": "change",
                **base_info,
                "field_changed": field_name,
                "from_value": from_value,
                "to_value": to_value,
                "changed_at": change_timestamp,
                "changed_by": change_author,
                "comment_body": None,
                "comment_author": None,
                "comment_created": None
            })

    # Add rows for all comments
    comments = fields.get("comment", {}).get("comments", [])
    for comment in comments:
        comment_body = comment.get("body", "")
        comment_author = comment.get("author", {}).get("displayName", "")
        comment_created = comment.get("created", "")
        
        rows.append({
            "row_type": "comment",
            **base_info,
            "field_changed": None,
            "from_value": None,
            "to_value": None,
            "changed_at": None,
            "changed_by": None,
            "comment_body": comment_body,
            "comment_author": comment_author,
            "comment_created": comment_created
        })

    return rows

# ==============================
# Step 3: Export to CSV
# ==============================
def export_to_csv(issues, filename="jira_export.csv"):
    rows = []

    print("📊 Processing issues and extracting all changes...")
    for issue in tqdm(issues, desc="Processing issues", unit="issue"):
        rows.extend(extract_rows(issue))

    fieldnames = [
        "row_type", "key", "summary", "status", "resolution", "created", "resolved", "analysis",
        "field_changed", "from_value", "to_value", "changed_at", "changed_by", "affects_versions", "origins", "priority", "sla_category",
        "comment_body", "comment_author", "comment_created"
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Export complete: {filename} ({len(rows)} rows)")

# ==============================
# Run
# ==============================
if __name__ == "__main__":
    issues = fetch_issues(JQL)
    print(f"✅ Found {len(issues)} issues in total")
    export_to_csv(issues)
