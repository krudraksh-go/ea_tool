#!/usr/bin/env python3
"""
FastAPI Service for Duplicate Detection
Analyzes new JIRA tickets and finds similar historical tickets using vector embeddings
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import os
import json
import asyncio
from typing import Optional, List, Dict
import traceback
import shutil

from jira_extractor import extract_ticket_data
from multimodal_processor import process_ticket_multimodal
from embedding_service import create_ticket_embedding, query_similar_tickets
from gemini_analyzer import analyze_with_gemini

app = FastAPI(title="Duplicate Detection Service", version="1.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration
JIRA_BASE_URL = "https://work.greyorange.com/jira"
JIRA_USER_ID = "XDR_log"
JIRA_API_TOKEN = "NTUwNDMxMjMwNjE5OtIfJ86FEMso4JPQjkiuQEvkqohc"

# Use relative paths that work across different environments
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "chroma_db")
TEMP_PROCESSING_DIR = os.path.join(BASE_DIR, "temp_processing")

# Ensure temp directory exists
os.makedirs(TEMP_PROCESSING_DIR, exist_ok=True)

def clean_temp_processing_dir():
    """
    Clean the temp_processing directory by removing all its contents
    """
    try:
        if os.path.exists(TEMP_PROCESSING_DIR):
            # Remove all contents
            for item in os.listdir(TEMP_PROCESSING_DIR):
                item_path = os.path.join(TEMP_PROCESSING_DIR, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            print(f"Cleaned temp_processing directory: {TEMP_PROCESSING_DIR}")
        # Recreate the directory
        os.makedirs(TEMP_PROCESSING_DIR, exist_ok=True)
    except Exception as e:
        print(f"Error cleaning temp_processing directory: {e}")

class TicketRequest(BaseModel):
    ticket_number: str  # Just the number part, e.g., "247999"

class AnalysisResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict] = None

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main web interface"""
    with open("templates/index.html", "r") as f:
        return f.read()

@app.post("/api/analyze")
async def analyze_ticket(request: TicketRequest):
    """
    Main endpoint to analyze a ticket
    Returns immediately with a task ID, actual processing happens via streaming
    """
    ticket_id = f"GM-{request.ticket_number}"
    
    return {
        "status": "started",
        "ticket_id": ticket_id,
        "message": f"Analysis started for {ticket_id}"
    }

