import requests
import json
import os
from urllib.parse import urlparse
import urllib3
from tqdm import tqdm
from datetime import datetime

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# Jira Setup with credentials from extract_ticket_gm247999.py
# ==============================
JIRA_BASE_URL = "https://work.greyorange.com/jira"
USER_ID = "XDR_log"
API_TOKEN = "NTUwNDMxMjMwNjE5OtIfJ86FEMso4JPQjkiuQEvkqohc"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}

# ==============================
# JQL for Engineering Analysis tickets from Aug 1, 2025
# ==============================
JQL = """
project = GreyMatter 
AND issuetype = "Engineering Analysis" 
AND created >= 2025-08-01
"""

# ==============================
# Main data directory
# ==============================
MAIN_DATA_DIR = "jira_tickets_data"

# ==============================
# Create main directory structure
# ==============================
def create_main_directory():
    """Create main directory to store all ticket data"""
    if not os.path.exists(MAIN_DATA_DIR):
        os.makedirs(MAIN_DATA_DIR)
    print(f"📁 Main data directory: {MAIN_DATA_DIR}")
    return MAIN_DATA_DIR

# ==============================
# Fetch all issues matching JQL
# ==============================
def fetch_all_issues(jql, max_results=50):
    """Fetch all issues matching the JQL query"""
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    start_at = 0
    issues = []
    
    print("🔍 Querying Jira for Engineering Analysis tickets...")
    
    # Fields to fetch
    fields = [
        "key", "summary", "description", "status", "resolution", "priority",
        "created", "updated", "resolutiondate",
        "attachment", "comment",
        "versions",  # Affects Version
        "fixVersions",  # Fix Versions
        "issuelinks",  # Issue Links
        "customfield_11401",  # Origins
        "customfield_11017",  # SLA category
        "customfield_10014",  # Severity (common field ID, may need adjustment)
    ]
    
    while True:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": fields,
            "expand": ["changelog", "renderedFields"]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            issues.extend(data.get("issues", []))
            total = data.get("total", 0)
            print(f"   ➡️ Retrieved {len(issues)}/{total} issues")
            
            if start_at + max_results >= total:
                break
            start_at += max_results
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching issues: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            break
    
    return issues

# ==============================
# Extract ticket metadata
# ==============================
def extract_ticket_metadata(issue):
    """Extract all requested metadata from a ticket"""
    fields = issue.get("fields", {})
    
    # Extract Affects Versions
    affects_versions = []
    if fields.get("versions"):
        affects_versions = [v.get("name") for v in fields["versions"]]
    
    # Extract Fix Versions
    fix_versions = []
    if fields.get("fixVersions"):
        fix_versions = [v.get("name") for v in fields["fixVersions"]]
    
    # Extract Origins
    origins = None
    if fields.get("customfield_11401"):
        origins_field = fields["customfield_11401"]
        if isinstance(origins_field, list):
            origins_list = []
            for origin in origins_field:
                if isinstance(origin, dict):
                    origins_list.append(origin.get("value", str(origin)))
                else:
                    origins_list.append(str(origin))
            origins = origins_list
        elif isinstance(origins_field, dict):
            origins = origins_field.get("value", str(origins_field))
        else:
            origins = str(origins_field)
    
    # Extract Severity
    severity = None
    if fields.get("customfield_10014"):
        severity_field = fields["customfield_10014"]
        if isinstance(severity_field, dict):
            severity = severity_field.get("value", str(severity_field))
        else:
            severity = str(severity_field)
    
    # Extract Issue Links
    issue_links = []
    if fields.get("issuelinks"):
        for link in fields["issuelinks"]:
            link_type = link.get("type", {}).get("name", "Unknown")
            if link.get("outwardIssue"):
                issue_links.append({
                    "type": link_type,
                    "direction": "outward",
                    "key": link["outwardIssue"].get("key"),
                    "summary": link["outwardIssue"].get("fields", {}).get("summary")
                })
            if link.get("inwardIssue"):
                issue_links.append({
                    "type": link_type,
                    "direction": "inward",
                    "key": link["inwardIssue"].get("key"),
                    "summary": link["inwardIssue"].get("fields", {}).get("summary")
                })
    
    # Extract Status Category
    status_category = None
    if fields.get("status"):
        status_category = fields["status"].get("statusCategory", {}).get("name")
    
    metadata = {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "description": fields.get("description"),
        "status": fields.get("status", {}).get("name") if fields.get("status") else None,
        "status_category": status_category,
        "resolution": fields.get("resolution", {}).get("name") if fields.get("resolution") else None,
        "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
        "severity": severity,
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "resolved": fields.get("resolutiondate"),
        "affects_versions": affects_versions,
        "fix_versions": fix_versions,
        "origins": origins,
        "issue_links": issue_links,
    }
    
    return metadata

# ==============================
# Extract comments
# ==============================
def extract_comments(issue):
    """Extract all comments from a ticket"""
    fields = issue.get("fields", {})
    comments = fields.get("comment", {}).get("comments", [])
    
    comment_data = []
    for comment in comments:
        comment_data.append({
            "body": comment.get("body", ""),
            "author": comment.get("author", {}).get("displayName", "Unknown"),
            "created": comment.get("created", ""),
            "updated": comment.get("updated", "")
        })
    
    return comment_data

