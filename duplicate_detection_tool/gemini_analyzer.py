"""
Gemini Pro Analyzer
Uses Gemini Pro to analyze new tickets against similar historical tickets
"""

import google.generativeai as genai

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyBrx2rU1XxfHw7hQ-iQNEzLrXHgeylrV-s"
genai.configure(api_key=GEMINI_API_KEY)

def format_image_analyses(multimodal_content):
    """Format image analysis for the prompt"""
    images = multimodal_content.get("images", [])
    
    if not images:
        return "* No images attached to this ticket."
    
    image_texts = []
    for i, img in enumerate(images, 1):
        image_texts.append(f"* **Image {i}: {img['filename']}**")
        image_texts.append(f"  * Caption: {img['caption']}")
        if img['text_content']:
            image_texts.append(f"  * Visible Text (OCR): {img['text_content']}")
        if img['technical_details']:
            image_texts.append(f"  * Technical Details: {img['technical_details']}")
    
    return "\n".join(image_texts)

def format_historical_tickets(similar_tickets):
    """Format historical tickets with all their chunks"""
    historical_texts = []
    
    for i, ticket in enumerate(similar_tickets, 1):
        ticket_id = ticket['ticket_id']
        metadata = ticket['metadata']
        combined_content = ticket['combined_content']
        num_chunks = ticket['num_chunks']
        
        # Header
        chunk_info = f" [Document was split into {num_chunks} chunks for storage]" if num_chunks > 1 else ""
        historical_texts.append(f"### Historical Ticket {i}: {ticket_id}{chunk_info}")
        historical_texts.append(f"**Similarity Score:** {ticket['similarity_score']:.2%}")
        historical_texts.append(f"**Resolution:** {metadata.get('resolution', 'N/A')}")
        historical_texts.append(f"**Status:** {metadata.get('status', 'N/A')}")
        historical_texts.append(f"**Priority:** {metadata.get('priority', 'N/A')}")
        historical_texts.append("")
        historical_texts.append("**Full Content:**")
        historical_texts.append("```")
        historical_texts.append(combined_content)
        historical_texts.append("```")
        historical_texts.append("")
        historical_texts.append("---")
        historical_texts.append("")
    
    return "\n".join(historical_texts)

