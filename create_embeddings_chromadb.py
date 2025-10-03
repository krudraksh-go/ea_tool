#!/usr/bin/env python3
"""
Embedding Pipeline for Multimodal Documents
This script creates embeddings from multimodal documents and stores them in ChromaDB

Usage:
    python create_embeddings_chromadb.py [num_documents]
    
Examples:
    python create_embeddings_chromadb.py         # Process all documents
    python create_embeddings_chromadb.py 5       # Process first 5 documents
    python create_embeddings_chromadb.py all     # Process all documents (explicit)
"""

import os
import sys
import json
import re
from pathlib import Path
from tqdm import tqdm
import google.generativeai as genai
import chromadb
from chromadb.config import Settings

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyBrx2rU1XxfHw7hQ-iQNEzLrXHgeylrV-s"
genai.configure(api_key=GEMINI_API_KEY)

# Paths
MULTIMODAL_DOCS_DIR = "/Users/rudraksh.k/Documents/tool_development/duplicate_detection/multimodal_documents"
JIRA_TICKETS_DIR = "/Users/rudraksh.k/Documents/tool_development/duplicate_detection/jira_tickets_data"
CHROMA_DB_DIR = "/Users/rudraksh.k/Documents/tool_development/duplicate_detection/chroma_db"

def setup_chromadb():
    """Initialize ChromaDB client and collection"""
    print(f"\nSetting up ChromaDB at: {CHROMA_DB_DIR}")
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)
    
    # Create ChromaDB client with persistent storage
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    
    # Get or create collection
    try:
        # Try to get existing collection first
        collection = client.get_collection(name="jira_tickets")
        print(f"Using existing collection: jira_tickets (contains {collection.count()} documents)")
    except:
        # Create new collection if it doesn't exist
        collection = client.create_collection(
            name="jira_tickets",
            metadata={"description": "Multimodal JIRA ticket embeddings"}
        )
        print("Created new collection: jira_tickets")
    
    return client, collection

def extract_ticket_id_from_filename(filename):
    """Extract ticket ID from consolidated document filename"""
    # Format: GM-XXXXXX_consolidated.txt
    match = re.match(r'(GM-\d+)_consolidated\.txt', filename)
    if match:
        return match.group(1)
    return None

def get_ticket_metadata(ticket_id):
    """Get ticket metadata from ticket_data.json"""
    ticket_data_path = os.path.join(JIRA_TICKETS_DIR, ticket_id, "ticket_data.json")
    
    try:
        with open(ticket_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            metadata = data.get('metadata', {})
            
            # Build metadata dict, replacing None values with 'N/A'
            raw_metadata = {
                'ticket_id': ticket_id,
                'resolution': metadata.get('resolution'),
                'status': metadata.get('status'),
                'summary': metadata.get('summary'),
                'priority': metadata.get('priority'),
                'created': metadata.get('created'),
                'resolved': metadata.get('resolved')
            }
            
            # Filter out None values and replace with 'N/A'
            clean_metadata = {}
            for key, value in raw_metadata.items():
                if value is None:
                    clean_metadata[key] = 'N/A'
                elif isinstance(value, str):
                    clean_metadata[key] = value
                else:
                    clean_metadata[key] = str(value)
            
            return clean_metadata
    except Exception as e:
        print(f"  [WARNING] Could not load metadata for {ticket_id}: {e}")
        # Return basic metadata with ticket_id
        return {
            'ticket_id': ticket_id,
            'resolution': 'N/A',
            'status': 'N/A',
            'summary': 'N/A',
            'priority': 'N/A',
            'created': 'N/A',
            'resolved': 'N/A'
        }

def read_consolidated_document(doc_path):
    """Read the consolidated document content"""
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"  [ERROR] Failed to read {doc_path}: {e}")
        return None

def create_embedding(text):
    """Create embedding using Google's text-embedding-004 model"""
    try:
        # Use the text-embedding-004 model
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        print(f"  [ERROR] Failed to create embedding: {e}")
        return None

