import requests
import sys
import json
from pprint import pprint
import urllib3

# Disable SSL warnings when using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# Jira Setup
# ==============================
JIRA_BASE_URL = "https://work.greyorange.com/jira"
API_TOKEN = "NjQzMTc1MzM3NjQ0On0fuL/A6sogWMfDPEUaHhPJAUV/"   # your token
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}

def fetch_jira_issue(ticket_id):
    """
    Fetch a Jira issue with all available fields and expansions
    """
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{ticket_id}"
    params = {
        "expand": "renderedFields,properties,changelog,operations,versionedRepresentations,editmeta,transitions,names,schema"
    }
    print(f"🔍 Fetching Jira issue {ticket_id}...")
    
    # Disable SSL verification for corporate/internal Jira instances
    # WARNING: This reduces security - only use for trusted internal servers
    resp = requests.get(url, headers=HEADERS, params=params, verify=False)
    resp.raise_for_status()
    return resp.json()

def print_section_header(title):
    """Print a formatted section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def print_field_value(key, value, indent=0):
    """Print a field key-value pair with proper formatting"""
    indent_str = "  " * indent
    
    # Handle None values
    if value is None:
        print(f"{indent_str}{key}: None")
        return
    
    if isinstance(value, (dict, list)):
        print(f"{indent_str}{key}:")
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                print_field_value(sub_key, sub_value, indent + 1)
        elif isinstance(value, list) and value:
            for i, item in enumerate(value):
                print(f"{indent_str}  [{i}]:")
                if isinstance(item, dict):
                    for sub_key, sub_value in item.items():
                        print_field_value(sub_key, sub_value, indent + 2)
                else:
                    print(f"{indent_str}    {item}")
    else:
        # Truncate very long values for readability
        if isinstance(value, str) and len(value) > 200:
            value = value[:200] + "... [truncated]"
        print(f"{indent_str}{key}: {value}")

def extract_and_display_all_fields(issue_json):
    """
    Extract and display all available fields from the Jira issue
    """
    print_section_header("BASIC ISSUE INFORMATION")
    
    # Basic info
    basic_fields = {
        "Issue Key": issue_json.get("key", "N/A"),
        "Issue ID": issue_json.get("id", "N/A"),
        "Self URL": issue_json.get("self", "N/A")
    }
    
    for key, value in basic_fields.items():
        print_field_value(key, value)
    
    # Fields section
    if "fields" in issue_json and issue_json["fields"] is not None:
        print_section_header("ISSUE FIELDS")
        fields = issue_json["fields"]
        
        # Common important fields first
        important_fields = [
            "summary", "description", "status", "priority", "issuetype", 
            "assignee", "reporter", "created", "updated", "resolution",
            "resolutiondate", "project", "components", "versions", "fixVersions"
        ]
        
        print("\n--- KEY FIELDS ---")
        for field in important_fields:
            try:
                if fields and field in fields:
                    print_field_value(field, fields[field])
            except Exception as e:
                print(f"Error processing field '{field}': {e}")
                print(f"Field value type: {type(fields.get(field) if fields else None)}")
                print(f"Field value: {fields.get(field) if fields else None}")
        
        print("\n--- ALL OTHER FIELDS ---")
        if fields:
            for field_key, field_value in fields.items():
                if field_key not in important_fields:
                    print_field_value(field_key, field_value)
    
    # Rendered fields
    if "renderedFields" in issue_json:
        print_section_header("RENDERED FIELDS")
        for key, value in issue_json["renderedFields"].items():
            print_field_value(key, value)
    
    # Properties
    if "properties" in issue_json:
        print_section_header("PROPERTIES")
        for key, value in issue_json["properties"].items():
            print_field_value(key, value)
    
    # Changelog
    if "changelog" in issue_json:
        print_section_header("CHANGELOG")
        changelog = issue_json["changelog"]
        print_field_value("Total Changelog Entries", changelog.get("total", 0))
        if "histories" in changelog and changelog["histories"]:
            print("\n--- RECENT HISTORY ENTRIES ---")
            for i, history in enumerate(changelog["histories"][:5]):  # Show only first 5
                print(f"\n  History Entry {i+1}:")
                print_field_value("Author", history.get("author", {}).get("displayName", "Unknown"), 1)
                print_field_value("Created", history.get("created", "Unknown"), 1)
                if "items" in history:
                    print_field_value("Changes", "", 1)
                    for item in history["items"]:
                        change_desc = f"{item.get('field', 'Unknown')} from '{item.get('fromString', 'N/A')}' to '{item.get('toString', 'N/A')}'"
                        print_field_value("", change_desc, 2)
    
    # Operations
    if "operations" in issue_json:
        print_section_header("AVAILABLE OPERATIONS")
        for key, value in issue_json["operations"].items():
            print_field_value(key, value)
    
    # Transitions
    if "transitions" in issue_json:
        print_section_header("AVAILABLE TRANSITIONS")
        for i, transition in enumerate(issue_json["transitions"]):
            print(f"\n  Transition {i+1}:")
            print_field_value("ID", transition.get("id"), 1)
            print_field_value("Name", transition.get("name"), 1)
            print_field_value("To Status", transition.get("to", {}).get("name"), 1)

def save_full_json(issue_json, ticket_id):
    """
    Save the complete JSON response to a file for detailed analysis
    """
    filename = f"jira_{ticket_id}_full_data.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(issue_json, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Full JSON data saved to: {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python jira_field_extractor.py <JIRA_TICKET_ID> [--save-json]")
        print("  --save-json: Also save the complete response to a JSON file")
        sys.exit(1)
    
    jira_ticket = sys.argv[1]
    save_json = "--save-json" in sys.argv
    
    try:
        issue = fetch_jira_issue(jira_ticket)
        
        print(f"\n🎯 Extracting all fields for Jira ticket: {jira_ticket}")
        extract_and_display_all_fields(issue)
        
        if save_json:
            save_full_json(issue, jira_ticket)
            
        print("\n" + "="*60)
        print("  ✅ EXTRACTION COMPLETE")
        print("="*60)
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"   Status Code: {e.response.status_code}")
        if e.response.status_code == 401:
            print("   Check your API token")
        elif e.response.status_code == 404:
            print("   Ticket not found or no access")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
