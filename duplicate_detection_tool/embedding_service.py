"""
Embedding Service
Creates embeddings and queries ChromaDB for similar tickets
"""

import google.generativeai as genai
import chromadb
from collections import defaultdict

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyBrx2rU1XxfHw7hQ-iQNEzLrXHgeylrV-s"
genai.configure(api_key=GEMINI_API_KEY)

def build_ticket_text(ticket_data, multimodal_content):
    """
    Build consolidated text representation of a ticket
    Weighted structure: Summary, Description, Comments get highest priority
    
    Args:
        ticket_data: Ticket data from jira_extractor
        multimodal_content: Processed multimodal content
    
    Returns:
        Complete text representation of the ticket
    """
    metadata = ticket_data.get("metadata", {})
    comments = ticket_data.get("comments", [])
    
    # Build text content
    text_parts = []
    
    # ========================================================================
    # 🔥 WEIGHTED SECTION: Most Important Fields First (High Semantic Weight)
    # ========================================================================
    text_parts.append("=" * 80)
    text_parts.append("PRIMARY ISSUE SUMMARY")
    text_parts.append("=" * 80)
    
    # Summary - Triple weight by repeating with variations
    summary = metadata.get('summary', 'N/A')
    text_parts.append(f"PROBLEM: {summary}")
    text_parts.append(f"ISSUE: {summary}")
    text_parts.append(f"SUMMARY: {summary}")
    text_parts.append("")
    
    # Key metadata for context
    text_parts.append(f"SEVERITY: {metadata.get('severity', 'N/A')}")
    text_parts.append(f"PRIORITY: {metadata.get('priority', 'N/A')}")
    text_parts.append(f"CATEGORY: {metadata.get('origins', 'N/A')}")
    text_parts.append("")
    
    # Affects Versions - High weight (repeated for emphasis)
    affects_versions = metadata.get('affects_versions', [])
    if affects_versions:
        affects_str = ', '.join(affects_versions)
        text_parts.append("=" * 80)
        text_parts.append("AFFECTED SOFTWARE VERSIONS (CRITICAL)")
        text_parts.append("=" * 80)
        text_parts.append(f"VERSION: {affects_str}")
        text_parts.append(f"AFFECTS VERSION: {affects_str}")
        text_parts.append(f"SOFTWARE VERSION: {affects_str}")
        text_parts.append("")
        text_parts.append("=" * 80)
        text_parts.append("")
    
    # Description - Double weight at the top
    description = str(metadata.get('description', 'No description available'))
    text_parts.append("=" * 80)
    text_parts.append("PROBLEM DESCRIPTION (PRIMARY)")
    text_parts.append("=" * 80)
    text_parts.append(description)
    text_parts.append("")
    text_parts.append("=" * 80)
    text_parts.append("")
    
    # Comments - High weight section
    if comments:
        text_parts.append("=" * 80)
        text_parts.append(f"KEY DISCUSSION AND ANALYSIS ({len(comments)} comments)")
        text_parts.append("=" * 80)
        for i, comment in enumerate(comments, 1):
            text_parts.append(f"\nComment #{i} by {comment['author']} on {comment['created']}:")
            text_parts.append(comment['body'])
            text_parts.append("-" * 40)
        text_parts.append("")
        text_parts.append("=" * 80)
        text_parts.append("")
    
    # ========================================================================
    # COMPLETE TICKET DETAILS (Standard Weight)
    # ========================================================================
    text_parts.append("=" * 80)
    text_parts.append("COMPLETE TICKET METADATA")
    text_parts.append("=" * 80)
    text_parts.append("")
    
    # Header
    text_parts.append(f"TICKET ID: {metadata.get('key', 'N/A')}")
    text_parts.append(f"STATUS: {metadata.get('status', 'N/A')}")
    text_parts.append(f"STATUS CATEGORY: {metadata.get('status_category', 'N/A')}")
    text_parts.append(f"RESOLUTION: {metadata.get('resolution', 'N/A')}")
    
    affects = ', '.join(metadata.get('affects_versions', [])) or 'N/A'
    fix = ', '.join(metadata.get('fix_versions', [])) or 'N/A'
    text_parts.append(f"AFFECTS VERSIONS: {affects}")
    text_parts.append(f"FIX VERSIONS: {fix}")
    
    text_parts.append(f"CREATED: {metadata.get('created', 'N/A')}")
    text_parts.append(f"UPDATED: {metadata.get('updated', 'N/A')}")
    text_parts.append(f"RESOLVED: {metadata.get('resolved', 'N/A')}")
    text_parts.append("")
    text_parts.append("=" * 80)
    text_parts.append("")
    
    # Description again (for completeness in full context)
    text_parts.append("FULL DESCRIPTION:")
    text_parts.append("-" * 80)
    text_parts.append(description)
    text_parts.append("")
    text_parts.append("=" * 80)
    text_parts.append("")
    
    # Image analyses
    images = multimodal_content.get("images", [])
    if images:
        text_parts.append(f"ATTACHED IMAGES ({len(images)}):")
        text_parts.append("-" * 80)
        for i, img in enumerate(images, 1):
            text_parts.append(f"\nImage {i}: {img['filename']}")
            text_parts.append(f"Caption: {img['caption']}")
            if img['text_content']:
                text_parts.append(f"Visible Text: {img['text_content']}")
            if img['technical_details']:
                text_parts.append(f"Technical Details: {img['technical_details']}")
            text_parts.append("-" * 40)
        text_parts.append("")
        text_parts.append("=" * 80)
        text_parts.append("")
    
    # Issue links
    issue_links = metadata.get('issue_links', [])
    if issue_links:
        text_parts.append("ISSUE LINKS:")
        text_parts.append("-" * 80)
        for link in issue_links:
            text_parts.append(f"  [{link['direction']}] {link['type']}: {link['key']} - {link['summary']}")
        text_parts.append("")
    
    return "\n".join(text_parts)