def build_analysis_prompt(ticket_data, multimodal_content, similar_tickets):
    """Build the comprehensive prompt for Gemini Pro"""
    
    metadata = ticket_data.get("metadata", {})
    comments = ticket_data.get("comments", [])
    changelog = ticket_data.get("changelog", [])
    
    # Format comments
    comments_text = ""
    if comments:
        comments_list = []
        for i, comment in enumerate(comments, 1):
            comments_list.append(f"  * **Comment {i}** (by {comment['author']} on {comment['created']}):")
            comments_list.append(f"    {comment['body'][:500]}...")  # Truncate long comments
        comments_text = "\n".join(comments_list)
    else:
        comments_text = "  * No comments on this ticket."
    
    # Format issue links
    issue_links_text = ""
    issue_links = metadata.get('issue_links', [])
    if issue_links:
        links_list = []
        for link in issue_links:
            links_list.append(f"  * [{link['direction']}] {link['type']}: {link['key']} - {link['summary']}")
        issue_links_text = "\n".join(links_list)
    else:
        issue_links_text = "  * No linked issues."
    
    # Format affects/fix versions
    affects_versions = ', '.join(metadata.get('affects_versions', [])) or 'N/A'
    fix_versions = ', '.join(metadata.get('fix_versions', [])) or 'N/A'
    
    # Build the prompt
    prompt = f"""You are an expert AI Support Analyst. Your job is to provide a concise, insightful summary for new engineering tickets by analyzing historical data.

You will be given the full context of a new JIRA ticket and the complete content from the top 5 most similar historical tickets. Some historical tickets may have been split into multiple chunks for storage - you will receive ALL chunks for each ticket.

Your task is to synthesize this information and generate a clear, actionable summary to be posted as a single comment on the new ticket.

---

## CONTEXT

### 1. New Ticket Information:

* **ID:** {metadata.get('key', 'N/A')}
* **Summary:** {metadata.get('summary', 'N/A')}
* **Status:** {metadata.get('status', 'N/A')} ({metadata.get('status_category', 'N/A')})
* **Priority:** {metadata.get('priority', 'N/A')}
* **Severity:** {metadata.get('severity', 'N/A')}
* **Origins:** {metadata.get('origins', 'N/A')}
* **Affects Versions:** {affects_versions}
* **Fix Versions:** {fix_versions}
* **Created:** {metadata.get('created', 'N/A')}
* **Resolution:** {metadata.get('resolution', 'N/A')}

**Description:**
```
{metadata.get('description', 'No description available')}
```

**Analysis of Attached Images:**
{format_image_analyses(multimodal_content)}

**Comments:**
{comments_text}

**Issue Links:**
{issue_links_text}

### 2. Historical Context from Similar Tickets:

{format_historical_tickets(similar_tickets)}

---

## YOUR ANALYSIS TASK

Based on all the provided context, perform the following analysis. Structure your response using the markdown format provided below.

1. **Summarize the New Problem:** In one sentence, what is the core issue reported in the new ticket?
2. **Identify Common Themes:** Analyze all the historical tickets (including all chunks). What are the recurring themes, keywords, or resolution categories? (e.g., "Database connection issues," "misconfigurations after deployment," "Sysops Issue").
3. **Pinpoint the Best Match:** Identify the single most relevant historical **JIRA ID**. Briefly explain *why* it is the strongest match to the new ticket, referencing specific details from both tickets.
4. **Root Cause Patterns:** If you can identify common root causes from the historical tickets, mention them.
5. **Provide a Final Recommendation:** Conclude with a brief, actionable summary suggesting a potential starting point for the assigned engineer. Include specific suggestions based on what worked in similar tickets.

---

## OUTPUT FORMAT

**Initial Problem Assessment:**
{{Your one-sentence summary of the new problem goes here.}}

**Analysis of Similar Historical Tickets:**
* **Common Themes:** {{List the recurring themes you identified.}}
* **Resolution Patterns:** {{Describe common resolution approaches from historical tickets.}}
* **Most Relevant Past Ticket:** **{{JIRA_ID of the best match}}**. This ticket is the strongest match because {{Your justification goes here}}.

**Root Cause Analysis:**
{{If applicable, describe common root causes identified in similar tickets.}}

**Recommendation:**
Based on the historical context, the engineer should start by investigating {{Your final recommendation goes here}}. Specifically:
* {{Specific action item 1}}
* {{Specific action item 2}}
* {{Specific action item 3 if applicable}}

**Confidence Level:** {{High/Medium/Low}} - {{Brief explanation of confidence}}

---

Please provide your analysis now.
"""
    
    return prompt

def analyze_with_gemini(ticket_data, multimodal_content, similar_tickets):
    """
    Analyze the new ticket against similar historical tickets using Gemini Pro
    
    Returns:
        Dictionary with analysis results
    """
    try:
        print("Building analysis prompt...")
        prompt = build_analysis_prompt(ticket_data, multimodal_content, similar_tickets)
        
        print(f"Prompt length: {len(prompt)} characters")
        
        # Use Gemini Pro for analysis - try multiple model names for compatibility
        # Using stable releases available in the API (Pro first for best quality)
        model_names = ['models/gemini-2.5-pro', 'models/gemini-2.5-flash', 'models/gemini-2.0-flash']
        
        last_error = None
        for model_name in model_names:
            try:
                print(f"Attempting to use model: {model_name}")
                model = genai.GenerativeModel(model_name)
                
                print("Sending to Gemini for analysis...")
                response = model.generate_content(prompt)
                
                analysis_text = response.text
                
                print(f"Analysis complete! Generated {len(analysis_text)} characters using {model_name}")
                
                return {
                    "analysis_text": analysis_text,
                    "prompt_used": prompt,
                    "model": model_name
                }
            except Exception as model_error:
                last_error = model_error
                print(f"Failed with {model_name}: {model_error}")
                continue
        
        # If all models failed, raise the last error
        if last_error:
            raise last_error
        
    except Exception as e:
        print(f"Error analyzing with Gemini: {e}")
        return {
            "analysis_text": f"Error: Failed to generate analysis - {str(e)}",
            "prompt_used": "",
            "model": "unknown",
            "error": str(e)
        }

