#!/usr/bin/env python3
"""
Multimodal Jira Ticket Processor
This script processes Jira tickets with text, OCR from images, and visual captioning using Gemini Pro Vision

Usage:
    python process_multimodal_tickets.py [num_tickets]
    
    By default, processes ALL tickets in jira_tickets_data/.
    
Examples:
    python process_multimodal_tickets.py         # Process all tickets
    python process_multimodal_tickets.py 10      # Process first 10 tickets
    python process_multimodal_tickets.py all     # Process all tickets (explicit)
"""

import os
import json
import sys
import google.generativeai as genai
from PIL import Image
import pytesseract
from pathlib import Path
from tqdm import tqdm

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyBrx2rU1XxfHw7hQ-iQNEzLrXHgeylrV-s"
genai.configure(api_key=GEMINI_API_KEY)

# Paths
JIRA_TICKETS_DIR = "/Users/rudraksh.k/Documents/tool_development/duplicate_detection/jira_tickets_data"
OUTPUT_DIR = "/Users/rudraksh.k/Documents/tool_development/duplicate_detection/multimodal_documents"

# OCR text threshold - if OCR extracts more than this many characters, consider it text-heavy
OCR_TEXT_THRESHOLD = 50

def setup_output_directory():
    """Create output directory if it doesn't exist"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

def get_ticket_folders(limit=None):
    """Get list of ticket folders"""
    tickets = [d for d in os.listdir(JIRA_TICKETS_DIR) 
               if os.path.isdir(os.path.join(JIRA_TICKETS_DIR, d)) and d.startswith('GM-')]
    tickets.sort()
    
    if limit:
        tickets = tickets[:limit]
    
    return tickets

def extract_text_with_ocr(image_path):
    """Extract text from image using Pytesseract OCR"""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"  [ERROR] OCR failed for {os.path.basename(image_path)}: {e}")
        return ""

def generate_image_caption(image_path):
    """Generate caption for image using Gemini Pro Vision"""
    try:
        # Load image
        image = Image.open(image_path)
        
        # Initialize Gemini Pro Vision model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Generate caption
        prompt = "Describe this image in detail. If it shows a dashboard, graph, chart, or UI, describe what it displays, what metrics or data it shows, and any notable patterns or issues visible."
        response = model.generate_content([prompt, image])
        
        return response.text.strip()
    except Exception as e:
        print(f"  [ERROR] Image captioning failed for {os.path.basename(image_path)}: {e}")
        return f"[Error generating caption: {str(e)}]"

def process_image(image_path, image_filename):
    """Process a single image - try OCR first, then visual captioning if needed"""
    print(f"  Processing image: {image_filename}")
    
    # First, try OCR
    ocr_text = extract_text_with_ocr(image_path)
    
    # Decide whether to use OCR text or visual captioning
    if len(ocr_text) > OCR_TEXT_THRESHOLD:
        # Significant text found - use OCR
        print(f"    -> OCR found {len(ocr_text)} characters")
        return {
            'type': 'ocr',
            'filename': image_filename,
            'content': ocr_text
        }
    else:
        # Little or no text - use visual captioning
        print(f"    -> OCR found only {len(ocr_text)} characters, using visual captioning")
        caption = generate_image_caption(image_path)
        return {
            'type': 'caption',
            'filename': image_filename,
            'content': caption
        }

def process_ticket(ticket_id):
    """Process a single ticket and create consolidated document"""
    print(f"\n{'='*60}")
    print(f"Processing ticket: {ticket_id}")
    print(f"{'='*60}")
    
    ticket_dir = os.path.join(JIRA_TICKETS_DIR, ticket_id)
    
    # Read ticket data
    ticket_data_path = os.path.join(ticket_dir, 'ticket_data.json')
    text_content_path = os.path.join(ticket_dir, 'text_content.txt')
    attachments_dir = os.path.join(ticket_dir, 'attachments')
    
    # Initialize document
    document_lines = []
    
    # Add header
    document_lines.append("="*80)
    document_lines.append(f"CONSOLIDATED DOCUMENT FOR TICKET: {ticket_id}")
    document_lines.append("="*80)
    document_lines.append("")
    
    # Read and add metadata
    if os.path.exists(ticket_data_path):
        with open(ticket_data_path, 'r', encoding='utf-8') as f:
            ticket_data = json.load(f)
            fields = ticket_data.get('fields', {})
            
            document_lines.append("TICKET METADATA")
            document_lines.append("-"*80)
            document_lines.append(f"Key: {ticket_data.get('key', 'N/A')}")
            document_lines.append(f"Summary: {fields.get('summary', 'N/A')}")
            document_lines.append(f"Status: {fields.get('status', {}).get('name', 'N/A')}")
            document_lines.append(f"Priority: {fields.get('priority', {}).get('name', 'N/A')}")
            document_lines.append(f"Created: {fields.get('created', 'N/A')}")
            document_lines.append(f"Updated: {fields.get('updated', 'N/A')}")
            
            # Add reporter and assignee info
            reporter = fields.get('reporter', {})
            if reporter:
                document_lines.append(f"Reporter: {reporter.get('displayName', 'N/A')} ({reporter.get('emailAddress', 'N/A')})")
            
            assignee = fields.get('assignee', {})
            if assignee:
                document_lines.append(f"Assignee: {assignee.get('displayName', 'N/A')} ({assignee.get('emailAddress', 'N/A')})")
            
            document_lines.append("")
    
    # Read and add text content
    if os.path.exists(text_content_path):
        print("  Reading text content...")
        with open(text_content_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
            
            document_lines.append("TICKET DESCRIPTION AND CONTENT")
            document_lines.append("-"*80)
            document_lines.append(text_content)
            document_lines.append("")
    
    # Process attachments/images
    if os.path.exists(attachments_dir):
        image_files = [f for f in os.listdir(attachments_dir) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
        
        # Remove duplicate files (files ending with _1, _2, etc.)
        unique_images = []
        seen_bases = set()
        for img in sorted(image_files):
            # Remove _1, _2, etc. suffix to get base name
            base = img
            for suffix in ['_1', '_2', '_3', '_4', '_5']:
                if base.endswith(f'{suffix}.png') or base.endswith(f'{suffix}.jpg') or base.endswith(f'{suffix}.jpeg'):
                    base = base.replace(suffix, '')
                    break
            
            if base not in seen_bases:
                seen_bases.add(base)
                unique_images.append(img)
        
        if unique_images:
            print(f"  Found {len(unique_images)} unique images to process")
            document_lines.append("EXTRACTED INFORMATION FROM IMAGES")
            document_lines.append("-"*80)
            document_lines.append("")
            
            for image_file in unique_images:
                image_path = os.path.join(attachments_dir, image_file)
                result = process_image(image_path, image_file)
                
                if result['type'] == 'ocr':
                    document_lines.append(f"[EXTRACTED TEXT FROM IMAGE: {result['filename']}]")
                    document_lines.append("-"*40)
                    document_lines.append(result['content'])
                    document_lines.append("")
                else:
                    document_lines.append(f"[IMAGE DESCRIPTION: {result['filename']}]")
                    document_lines.append("-"*40)
                    document_lines.append(result['content'])
                    document_lines.append("")
    
    # Add footer
    document_lines.append("="*80)
    document_lines.append("END OF DOCUMENT")
    document_lines.append("="*80)
    
    # Save document
    output_path = os.path.join(OUTPUT_DIR, f"{ticket_id}_consolidated.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(document_lines))
    
    print(f"✓ Document saved: {output_path}")
    
    return output_path

def main():
    """Main function"""
    print("="*60)
    print("MULTIMODAL JIRA TICKET PROCESSOR")
    print("="*60)
    print()
    
    # Setup
    setup_output_directory()
    
    # Parse command line arguments
    limit = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.lower() in ['all', '0']:
            limit = None
        else:
            try:
                limit = int(arg)
            except ValueError:
                print(f"Invalid argument: {arg}")
                print("Usage: python process_multimodal_tickets.py [num_tickets]")
                return
    else:
        # Default: process all tickets
        limit = None
    
    # Get tickets
    tickets = get_ticket_folders(limit=limit)
    print(f"\nProcessing {len(tickets)} tickets...")
    if len(tickets) <= 10:
        print(f"Tickets: {', '.join(tickets)}")
    else:
        print(f"First 10 tickets: {', '.join(tickets[:10])} ...")
    
    # Process each ticket with progress bar
    processed_docs = []
    failed_tickets = []
    
    for ticket_id in tqdm(tickets, desc="Processing tickets", unit="ticket"):
        try:
            doc_path = process_ticket(ticket_id)
            processed_docs.append(doc_path)
        except Exception as e:
            failed_tickets.append(ticket_id)
            tqdm.write(f"\n[ERROR] Failed to process {ticket_id}: {e}")
            import traceback
            tqdm.write(traceback.format_exc())
    
    # Summary
    print("\n" + "="*60)
    print("PROCESSING COMPLETE")
    print("="*60)
    print(f"Total tickets processed: {len(processed_docs)}/{len(tickets)}")
    print(f"Successfully processed: {len(processed_docs)}")
    if failed_tickets:
        print(f"Failed tickets: {len(failed_tickets)}")
        print(f"Failed ticket IDs: {', '.join(failed_tickets)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("\nGenerated documents:")
    if len(processed_docs) <= 20:
        for doc in processed_docs:
            print(f"  - {os.path.basename(doc)}")
    else:
        for doc in processed_docs[:10]:
            print(f"  - {os.path.basename(doc)}")
        print(f"  ... and {len(processed_docs) - 10} more documents")

if __name__ == "__main__":
    main()