@app.get("/api/analyze-stream/{ticket_number}")
async def analyze_ticket_stream(ticket_number: str):
    """
    Streaming endpoint that processes the ticket and yields progress updates
    """
    async def event_generator():
        ticket_id = f"GM-{ticket_number}"
        
        try:
            # Step 0: Clean temp_processing directory (silently)
            await asyncio.to_thread(clean_temp_processing_dir)
            
            # Step 1: Extract ticket data from JIRA
            msg = f'Extracting data for {ticket_id}...'
            yield f"data: {json.dumps({'step': 'extract', 'status': 'in_progress', 'message': msg})}\n\n"
            
            ticket_data = await asyncio.to_thread(
                extract_ticket_data,
                ticket_id,
                JIRA_BASE_URL,
                JIRA_API_TOKEN,
                TEMP_PROCESSING_DIR
            )
            
            # Check for extraction errors
            if not ticket_data or "error" in ticket_data:
                if ticket_data and "error" in ticket_data:
                    # Specific error from JIRA extraction
                    error_msg = ticket_data.get("error", "Unknown error occurred")
                    error_type = ticket_data.get("error_type", "unknown")
                else:
                    # General failure
                    error_msg = f'Failed to extract ticket {ticket_id}'
                    error_type = "unknown"
                
                yield f"data: {json.dumps({'step': 'extract', 'status': 'error', 'message': error_msg, 'error_type': error_type})}\n\n"
                return
            
            msg = f'Successfully extracted {ticket_id}'
            yield f"data: {json.dumps({'step': 'extract', 'status': 'complete', 'message': msg, 'summary': ticket_data['metadata']['summary']})}\n\n"
            
            # Step 2: Process multimodal content (images, attachments)
            yield f"data: {json.dumps({'step': 'multimodal', 'status': 'in_progress', 'message': 'Processing images and attachments...'})}\n\n"
            
            multimodal_content = await asyncio.to_thread(
                process_ticket_multimodal,
                ticket_data,
                ticket_id
            )
            
            num_images = len(multimodal_content.get("images", []))
            msg = f'Processed {num_images} images'
            yield f"data: {json.dumps({'step': 'multimodal', 'status': 'complete', 'message': msg})}\n\n"
            
            # Step 3: Create embedding
            yield f"data: {json.dumps({'step': 'embedding', 'status': 'in_progress', 'message': 'Creating vector embedding...'})}\n\n"
            
            embedding = await asyncio.to_thread(
                create_ticket_embedding,
                ticket_data,
                multimodal_content
            )
            
            if not embedding:
                yield f"data: {json.dumps({'step': 'embedding', 'status': 'error', 'message': 'Failed to create embedding'})}\n\n"
                return
            
            msg = f'Created embedding (dimension: {len(embedding)})'
            yield f"data: {json.dumps({'step': 'embedding', 'status': 'complete', 'message': msg})}\n\n"
            
            # Step 4: Query ChromaDB for similar tickets
            yield f"data: {json.dumps({'step': 'search', 'status': 'in_progress', 'message': 'Searching for similar tickets...'})}\n\n"
            
            similar_tickets = await asyncio.to_thread(
                query_similar_tickets,
                embedding,
                CHROMA_DB_DIR,
                top_k=5,
                exclude_ticket_id=ticket_id  # Exclude the input ticket from results
            )
            
            if not similar_tickets:
                yield f"data: {json.dumps({'step': 'search', 'status': 'error', 'message': 'No similar tickets found'})}\n\n"
                return
            
            similar_ticket_ids = [t['ticket_id'] for t in similar_tickets]
            msg = f'Found {len(similar_tickets)} similar tickets'
            yield f"data: {json.dumps({'step': 'search', 'status': 'complete', 'message': msg, 'similar_tickets': similar_ticket_ids})}\n\n"
            
            # Step 5: Analyze with Gemini Pro
            yield f"data: {json.dumps({'step': 'analyze', 'status': 'in_progress', 'message': 'Analyzing with Gemini Pro...'})}\n\n"
            
            analysis_result = await asyncio.to_thread(
                analyze_with_gemini,
                ticket_data,
                multimodal_content,
                similar_tickets
            )
            
            if not analysis_result:
                yield f"data: {json.dumps({'step': 'analyze', 'status': 'error', 'message': 'Failed to analyze with Gemini'})}\n\n"
                return
            
            yield f"data: {json.dumps({'step': 'analyze', 'status': 'complete', 'message': 'Analysis complete!'})}\n\n"
            
            # Step 6: Send final results
            final_result = {
                'step': 'complete',
                'status': 'success',
                'ticket_id': ticket_id,
                'summary': ticket_data['metadata']['summary'],
                'similar_tickets': similar_tickets,
                'analysis': analysis_result,
                'new_ticket_data': {
                    'description': ticket_data['metadata'].get('description', 'N/A'),
                    'status': ticket_data['metadata'].get('status', 'N/A'),
                    'priority': ticket_data['metadata'].get('priority', 'N/A'),
                    'created': ticket_data['metadata'].get('created', 'N/A'),
                }
            }
            
            yield f"data: {json.dumps(final_result)}\n\n"
            
        except Exception as e:
            error_message = str(e)
            error_traceback = traceback.format_exc()
            print(f"Error processing ticket: {error_traceback}")
            msg = f'Error: {error_message}'
            yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': msg})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "duplicate_detection"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