# ==============================
# Extract changelog (field changes)
# ==============================
def extract_changelog(issue):
    """Extract all field changes from ticket history"""
    changelog_data = []
    
    for history in issue.get("changelog", {}).get("histories", []):
        change_timestamp = history.get("created")
        change_author = history.get("author", {}).get("displayName")
        
        for item in history.get("items", []):
            field_name = item.get("field")
            from_value = item.get("fromString")
            to_value = item.get("toString")
            
            # For some fields, use the field ID if fieldId is available
            if not from_value and not to_value:
                from_value = item.get("from")
                to_value = item.get("to")
            
            changelog_data.append({
                "field": field_name,
                "from_value": from_value,
                "to_value": to_value,
                "changed_at": change_timestamp,
                "changed_by": change_author
            })
    
    return changelog_data

# ==============================
# Download attachments for a ticket
# ==============================
def download_attachments(issue, ticket_dir):
    """Download all attachments from a ticket"""
    fields = issue.get("fields", {})
    attachments = fields.get("attachment", [])
    
    if not attachments:
        return []
    
    ticket_key = issue.get("key")
    print(f"      📎 Found {len(attachments)} attachment(s) for {ticket_key}")
    downloaded_files = []
    
    # Create attachments subdirectory
    attachments_dir = os.path.join(ticket_dir, "attachments")
    if not os.path.exists(attachments_dir):
        os.makedirs(attachments_dir)
    
    for i, attachment in enumerate(attachments, 1):
        filename = attachment.get("filename", f"attachment_{i}")
        content_url = attachment.get("content")
        file_size = attachment.get("size", 0)
        
        if content_url:
            try:
                # Download the attachment
                attachment_response = requests.get(content_url, headers=headers, verify=False, timeout=30)
                attachment_response.raise_for_status()
                
                # Save to file
                file_path = os.path.join(attachments_dir, filename)
                
                # Handle potential filename conflicts
                counter = 1
                original_file_path = file_path
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_file_path)
                    file_path = f"{name}_{counter}{ext}"
                    counter += 1
                
                with open(file_path, "wb") as f:
                    f.write(attachment_response.content)
                
                downloaded_files.append({
                    "filename": filename,
                    "path": file_path,
                    "size": file_size,
                    "created": attachment.get("created"),
                    "author": attachment.get("author", {}).get("displayName", "Unknown")
                })
                
            except requests.exceptions.RequestException as e:
                print(f"         ❌ Failed to download {filename}: {e}")
    
    return downloaded_files

