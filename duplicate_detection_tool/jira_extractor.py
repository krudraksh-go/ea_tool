"""
JIRA Ticket Extraction Module
Extracts ticket data and attachments from JIRA API
"""

import requests
import json
import os
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def extract_ticket_data(ticket_id, base_url, api_token, output_dir):
    """
    Extract all data for a specific JIRA ticket
    
    Args:
        ticket_id: Full ticket ID (e.g., "GM-247999")
        base_url: JIRA base URL
        api_token: API token for authentication
        output_dir: Directory to save ticket data
    
    Returns:
        Dictionary containing ticket data and metadata
    """
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json"
    }
    
    # Create ticket directory
    ticket_dir = os.path.join(output_dir, ticket_id)
    os.makedirs(ticket_dir, exist_ok=True)
    
    try:
        # Fetch ticket data
        url = f"{base_url}/rest/api/2/issue/{ticket_id}"
        
        # Fields to fetch
        params = {
            "expand": "changelog,renderedFields",
            "fields": [
                "key", "summary", "description", "status", "resolution", "priority",
                "created", "updated", "resolutiondate",
                "attachment", "comment",
                "versions", "fixVersions", "issuelinks",
                "customfield_11401",  # Origins
                "customfield_11017",  # SLA category
                "customfield_10014",  # Severity
            ]
        }
        
        response = requests.get(
            url,
            headers=headers,
            params={"expand": params["expand"]},
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        issue_data = response.json()
        
        # Extract metadata
        fields = issue_data.get("fields", {})
        
        # Extract basic metadata
        metadata = {
            "key": issue_data.get("key"),
            "summary": fields.get("summary"),
            "description": fields.get("description"),
            "status": fields.get("status", {}).get("name") if fields.get("status") else None,
            "status_category": fields.get("status", {}).get("statusCategory", {}).get("name") if fields.get("status") else None,
            "resolution": fields.get("resolution", {}).get("name") if fields.get("resolution") else None,
            "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "resolved": fields.get("resolutiondate"),
        }
        
        # Extract severity
        if fields.get("customfield_10014"):
            severity_field = fields["customfield_10014"]
            metadata["severity"] = severity_field.get("value") if isinstance(severity_field, dict) else str(severity_field)
        else:
            metadata["severity"] = None
        
        # Extract origins
        if fields.get("customfield_11401"):
            origins_field = fields["customfield_11401"]
            if isinstance(origins_field, list):
                metadata["origins"] = [o.get("value") if isinstance(o, dict) else str(o) for o in origins_field]
            elif isinstance(origins_field, dict):
                metadata["origins"] = origins_field.get("value")
            else:
                metadata["origins"] = str(origins_field)
        else:
            metadata["origins"] = None
        
        # Extract affects/fix versions
        metadata["affects_versions"] = [v.get("name") for v in fields.get("versions", [])]
        metadata["fix_versions"] = [v.get("name") for v in fields.get("fixVersions", [])]
        
        # Extract issue links
        issue_links = []
        for link in fields.get("issuelinks", []):
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
        metadata["issue_links"] = issue_links
        
        # Extract comments
        comments = []
        for comment in fields.get("comment", {}).get("comments", []):
            comments.append({
                "body": comment.get("body", ""),
                "author": comment.get("author", {}).get("displayName", "Unknown"),
                "created": comment.get("created", ""),
                "updated": comment.get("updated", "")
            })
        
        # Extract changelog
        changelog = []
        for history in issue_data.get("changelog", {}).get("histories", []):
            for item in history.get("items", []):
                changelog.append({
                    "field": item.get("field"),
                    "from_value": item.get("fromString") or item.get("from"),
                    "to_value": item.get("toString") or item.get("to"),
                    "changed_at": history.get("created"),
                    "changed_by": history.get("author", {}).get("displayName")
                })
        
        # Download attachments
        attachments = []
        attachments_dir = os.path.join(ticket_dir, "attachments")
        os.makedirs(attachments_dir, exist_ok=True)
        
        for attachment in fields.get("attachment", []):
            filename = attachment.get("filename", "unknown")
            content_url = attachment.get("content")
            
            if content_url:
                try:
                    att_response = requests.get(content_url, headers=headers, verify=False, timeout=30)
                    att_response.raise_for_status()
                    
                    file_path = os.path.join(attachments_dir, filename)
                    
                    # Handle filename conflicts
                    counter = 1
                    original_path = file_path
                    while os.path.exists(file_path):
                        name, ext = os.path.splitext(original_path)
                        file_path = f"{name}_{counter}{ext}"
                        counter += 1
                    
                    with open(file_path, "wb") as f:
                        f.write(att_response.content)
                    
                    attachments.append({
                        "filename": filename,
                        "path": file_path,
                        "size": attachment.get("size", 0),
                        "created": attachment.get("created"),
                        "author": attachment.get("author", {}).get("displayName", "Unknown"),
                        "mime_type": attachment.get("mimeType")
                    })
                except Exception as e:
                    print(f"Failed to download attachment {filename}: {e}")
        
        # Compile complete ticket data
        ticket_data = {
            "metadata": metadata,
            "comments": comments,
            "changelog": changelog,
            "attachments": attachments,
            "ticket_dir": ticket_dir
        }
        
        # Save to JSON
        data_file = os.path.join(ticket_dir, "ticket_data.json")
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(ticket_data, f, indent=2, ensure_ascii=False)
        
        return ticket_data
        
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error: Unable to connect to JIRA server. Please check your network connection and JIRA URL."
        print(f"Error fetching ticket {ticket_id}: {error_msg}")
        return {"error": error_msg, "error_type": "connection"}
    
    except requests.exceptions.Timeout as e:
        error_msg = f"Timeout error: JIRA server took too long to respond. Please try again."
        print(f"Error fetching ticket {ticket_id}: {error_msg}")
        return {"error": error_msg, "error_type": "timeout"}
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            error_msg = "Authentication error: Invalid or expired JIRA API token. Please check your credentials."
        elif e.response.status_code == 403:
            error_msg = "Authorization error: You don't have permission to access this ticket."
        elif e.response.status_code == 404:
            error_msg = f"Ticket not found: {ticket_id} does not exist or you don't have access to it."
        else:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text[:200]}"
        print(f"Error fetching ticket {ticket_id}: {error_msg}")
        return {"error": error_msg, "error_type": "http", "status_code": e.response.status_code}
    
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        print(f"Error fetching ticket {ticket_id}: {error_msg}")
        return {"error": error_msg, "error_type": "request"}
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Unexpected error extracting ticket {ticket_id}: {error_msg}")
        return {"error": error_msg, "error_type": "unknown"}