def create_ticket_embedding(ticket_data, multimodal_content):
    """
    Create embedding for a ticket
    
    Returns:
        Embedding vector
    """
    try:
        # Build text representation
        ticket_text = build_ticket_text(ticket_data, multimodal_content)
        
        # Check size and chunk if necessary
        text_bytes = len(ticket_text.encode('utf-8'))
        if text_bytes > 30000:
            print(f"Warning: Ticket text is large ({text_bytes} bytes), truncating to 30000 bytes")
            # Truncate to safe size
            ticket_text = ticket_text.encode('utf-8')[:30000].decode('utf-8', errors='ignore')
        
        # Create embedding
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=ticket_text,
            task_type="retrieval_query"  # Use query mode for searching
        )
        
        return result['embedding']
        
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return None

def query_similar_tickets(embedding, chroma_db_dir, top_k=5, exclude_ticket_id=None):
    """
    Query ChromaDB for similar tickets
    
    Args:
        embedding: Query embedding vector
        chroma_db_dir: Path to ChromaDB directory
        top_k: Number of similar tickets to retrieve (excluding the input ticket)
        exclude_ticket_id: Ticket ID to exclude from results (usually the input ticket itself)
    
    Returns:
        List of similar tickets with all their chunks combined (excluding the input ticket)
    """
    try:
        # Connect to ChromaDB
        client = chromadb.PersistentClient(path=chroma_db_dir)
        collection = client.get_collection(name="jira_tickets")
        
        # Query for more results to account for:
        # 1. Chunked documents (multiple chunks per ticket)
        # 2. Self-match exclusion (the input ticket itself)
        # Request extra to ensure we get enough after filtering
        query_results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k * 8,  # Increased to account for self-match and chunking
            include=['embeddings', 'metadatas', 'documents', 'distances']
        )
        
        if not query_results or not query_results['ids']:
            print("No similar tickets found")
            return []
        
        # Group results by ticket_id (handling chunks)
        ticket_groups = defaultdict(lambda: {
            'chunks': [],
            'metadata': None,
            'min_distance': float('inf')
        })
        
        for i in range(len(query_results['ids'][0])):
            chunk_id = query_results['ids'][0][i]
            metadata = query_results['metadatas'][0][i]
            document = query_results['documents'][0][i]
            distance = query_results['distances'][0][i]
            
            # Extract base ticket_id (remove _chunkX suffix if present)
            ticket_id = metadata.get('ticket_id', chunk_id.split('_chunk')[0])
            
            # 🔥 FILTER: Skip the input ticket itself
            if exclude_ticket_id and ticket_id == exclude_ticket_id:
                continue
            
            ticket_groups[ticket_id]['chunks'].append({
                'chunk_id': chunk_id,
                'content': document,
                'distance': distance,
                'chunk_index': metadata.get('chunk_index', '0')
            })
            
            # Keep the best distance for this ticket
            if distance < ticket_groups[ticket_id]['min_distance']:
                ticket_groups[ticket_id]['min_distance'] = distance
            
            # Store metadata (same for all chunks of a ticket)
            if ticket_groups[ticket_id]['metadata'] is None:
                ticket_groups[ticket_id]['metadata'] = metadata
        
        # Sort tickets by their best match distance and get top_k (excluding input ticket)
        sorted_tickets = sorted(
            ticket_groups.items(),
            key=lambda x: x[1]['min_distance']
        )[:top_k]
        
        # Build result list
        similar_tickets = []
        for ticket_id, data in sorted_tickets:
            # Sort chunks by index
            chunks = sorted(data['chunks'], key=lambda x: int(x.get('chunk_index', 0)))
            
            # Combine all chunks for this ticket
            combined_content = "\n\n--- CHUNK BOUNDARY ---\n\n".join(
                [chunk['content'] for chunk in chunks]
            )
            
            similar_tickets.append({
                'ticket_id': ticket_id,
                'metadata': data['metadata'],
                'distance': data['min_distance'],
                'similarity_score': 1 - data['min_distance'],  # Convert distance to similarity
                'num_chunks': len(chunks),
                'chunks': chunks,
                'combined_content': combined_content
            })
        
        if exclude_ticket_id:
            print(f"Found {len(similar_tickets)} similar tickets (excluding input ticket {exclude_ticket_id})")
        else:
            print(f"Found {len(similar_tickets)} similar tickets")
        
        for ticket in similar_tickets:
            chunks_info = f" ({ticket['num_chunks']} chunks)" if ticket['num_chunks'] > 1 else ""
            print(f"  - {ticket['ticket_id']}: similarity={ticket['similarity_score']:.3f}{chunks_info}")
        
        return similar_tickets
        
    except Exception as e:
        print(f"Error querying ChromaDB: {e}")
        return []

