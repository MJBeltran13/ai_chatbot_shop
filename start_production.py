#!/usr/bin/env python3
"""
Production startup script for PomWorkz AI Chatbot
Uses Waitress WSGI server for production deployment
"""

import os
import sys
from waitress import serve
from main import app, load_knowledge_from_pdf, PDF_PATH

def main():
    """Main function to start the production server"""
    
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    
    # Load knowledge base
    print("Loading knowledge base from PDF...")
    success = load_knowledge_from_pdf(PDF_PATH)
    if success:
        print("✅ Knowledge base loaded successfully")
    else:
        print("❌ Failed to load knowledge base")
        sys.exit(1)
    
    # Get configuration
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 1551))
    threads = int(os.environ.get('THREADS', 4))
    
    print(f"🚀 Starting PomWorkz AI Chatbot on {host}:{port}")
    print(f"📄 PDF Path: {PDF_PATH}")
    print(f"🧵 Threads: {threads}")
    print("="*50)
    
    # Start production server with Waitress
    serve(
        app,
        host=host,
        port=port,
        threads=threads,
        connection_limit=1000,
        cleanup_interval=30,
        channel_timeout=120,
        expose_tracebacks=False
    )

if __name__ == '__main__':
    main() 