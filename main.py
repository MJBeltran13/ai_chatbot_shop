import re
import os
import requests
from flask import Flask, request, jsonify
from functools import lru_cache
from waitress import serve
import json
import time
from werkzeug.serving import run_simple
from flask_cors import CORS
import PyPDF2
import pdfplumber
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for API routes

# Configuration
OLLAMA_API_URL = "http://localhost:11434/api/generate"
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = int(os.environ.get("PORT", 1551))
PDF_PATH = os.environ.get("PDF_PATH", "POMWORKZ AUTO PARTS CATALOG.pdf")  # Updated to use your PDF name

# Global variables to store PDF-extracted data
KNOWLEDGE_BASE = ""
PRODUCTS = {}
SERVICES = {}

BADWORDS = [
    "arse", "arsehead", "arsehole", "ass", "ass hole", "asshole", "bastard", "bitch", 
    "bloody", "bollocks", "brotherfucker", "bugger", "bullshit", "child-fucker",
    "Christ on a bike", "Christ on a cracker", "cock", "cocksucker", "crap", "cunt",
    "dammit", "damn", "damned", "damn it", "dick", "dick-head", "dickhead", 
    "dumb ass", "dumb-ass", "dumbass", "dyke", "faggot", "father-fucker", "fatherfucker",
    "fuck", "fucker", "fucking", "god dammit", "goddammit", "God damn", "god damn",
    "goddamn", "Goddamn", "goddamned", "goddamnit", "godsdamn", "hell", "holy shit",
    "horseshit", "in shit", "jackarse", "jack-ass", "jackass", "Jesus Christ", 
    "Jesus fuck", "Jesus Harold Christ", "Jesus H. Christ", "Jesus, Mary and Joseph",
    "Jesus wept", "kike", "mother fucker", "mother-fucker", "motherfucker", "nigga",
    "nigra", "pigfucker", "piss", "prick", "pussy", "shit", "shit ass", "shite",
    "sibling fucker", "sisterfuck", "sisterfucker", "slut", "son of a bitch",
    "son of a whore", "spastic", "sweet Jesus", "twat", "wanker",
]


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using multiple methods for better compatibility"""
    text = ""
    
    try:
        # Try pdfplumber first (better for complex layouts)
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if text.strip():
            logger.info(f"Successfully extracted text using pdfplumber: {len(text)} characters")
            return text
            
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}, trying PyPDF2...")
    
    try:
        # Fallback to PyPDF2
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if text.strip():
            logger.info(f"Successfully extracted text using PyPDF2: {len(text)} characters")
            return text
            
    except Exception as e:
        logger.error(f"PyPDF2 also failed: {e}")
    
    return text


def parse_products_from_text(text):
    """Parse products and prices from PDF text"""
    products = {}
    
    # Print extracted text for debugging
    print(f"DEBUG: First 500 characters of extracted text:")
    print(f"'{text[:500]}'")
    
    # Look for price patterns (₱, PHP, or "n" followed by numbers - PDF encoding issue)
    price_patterns = [
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*₱\s*(\d+(?:,\d+)*)',      # Product - ₱1,700
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*PHP\s*(\d+(?:,\d+)*)',    # Product - PHP 1,700
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*n(\d+(?:,\d+)*)',        # Product - n1,700 (encoding issue)
        r'([A-Za-z\s\(\)]+?)\s*:\s*₱\s*(\d+(?:,\d+)*)',          # Product: ₱1,700
        r'([A-Za-z\s\(\)]+?)\s*:\s*PHP\s*(\d+(?:,\d+)*)',        # Product: PHP 1,700
        r'([A-Za-z\s\(\)]+?)\s*:\s*n(\d+(?:,\d+)*)',            # Product: n1,700 (encoding issue)
        r'([A-Za-z\s\(\)]+?)\s*₱\s*(\d+(?:,\d+)*)',             # Product ₱1,700
        r'([A-Za-z\s\(\)]+?)\s*PHP\s*(\d+(?:,\d+)*)',           # Product PHP 1,700
        r'([A-Za-z\s\(\)]+?)\s*n(\d+(?:,\d+)*)',               # Product n1,700 (encoding issue)
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for product_name, price_str in matches:
            product_name = product_name.strip().lower()
            price_str = price_str.replace(',', '')
            
            # Skip if it's likely a service (contains service keywords)
            service_indicators = ['labor', 'service', 'upgrade', 'works', 'cleaning', 'refresh', 'change', 'rebuild', 'overhaul', 'repair', 'adjustment', 'replacement']
            if any(indicator in product_name for indicator in service_indicators):
                continue
                
            # Skip if price contains range indicators
            if '-' in price_str or 'to' in price_str.lower():
                continue
                
            try:
                price = int(price_str)
                products[product_name] = price
                logger.info(f"Found product: {product_name} = ₱{price}")
            except ValueError:
                continue
    
    return products


def parse_services_from_text(text):
    """Parse services and prices from PDF text"""
    services = {}
    
    # Look for service patterns (often contain ranges, Labor, or service keywords)
    service_patterns = [
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*Labor:\s*₱\s*([\d,\s\-–—]+)',     # Service - Labor: ₱1,000 - ₱5,000
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*Labor:\s*PHP\s*([\d,\s\-–—]+)',   # Service - Labor: PHP 1,000 - 5,000
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*Labor:\s*n([\d,\s\-–—]+)',       # Service - Labor: n1,000 - n5,000 (encoding issue)
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*₱\s*([\d,\s\-–—]+)',             # Service - ₱1,000 - ₱5,000
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*PHP\s*([\d,\s\-–—]+)',           # Service - PHP 1,000 - 5,000
        r'([A-Za-z\s\(\)]+?)\s*[-–—]\s*n([\d,\s\-–—]+)',               # Service - n1,000 - n5,000 (encoding issue)
        r'([A-Za-z\s\(\)]+?)\s*:\s*₱\s*([\d,\s\-–—]+)',                 # Service: ₱1,000 - ₱5,000
        r'([A-Za-z\s\(\)]+?)\s*:\s*PHP\s*([\d,\s\-–—]+)',               # Service: PHP 1,000 - 5,000
        r'([A-Za-z\s\(\)]+?)\s*:\s*n([\d,\s\-–—]+)',                   # Service: n1,000 - n5,000 (encoding issue)
    ]
    
    for pattern in service_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for service_name, price_str in matches:
            service_name = service_name.strip().lower()
            price_str = price_str.strip()
            
            # Check if it's likely a service based on keywords or price range
            service_indicators = ['upgrade', 'works', 'cleaning', 'refresh', 'change', 'rebuild', 'overhaul', 'repair', 'adjustment', 'replacement', 'service', 'maintenance']
            has_service_keyword = any(indicator in service_name for indicator in service_indicators)
            has_price_range = '-' in price_str or 'to' in price_str.lower()
            contains_labor = 'labor' in price_str.lower()
            
            if has_service_keyword or has_price_range or contains_labor:
                # Clean up the price string
                price_str = price_str.replace('n', '₱')  # Fix encoding issue
                if price_str.startswith('PHP'):
                    price_str = price_str.replace('PHP', '₱')
                elif not price_str.startswith('₱'):
                    price_str = f"₱{price_str}"
                    
                services[service_name] = price_str
                logger.info(f"Found service: {service_name} = {price_str}")
    
    # Additional pass: Look for lines that clearly indicate services (but filter out non-service content)
    lines = text.split('\n')
    current_section = ""
    
    for line in lines:
        line = line.strip()
        
        # Track sections
        if "services" in line.lower() or "maintenance" in line.lower():
            current_section = "services"
            continue
        elif line.startswith('=') or any(x in line.lower() for x in ['product', 'component', 'part', 'catalog', 'workshop information', 'technical', 'faq', 'notes']):
            current_section = ""
            continue
            
        # If we're in a service section, try to parse everything as services
        if current_section == "services" and ('-' in line or ':' in line):
            # Skip obvious non-service lines
            if any(skip in line.lower() for skip in ['location', 'phone', 'email', 'hours', 'warranty', 'engines', 'cylinder', 'cooled', 'systems', 'often', 'change my']):
                continue
                
            # Try to extract service info from line
            for pattern in [r'([^-:]+)[-:]\s*(.+)', r'([^₱PHPn]+)[₱PHPn]\s*([\d,\s\-–—]+)']:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    name = match.group(1).strip().lower()
                    price = match.group(2).strip()
                    
                    # Filter out non-service names
                    if any(skip in name for skip in ['location', 'phone', 'email', 'hours', 'warranty', 'stroke', 'cylinder', 'cooled', 'q', 'a']):
                        continue
                    
                    if name and price and name not in services and len(name) > 3:
                        price = price.replace('n', '₱')  # Fix encoding issue
                        if not price.startswith('₱') and not price.startswith('PHP'):
                            price = f"₱{price}"
                        price = price.replace('PHP', '₱')
                        services[name] = price
                        logger.info(f"Found service (section): {name} = {price}")
                    break
    
    return services


def load_knowledge_from_pdf(pdf_path):
    """Load and parse knowledge base from PDF"""
    global KNOWLEDGE_BASE, PRODUCTS, SERVICES
    
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        # Create a default PDF message
        KNOWLEDGE_BASE = f"""
