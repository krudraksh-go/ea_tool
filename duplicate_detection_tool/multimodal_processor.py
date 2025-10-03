"""
Multimodal Content Processor
Processes images and other attachments using Gemini Vision API
"""

import google.generativeai as genai
from PIL import Image
import os

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyBrx2rU1XxfHw7hQ-iQNEzLrXHgeylrV-s"
genai.configure(api_key=GEMINI_API_KEY)

# Supported image formats
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

def is_image_file(filename):
    """Check if file is an image"""
    ext = os.path.splitext(filename.lower())[1]
    return ext in IMAGE_EXTENSIONS

def process_image_with_gemini(image_path):
    """
    Process an image using Gemini Vision API
    
    Returns:
        Dictionary with caption and OCR text
    """
    try:
        # Load image
        img = Image.open(image_path)
        
        # Prompt for comprehensive image analysis
        prompt = """Analyze this image in detail. Provide:
1. A descriptive caption of what the image shows
2. Any text visible in the image (OCR)
3. Technical details if it appears to be a screenshot (error messages, stack traces, logs, metrics, etc.)
4. Any charts, graphs, or visualizations and their key information

Format your response as:
CAPTION: [Your description]
TEXT_CONTENT: [All visible text]
TECHNICAL_DETAILS: [Any technical information observed]
"""
        
        # Use Gemini models with fallback - try pro first for best quality
        model_names = ['models/gemini-2.5-pro', 'models/gemini-2.5-flash', 'models/gemini-2.0-flash']
        
        response = None
        last_error = None
        
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([prompt, img])
                break  # Success, exit loop
            except Exception as model_error:
                last_error = model_error
                continue
        
        if response is None:
            raise last_error or Exception("All models failed")
        
        # Parse response
        analysis_text = response.text
        
        # Extract sections
        caption = ""
        text_content = ""
        technical_details = ""
        
        lines = analysis_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("CAPTION:"):
                current_section = "caption"
                caption = line.replace("CAPTION:", "").strip()
            elif line.startswith("TEXT_CONTENT:"):
                current_section = "text"
                text_content = line.replace("TEXT_CONTENT:", "").strip()
            elif line.startswith("TECHNICAL_DETAILS:"):
                current_section = "technical"
                technical_details = line.replace("TECHNICAL_DETAILS:", "").strip()
            elif current_section == "caption" and line:
                caption += " " + line
            elif current_section == "text" and line:
                text_content += " " + line
            elif current_section == "technical" and line:
                technical_details += " " + line
        
        # If parsing failed, use entire response as caption
        if not caption:
            caption = analysis_text[:500]  # First 500 chars
        
        return {
            "caption": caption.strip(),
            "text_content": text_content.strip(),
            "technical_details": technical_details.strip(),
            "full_analysis": analysis_text
        }
        
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return {
            "caption": f"[Error processing image: {str(e)}]",
            "text_content": "",
            "technical_details": "",
            "full_analysis": ""
        }

def process_ticket_multimodal(ticket_data, ticket_id):
    """
    Process all multimodal content for a ticket
    
    Args:
        ticket_data: Ticket data dictionary from jira_extractor
        ticket_id: Ticket ID for logging
    
    Returns:
        Dictionary with processed multimodal content
    """
    multimodal_content = {
        "images": [],
        "other_attachments": []
    }
    
    attachments = ticket_data.get("attachments", [])
    
    if not attachments:
        print(f"No attachments found for {ticket_id}")
        return multimodal_content
    
    print(f"Processing {len(attachments)} attachments for {ticket_id}")
    
    for attachment in attachments:
        filename = attachment.get("filename", "")
        file_path = attachment.get("path", "")
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
        
        if is_image_file(filename):
            print(f"  Processing image: {filename}")
            image_analysis = process_image_with_gemini(file_path)
            
            multimodal_content["images"].append({
                "filename": filename,
                "path": file_path,
                "size": attachment.get("size", 0),
                "caption": image_analysis["caption"],
                "text_content": image_analysis["text_content"],
                "technical_details": image_analysis["technical_details"],
                "full_analysis": image_analysis["full_analysis"]
            })
        else:
            # For non-image files, just record metadata
            multimodal_content["other_attachments"].append({
                "filename": filename,
                "path": file_path,
                "size": attachment.get("size", 0),
                "mime_type": attachment.get("mime_type", "unknown")
            })
    
    print(f"Processed {len(multimodal_content['images'])} images and {len(multimodal_content['other_attachments'])} other files")
    
    return multimodal_content

