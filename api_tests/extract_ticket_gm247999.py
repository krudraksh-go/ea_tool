import requests
import json
import os
from urllib.parse import urlparse
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# Jira Setup with new credentials
# ==============================
JIRA_BASE_URL = "https://work.greyorange.com/jira"
USER_ID = "XDR_log"
API_TOKEN = "NTUwNDMxMjMwNjE5OtIfJ86FEMso4JPQjkiuQEvkqohc"
TICKET_ID = "GM-247999"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}

# ==============================
# Create directory for downloads
# ==============================
def create_download_directory():
    """Create a directory to store the ticket data and attachments"""
    download_dir = f"ticket_{TICKET_ID.replace('-', '_')}_data"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    return download_dir

# ==============================
# Fetch ticket details
# ==============================
def fetch_ticket_details(ticket_id):
    """Fetch ticket details including description and attachment information"""
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{ticket_id}"
    
    # Request all fields including description and attachment
    params = {
        "fields": "summary,description,attachment,created,updated,status,priority,reporter,assignee",
        "expand": "renderedFields"
    }
    
    print(f"🔍 Fetching details for ticket {ticket_id}...")
    print(f"🌐 URL: {url}")
    print(f"🔑 Headers: {dict(headers)}")
    
    try:
        response = requests.get(url, headers=headers, params=params, verify=False, timeout=30)
        print(f"📊 Response status: {response.status_code}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL Error: {e}")
        print("💡 Suggestion: The SSL certificate verification failed. This is common with corporate networks.")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        print("💡 Suggestion: Check if the Jira URL is correct and accessible from your network.")
        return None
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout Error: {e}")
        print("💡 Suggestion: The request timed out. Try again or check your network connection.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
            if e.response.status_code == 401:
                print("💡 Suggestion: Authentication failed. Check your API token and user ID.")
            elif e.response.status_code == 403:
                print("💡 Suggestion: Access forbidden. You may not have permission to access this ticket.")
            elif e.response.status_code == 404:
                print("💡 Suggestion: Ticket not found. Check if the ticket ID is correct.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return None

# ==============================
# Save description to file
# ==============================
def save_description(ticket_data, download_dir):
    """Save the ticket description to a text file"""
    fields = ticket_data.get("fields", {})
    description = fields.get("description", "No description available")
    
    # Also get rendered description if available
    rendered_fields = ticket_data.get("renderedFields", {})
    rendered_description = rendered_fields.get("description", "")
    
    # Save raw description
    desc_file = os.path.join(download_dir, f"{TICKET_ID}_description.txt")
    with open(desc_file, "w", encoding="utf-8") as f:
        f.write(f"Ticket: {TICKET_ID}\n")
        f.write(f"Summary: {fields.get('summary', 'N/A')}\n")
        f.write(f"Status: {fields.get('status', {}).get('name', 'N/A')}\n")
        f.write(f"Created: {fields.get('created', 'N/A')}\n")
        f.write(f"Updated: {fields.get('updated', 'N/A')}\n")
        f.write("=" * 50 + "\n")
        f.write("DESCRIPTION (Raw):\n")
        f.write("=" * 50 + "\n")
        f.write(str(description))
        
        if rendered_description and rendered_description != description:
            f.write("\n\n" + "=" * 50 + "\n")
            f.write("DESCRIPTION (Rendered HTML):\n")
            f.write("=" * 50 + "\n")
            f.write(rendered_description)
    
    print(f"✅ Description saved to: {desc_file}")
    return desc_file

# ==============================
# Download attachments
# ==============================
def download_attachments(ticket_data, download_dir):
    """Download all attachments from the ticket"""
    fields = ticket_data.get("fields", {})
    attachments = fields.get("attachment", [])
    
    if not attachments:
        print("ℹ️  No attachments found for this ticket")
        return []
    
    print(f"📎 Found {len(attachments)} attachment(s)")
    downloaded_files = []
    
    # Create attachments subdirectory
    attachments_dir = os.path.join(download_dir, "attachments")
    if not os.path.exists(attachments_dir):
        os.makedirs(attachments_dir)
    
    for i, attachment in enumerate(attachments, 1):
        filename = attachment.get("filename", f"attachment_{i}")
        content_url = attachment.get("content")
        file_size = attachment.get("size", 0)
        created = attachment.get("created", "Unknown")
        author = attachment.get("author", {}).get("displayName", "Unknown")
        
        print(f"  📥 Downloading {i}/{len(attachments)}: {filename} ({file_size} bytes)")
        print(f"      Created: {created} by {author}")
        
        if content_url:
            try:
                # Download the attachment
                attachment_response = requests.get(content_url, headers=headers, verify=False)
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
                
                downloaded_files.append(file_path)
                print(f"      ✅ Saved as: {file_path}")
                
            except requests.exceptions.RequestException as e:
                print(f"      ❌ Failed to download {filename}: {e}")
        else:
            print(f"      ⚠️  No download URL found for {filename}")
    
    return downloaded_files

# ==============================
# Save ticket metadata
# ==============================
def save_ticket_metadata(ticket_data, download_dir):
    """Save complete ticket metadata as JSON"""
    metadata_file = os.path.join(download_dir, f"{TICKET_ID}_metadata.json")
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(ticket_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Ticket metadata saved to: {metadata_file}")
    return metadata_file

# ==============================
# Main execution
# ==============================
def main():
    print(f"🎯 Starting extraction for ticket: {TICKET_ID}")
    print(f"🔐 Using user: {USER_ID}")
    
    # Create download directory
    download_dir = create_download_directory()
    print(f"📁 Download directory: {download_dir}")
    
    # Fetch ticket details
    ticket_data = fetch_ticket_details(TICKET_ID)
    
    if not ticket_data:
        print("❌ Failed to fetch ticket data. Exiting.")
        return
    
    # Save description
    desc_file = save_description(ticket_data, download_dir)
    
    # Download attachments
    downloaded_files = download_attachments(ticket_data, download_dir)
    
    # Save complete metadata
    metadata_file = save_ticket_metadata(ticket_data, download_dir)
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 EXTRACTION COMPLETE!")
    print("=" * 60)
    print(f"📁 All files saved in: {download_dir}")
    print(f"📝 Description: {desc_file}")
    print(f"📊 Metadata: {metadata_file}")
    if downloaded_files:
        print(f"📎 Attachments ({len(downloaded_files)}):")
        for file_path in downloaded_files:
            print(f"   • {file_path}")
    else:
        print("📎 No attachments downloaded")

if __name__ == "__main__":
    main()