PDF file not found at: {pdf_path}

Please create a PDF file with your product catalog and service information.
The PDF should include:
- Product names and prices (e.g., "Camshaft - ₱1700")
- Service names and prices (e.g., "Engine Upgrade - Labor: ₱1,000 - ₱5,000")

Using fallback mode with basic responses only.
"""
        return False
    
    try:
        # Extract text from PDF
        pdf_text = extract_text_from_pdf(pdf_path)
        
        if not pdf_text.strip():
            logger.error("No text could be extracted from PDF")
            return False
        
        # Parse products and services
        PRODUCTS = parse_products_from_text(pdf_text)
        SERVICES = parse_services_from_text(pdf_text)
        
        # Extract warranty information specifically
        warranty_info = extract_warranty_info(pdf_text)
        
        # Extract FAQ information
        faq_info = extract_faq_info(pdf_text)
        
        # Extract contact and workshop information
        workshop_info = extract_workshop_info(pdf_text)
        
        # Create comprehensive knowledge base from extracted content
        KNOWLEDGE_BASE = f"""
You are PomBot, the auto parts specialist at PomWorkz workshop.
You ONLY answer questions about the products and services listed below.
You are created by Cleo Dipasupil.
You can respond in English or Tagalog.

❌ DO NOT answer any question that is NOT related to the products below.  
✅ If asked anything else, reply: "I only answer questions about auto parts at PomWorkz."  

COMPLETE WORKSHOP INFORMATION:
{pdf_text}

EXTRACTED PRODUCTS:
{chr(10).join([f"- {product.title()}: ₱{price:,}" for product, price in PRODUCTS.items()])}

EXTRACTED SERVICES:
{chr(10).join([f"- {service.title()}: {price}" for service, price in SERVICES.items()])}

WARRANTY INFORMATION:
{warranty_info}

FREQUENTLY ASKED QUESTIONS:
{faq_info}