# ==============================
# Process single ticket
# ==============================
def process_ticket(issue):
    """Process a single ticket and save all data"""
    ticket_key = issue.get("key")
    ticket_dir = os.path.join(MAIN_DATA_DIR, ticket_key)
    
    # Create ticket directory
    if not os.path.exists(ticket_dir):
        os.makedirs(ticket_dir)
    
    print(f"   📝 Processing {ticket_key}...")
    
    # Extract all data
    metadata = extract_ticket_metadata(issue)
    comments = extract_comments(issue)
    changelog = extract_changelog(issue)
    attachment_info = download_attachments(issue, ticket_dir)
    
    # Save metadata JSON (complete ticket data for reference)
    full_data = {
        "metadata": metadata,
        "comments": comments,
        "changelog": changelog,
        "attachments": attachment_info,
        "raw_issue": issue  # Keep raw data for any additional processing
    }
    
    metadata_file = os.path.join(ticket_dir, "ticket_data.json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=2, ensure_ascii=False)
    
    # Save text content (for easy text extraction and embedding)
    text_file = os.path.join(ticket_dir, "text_content.txt")
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(f"TICKET: {ticket_key}\n")
        f.write("=" * 80 + "\n\n")
        
        # Basic info
        f.write(f"SUMMARY: {metadata.get('summary', 'N/A')}\n")
        f.write(f"STATUS: {metadata.get('status', 'N/A')}\n")
        f.write(f"STATUS CATEGORY: {metadata.get('status_category', 'N/A')}\n")
        f.write(f"RESOLUTION: {metadata.get('resolution', 'N/A')}\n")
        f.write(f"PRIORITY: {metadata.get('priority', 'N/A')}\n")
        f.write(f"SEVERITY: {metadata.get('severity', 'N/A')}\n")
        f.write(f"ORIGINS: {metadata.get('origins', 'N/A')}\n")
        f.write(f"AFFECTS VERSIONS: {', '.join(metadata.get('affects_versions', [])) or 'N/A'}\n")
        f.write(f"FIX VERSIONS: {', '.join(metadata.get('fix_versions', [])) or 'N/A'}\n")
        f.write(f"CREATED: {metadata.get('created', 'N/A')}\n")
        f.write(f"UPDATED: {metadata.get('updated', 'N/A')}\n")
        f.write(f"RESOLVED: {metadata.get('resolved', 'N/A')}\n")
        f.write("\n" + "=" * 80 + "\n\n")
        
        # Description
        f.write("DESCRIPTION:\n")
        f.write("-" * 80 + "\n")
        f.write(str(metadata.get('description', 'No description available')))
        f.write("\n\n" + "=" * 80 + "\n\n")
        
        # Comments
        if comments:
            f.write(f"COMMENTS ({len(comments)}):\n")
            f.write("-" * 80 + "\n")
            for i, comment in enumerate(comments, 1):
                f.write(f"\nComment #{i}:\n")
                f.write(f"Author: {comment['author']}\n")
                f.write(f"Created: {comment['created']}\n")
                f.write(f"Body:\n{comment['body']}\n")
                f.write("-" * 40 + "\n")
        else:
            f.write("COMMENTS: None\n")
        
        f.write("\n" + "=" * 80 + "\n\n")
        
        # Issue Links
        if metadata.get('issue_links'):
            f.write("ISSUE LINKS:\n")
            f.write("-" * 80 + "\n")
            for link in metadata['issue_links']:
                f.write(f"  [{link['direction']}] {link['type']}: {link['key']} - {link['summary']}\n")
        else:
            f.write("ISSUE LINKS: None\n")
    
    # Save changelog separately
    if changelog:
        changelog_file = os.path.join(ticket_dir, "changelog.json")
        with open(changelog_file, "w", encoding="utf-8") as f:
            json.dump(changelog, f, indent=2, ensure_ascii=False)
        
        # Also save as text for easy reading
        changelog_text_file = os.path.join(ticket_dir, "changelog.txt")
        with open(changelog_text_file, "w", encoding="utf-8") as f:
            f.write(f"CHANGELOG FOR {ticket_key}\n")
            f.write("=" * 80 + "\n\n")
            for change in changelog:
                f.write(f"Field: {change['field']}\n")
                f.write(f"From: {change['from_value']}\n")
                f.write(f"To: {change['to_value']}\n")
                f.write(f"Changed at: {change['changed_at']}\n")
                f.write(f"Changed by: {change['changed_by']}\n")
                f.write("-" * 40 + "\n")
    
    return ticket_key

# ==============================
# Create summary index
# ==============================
def create_summary_index(processed_tickets):
    """Create a summary index of all processed tickets"""
    index_file = os.path.join(MAIN_DATA_DIR, "index.json")
    
    summary = {
        "extraction_date": datetime.now().isoformat(),
        "total_tickets": len(processed_tickets),
        "tickets": processed_tickets
    }
    
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Summary index created: {index_file}")
    
    # Also create a simple text list
    list_file = os.path.join(MAIN_DATA_DIR, "ticket_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        f.write(f"Extracted Tickets - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        for ticket in processed_tickets:
            f.write(f"{ticket}\n")
    
    print(f"✅ Ticket list created: {list_file}")

# ==============================
# Main execution
# ==============================
def main():
    print("=" * 80)
    print("🎯 JIRA ENGINEERING ANALYSIS TICKETS EXTRACTION")
    print("=" * 80)
    print(f"🔐 Using user: {USER_ID}")
    print(f"📅 Fetching tickets from: Aug 1, 2025 onwards")
    print(f"📊 Issue Type: Engineering Analysis")
    print("=" * 80 + "\n")
    
    # Create main directory
    create_main_directory()
    
    # Fetch all issues
    issues = fetch_all_issues(JQL)
    
    if not issues:
        print("\n❌ No issues found matching the criteria.")
        return
    
    print(f"\n✅ Found {len(issues)} tickets to process\n")
    print("=" * 80)
    print("📦 Processing tickets and downloading attachments...")
    print("=" * 80 + "\n")
    
    # Process each ticket
    processed_tickets = []
    for issue in tqdm(issues, desc="Processing tickets", unit="ticket"):
        try:
            ticket_key = process_ticket(issue)
            processed_tickets.append(ticket_key)
        except Exception as e:
            ticket_key = issue.get("key", "Unknown")
            print(f"\n   ❌ Error processing {ticket_key}: {e}")
            continue
    
    # Create summary index
    create_summary_index(processed_tickets)
    
    # Final summary
    print("\n" + "=" * 80)
    print("🎉 EXTRACTION COMPLETE!")
    print("=" * 80)
    print(f"📁 All data saved in: {MAIN_DATA_DIR}/")
    print(f"📊 Total tickets processed: {len(processed_tickets)}")
    print(f"📝 Each ticket has:")
    print(f"   • ticket_data.json - Complete metadata, comments, changelog, attachments info")
    print(f"   • text_content.txt - All text content for embedding")
    print(f"   • changelog.json/txt - Field change history")
    print(f"   • attachments/ - All downloaded files (images, documents, etc.)")
    print("=" * 80)
    print("\n💡 Next steps:")
    print("   1. Use text_content.txt files for text embedding")
    print("   2. Process images in attachments/ folders with OCR/Vision models")
    print("   3. Create vector embeddings from processed text")
    print("   4. Build your vector database for similarity search")
    print("=" * 80)

if __name__ == "__main__":
    main()