def chunk_text(text, max_bytes=30000):
    """
    Split text into chunks that don't exceed max_bytes when encoded as UTF-8.
    Tries to split at natural boundaries (paragraphs, sentences).
    """
    chunks = []
    
    # If text fits in one chunk, return it
    if len(text.encode('utf-8')) <= max_bytes:
        return [text]
    
    # Split by double newlines (paragraphs) first
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for paragraph in paragraphs:
        # Check if adding this paragraph would exceed the limit
        test_chunk = current_chunk + '\n\n' + paragraph if current_chunk else paragraph
        
        if len(test_chunk.encode('utf-8')) <= max_bytes:
            current_chunk = test_chunk
        else:
            # Save current chunk if it has content
            if current_chunk:
                chunks.append(current_chunk)
            
            # If single paragraph is too large, split it further
            if len(paragraph.encode('utf-8')) > max_bytes:
                # Split by sentences
                sentences = paragraph.replace('. ', '.\n').split('\n')
                temp_chunk = ""
                
                for sentence in sentences:
                    test_sentence = temp_chunk + ' ' + sentence if temp_chunk else sentence
                    
                    if len(test_sentence.encode('utf-8')) <= max_bytes:
                        temp_chunk = test_sentence
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk)
                        
                        # If single sentence is still too large, force split
                        if len(sentence.encode('utf-8')) > max_bytes:
                            # Split by bytes as last resort
                            byte_data = sentence.encode('utf-8')
                            for i in range(0, len(byte_data), max_bytes):
                                chunk_bytes = byte_data[i:i+max_bytes]
                                # Decode, ignoring errors for incomplete UTF-8 sequences
                                chunks.append(chunk_bytes.decode('utf-8', errors='ignore'))
                        else:
                            temp_chunk = sentence
                
                if temp_chunk:
                    chunks.append(temp_chunk)
                current_chunk = ""
            else:
                current_chunk = paragraph
    
    # Add remaining chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def get_document_files(limit=None):
    """Get list of consolidated document files"""
    files = [f for f in os.listdir(MULTIMODAL_DOCS_DIR) 
             if f.endswith('_consolidated.txt')]
    files.sort()
    
    if limit:
        files = files[:limit]
    
    return files

def process_and_store_document(doc_filename, collection):
    """Process a single document and store in ChromaDB with chunking support"""
    # Extract ticket ID
    ticket_id = extract_ticket_id_from_filename(doc_filename)
    if not ticket_id:
        print(f"  [ERROR] Could not extract ticket ID from {doc_filename}")
        return False
    
    print(f"\nProcessing: {ticket_id}")
    
    # Read document content
    doc_path = os.path.join(MULTIMODAL_DOCS_DIR, doc_filename)
    content = read_consolidated_document(doc_path)
    if not content:
        return False
    
    content_bytes = len(content.encode('utf-8'))
    print(f"  Document size: {len(content)} characters ({content_bytes} bytes)")
    
    # Get metadata
    metadata = get_ticket_metadata(ticket_id)
    print(f"  Resolution: {metadata['resolution']}")
    print(f"  Status: {metadata['status']}")
    
    # Check if document needs chunking
    MAX_BYTES = 30000  # Safe limit to avoid 36,000 byte API limit
    chunks = chunk_text(content, max_bytes=MAX_BYTES)
    
    if len(chunks) > 1:
        print(f"  Document split into {len(chunks)} chunks to preserve all information")
    
    # Process each chunk
    all_success = True
    for chunk_idx, chunk in enumerate(chunks):
        chunk_id = f"{ticket_id}_chunk{chunk_idx}" if len(chunks) > 1 else ticket_id
        
        if len(chunks) > 1:
            print(f"  Creating embedding for chunk {chunk_idx + 1}/{len(chunks)}...")
        else:
            print(f"  Creating embedding...")
        
        embedding = create_embedding(chunk)
        if not embedding:
            all_success = False
            continue
        
        print(f"    Embedding dimension: {len(embedding)}")
        
        # Add chunk info to metadata if multiple chunks
        chunk_metadata = metadata.copy()
        if len(chunks) > 1:
            chunk_metadata['chunk_index'] = str(chunk_idx)
            chunk_metadata['total_chunks'] = str(len(chunks))
            chunk_metadata['is_chunked'] = 'true'
        else:
            chunk_metadata['is_chunked'] = 'false'
        
        # Store in ChromaDB
        try:
            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[chunk_metadata]
            )
            if len(chunks) > 1:
                print(f"    ✓ Chunk {chunk_idx + 1} stored in ChromaDB")
            else:
                print(f"  ✓ Stored in ChromaDB")
        except Exception as e:
            print(f"  [ERROR] Failed to store chunk {chunk_idx} in ChromaDB: {e}")
            all_success = False
    
    return all_success