WORKSHOP DETAILS:
{workshop_info}

🚨 STRICT RESPONSE RULES:
- ❌ **DO NOT answer unrelated questions.**
- ✅ **Always include exact product prices and availability.**
- ✅ **Include warranty information when relevant.**
- ✅ **For unrelated questions, reply: "I only answer questions about auto parts at PomWorkz."**
"""

        logger.info(f"Successfully loaded knowledge base from PDF. Found {len(PRODUCTS)} products and {len(SERVICES)} services.")
        logger.info(f"Warranty info length: {len(warranty_info)} characters")
        logger.info(f"FAQ info length: {len(faq_info)} characters")
        return True
        
    except Exception as e:
        logger.error(f"Error loading PDF: {e}")
        return False


def extract_warranty_info(text):
    """Extract warranty-related information from PDF text"""
    warranty_lines = []
    lines = text.split('\n')
    
    # Look for warranty section
    in_warranty_section = False
    
    for line in lines:
        line = line.strip()
        
        # Check if this line starts a warranty section
        if line.lower() == 'warranty information:':
            in_warranty_section = True
            continue
            
        # Check if we're leaving warranty section (entering other sections)
        if in_warranty_section and (line.lower().startswith('payment methods') or 
                                   line.lower().startswith('technical specifications') or
                                   line.lower().startswith('supported vehicle') or
                                   line.lower().startswith('engine types') or
                                   line.lower().startswith('frequently asked') or
                                   line.lower().startswith('contact information') or
                                   line.startswith('=') or
                                   not line):
            break
            
        # Add lines while in warranty section
        if in_warranty_section and line.startswith('- '):
            # Only include lines that start with dash (warranty items)
            warranty_lines.append(line)
    
    # Remove duplicates while preserving order
    unique_lines = []
    seen = set()
    
    for line in warranty_lines:
        line_lower = line.lower().strip()
        if line_lower not in seen and line_lower:
            seen.add(line_lower)
            unique_lines.append(line.strip())
    
    # Clean up and format the warranty information
    if unique_lines:
        warranty_info = "WARRANTY POLICY:\n" + '\n'.join(unique_lines)
        return warranty_info
    else:
        return "No specific warranty information found in PDF."


def extract_faq_info(text):
    """Extract FAQ information from PDF text"""
    faq_lines = []
    lines = text.split('\n')
    
    # Look for FAQ section
    in_faq_section = False
    
    for line in lines:
        line = line.strip()
        
        # Check if this line starts FAQ section
        if any(keyword in line.lower() for keyword in ['frequently asked questions', 'faq:', 'common questions']):
            in_faq_section = True
            if 'frequently asked questions' not in line.lower():
                faq_lines.append(line)
            continue
            
        # Check if we're leaving FAQ section
        if in_faq_section and (line.startswith('=') or 
                              any(keyword in line.lower() for keyword in [
                                  'notes', 'contact', 'technical specifications',
                                  'warranty information', 'workshop information',
                                  'payment methods'
                              ])):
            break
            
        # Add lines while in FAQ section
        if in_faq_section and line:
            # Skip lines that are clearly not FAQ related
            if any(skip in line.lower() for skip in ['warranty:', 'payment:', 'location:', 'phone:', 'email:']):
                continue
            faq_lines.append(line)
    
    # Remove duplicates while preserving order
    unique_lines = []
    seen = set()
    
    for line in faq_lines:
        line_lower = line.lower().strip()
        if line_lower not in seen and line_lower:
            seen.add(line_lower)
            unique_lines.append(line.strip())
    
    if unique_lines:
        faq_info = "FREQUENTLY ASKED QUESTIONS:\n" + '\n'.join(unique_lines)
        return faq_info
    else:
        return "No FAQ information found in PDF."


def extract_workshop_info(text):
    """Extract workshop/contact information from PDF text"""
    workshop_info = ""
    lines = text.split('\n')
    
    # Look for workshop information section
    in_workshop_section = False
    workshop_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Check if this line starts workshop section
        if any(keyword in line.lower() for keyword in ['workshop information', 'about pomworkz', 'contact', 'location', 'hours']):
            in_workshop_section = True
            workshop_lines.append(line)
            continue
            
        # Check if we're leaving workshop section
        if in_workshop_section and (line.startswith('=') or 
                                   any(keyword in line.lower() for keyword in ['technical', 'faq', 'notes'])):
            break
            
        # Add lines while in workshop section
        if in_workshop_section and line:
            workshop_lines.append(line)
    
    # Also look for specific contact patterns
    contact_patterns = [
        r'phone[:\s]+([^.]+)',
        r'email[:\s]+([^.]+)',
        r'location[:\s]+([^.]+)',
        r'hours[:\s]+([^.]+)',
        r'address[:\s]+([^.]+)'
    ]
    
    for pattern in contact_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            workshop_lines.append(f"Contact: {match}")
    
    workshop_info = '\n'.join(workshop_lines)
    return workshop_info if workshop_info.strip() else "Workshop information not found in PDF."


def reload_pdf_data():
    """Reload PDF data - useful for updates without restart"""
    return load_knowledge_from_pdf(PDF_PATH)


def contains_badwords(text):
    # Convert text to lowercase and split into words
    words = text.lower().split()
    # Check if any complete word matches a bad word
    return any(word in words for word in BADWORDS)


def get_ollama_response(query, context="", max_retries=3):
    """Get response from Ollama with retry logic - PDF-driven only"""
    cleaned_query = query.strip().lower()
    
    # Check if we have PDF data loaded
    if not KNOWLEDGE_BASE or (not PRODUCTS and not SERVICES):
        return "PDF knowledge base is not loaded. Please ensure your PDF file is available and reload the system."
    
    # Detect if query is in Tagalog
    tagalog_indicators = ['ano', 'gaano', 'ilang', 'paano', 'saan', 'kailan', 'bakit', 'kung', 'mga', 'ng', 'sa', 'para', 'naman', 'lang', 'po', 'magkano', 'meron', 'walang', 'kumusta', 'kamusta']
    is_tagalog = any(indicator in cleaned_query for indicator in tagalog_indicators)
    
    # Expanded service-related keywords
    service_keywords = [
        "what are the service", "what are the servic",  # Handles typos like "servies"
        "what service", "list service",
        "available service", "show service",
        "tell me the service", "what are your service",
        "services offer", "service list",
        # Tagalog keywords
        "ano ang service", "ano ang mga service", "anong service",
        "mga service", "lista ng service", "available na service"
    ]
    
    # Check for service queries with more flexible matching
    if any(keyword in cleaned_query for keyword in service_keywords):
        if SERVICES:
            service_list = []
            for i, (service, price) in enumerate(SERVICES.items(), 1):
                service_list.append(f"{i}. {service.title()} – {price}")
            
            if is_tagalog:
                return "Narito ang lahat ng services na inooffer namin sa PomWorkz:\n" + "\n".join(service_list)
            else:
                return "Here are all services offered at PomWorkz:\n" + "\n".join(service_list)
        else:
            if is_tagalog:
                return "Walang services na nakita sa PDF knowledge base. Pakicheck ang PDF content."
            else:
                return "No services found in PDF knowledge base. Please check your PDF content."
    
    # Handle price queries directly from PDF data
    price_keywords_en = ["how much", "price", "cost", "magkano"]
    price_keywords_tl = ["magkano", "presyo", "halaga", "bayad"]
    
    if (any(keyword in cleaned_query for keyword in price_keywords_en) or 
        any(keyword in cleaned_query for keyword in price_keywords_tl)):
        # Check services first
        for service, price in SERVICES.items():
            if service in cleaned_query:
                if is_tagalog:
                    return f"Ang bayad para sa {service} ay {price}."
                else:
                    return f"The cost for {service} is {price}."
                
        # Check products
        for product, price in PRODUCTS.items():
            if product in cleaned_query:
                if is_tagalog:
                    return f"Ang presyo ng {product} ay ₱{price:,}."
                else:
                    return f"The price of {product} is ₱{price:,}."
        
        # If no specific item found, suggest available options
        if is_tagalog:
            return "Hindi ko nahanap yung specific na item. Maaari mong itanong ang mga available products o services, o maging mas specific sa item name."
        else:
            return "I couldn't find that specific item. You can ask about our available products or services, or try being more specific with the item name."
    
    # Detect if query is in Tagalog
    tagalog_indicators = ['ano', 'gaano', 'ilang', 'paano', 'saan', 'kailan', 'bakit', 'kung', 'mga', 'ng', 'sa', 'para', 'naman', 'lang', 'po']
    is_tagalog = any(indicator in cleaned_query for indicator in tagalog_indicators)
    
    # Check for product availability questions in Tagalog
    availability_keywords_tl = ['may', 'meron', 'available', 'ba kayo', 'po ba']
    is_availability_query = any(keyword in cleaned_query for keyword in availability_keywords_tl)
    
    if is_availability_query and is_tagalog:
        # Extract product name from query (remove question words)
        query_words = cleaned_query.split()
        product_keywords = []
        skip_words = ['may', 'meron', 'po', 'ba', 'kayo', 'available', 'ang', 'ng', 'na']
        
        for word in query_words:
            if word not in skip_words and len(word) > 2:
                product_keywords.append(word)
        
        if product_keywords:
            # Check if any products match the keywords
            found_products = []
            for product, price in PRODUCTS.items():
                for keyword in product_keywords:
                    if keyword in product.lower() or product.lower() in keyword:
                        found_products.append((product, price))
                        break
            
            if found_products:
                # Found matching products
                product_list = []
                for product, price in found_products:
                    product_list.append(f"- {product.title()}: ₱{price:,}")
                return f"Yes po, meron kaming mga sumusunod na {' '.join(product_keywords)}:\n" + "\n".join(product_list)
            else:
                # Check if it's available as a service
                found_services = []
                for service, price in SERVICES.items():
                    for keyword in product_keywords:
                        if keyword in service.lower() or service.lower() in keyword:
                            found_services.append((service, price))
                            break
                
                if found_services:
                    service_list = []
                    for service, price in found_services:
                        service_list.append(f"- {service.title()}: {price}")
                    return f"Hindi namin directly binebenta ang {' '.join(product_keywords)}, pero meron kaming service para dito:\n" + "\n".join(service_list)
                else:
                    return f"Hindi po namin available ang {' '.join(product_keywords)} sa aming inventory. Maaari ninyo pong tingnan ang aming complete product list o magtanong tungkol sa ibang parts na kailangan ninyo."

    # Check for warranty-related questions in English and Tagalog
    warranty_keywords_en = ['warranty', 'guarantee', 'coverage', 'how long', 'return policy']
    warranty_keywords_tl = ['warranty', 'garantiya', 'takot', 'gaano katagal', 'ilang araw', 'ilang buwan', 'ilang taon', 'policy', 'patakaran']
    
    is_warranty_query = (any(keyword in cleaned_query for keyword in warranty_keywords_en) or 
                       any(keyword in cleaned_query for keyword in warranty_keywords_tl))
    
    if is_warranty_query:
        # Extract warranty info from knowledge base
        warranty_section = ""
        lines = KNOWLEDGE_BASE.split('\n')
        in_warranty = False
        
        for line in lines:
            if "WARRANTY INFORMATION:" in line:
                in_warranty = True
                continue
            elif in_warranty and "FREQUENTLY ASKED QUESTIONS:" in line:
                break
            elif in_warranty:
                warranty_section += line + "\n"
        
        if warranty_section.strip():
            if is_tagalog:
                # Tagalog response
                return f"""Narito ang aming warranty information:

WARRANTY POLICY:
- Lahat ng parts ay may manufacturer warranty
- Labor warranty: 30 araw para sa general services, 90 araw para sa major overhauls  
- Engine rebuilds: 6 na buwan warranty

Para sa mga tanong tungkol sa warranty, maaari kayong magtanong sa Tagalog o English."""
            else:
                # English response  
                return f"Here's our warranty information:\n\n{warranty_section.strip()}"
        else:
            # Fallback to Ollama for warranty questions
            response = get_ollama_response(cleaned_query, KNOWLEDGE_BASE)
            if response:
                return response
            return "I have warranty information in our knowledge base, but let me get that for you from our complete catalog."

    # Move service check before greetings to prevent greeting responses for service queries
    service_keywords_en = [
        "what are the service", "what are the servic",
        "what service", "list service",
        "available service", "show service",
        "tell me the service", "what are your service",
        "services offer", "service list"
    ]
    
    service_keywords_tl = [
        "ano ang service", "ano ang mga service", "anong service",
        "mga service", "lista ng service", "available na service",
        "pwedeng service", "ano ang pwedeng service"
    ]
    
    is_service_query = (any(keyword in cleaned_query for keyword in service_keywords_en) or
                      any(keyword in cleaned_query for keyword in service_keywords_tl))
    
    if is_service_query:
        if SERVICES:
            service_list = []
            for i, (service, price) in enumerate(SERVICES.items(), 1):
                service_list.append(f"{i}. {service.title()} – {price}")
            
            if is_tagalog:
                return "Narito ang lahat ng services na inooffer namin sa PomWorkz:\n" + "\n".join(service_list)
            else:
                return "Here are all services offered at PomWorkz:\n" + "\n".join(service_list)
        else:
            if is_tagalog:
                return "Walang services na nakita sa PDF knowledge base."
            else:
                return "No services found in PDF knowledge base."

    # Check for greetings in English and Tagalog
    greetings_en = ["hello", "hi"]
    greetings_tl = ["kumusta", "magandang", "kamusta", "hoy", "oy"]
    
    is_greeting = (any(greeting in cleaned_query for greeting in greetings_en) or
                  any(greeting in cleaned_query for greeting in greetings_tl))
    
    # For greetings, check specifically if it's Tagalog
    is_tagalog_greeting = any(greeting in cleaned_query for greeting in greetings_tl)
    
    if is_greeting:
        available_items = len(PRODUCTS) + len(SERVICES)
        if is_tagalog_greeting or is_tagalog:
            return f"Kumusta! Ako si PomBot, ang auto parts specialist ninyo sa PomWorkz. May {len(PRODUCTS)} products at {len(SERVICES)} services akong alam mula sa aming catalog. Paano kita matutulungan ngayon?"
        else:
            return f"Hello! I'm PomBot, your auto parts specialist at PomWorkz. I have information about {len(PRODUCTS)} products and {len(SERVICES)} services from our catalog. How can I help you today?"

    # Check for creator/identity questions in English and Tagalog
    creator_keywords_en = ["who created you", "who made you", "who is your creator"]
    creator_keywords_tl = ["sino gumawa", "sino naggawa", "sino creator", "sino ang gumawa"]
    
    is_creator_query = (any(q in cleaned_query for q in creator_keywords_en) or
                      any(q in cleaned_query for q in creator_keywords_tl))
    
    if is_creator_query:
        if is_tagalog:
            return "Ginawa ako ni Cleo Dipasupil."
        else:
            return "I am created by Cleo Dipasupil."

    # Check for FAQ questions in English and Tagalog
    faq_keywords_en = ['faq', 'frequently asked', 'common questions']
    faq_keywords_tl = ['mga tanong', 'common na tanong', 'madalas na tanong']
    
    is_faq_query = (any(keyword in cleaned_query for keyword in faq_keywords_en) or
                   any(keyword in cleaned_query for keyword in faq_keywords_tl))
    
    if is_faq_query:
        # Extract FAQ info from knowledge base
        faq_section = ""
        lines = KNOWLEDGE_BASE.split('\n')
        in_faq = False
        
        for line in lines:
            if "FREQUENTLY ASKED QUESTIONS:" in line:
                in_faq = True
                continue
            elif in_faq and "WORKSHOP DETAILS:" in line:
                break
            elif in_faq:
                faq_section += line + "\n"
        
        if faq_section.strip():
            if is_tagalog:
                return f"Narito ang mga madalas na tanong:\n\n{faq_section.strip()}"
            else:
                return f"Here are frequently asked questions:\n\n{faq_section.strip()}"

    # Check for service/product lists from PDF data only
    product_keywords_en = ["what products", "available products", "list products"]
    product_keywords_tl = ["ano ang products", "mga products", "anong products", "lista ng products", 
                          "ano po mga parts", "mga parts nyo", "ano ang parts", "anong parts", 
                          "available na parts", "mga available na parts"]
    
    is_product_query = (any(keyword in cleaned_query for keyword in product_keywords_en) or
                      any(keyword in cleaned_query for keyword in product_keywords_tl))
    
    if any(keyword in cleaned_query for keyword in ["what services", "available services", "list services"]):
        if SERVICES:
            service_list = []
            for i, (service, price) in enumerate(SERVICES.items(), 1):
                service_list.append(f"{i}. {service.title()} – {price}")
            
            if is_tagalog:
                return "Available na Services sa PomWorkz:\n" + "\n".join(service_list)
            else:
                return "Available Services at PomWorkz:\n" + "\n".join(service_list)
        else:
            if is_tagalog:
                return "Walang services na nakita sa PDF knowledge base."
            else:
                return "No services found in PDF knowledge base."
    
    if is_product_query:
        if PRODUCTS:
            product_list = []
            for product, price in PRODUCTS.items():
                product_list.append(f"- {product.title()}: ₱{price:,}")
            
            if is_tagalog:
                return "Available na Products sa PomWorkz:\n" + "\n".join(product_list)
            else:
                return "Available Products at PomWorkz:\n" + "\n".join(product_list)
        else:
            if is_tagalog:
                return "Walang products na nakita sa PDF knowledge base."
            else:
                return "No products found in PDF knowledge base."

    # Get response from Ollama using PDF data
    response = get_ollama_response(cleaned_query, KNOWLEDGE_BASE)
    
    # If we got a valid response, return it
    if response and response.strip():
        return response
        
    # Fallback responses based on PDF data
    if PRODUCTS or SERVICES:
        if is_tagalog:
            return f"""Paano kita matutulungan? Base sa aming PDF catalog, maaari mong itanong:
• Tungkol sa presyo ng specific products mula sa {len(PRODUCTS)} available products namin
• Tungkol sa cost ng services mula sa {len(SERVICES)} available services namin
• Para sa complete product o service listings
• Tungkol sa warranty information at policies
• General information tungkol sa PomWorkz workshop"""
        else:
            return f"""How can I help you? Based on our PDF catalog, you can ask:
• About specific product prices from our {len(PRODUCTS)} available products
• About service costs from our {len(SERVICES)} available services  
• For complete product or service listings
• About warranty information and policies
• General information about PomWorkz workshop"""
    else:
        if is_tagalog:
            return "PDF knowledge base ay mukhang walang laman. Pakicheck ang PDF file content."
        else:
            return "PDF knowledge base appears to be empty. Please check your PDF file content."
            
    return None


@lru_cache(maxsize=100)
def get_ai_response(query):
    """Get AI response with fallback - completely PDF-driven"""
    try:
        # Clean and format the input
        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return "Please provide a message."

        # Check if PDF data is loaded
        if not KNOWLEDGE_BASE or (not PRODUCTS and not SERVICES):
            return "PDF knowledge base is not loaded. Please ensure 'POMWORKZ AUTO PARTS CATALOG.pdf' is in the project directory and restart the application."

        # Check for warranty-related questions in English and Tagalog
        warranty_keywords_en = ['warranty', 'guarantee', 'coverage', 'how long', 'return policy']
        warranty_keywords_tl = ['warranty', 'garantiya', 'takot', 'gaano katagal', 'ilang araw', 'ilang buwan', 'ilang taon', 'policy', 'patakaran']
        
        is_warranty_query = (any(keyword in cleaned_query for keyword in warranty_keywords_en) or 
                           any(keyword in cleaned_query for keyword in warranty_keywords_tl))
        
        # Detect if query is in Tagalog
        tagalog_indicators = ['ano', 'gaano', 'ilang', 'paano', 'saan', 'kailan', 'bakit', 'kung', 'mga', 'ng', 'sa', 'para', 'naman', 'lang', 'po', 'magkano', 'meron', 'walang', 'kumusta', 'kamusta']
        is_tagalog = any(indicator in cleaned_query for indicator in tagalog_indicators)
        
        # Check for product availability questions in Tagalog
        availability_keywords_tl = ['may', 'meron', 'available', 'ba kayo', 'po ba']
        is_availability_query = any(keyword in cleaned_query for keyword in availability_keywords_tl)
        
        if is_availability_query and is_tagalog:
            # Extract product name from query (remove question words)
            query_words = cleaned_query.split()
            product_keywords = []
            skip_words = ['may', 'meron', 'po', 'ba', 'kayo', 'available', 'ang', 'ng', 'na']
            
            for word in query_words:
                if word not in skip_words and len(word) > 2:
                    product_keywords.append(word)
            
            if product_keywords:
                # Check if any products match the keywords
                found_products = []
                for product, price in PRODUCTS.items():
                    for keyword in product_keywords:
                        if keyword in product.lower() or product.lower() in keyword:
                            found_products.append((product, price))
                            break
                
                if found_products:
                    # Found matching products
                    product_list = []
                    for product, price in found_products:
                        product_list.append(f"- {product.title()}: ₱{price:,}")
                    return f"Yes po, meron kaming mga sumusunod na {' '.join(product_keywords)}:\n" + "\n".join(product_list)
                else:
                    # Check if it's available as a service
                    found_services = []
                    for service, price in SERVICES.items():
                        for keyword in product_keywords:
                            if keyword in service.lower() or service.lower() in keyword:
                                found_services.append((service, price))
                                break
                    
                    if found_services:
                        service_list = []
                        for service, price in found_services:
                            service_list.append(f"- {service.title()}: {price}")
                        return f"Hindi namin directly binebenta ang {' '.join(product_keywords)}, pero meron kaming service para dito:\n" + "\n".join(service_list)
                    else:
                        return f"Hindi po namin available ang {' '.join(product_keywords)} sa aming inventory. Maaari ninyo pong tingnan ang aming complete product list o magtanong tungkol sa ibang parts na kailangan ninyo."

        if is_warranty_query:
            # Extract warranty info from knowledge base
            warranty_section = ""
            lines = KNOWLEDGE_BASE.split('\n')
            in_warranty = False
            
            for line in lines:
                if "WARRANTY INFORMATION:" in line:
                    in_warranty = True
                    continue
                elif in_warranty and "FREQUENTLY ASKED QUESTIONS:" in line:
                    break
                elif in_warranty:
                    warranty_section += line + "\n"
            
            if warranty_section.strip():
                if is_tagalog:
                    # Tagalog response
                    return f"""Narito ang aming warranty information:

WARRANTY POLICY:
- Lahat ng parts ay may manufacturer warranty
- Labor warranty: 30 araw para sa general services, 90 araw para sa major overhauls  
- Engine rebuilds: 6 na buwan warranty

Para sa mga tanong tungkol sa warranty, maaari kayong magtanong sa Tagalog o English."""
                else:
                    # English response  
                    return f"Here's our warranty information:\n\n{warranty_section.strip()}"
            else:
                # Fallback to Ollama for warranty questions
                response = get_ollama_response(cleaned_query, KNOWLEDGE_BASE)
                if response:
                    return response
                return "I have warranty information in our knowledge base, but let me get that for you from our complete catalog."

        # Move service check before greetings to prevent greeting responses for service queries
        service_keywords_en = [
            "what are the service", "what are the servic",
            "what service", "list service",
            "available service", "show service",
            "tell me the service", "what are your service",
            "services offer", "service list"
        ]
        
        service_keywords_tl = [
            "ano ang service", "ano ang mga service", "anong service",
            "mga service", "lista ng service", "available na service",
            "pwedeng service", "ano ang pwedeng service"
        ]
        
        is_service_query = (any(keyword in cleaned_query for keyword in service_keywords_en) or
                          any(keyword in cleaned_query for keyword in service_keywords_tl))
        
        if is_service_query:
            if SERVICES:
                service_list = []
                for i, (service, price) in enumerate(SERVICES.items(), 1):
                    service_list.append(f"{i}. {service.title()} – {price}")
                
                if is_tagalog:
                    return "Narito ang lahat ng services na inooffer namin sa PomWorkz:\n" + "\n".join(service_list)
                else:
                    return "Here are all services offered at PomWorkz:\n" + "\n".join(service_list)
            else:
                if is_tagalog:
                    return "Walang services na nakita sa PDF knowledge base."
                else:
                    return "No services found in PDF knowledge base."

        # Check for greetings in English and Tagalog
        greetings_en = ["hello", "hi"]
        greetings_tl = ["kumusta", "magandang", "kamusta", "hoy", "oy"]
        
        is_greeting = (any(greeting in cleaned_query for greeting in greetings_en) or
                      any(greeting in cleaned_query for greeting in greetings_tl))
        
        # For greetings, check specifically if it's Tagalog
        is_tagalog_greeting = any(greeting in cleaned_query for greeting in greetings_tl)
        
        if is_greeting:
            available_items = len(PRODUCTS) + len(SERVICES)
            if is_tagalog_greeting or is_tagalog:
                return f"Kumusta! Ako si PomBot, ang auto parts specialist ninyo sa PomWorkz. May {len(PRODUCTS)} products at {len(SERVICES)} services akong alam mula sa aming catalog. Paano kita matutulungan ngayon?"
            else:
                return f"Hello! I'm PomBot, your auto parts specialist at PomWorkz. I have information about {len(PRODUCTS)} products and {len(SERVICES)} services from our catalog. How can I help you today?"

        # Check for creator/identity questions in English and Tagalog
        creator_keywords_en = ["who created you", "who made you", "who is your creator"]
        creator_keywords_tl = ["sino gumawa", "sino naggawa", "sino creator", "sino ang gumawa"]
        
        is_creator_query = (any(q in cleaned_query for q in creator_keywords_en) or
                          any(q in cleaned_query for q in creator_keywords_tl))
        
        if is_creator_query:
            if is_tagalog:
                return "Ginawa ako ni Cleo Dipasupil."
            else:
                return "I am created by Cleo Dipasupil."

        # Check for FAQ questions in English and Tagalog
        faq_keywords_en = ['faq', 'frequently asked', 'common questions']
        faq_keywords_tl = ['mga tanong', 'common na tanong', 'madalas na tanong']
        
        is_faq_query = (any(keyword in cleaned_query for keyword in faq_keywords_en) or
                       any(keyword in cleaned_query for keyword in faq_keywords_tl))
        
        if is_faq_query:
            # Extract FAQ info from knowledge base
            faq_section = ""
            lines = KNOWLEDGE_BASE.split('\n')
            in_faq = False
            
            for line in lines:
                if "FREQUENTLY ASKED QUESTIONS:" in line:
                    in_faq = True
                    continue
                elif in_faq and "WORKSHOP DETAILS:" in line:
                    break
                elif in_faq:
                    faq_section += line + "\n"
            
            if faq_section.strip():
                if is_tagalog:
                    return f"Narito ang mga madalas na tanong:\n\n{faq_section.strip()}"
                else:
                    return f"Here are frequently asked questions:\n\n{faq_section.strip()}"

        # Check for service/product lists from PDF data only
        product_keywords_en = ["what products", "available products", "list products"]
        product_keywords_tl = ["ano ang products", "mga products", "anong products", "lista ng products", 
                              "ano po mga parts", "mga parts nyo", "ano ang parts", "anong parts", 
                              "available na parts", "mga available na parts"]
        
        is_product_query = (any(keyword in cleaned_query for keyword in product_keywords_en) or
                          any(keyword in cleaned_query for keyword in product_keywords_tl))
        
        if any(keyword in cleaned_query for keyword in ["what services", "available services", "list services"]):
            if SERVICES:
                service_list = []
                for i, (service, price) in enumerate(SERVICES.items(), 1):
                    service_list.append(f"{i}. {service.title()} – {price}")
                
                if is_tagalog:
                    return "Available na Services sa PomWorkz:\n" + "\n".join(service_list)
                else:
                    return "Available Services at PomWorkz:\n" + "\n".join(service_list)
            else:
                if is_tagalog:
                    return "Walang services na nakita sa PDF knowledge base."
                else:
                    return "No services found in PDF knowledge base."
        
        if is_product_query:
            if PRODUCTS:
                product_list = []
                for product, price in PRODUCTS.items():
                    product_list.append(f"- {product.title()}: ₱{price:,}")
                
                if is_tagalog:
                    return "Available na Products sa PomWorkz:\n" + "\n".join(product_list)
                else:
                    return "Available Products at PomWorkz:\n" + "\n".join(product_list)
            else:
                if is_tagalog:
                    return "Walang products na nakita sa PDF knowledge base."
                else:
                    return "No products found in PDF knowledge base."

        # Get response from Ollama using PDF data
        response = get_ollama_response(cleaned_query, KNOWLEDGE_BASE)
        
        # If we got a valid response, return it
        if response and response.strip():
            return response
            
        # Fallback responses based on PDF data
        if PRODUCTS or SERVICES:
            if is_tagalog:
                return f"""Paano kita matutulungan? Base sa aming PDF catalog, maaari mong itanong:
• Tungkol sa presyo ng specific products mula sa {len(PRODUCTS)} available products namin
• Tungkol sa cost ng services mula sa {len(SERVICES)} available services namin
• Para sa complete product o service listings
• Tungkol sa warranty information at policies
• General information tungkol sa PomWorkz workshop"""
            else:
                return f"""How can I help you? Based on our PDF catalog, you can ask:
• About specific product prices from our {len(PRODUCTS)} available products
• About service costs from our {len(SERVICES)} available services  
• For complete product or service listings
• About warranty information and policies
• General information about PomWorkz workshop"""
        else:
            if is_tagalog:
                return "PDF knowledge base ay mukhang walang laman. Pakicheck ang PDF file content."
            else:
                return "PDF knowledge base appears to be empty. Please check your PDF file content."
            
    except Exception as e:
        print(f"Error in get_ai_response: {str(e)}")
        return "I encountered an error. Please ensure the PDF knowledge base is properly loaded."


@app.after_request
def after_request(response):
    """Add headers to allow cross-origin requests"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Missing 'message' field"}), 400

        user_message = data["message"]
        print(f"\nProcessing message: {user_message}")
        
        response = get_ai_response(user_message)
        print(f"AI response: {response}")
        
        if not response:
            return jsonify({
                "response": "I apologize, but I couldn't generate a response. Please try again."
            }), 503
            
        return jsonify({"response": response})

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            "response": "An error occurred while processing your request."
        }), 500


