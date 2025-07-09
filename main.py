import re
import os
import requests
import ollama  # Added for local LLM integration
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
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi:latest")  # Default to phi:latest if not specified
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
    
    # Improved regex patterns with stricter matching
    price_patterns = [
        r'([A-Za-z][A-Za-z\s\(\)\.]{2,40}?)\s*[-–—]\s*₱\s*(\d+(?:,\d+)*)',      # Product - ₱1,700
        r'([A-Za-z][A-Za-z\s\(\)\.]{2,40}?)\s*[-–—]\s*PHP\s*(\d+(?:,\d+)*)',    # Product - PHP 1,700
        r'([A-Za-z][A-Za-z\s\(\)\.]{2,40}?)\s*[-–—]\s*n(\d+(?:,\d+)*)',        # Product - n1,700 (encoding issue)
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for product_name, price_str in matches:
            # Clean and validate product name
            product_name = product_name.strip().lower()
            product_name = re.sub(r'\s+', ' ', product_name)  # Normalize whitespace
            price_str = price_str.replace(',', '').strip()
            
            # Validate product name
            if len(product_name) < 3 or len(product_name) > 50:
                continue
                
            # Skip if contains only spaces or invalid characters
            if not re.match(r'^[a-zA-Z][a-zA-Z\s\(\)\.]+$', product_name):
                continue
                
            # Skip if it's likely a service (contains service keywords)
            service_indicators = ['labor', 'service', 'upgrade', 'works', 'cleaning', 'refresh', 'change', 'rebuild', 'overhaul', 'repair', 'adjustment', 'replacement', 'tune', 'maintenance']
            if any(indicator in product_name for indicator in service_indicators):
                continue
                
            # Skip if price contains range indicators
            if '-' in price_str or 'to' in price_str.lower():
                continue
                
            # Skip common non-product words
            skip_words = ['hours', 'phone', 'email', 'location', 'warranty', 'technical', 'faq', 'contact', 'information', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            if any(skip_word in product_name for skip_word in skip_words):
                continue
                
            try:
                price = int(price_str)
                # Reasonable price range validation (₱50 to ₱50,000)
                if 50 <= price <= 50000:
                    # Avoid duplicates
                    if product_name not in products:
                        products[product_name] = price
                        logger.info(f"Found product: {product_name} = ₱{price}")
            except ValueError:
                continue
    
    return products


def parse_services_from_text(text):
    """Parse services and prices from PDF text"""
    services = {}
    
    # Improved service patterns with stricter matching
    service_patterns = [
        r'([A-Za-z][A-Za-z\s\(\)]{3,40}?)\s*[-–—]\s*Labor:\s*₱\s*([\d,\s\-–—]+)',     # Service - Labor: ₱1,000 - ₱5,000
        r'([A-Za-z][A-Za-z\s\(\)]{3,40}?)\s*[-–—]\s*₱\s*([\d,\s\-–—]+)',             # Service - ₱1,000 - ₱5,000
        r'([A-Za-z][A-Za-z\s\(\)]{3,40}?)\s*[-–—]\s*n([\d,\s\-–—]+)',               # Service - n1,000 - n5,000 (encoding issue)
    ]
    
    for pattern in service_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for service_name, price_str in matches:
            # Clean and validate service name
            service_name = service_name.strip().lower()
            service_name = re.sub(r'\s+', ' ', service_name)  # Normalize whitespace
            price_str = price_str.strip()
            
            # Validate service name length and content
            if len(service_name) < 4 or len(service_name) > 50:
                continue
                
            # Skip if contains only spaces or invalid characters
            if not re.match(r'^[a-zA-Z][a-zA-Z\s\(\)]+$', service_name):
                continue
            
            # Check if it's likely a service based on keywords or price range
            service_indicators = ['upgrade', 'works', 'cleaning', 'refresh', 'change', 'rebuild', 'overhaul', 'repair', 'adjustment', 'replacement', 'service', 'maintenance', 'tune', 'honing', 'grinding', 'cutting', 'resurfacing']
            has_service_keyword = any(indicator in service_name for indicator in service_indicators)
            has_price_range = '-' in price_str or 'to' in price_str.lower()
            contains_labor = 'labor' in price_str.lower()
            
            # Skip common non-service words
            skip_words = ['hours', 'phone', 'email', 'location', 'warranty', 'technical', 'faq', 'contact', 'information', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'engine components', 'electrical components']
            if any(skip_word in service_name for skip_word in skip_words):
                continue
            
            if has_service_keyword or has_price_range or contains_labor:
                # Clean up the price string
                price_str = price_str.replace('n', '₱')  # Fix encoding issue
                if price_str.startswith('PHP'):
                    price_str = price_str.replace('PHP', '₱')
                elif not price_str.startswith('₱'):
                    price_str = f"₱{price_str}"
                    
                # Avoid duplicates
                if service_name not in services:
                    services[service_name] = price_str
                    logger.info(f"Found service: {service_name} = {price_str}")
    
    return services


def load_knowledge_from_pdf(pdf_path):
    """Load and parse knowledge base from PDF and knowledge_base.txt"""
    global KNOWLEDGE_BASE, PRODUCTS, SERVICES
    
    # Load additional knowledge from text file
    additional_knowledge = ""
    txt_path = "knowledge_base.txt"
    if os.path.exists(txt_path):
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                additional_knowledge = f.read()
            logger.info(f"Successfully loaded additional knowledge from {txt_path}")
        except Exception as e:
            logger.warning(f"Could not load {txt_path}: {e}")
    
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        # If PDF not found but we have text file, use that
        if additional_knowledge:
            KNOWLEDGE_BASE = f"""
You are PomBot, the auto parts specialist at PomWorkz workshop.
You ONLY answer questions about the products and services listed below.
You are created by Cleo Dipasupil.
You can respond in English or Tagalog.

❌ DO NOT answer any question that is NOT related to the products below.  
✅ If asked anything else, reply: "I only answer questions about auto parts at PomWorkz."  

{additional_knowledge}

🚨 STRICT RESPONSE RULES:
- ❌ **DO NOT answer unrelated questions.**
- ✅ **Always include exact product prices and availability.**
- ✅ **Include warranty information when relevant.**
- ✅ **For unrelated questions, reply: "I only answer questions about auto parts at PomWorkz."**
"""
            return True
        else:
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
        
        # Create comprehensive knowledge base from extracted content + additional text file
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
{workshop_info}"""

        # Add additional knowledge from text file if available
        if additional_knowledge:
            KNOWLEDGE_BASE += f"""

ADDITIONAL INFORMATION:
{additional_knowledge}"""

        KNOWLEDGE_BASE += """

🚨 STRICT RESPONSE RULES:
- ❌ **DO NOT answer unrelated questions.**
- ✅ **Always include exact product prices and availability.**
- ✅ **Include warranty information when relevant.**
- ✅ **For unrelated questions, reply: "I only answer questions about auto parts at PomWorkz."**
"""

        logger.info(f"Successfully loaded knowledge base from PDF. Found {len(PRODUCTS)} products and {len(SERVICES)} services.")
        logger.info(f"Warranty info length: {len(warranty_info)} characters")
        logger.info(f"FAQ info length: {len(faq_info)} characters")
        if additional_knowledge:
            logger.info(f"Additional knowledge from text file: {len(additional_knowledge)} characters")
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
    
    # Look for contact information section
    in_contact_section = False
    contact_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Check if this line starts contact section
        if any(keyword in line.lower() for keyword in ['contact information:', 'contact info:', 'workshop information', 'about pomworkz']):
            in_contact_section = True
            if 'contact information:' not in line.lower():
                contact_lines.append(line)
            continue
            
        # Check if we're leaving contact section
        if in_contact_section and (line.startswith('=') or 
                                   any(keyword in line.lower() for keyword in ['technical', 'faq', 'notes', 'warranty', 'payment methods'])):
            break
            
        # Add lines while in contact section
        if in_contact_section and line:
            contact_lines.append(line)
    
    # Also search for specific contact patterns throughout the text
    contact_patterns = [
        r'- Location: (.+)',
        r'- Phone: (.+)',
        r'- Email: (.+)',
        r'- Hours: (.+)',
        r'Location: (.+)',
        r'Phone: (.+)',
        r'Email: (.+)',
        r'Hours: (.+)',
        r'Contact: (.+)'
    ]
    
    extracted_info = []
    for pattern in contact_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            extracted_info.append(match.strip())
    
    # Combine section-based and pattern-based extraction
    all_info = contact_lines + extracted_info
    
    # Remove duplicates while preserving order
    unique_info = []
    seen = set()
    for info in all_info:
        info_clean = info.lower().strip()
        if info_clean not in seen and info_clean:
            seen.add(info_clean)
            unique_info.append(info.strip())
    
    if unique_info:
        workshop_info = '\n'.join(unique_info)
        return f"WORKSHOP CONTACT INFORMATION:\n{workshop_info}"
    else:
        return "Workshop information not found in PDF."


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
    
    # Handle location/contact queries first
    location_keywords_en = ['where are you located', 'where is your shop', 'your location', 'your address', 'where can i find you', 'shop location', 'workshop location', 'location']
    location_keywords_tl = ['saan kayo', 'nasaan kayo', 'asan ang shop', 'location nyo', 'address nyo', 'saan po kayo', 'nasaan po kayo', 'saan kayo located', 'saan po kayo located', 'saan ang location', 'asan kayo', 'saan ang shop']
    
    is_location_query = (any(keyword in cleaned_query for keyword in location_keywords_en) or
                        any(keyword in cleaned_query for keyword in location_keywords_tl))
    
    if is_location_query:
        # Extract contact info from knowledge base
        contact_section = ""
        lines = KNOWLEDGE_BASE.split('\n')
        in_workshop = False
        
        for line in lines:
            if "WORKSHOP CONTACT INFORMATION:" in line:
                in_workshop = True
                continue
            elif in_workshop and any(x in line for x in ["EXTRACTED PRODUCTS:", "WARRANTY INFORMATION:", "FREQUENTLY ASKED"]):
                break
            elif in_workshop and line.strip():
                contact_section += line + "\n"
        
        if contact_section.strip():
            # Parse the extracted contact information
            contact_lines = contact_section.strip().split('\n')
            location = ""
            phone = ""
            email = ""
            hours = ""
            
            for line in contact_lines:
                line = line.strip()
                if line.startswith('- Location:') or line.startswith('Location:'):
                    location = line.replace('- Location:', '').replace('Location:', '').strip()
                elif line.startswith('- Phone:') or line.startswith('Phone:'):
                    phone = line.replace('- Phone:', '').replace('Phone:', '').strip()
                elif line.startswith('- Email:') or line.startswith('Email:'):
                    email = line.replace('- Email:', '').replace('Email:', '').strip()
                elif line.startswith('- Hours:') or line.startswith('Hours:'):
                    hours = line.replace('- Hours:', '').replace('Hours:', '').strip()
                elif 'purok' in line.lower() and 'batangas' in line.lower() and not location:
                    location = line
                elif '@' in line and '.com' in line and not email:
                    email = line
                elif ('monday' in line.lower() and 'saturday' in line.lower()) and not hours:
                    hours = line
                elif line.startswith('09') and len(line) >= 11 and not phone:
                    phone = line
            
            # Use extracted PDF contact information with proper formatting
            if is_tagalog:
                response = "📍 LOCATION NG POMWORKZ:\n"
                if location:
                    response += f"{location}\n\n"
                response += "📞 CONTACT INFO:\n"
                if phone:
                    response += f"Phone: {phone}\n"
                if email:
                    response += f"Email: {email}\n\n"
                if hours:
                    response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                response += "Pumunta na kayo sa amin para sa lahat ng motorcycle parts needs ninyo!"
                return response
            else:
                response = "📍 POMWORKZ LOCATION:\n"
                if location:
                    response += f"{location}\n\n"
                response += "📞 CONTACT INFORMATION:\n"
                if phone:
                    response += f"Phone: {phone}\n"
                if email:
                    response += f"Email: {email}\n\n"
                if hours:
                    response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                response += "Visit us for all your motorcycle parts needs!"
                return response
        
        # Only use fallback if extraction completely failed
        if is_tagalog:
            return "Hindi ko mahanap ang contact information sa PDF. Pakicheck ang PDF content."
        else:
            return "Contact information not found in PDF. Please check your PDF content."
    
    # Handle contact/hours queries - also use PDF extraction
    contact_keywords_en = ['contact', 'phone', 'email', 'hours', 'operating hours', 'open hours', 'business hours']
    contact_keywords_tl = ['contact', 'numero', 'email', 'oras', 'bukas', 'operating hours']
    
    is_contact_query = (any(keyword in cleaned_query for keyword in contact_keywords_en) or
                       any(keyword in cleaned_query for keyword in contact_keywords_tl))
    
    if is_contact_query:
        # Extract contact info from knowledge base (same logic as location)
        contact_section = ""
        lines = KNOWLEDGE_BASE.split('\n')
        in_workshop = False
        
        for line in lines:
            if "WORKSHOP CONTACT INFORMATION:" in line:
                in_workshop = True
                continue
            elif in_workshop and any(x in line for x in ["EXTRACTED PRODUCTS:", "WARRANTY INFORMATION:", "FREQUENTLY ASKED"]):
                break
            elif in_workshop and line.strip():
                contact_section += line + "\n"
        
        if contact_section.strip():
            # Parse the extracted contact information
            contact_lines = contact_section.strip().split('\n')
            location = ""
            phone = ""
            email = ""
            hours = ""
            
            for line in contact_lines:
                line = line.strip()
                if line.startswith('- Location:') or line.startswith('Location:'):
                    location = line.replace('- Location:', '').replace('Location:', '').strip()
                elif line.startswith('- Phone:') or line.startswith('Phone:'):
                    phone = line.replace('- Phone:', '').replace('Phone:', '').strip()
                elif line.startswith('- Email:') or line.startswith('Email:'):
                    email = line.replace('- Email:', '').replace('Email:', '').strip()
                elif line.startswith('- Hours:') or line.startswith('Hours:'):
                    hours = line.replace('- Hours:', '').replace('Hours:', '').strip()
                elif 'purok' in line.lower() and 'batangas' in line.lower() and not location:
                    location = line
                elif '@' in line and '.com' in line and not email:
                    email = line
                elif ('monday' in line.lower() and 'saturday' in line.lower()) and not hours:
                    hours = line
                elif line.startswith('09') and len(line) >= 11 and not phone:
                    phone = line
            
            # Use extracted PDF contact information
            if is_tagalog:
                response = "📞 CONTACT INFORMATION:\n"
                if phone:
                    response += f"Phone: {phone}\n"
                if email:
                    response += f"Email: {email}\n\n"
                if hours:
                    response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                if location:
                    response += f"📍 LOCATION:\n{location}"
                return response
            else:
                response = "📞 CONTACT INFORMATION:\n"
                if phone:
                    response += f"Phone: {phone}\n"
                if email:
                    response += f"Email: {email}\n\n"
                if hours:
                    response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                if location:
                    response += f"📍 LOCATION:\n{location}"
                return response
        
        # Fallback if extraction failed
        if is_tagalog:
            return "Hindi ko mahanap ang contact information sa PDF. Pakicheck ang PDF content."
        else:
            return "Contact information not found in PDF. Please check your PDF content."

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
        
        # Fuzzy token-based matching for products (partial names)
        query_tokens = set(re.sub(r'[^a-z0-9\s]','', cleaned_query).split())
        for product, price in PRODUCTS.items():
            tokens = set(re.sub(r'[^a-z0-9\s]','', product).split())
            overlap = query_tokens.intersection(tokens)
            if overlap:
                if is_tagalog:
                    return f"Ang presyo ng {product} ay ₱{price:,}."
                else:
                    return f"The price of {product} is ₱{price:,}."
        
        # If no specific item found, suggest available options
        if is_tagalog:
            return "Hindi ko nahanap yung specific na item. Maaari mong itanong ang mga available products o services, o maging mas specific sa item name."
        else:
            return "I couldn't find that specific item. You can ask about our available products or services, or try being more specific with the item name."

    # ------------------------------------------------------------
    # Fallback: Query the local Ollama model with the PDF context
    # ------------------------------------------------------------
    try:
        # Build a concise system prompt that instructs the model to stick to
        # answers that can be grounded on the provided knowledge base.
        knowledge_context = (context or KNOWLEDGE_BASE).strip()
        system_prompt = (
            "You are PomBot, the helpful AI assistant for the motorcycle parts "
            "shop PomWorkz. Use ONLY the information contained in the knowledge "
            "base below to answer the user's question. If the answer cannot be "
            "found in the knowledge base, respond with 'I am not sure about that.'\n\n"
            f"KNOWLEDGE BASE:\n{knowledge_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        for attempt in range(max_retries):
            try:
                ollama_response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
                answer = ollama_response.get("message", {}).get("content", "").strip()
                if answer:
                    return answer
            except Exception as retry_err:
                logger.warning(f"Ollama attempt {attempt + 1} failed: {retry_err}")
                time.sleep(1)

        # If all retries failed, fall through to a generic message
        return "I couldn't retrieve a response from the local language model at the moment."  # noqa: E501

    except Exception as e:
        logger.error(f"Error communicating with Ollama: {e}")
        return "I encountered an error while contacting the local language model."  # noqa: E501


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

        # Detect if query is in Tagalog
        tagalog_indicators = ['ano', 'gaano', 'ilang', 'paano', 'saan', 'kailan', 'bakit', 'kung', 'mga', 'ng', 'sa', 'para', 'naman', 'lang', 'po', 'magkano', 'meron', 'walang', 'kumusta', 'kamusta']
        is_tagalog = any(indicator in cleaned_query for indicator in tagalog_indicators)

        # Handle location/contact queries first
        location_keywords_en = ['where are you located', 'where is your shop', 'your location', 'your address', 'where can i find you', 'shop location', 'workshop location', 'location']
        location_keywords_tl = ['saan kayo', 'nasaan kayo', 'asan ang shop', 'location nyo', 'address nyo', 'saan po kayo', 'nasaan po kayo', 'saan kayo located', 'saan po kayo located', 'saan ang location', 'asan kayo', 'saan ang shop']
        
        is_location_query = (any(keyword in cleaned_query for keyword in location_keywords_en) or
                            any(keyword in cleaned_query for keyword in location_keywords_tl))
        
        if is_location_query:
            # Extract contact info from knowledge base
            contact_section = ""
            lines = KNOWLEDGE_BASE.split('\n')
            in_workshop = False
            
            for line in lines:
                if "WORKSHOP CONTACT INFORMATION:" in line:
                    in_workshop = True
                    continue
                elif in_workshop and any(x in line for x in ["EXTRACTED PRODUCTS:", "WARRANTY INFORMATION:", "FREQUENTLY ASKED"]):
                    break
                elif in_workshop and line.strip():
                    contact_section += line + "\n"
            
            if contact_section.strip():
                # Parse the extracted contact information
                contact_lines = contact_section.strip().split('\n')
                location = ""
                phone = ""
                email = ""
                hours = ""
                
                for line in contact_lines:
                    line = line.strip()
                    if line.startswith('- Location:') or line.startswith('Location:'):
                        location = line.replace('- Location:', '').replace('Location:', '').strip()
                    elif line.startswith('- Phone:') or line.startswith('Phone:'):
                        phone = line.replace('- Phone:', '').replace('Phone:', '').strip()
                    elif line.startswith('- Email:') or line.startswith('Email:'):
                        email = line.replace('- Email:', '').replace('Email:', '').strip()
                    elif line.startswith('- Hours:') or line.startswith('Hours:'):
                        hours = line.replace('- Hours:', '').replace('Hours:', '').strip()
                    elif 'purok' in line.lower() and 'batangas' in line.lower() and not location:
                        location = line
                    elif '@' in line and '.com' in line and not email:
                        email = line
                    elif ('monday' in line.lower() and 'saturday' in line.lower()) and not hours:
                        hours = line
                    elif line.startswith('09') and len(line) >= 11 and not phone:
                        phone = line
                
                # Use extracted PDF contact information with proper formatting
                if is_tagalog:
                    response = "📍 LOCATION NG POMWORKZ:\n"
                    if location:
                        response += f"{location}\n\n"
                    response += "📞 CONTACT INFO:\n"
                    if phone:
                        response += f"Phone: {phone}\n"
                    if email:
                        response += f"Email: {email}\n\n"
                    if hours:
                        response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                    response += "Pumunta na kayo sa amin para sa lahat ng motorcycle parts needs ninyo!"
                    return response
                else:
                    response = "📍 POMWORKZ LOCATION:\n"
                    if location:
                        response += f"{location}\n\n"
                    response += "📞 CONTACT INFORMATION:\n"
                    if phone:
                        response += f"Phone: {phone}\n"
                    if email:
                        response += f"Email: {email}\n\n"
                    if hours:
                        response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                    response += "Visit us for all your motorcycle parts needs!"
                    return response
            
            # Only use fallback if extraction completely failed
            if is_tagalog:
                return "Hindi ko mahanap ang contact information sa PDF. Pakicheck ang PDF content."
            else:
                return "Contact information not found in PDF. Please check your PDF content."
        
        # Handle contact/hours queries - also use PDF extraction
        contact_keywords_en = ['contact', 'phone', 'email', 'hours', 'operating hours', 'open hours', 'business hours']
        contact_keywords_tl = ['contact', 'numero', 'email', 'oras', 'bukas', 'operating hours']
        
        is_contact_query = (any(keyword in cleaned_query for keyword in contact_keywords_en) or
                           any(keyword in cleaned_query for keyword in contact_keywords_tl))
        
        if is_contact_query:
            # Extract contact info from knowledge base (same logic as location)
            contact_section = ""
            lines = KNOWLEDGE_BASE.split('\n')
            in_workshop = False
            
            for line in lines:
                if "WORKSHOP CONTACT INFORMATION:" in line:
                    in_workshop = True
                    continue
                elif in_workshop and any(x in line for x in ["EXTRACTED PRODUCTS:", "WARRANTY INFORMATION:", "FREQUENTLY ASKED"]):
                    break
                elif in_workshop and line.strip():
                    contact_section += line + "\n"
            
            if contact_section.strip():
                # Parse the extracted contact information
                contact_lines = contact_section.strip().split('\n')
                location = ""
                phone = ""
                email = ""
                hours = ""
                
                for line in contact_lines:
                    line = line.strip()
                    if line.startswith('- Location:') or line.startswith('Location:'):
                        location = line.replace('- Location:', '').replace('Location:', '').strip()
                    elif line.startswith('- Phone:') or line.startswith('Phone:'):
                        phone = line.replace('- Phone:', '').replace('Phone:', '').strip()
                    elif line.startswith('- Email:') or line.startswith('Email:'):
                        email = line.replace('- Email:', '').replace('Email:', '').strip()
                    elif line.startswith('- Hours:') or line.startswith('Hours:'):
                        hours = line.replace('- Hours:', '').replace('Hours:', '').strip()
                    elif 'purok' in line.lower() and 'batangas' in line.lower() and not location:
                        location = line
                    elif '@' in line and '.com' in line and not email:
                        email = line
                    elif ('monday' in line.lower() and 'saturday' in line.lower()) and not hours:
                        hours = line
                    elif line.startswith('09') and len(line) >= 11 and not phone:
                        phone = line
                
                # Use extracted PDF contact information
                if is_tagalog:
                    response = "📞 CONTACT INFORMATION:\n"
                    if phone:
                        response += f"Phone: {phone}\n"
                    if email:
                        response += f"Email: {email}\n\n"
                    if hours:
                        response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                    if location:
                        response += f"📍 LOCATION:\n{location}"
                    return response
                else:
                    response = "📞 CONTACT INFORMATION:\n"
                    if phone:
                        response += f"Phone: {phone}\n"
                    if email:
                        response += f"Email: {email}\n\n"
                    if hours:
                        response += f"⏰ OPERATING HOURS:\n{hours}\n\n"
                    if location:
                        response += f"📍 LOCATION:\n{location}"
                    return response
            
            # Fallback if extraction failed
            if is_tagalog:
                return "Hindi ko mahanap ang contact information sa PDF. Pakicheck ang PDF content."
            else:
                return "Contact information not found in PDF. Please check your PDF content."

        # Check for warranty-related questions in English and Tagalog
        warranty_keywords_en = ['warranty', 'guarantee', 'coverage', 'how long', 'return policy']
        warranty_keywords_tl = ['warranty', 'garantiya', 'takot', 'gaano katagal', 'ilang araw', 'ilang buwan', 'ilang taon', 'policy', 'patakaran']
        
        is_warranty_query = (any(keyword in cleaned_query for keyword in warranty_keywords_en) or 
                           any(keyword in cleaned_query for keyword in warranty_keywords_tl))
        
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

        # Check for booking-related questions in English and Tagalog
        booking_keywords_en = [
            "how to book", "book service", "book a service", "booking process", 
            "how do i book", "steps to book", "booking procedure", "how can i book",
            "service booking", "book services", "schedule service", "appointment"
        ]
        booking_keywords_tl = [
            "paano mag book", "pano mag book", "booking process", "paano mag appointment",
            "book service", "mag book ng service", "paano mag schedule"
        ]
        
        is_booking_query = (any(keyword in cleaned_query for keyword in booking_keywords_en) or
                           any(keyword in cleaned_query for keyword in booking_keywords_tl))
        
        if is_booking_query:
            if is_tagalog:
                return """Paano mag-book ng services sa PomWorkz:

1. 🌐 Pumunta sa aming online booking platform: https://pomworkz.vercel.app/services/book

2. 🔧 Select Services: Piliin ang mga service na kailangan ninyo tulad ng engine repairs, transmission work, general maintenance, at iba pa.

3. 📝 Type Customer Information: I-enter ang inyong contact details, vehicle information, at service requirements.

4. 📅 Pick Schedule: Piliin ang preferred date at time para sa service appointment.

5. ✅ Book a Service: I-click ang "Book a service" button para ma-confirm ang appointment.

🌟 Benefits ng Online Booking:
- Available 24/7
- Instant confirmation
- Flexible scheduling
- Easy appointment management

Para sa urgent repairs o kung gusto ninyo ng phone booking, pwede rin kayong tumawag sa amin during business hours!"""
            else:
                return """How to Book Services at PomWorkz:

1. 🌐 Go to our online booking platform: https://pomworkz.vercel.app/services/book

2. 🔧 Select Services: Choose from our wide range of available services including engine repairs, transmission work, general maintenance, and more.

3. 📝 Type Customer Information: Enter your contact details, vehicle information, and service requirements.

4. 📅 Pick Schedule: Select your preferred date and time for the service appointment.

5. ✅ Book a Service: Press the "Book a service" button to confirm your appointment.

🌟 Online Booking Benefits:
- 24/7 booking availability
- Instant confirmation
- Service scheduling flexibility
- Easy appointment management
- No phone calls required

For urgent repairs or if you prefer phone booking, you can also contact us directly during business hours!"""

        # Check for ordering/purchasing-related questions in English and Tagalog
        ordering_keywords_en = [
            "how to order", "order product", "order products", "ordering process", 
            "how do i order", "steps to order", "ordering procedure", "how can i order",
            "product ordering", "buy product", "purchase product", "how to buy", "how to purchase"
        ]
        ordering_keywords_tl = [
            "paano mag order", "pano mag order", "ordering process", "paano bumili",
            "order product", "mag order ng product", "paano mag purchase", "bumili ng product"
        ]
        
        is_ordering_query = (any(keyword in cleaned_query for keyword in ordering_keywords_en) or
                            any(keyword in cleaned_query for keyword in ordering_keywords_tl))
        
        if is_ordering_query:
            if is_tagalog:
                return """Paano mag-order ng products sa PomWorkz:

1. 🛒 Choose a Product: Piliin ang product na kailangan ninyo mula sa aming catalog

2. ➕ Press Add to Cart: I-click ang "Add to Cart" para ilagay sa shopping cart

3. 🛍️ Press Show Cart: I-click ang "Show Cart" para tingnan ang mga nasa cart ninyo

4. 💳 Then Proceed to Checkout: I-click ang "Proceed to Checkout" para ma-complete ang order

🌟 Simple at convenient na ordering process para sa lahat ng inyong motorcycle parts needs!"""
            else:
                return """How to Order Products at PomWorkz:

1. 🛒 Choose a Product: Select the product you need from our catalog

2. ➕ Press Add to Cart: Click "Add to Cart" to add the item to your shopping cart

3. 🛍️ Press Show Cart: Click "Show Cart" to review the items in your cart

4. 💳 Then Proceed to Checkout: Click "Proceed to Checkout" to complete your order

🌟 Simple and convenient ordering process for all your motorcycle parts needs!"""

        # Check for service process questions in English and Tagalog
        service_process_keywords_en = [
            "how is the process of the service", "service process", "what is the service process",
            "how does the service work", "service workflow", "what happens during service",
            "service procedure", "steps of service", "how do you service", "service steps"
        ]
        service_process_keywords_tl = [
            "ano ang process ng service", "paano ang service process", "service workflow",
            "ano ang nangyayari sa service", "process ng pag service", "hakbang sa service"
        ]
        
        is_service_process_query = (any(keyword in cleaned_query for keyword in service_process_keywords_en) or
                                   any(keyword in cleaned_query for keyword in service_process_keywords_tl))
        
        if is_service_process_query:
            if is_tagalog:
                return """Ang Service Process sa PomWorkz:

1. 📅 Book Appointment: Mag-schedule ng service appointment sa aming website, sa phone, o personal na pagpunta.

2. 🔍 Initial Assessment: Aming mga technicians ay mag-aassess ng inyong motorcycle at magbibigay ng detailed service plan.

3. 🔧 Service Execution: Ang aming skilled mechanics ay gagawin ang requested services nang may precision at care.

4. ✅ Quality Check: Thoroughly namin tinetest ang lahat ng work para ma-ensure na naaabot namin ang aming high standards.

5. 🚀 Delivery: Pick up ninyo ang inyong motorcycle at mag-enjoy sa improved performance at reliability.

🌟 Professional at comprehensive service process para sa best results!"""
            else:
                return """The Service Process at PomWorkz:

1. 📅 Book Appointment: Schedule a service appointment through our website, by phone, or in person.

2. 🔍 Initial Assessment: Our technicians will assess your motorcycle and provide a detailed service plan.

3. 🔧 Service Execution: Skilled mechanics perform the requested services with precision and care.

4. ✅ Quality Check: We thoroughly test all work to ensure everything meets our high standards.

5. 🚀 Delivery: Pick up your motorcycle and enjoy the improved performance and reliability.

🌟 Professional and comprehensive service process for the best results!"""

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


# Load knowledge base automatically when module is imported
print(f"Loading knowledge base from PDF: {PDF_PATH}")
load_knowledge_from_pdf(PDF_PATH)
print(f"PDF Knowledge base loaded: {len(PRODUCTS)} products, {len(SERVICES)} services")


if __name__ == "__main__":
    print(f"Starting server on {HOST}:{PORT}")
    run_simple(HOST, PORT, app, use_reloader=True)