def verify_stored_data(collection, ticket_ids):
    """Verify and display stored data from ChromaDB"""
    print("\n" + "="*80)
    print("VERIFICATION: Displaying stored data")
    print("="*80)
    
    for ticket_id in ticket_ids:
        print(f"\n{'-'*80}")
        print(f"Ticket ID: {ticket_id}")
        print(f"{'-'*80}")
        
        try:
            # Query the specific document
            result = collection.get(
                ids=[ticket_id],
                include=['embeddings', 'metadatas', 'documents']
            )
            
            if result and result['ids']:
                # Display metadata
                metadata = result['metadatas'][0]
                print(f"Metadata:")
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
                
                # Display embedding info
                embedding = result['embeddings'][0]
                print(f"\nEmbedding:")
                print(f"  Dimension: {len(embedding)}")
                print(f"  First 10 values: {embedding[:10]}")
                print(f"  Last 10 values: {embedding[-10:]}")
                print(f"  Min value: {min(embedding):.6f}")
                print(f"  Max value: {max(embedding):.6f}")
                
                # Display document excerpt
                document = result['documents'][0]
                print(f"\nDocument:")
                print(f"  Total length: {len(document)} characters")
                print(f"  First 500 characters:")
                print(f"  {document[:500]}...")
            else:
                print(f"  [WARNING] No data found for {ticket_id}")
        
        except Exception as e:
            print(f"  [ERROR] Failed to retrieve {ticket_id}: {e}")

def display_collection_stats(collection):
    """Display overall collection statistics"""
    print("\n" + "="*80)
    print("COLLECTION STATISTICS")
    print("="*80)
    
    try:
        count = collection.count()
        print(f"Total documents in collection: {count}")
        
        if count > 0:
            # Get a sample of documents to analyze
            sample_size = min(10, count)
            sample = collection.peek(sample_size)
            
            print(f"\nSample metadata fields (from {sample_size} documents):")
            if sample['metadatas']:
                first_metadata = sample['metadatas'][0]
                for key in first_metadata.keys():
                    print(f"  - {key}")
            
            # Count resolutions
            if sample['metadatas']:
                resolutions = {}
                for metadata in sample['metadatas']:
                    res = metadata.get('resolution', 'N/A')
                    resolutions[res] = resolutions.get(res, 0) + 1
                
                print(f"\nResolution categories (in sample):")
                for res, count in sorted(resolutions.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {res}: {count}")
    
    except Exception as e:
        print(f"[ERROR] Failed to get collection stats: {e}")

def main():
    """Main function"""
    print("="*80)
    print("EMBEDDING PIPELINE - CHROMADB V1")
    print("="*80)
    print("\nThis script will:")
    print("1. Read multimodal consolidated documents")
    print("2. Create embeddings using Google text-embedding-004")
    print("3. Store embeddings in ChromaDB with metadata")
    print("4. Verify and display the stored data")
    
    # Parse command line arguments - default to ALL documents
    limit = None  # Default: process all documents
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.lower() in ['all', '0']:
            limit = None
        else:
            try:
                limit = int(arg)
            except ValueError:
                print(f"\nInvalid argument: {arg}")
                print("Usage: python create_embeddings_chromadb.py [num_documents]")
                return
    
    # Setup ChromaDB
    client, collection = setup_chromadb()
    
    # Get document files
    doc_files = get_document_files(limit=limit)
    if limit:
        print(f"\nProcessing {len(doc_files)} documents (limited to {limit})")
    else:
        print(f"\nProcessing ALL {len(doc_files)} documents")
    
    if len(doc_files) <= 10:
        print(f"Documents: {', '.join(doc_files)}")
    else:
        print(f"First 10 documents: {', '.join(doc_files[:10])} ...")
    
    # Process documents
    processed_tickets = []
    failed_tickets = []
    
    print("\n" + "="*80)
    print("PROCESSING DOCUMENTS")
    print("="*80)
    
    for doc_file in tqdm(doc_files, desc="Processing documents", unit="doc"):
        ticket_id = extract_ticket_id_from_filename(doc_file)
        if process_and_store_document(doc_file, collection):
            processed_tickets.append(ticket_id)
        else:
            failed_tickets.append(ticket_id if ticket_id else doc_file)
    
    # Summary
    print("\n" + "="*80)
    print("PROCESSING SUMMARY")
    print("="*80)
    print(f"Successfully processed: {len(processed_tickets)}/{len(doc_files)}")
    if failed_tickets:
        print(f"Failed: {len(failed_tickets)}")
        print(f"Failed tickets: {', '.join(failed_tickets)}")
    
    # Verify stored data - display first 5 for verification
    if processed_tickets:
        verify_tickets = processed_tickets[:min(5, len(processed_tickets))]
        verify_stored_data(collection, verify_tickets)
    
    # Display collection statistics
    display_collection_stats(collection)
    
    print("\n" + "="*80)
    print("EMBEDDING PIPELINE COMPLETE")
    print("="*80)
    print(f"ChromaDB location: {CHROMA_DB_DIR}")
    print(f"Collection name: jira_tickets")
    print(f"Total documents: {collection.count()}")

if __name__ == "__main__":
    main()