@app.route("/api/reload", methods=["POST"])
def reload_knowledge():
    """Endpoint to reload PDF knowledge base"""
    try:
        success = reload_pdf_data()
        if success:
            return jsonify({
                "status": "success", 
                "message": f"Knowledge base reloaded. Found {len(PRODUCTS)} products and {len(SERVICES)} services.",
                "products_count": len(PRODUCTS),
                "services_count": len(SERVICES)
            }), 200
        else:
            return jsonify({
                "status": "error", 
                "message": "Failed to reload knowledge base from PDF"
            }), 500
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error reloading knowledge base: {str(e)}"
        }), 500


@app.route("/health", methods=["GET"])
def health():
    try:
        # Test Ollama connection
        response = get_ollama_response("test", max_retries=1)
        
        # Detailed PDF status
        pdf_exists = os.path.exists(PDF_PATH)
        pdf_status = "not found"
        if pdf_exists:
            if KNOWLEDGE_BASE and (PRODUCTS or SERVICES):
                pdf_status = "loaded and parsed"
            elif KNOWLEDGE_BASE:
                pdf_status = "loaded but no data extracted"
            else:
                pdf_status = "found but not loaded"
        
        health_info = {
            "status": "healthy" if response and pdf_status == "loaded and parsed" else "degraded",
            "ollama": "connected" if response else "not responding",
            "pdf_file": {
                "path": PDF_PATH,
                "exists": pdf_exists,
                "status": pdf_status
            },
            "knowledge_base": {
                "loaded": bool(KNOWLEDGE_BASE),
                "content_length": len(KNOWLEDGE_BASE) if KNOWLEDGE_BASE else 0,
                "products_count": len(PRODUCTS),
                "services_count": len(SERVICES)
            },
            "data_source": "PDF-only (no hardcoded data)"
        }
        
        status_code = 200 if health_info["status"] == "healthy" else 503
        return jsonify(health_info), status_code
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy", 
            "error": str(e),
            "data_source": "PDF-only (no hardcoded data)"
        }), 503


# WSGI Application
def create_app():
    return app


if __name__ == "__main__":
    print(f"Loading knowledge base from PDF: {PDF_PATH}")
    load_knowledge_from_pdf(PDF_PATH)
    print(f"Starting server on {HOST}:{PORT}")
    run_simple(HOST, PORT, app, use_reloader=True)
