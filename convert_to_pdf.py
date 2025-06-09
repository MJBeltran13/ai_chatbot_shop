#!/usr/bin/env python3
"""
Simple script to convert knowledge_base.txt to PDF format
This helps create the PDF file that the chatbot can read from
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def convert_txt_to_pdf(input_file="knowledge_base.txt", output_file="POMWORKZ AUTO PARTS CATALOG.pdf"):
    """Convert text file to PDF"""
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found!")
        return False
    
    try:
        # Read the text file
        with open(input_file, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Create PDF
        doc = SimpleDocTemplate(output_file, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1  # Center alignment
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=12
        )
        
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        
        story = []
        
        # Split content into lines
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if not line:
                story.append(Spacer(1, 6))
                continue
            
            # Title (first line)
            if "POMWORKZ AUTO PARTS CATALOG" in line:
                story.append(Paragraph(line, title_style))
            
            # Section headers (lines with =)
            elif line.startswith('=') and line.endswith('='):
                section_name = line.replace('=', '').strip()
                if section_name:
                    story.append(Paragraph(section_name, heading_style))
            
            # Subsection headers (lines ending with :)
            elif line.endswith(':') and not line.startswith('-'):
                story.append(Paragraph(f"<b>{line}</b>", normal_style))
            
            # Regular content
            else:
                # Keep original currency symbols for better parsing
                story.append(Paragraph(line, normal_style))
        
        # Build PDF
        doc.build(story)
        print(f"✅ Successfully created {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating PDF: {e}")
        print("\nTry installing reportlab: pip install reportlab")
        return False

if __name__ == "__main__":
    print("Converting knowledge_base.txt to PDF...")
    success = convert_txt_to_pdf()
    
    if success:
        print("\n🎉 PDF created successfully!")
        print("You can now run: python main.py")
    else:
        print("\n💡 Alternative: Create PDF manually from knowledge_base.txt using:")
        print("- Microsoft Word (Save As PDF)")
        print("- Google Docs (Download as PDF)")  
        print("- Online converters (SmallPDF, ILovePDF)") 