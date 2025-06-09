# PomBot - AI Chatbot for Auto Parts Shop

An intelligent chatbot powered by Ollama that reads product and service information from PDF files instead of hardcoded data.

## 🚀 Key Improvements

- **PDF Knowledge Base**: No more hardcoded data - reads from PDF files
- **Dynamic Loading**: Automatically extracts products and services from PDF
- **Flexible Pricing**: Supports various price formats and patterns
- **Hot Reload**: Update knowledge base without restarting the server
- **Better Error Handling**: Graceful fallbacks when PDF is unavailable
- **Enhanced Logging**: Detailed logs for debugging and monitoring

## 📋 Requirements

Install dependencies:
```bash
pip install -r requirements.txt
```

Required packages:
- Flask 2.3.3
- flask-cors 4.0.0
- requests 2.31.0
- PyPDF2 3.0.1
- pdfplumber 0.10.3
- waitress 2.1.2

## 📁 Setup

1. **Create your PDF knowledge base** with the following format:

```
POMWORKZ AUTO PARTS CATALOG

PRODUCT CATALOG:

Engine Components:
Camshaft - ₱1,700
Valve - ₱1,500
Muffler (Chix Pipe) - ₱1,900

Transmission & Drive:
Pulley Set - ₱2,100
Flyball - ₱500
CVT Cleaner - ₱200

SERVICES OFFERED:

Engine Upgrade (Touring/Racing) – Labor: ₱1,000 - ₱5,000
Machine Works – Labor: ₱1,000 - ₱3,000
Change Oil – Labor: ₱250
```

2. **Save the PDF file** as `knowledge_base.pdf` in your project directory

3. **Set environment variables** (optional):
```bash
export PDF_PATH="path/to/your/knowledge_base.pdf"
export PORT=1551
```

## 🏃‍♂️ Running the Application

```bash
python main.py
```

The server will start on `http://0.0.0.0:1551`

## 📡 API Endpoints

### Chat Endpoint
```http
POST /api/chat
Content-Type: application/json

{
  "message": "What products do you have?"
}
```

### Health Check
```http
GET /health
```

Returns system status including PDF loading status:
```json
{
  "status": "healthy",
  "ollama": "connected",
  "pdf_knowledge": "loaded",
  "products_count": 8,
  "services_count": 5,
  "pdf_path": "knowledge_base.pdf"
}
```

### Reload Knowledge Base
```http
POST /api/reload
```

Reloads the PDF knowledge base without restarting:
```json
{
  "status": "success",
  "message": "Knowledge base reloaded. Found 8 products and 5 services.",
  "products_count": 8,
  "services_count": 5
}
```

## 🧠 PDF Format Guidelines

The system can parse various formats:

**Products:**
- `Product Name - ₱1,700`
- `Product Name: ₱1,700`
- `Product Name ₱1,700`

**Services:**
- `Service Name - Labor: ₱1,000 - ₱5,000`
- `Service Name: ₱300`
- `Service Name - ₱1,000 - ₱3,000`

## 🔄 Features

### Automatic PDF Processing
- Extracts text using multiple PDF libraries for compatibility
- Parses products and services using regex patterns
- Handles various price formats and currencies
- Distinguishes between products and services automatically

### Intelligent Responses
- Direct price lookups for specific items
- Service listings and descriptions
- Greeting responses and identity questions
- Fallback responses when information is unavailable

### Error Handling
- Graceful degradation when PDF is missing
- Fallback to basic responses if PDF parsing fails
- Detailed logging for troubleshooting

## 🔧 Configuration

Environment variables:
- `PDF_PATH`: Path to your knowledge base PDF (default: "knowledge_base.pdf")
- `PORT`: Server port (default: 1551)
- `OLLAMA_API_URL`: Ollama API endpoint (default: "http://localhost:11434/api/generate")

## 📝 Logging

The application provides detailed logging:
- PDF loading status
- Product/service discovery
- API request processing
- Error tracking

## 🤖 Bot Capabilities

PomBot can answer questions about:
- Product prices and availability
- Service costs and descriptions
- Complete product/service listings
- General workshop information

**Example queries:**
- "How much is a camshaft?"
- "What services do you offer?"
- "List all products"
- "What is the cost of engine upgrade?"

## 🚫 Content Filtering

The bot includes badword filtering and will only respond to auto parts related questions, maintaining professional interaction standards.

---

Created by Cleo Dipasupil for PomWorkz Workshop 