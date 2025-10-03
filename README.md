# JIRA Ticket Duplicate Detection

Extract and process Engineering Analysis tickets from JIRA for duplicate detection and analysis.

---

## 📁 Project Structure

```
duplicate_detection/
├── extract_all_engineering_tickets.py    # JIRA data extraction script
├── process_multimodal_tickets.py         # Multimodal processing script
├── create_embeddings_chromadb.py         # Embedding pipeline (V1)
├── requirements.txt                      # Master Python dependencies
├── duplicate_detection_tool/             # Web-based duplicate detection tool
│   ├── app.py                            # FastAPI web application
│   ├── embedding_service.py              # Embedding generation service
│   ├── gemini_analyzer.py                # Gemini-based similarity analysis
│   ├── jira_extractor.py                 # JIRA ticket extraction utilities
│   ├── multimodal_processor.py           # Multimodal content processing
│   ├── templates/                        # HTML templates
│   ├── static/                           # Static assets
│   ├── requirements.txt                  # [DEPRECATED - use root requirements.txt]
│   └── start_server.sh                   # Server startup script
├── jira_tickets_data/                    # Extracted ticket data
│   ├── index.json                        # Master index
│   ├── ticket_list.txt                   # List of ticket IDs
│   └── GM-XXXXX/                         # Individual tickets
│       ├── ticket_data.json              # Complete metadata (JSON)
│       ├── text_content.txt              # Text for embedding models
│       ├── changelog.json/txt            # Field change history
│       └── attachments/                  # Images, PDFs, docs
├── multimodal_documents/                 # Processed consolidated documents
│   └── GM-XXXXX_consolidated.txt         # Text + OCR + image descriptions
├── chroma_db/                            # Vector database storage
│   └── [ChromaDB files]                  # Persistent embeddings
├── api_tests/                            # API testing utilities
└── README.md
```

---

## 🚀 Quick Start

### Installation

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file with:
   ```
   JIRA_URL=your_jira_url
   JIRA_USERNAME=your_username
   JIRA_API_TOKEN=your_api_token
   GEMINI_API_KEY=your_gemini_api_key
   ```

### Running the Web Tool

```bash
cd duplicate_detection_tool
./start_server.sh
# Or manually:
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Access the tool at: http://localhost:8000

---

## 📄 Scripts

#### `extract_all_engineering_tickets.py`
Extracts JIRA tickets with metadata, comments, changelog, and attachments.

**Usage:**
```bash
python extract_all_engineering_tickets.py
```

#### `process_multimodal_tickets.py`
Processes tickets with multimodal capabilities:
- Consolidates all ticket text content
- Extracts text from images using OCR (Pytesseract)
- Generates visual descriptions using Gemini 2.5 Flash
- Automatically routes images to OCR or visual captioning based on text content

**Usage:**
```bash
python process_multimodal_tickets.py
```

#### `create_embeddings_chromadb.py`
**Embedding Pipeline V1** - Creates semantic embeddings and stores in vector database:
- Uses Google's `text-embedding-004` model (768-dimensional vectors)
- Processes multimodal consolidated documents
- Stores embeddings in ChromaDB with metadata (Ticket ID, Resolution Category, Status, Priority, etc.)
- Handles large documents by automatic truncation
- Includes verification and statistics display

**Usage:**
```bash
python create_embeddings_chromadb.py         # Process all documents
python create_embeddings_chromadb.py 5       # Process first 5 documents
python create_embeddings_chromadb.py all     # Process all documents (explicit)
```

---

## 🌐 Web Application

The `duplicate_detection_tool/` provides a web-based interface for duplicate detection:

### Features
- **Ticket Input:** Paste JIRA ticket ID or URL
- **Real-time Extraction:** Automatically fetches ticket data from JIRA
- **Multimodal Processing:** Processes text, images, and attachments
- **Semantic Search:** Finds similar tickets using vector embeddings
- **AI Analysis:** Uses Gemini for detailed similarity assessment
- **Interactive UI:** Modern, responsive web interface

### Architecture
- **Backend:** FastAPI (Python)
- **Frontend:** HTML/CSS/JavaScript
- **Vector DB:** ChromaDB
- **AI Models:** Google Gemini & text-embedding-004
- **OCR:** Pytesseract for image text extraction

### API Endpoints
- `GET /` - Main web interface
- `POST /process_ticket` - Process and find duplicates for a ticket
- `GET /health` - Health check endpoint

---

## 🗂️ Data Files

#### `jira_tickets_data/`
Raw ticket data extracted from JIRA:
- **`ticket_data.json`** - Complete structured metadata (JSON)
- **`text_content.txt`** - Formatted text for embedding models
- **`changelog.json/txt`** - Field change history
- **`attachments/`** - Downloaded images and documents

#### `multimodal_documents/`
Processed consolidated documents:
- **`GM-XXXXX_consolidated.txt`** - Complete ticket with text, OCR extractions, and image descriptions

#### `chroma_db/`
Vector database storage:
- **Collection:** `jira_tickets`
- **Embedding Model:** Google text-embedding-004 (768 dimensions)
- **Metadata:** Ticket ID, Resolution, Status, Priority, Summary, Created/Resolved dates
- **Storage:** Persistent local ChromaDB instance

---

## 🔧 Technical Details

### Dependencies
- **JIRA Integration:** jira-python
- **Web Framework:** FastAPI, Uvicorn, Pydantic
- **AI/ML:** google-generativeai, chromadb
- **Image Processing:** Pillow, pytesseract
- **Utilities:** requests, tqdm, python-multipart

### Workflow
1. **Extract** tickets from JIRA → `jira_tickets_data/`
2. **Process** multimodal content → `multimodal_documents/`
3. **Embed** documents → `chroma_db/`
4. **Search** for duplicates via web interface or API

---

## 📝 Notes

- Ensure Tesseract OCR is installed for image text extraction
- ChromaDB stores embeddings persistently in `chroma_db/`
- The web tool automatically creates embeddings for new tickets
- All API keys should be stored in `.env` file (never commit!)

---

## 🤝 Contributing

This is an internal tool for duplicate ticket detection. For issues or improvements, please contact the development team.
