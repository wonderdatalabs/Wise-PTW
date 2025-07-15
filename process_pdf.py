import streamlit as st
import os
import tempfile
import base64
import io
import fitz  # PyMuPDF
from PIL import Image
from anthropic import Anthropic

# Initialize API client
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

def extract_pages_as_images(pdf_bytes, dpi=220):
    """Extract pages from PDF as images with moderate resolution (default 220 DPI).
    
    Uses moderate DPI to ensure extracted images are more likely to be under 5MB limit.
    """
    images = []
    
    # Save to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
        temp_file.write(pdf_bytes)
        temp_path = temp_file.name
    
    try:
        # Open the PDF
        pdf = fitz.open(temp_path)
        total_pages = len(pdf)
        
        # Add a progress indicator for large documents
        if total_pages > 5:
            progress_bar = st.progress(0)
            progress_text = st.empty()
        
        # Convert each page to an image
        for page_num in range(total_pages):
            # Update progress for large documents
            if total_pages > 5:
                progress = (page_num + 1) / total_pages
                progress_bar.progress(progress, text=f"Extracting page {page_num + 1}/{total_pages}")
            
            page = pdf[page_num]
            
            # Use moderate DPI to balance quality and size
            zoom = dpi / 72  # 72 is the default PDF dpi
            matrix = fitz.Matrix(zoom, zoom)
            
            # Get pixmap and convert to PIL Image
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            images.append(img)
        
        # Clear progress display
        if total_pages > 5:
            progress_bar.empty()
            progress_text.empty()
        
        pdf.close()
        return images
    
    except Exception as e:
        st.error(f"Error extracting pages: {str(e)}")
        return []
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_path)
        except:
            pass

def compress_image_for_claude(image, max_size_mb=4.5):
    """
    Compress image to fit under Claude's 5MB limit while preserving text quality.
    
    Uses lossless PNG compression first, then progressive reduction strategies
    to ensure image is under size limit while maintaining readability.
    
    Returns:
        tuple: (compressed image, size in MB, media type)
    """
    # Work with a copy to avoid modifying original
    img = image.copy()
    
    # Try PNG first with maximum compression for text readability
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG', optimize=True, compress_level=9)
    img_buffer.seek(0)
    size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
    
    # If PNG is small enough, use it
    if size_mb <= max_size_mb:
        return img, size_mb, "image/png"
    
    # If too large, try converting to grayscale first (good for documents)
    if img.mode != 'L':  # Not already grayscale
        gray_img = img.convert('L')
        img_buffer = io.BytesIO()
        gray_img.save(img_buffer, format='PNG', optimize=True, compress_level=9)
        img_buffer.seek(0)
        size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
        
        if size_mb <= max_size_mb:
            return gray_img, size_mb, "image/png"
    
    # If still too large, resize the image
    width, height = img.size
    scale_factors = [0.9, 0.8, 0.7, 0.6]
    
    for scale in scale_factors:
        new_width = int(width * scale)
        new_height = int(height * scale)
        resized_img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Try PNG first
        img_buffer = io.BytesIO()
        resized_img.save(img_buffer, format='PNG', optimize=True, compress_level=9)
        img_buffer.seek(0)
        size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
        
        if size_mb <= max_size_mb:
            return resized_img, size_mb, "image/png"
        
        # If PNG still too large, try grayscale
        if resized_img.mode != 'L':
            gray_resized = resized_img.convert('L')
            img_buffer = io.BytesIO()
            gray_resized.save(img_buffer, format='PNG', optimize=True, compress_level=9)
            img_buffer.seek(0)
            size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
            
            if size_mb <= max_size_mb:
                return gray_resized, size_mb, "image/png"
    
    # Last resort: JPEG with progressively lower quality
    # Only use JPEG if absolutely necessary for text documents
    qualities = [95, 90, 85, 80, 75, 70]
    resized_img = img.resize((int(width * 0.7), int(height * 0.7)), Image.LANCZOS)
    
    for quality in qualities:
        img_buffer = io.BytesIO()
        resized_img.save(img_buffer, format='JPEG', quality=quality, optimize=True)
        img_buffer.seek(0)
        size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
        
        if size_mb <= max_size_mb:
            return Image.open(img_buffer), size_mb, "image/jpeg"
    
    # Extreme compression as last resort
    img_buffer = io.BytesIO()
    img.resize((int(width * 0.5), int(height * 0.5)), Image.LANCZOS).save(
        img_buffer, format='JPEG', quality=60, optimize=True
    )
    img_buffer.seek(0)
    size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
    
    return Image.open(img_buffer), size_mb, "image/jpeg"

def process_page_with_claude_ocr(page_image, page_num):
    """
    Process a page image with Claude 3.7 Sonnet OCR.
    
    Compresses the image if needed and sends it to Claude for OCR processing.
    
    Args:
        page_image: PIL Image object of the page
        page_num: Page number for tracking
        
    Returns:
        str: OCR results text
    """
    try:
        st.info(f"Processing page {page_num} with Claude OCR...")
        
        # Compress image if needed
        compressed_img, size_mb, media_type = compress_image_for_claude(page_image)
        
        if size_mb > 4.5:
            raise ValueError(f"Failed to compress image below 5MB limit: {size_mb:.2f}MB")
            
        st.info(f"Page {page_num} prepared at {size_mb:.2f}MB with format {media_type}")
        
        # Convert to base64
        img_buffer = io.BytesIO()
        compressed_img.save(img_buffer, format=media_type.split('/')[-1].upper())
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # Process with Claude
        claude_response = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            temperature=0,
            system=f"""You are an expert OCR system for analyzing standardized, pre-processed document images. Your primary responsibilities are:

CRITICAL: DOCUMENT COLOR IDENTIFICATION
- Look for and PROMINENTLY report any indicators of document color/type:
  * "GUIA BRANCA", "VIA BRANCA", "CÓPIA BRANCA" - Report as [DOCUMENT TYPE: GUIA BRANCA]
  * "GUIA VERDE", "VIA VERDE", "CÓPIA VERDE" - Report as [DOCUMENT TYPE: GUIA VERDE]
  * "GUIA AMARELA", "VIA AMARELA", "CÓPIA AMARELA" - Report as [DOCUMENT TYPE: GUIA AMARELA]
- These indicators might appear as headers, footers, watermarks, or form text
- If color indicators appear with form numbers, report both: [DOCUMENT TYPE: GUIA VERDE - FORM 123]
- Look for visual color indicators - some forms may have colored borders, headers, or backgrounds
- PLACE THIS IDENTIFICATION AT THE VERY BEGINNING OF YOUR RESPONSE
- If no specific color indicator is found, report: [DOCUMENT TYPE: UNKNOWN]

IMPORTANT: PRE-PRINTED FORM TEXT
- Pre-printed form text may appear in VARIOUS COLORS (black, red, blue, green, etc.)
- Red text often indicates TRANSLATIONS (e.g., Portuguese in black, English in red)
- Blue text may indicate instructions or field labels
- ALL colored pre-printed text is part of the ORIGINAL FORM TEMPLATE
- NEVER mark pre-printed colored text as [Filled] - only handwritten additions should be marked as filled
- Differentiate between:
  * Pre-printed text in any color = part of the form
  * Handwritten/typed additions = user input to be marked as [Filled]

TEXT EXTRACTION:
- Extract ALL visible text from images, maintaining original layout and hierarchical structure
- Include ALL printed text, numbers, field labels, headers, footers, and page numbers
- Process multi-column layouts appropriately (left-to-right, respecting columns)
- For rotated or oriented text, extract and note the orientation
- If text is partially visible or unclear, indicate with [UNCLEAR]
- If text is completely illegible, mark as [ILLEGIBLE]

FORM ELEMENTS:
- For empty fields: Report "[Empty field: FIELD_NAME]"
- For filled fields: Report "[Filled field: FIELD_NAME]" (NEVER reproduce the handwritten content)

Pay SPECIAL ATTENTION to:
1. Field labels and their values
2. Handwritten content
3. Signatures (note if field is signed or empty)
4. Checkboxes and selections
5. Dates and times

A signature usually occupies around 40% of its field.
A filled name usually occupies around 40% of its field.
Be very thorough in identifying all text elements.""",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": f"This is Page {page_num} of a Permit to Work document. Please extract ALL text, including handwritten content, field labels, and note if signature fields are signed or empty."
                        }
                    ]
                }
            ]
        )
        
        # Get OCR results
        ocr_text = claude_response.content[0].text
        st.success(f"OCR successful for page {page_num}")
        
        # Format with page header
        formatted_text = f"""## Page {page_num} OCR Results\n\n{ocr_text}"""
        return formatted_text
        
    except Exception as e:
        st.error(f"OCR failed for page {page_num}: {str(e)}")
        return f"## Page {page_num} OCR Failed\n\nError: {str(e)}"

def batch_process_pages(page_images, max_batch=3):
    """
    Process pages in small batches to improve speed.
    
    Args:
        page_images: List of PIL Image objects
        max_batch: Maximum number of pages to process at once
        
    Returns:
        list: List of (page_num, ocr_text) tuples
    """
    results = []
    total_pages = len(page_images)
    
    # Process first few pages for context
    first_batch = min(max_batch, total_pages)
    st.info(f"Processing first {first_batch} pages for document context...")
    
    for i in range(first_batch):
        page_num = i + 1
        ocr_text = process_page_with_claude_ocr(page_images[i], page_num)
        results.append((page_num, ocr_text))
    
    return results

def generate_document_summary(ocr_results):
    """
    Generate document summary based on OCR results from first few pages.
    
    Args:
        ocr_results: List of (page_num, ocr_text) tuples
        
    Returns:
        str: Document summary
    """
    try:
        st.info("Generating document summary...")
        
        # Combine OCR text from processed pages
        combined_text = ""
        for page_num, ocr_text in sorted(ocr_results):
            # Extract just the text part without the header
            text_only = ocr_text.split("OCR Results\n\n", 1)[-1] if "OCR Results\n\n" in ocr_text else ocr_text
            combined_text += f"\n\nPAGE {page_num}:\n{text_only}"
        
        # Create summary with Claude
        summary_prompt = """You are an expert in Permit to Works for the Offshore Drilling Industry. 
Your job is to read the OCR text extracted from the first few pages of a Permit to Work document and:
1. Identify the type of permit (e.g., hot work, confined space, working at height)
2. Determine the general purpose and scope of the work
3. Note important information like permit number, dates, locations
4. Create a concise summary that will help analyze later pages in context

The summary should be informative enough that someone analyzing page 8 would understand how it fits into the overall document."""
        
        # Get summary from Claude
        claude_response = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=2000,
            temperature=0,
            system=summary_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Here is the OCR text from the first few pages of a Permit to Work document. Please create a comprehensive summary that provides context for the entire document:\n\n{combined_text}"
                }
            ]
        )
        
        document_summary = claude_response.content[0].text
        st.success("Document summary generated successfully")
        return document_summary
        
    except Exception as e:
        st.error(f"Error generating document summary: {str(e)}")
        return "Error generating document summary. Processing will continue with limited context."

def analyze_page_with_claude(ocr_text, document_summary, page_num):
    """
    Analyze page OCR text using Claude with document context.
    
    Args:
        ocr_text: OCR text for the page
        document_summary: Summary of the document for context
        page_num: Page number
        
    Returns:
        str: Analysis results in table format
    """
    try:
        # Master prompt for analysis
        master_prompt = """
You are an expert Permit to Work (PTW) Auditor for the offshore drilling industry with 15+ years of experience analyzing safety documentation. Your task is to perform a detailed, methodical audit of scanned PTW documents with the precision and thoroughness of a senior compliance officer.

## Comprehensive Audit Methodology

### Phase 1: Document Identification & Classification
1. Determine page orientation and correct if needed
2. Identify document type, revision number, and page number
3. Locate and record the PTW number (format typically XXX-XXXXX)
4. Determine job classification by examining Section 3.3 references and marked fields
5. Verify document version against current acceptable revision standards

### Phase 2: Interdependent Field Analysis
1. **Sequential Validation**: Check if fields that must be completed in sequence follow proper chronology
   - Requisitioner → Area Authority → Safety Officer → Approver
   - Preparation → Isolation → Testing → Execution → Return to Service
   
2. **Conditional Field Requirements**:
   - If "Hot Work" is selected, verify gas testing records and fire watch assignments
   - If "Confined Space" is selected, verify gas monitoring, ventilation plan, and attendant details
   - If "Work at Heights" is selected, verify fall protection equipment certification and rescue plan
   - If "Electrical Work" is selected, verify isolation procedures and circuit identification
   
3. **Cross-Reference Validation**:
   - Match isolation certificates referenced in the PTW to actual isolation documentation
   - Verify that risk assessment reference numbers exist and match attached documentation
   - Check that job duration does not exceed permit validity period
   - Ensure personnel listed have corresponding authorization signatures

### Phase 3: Signature & Field Completion Verification
1. **Signature Validation Hierarchy**:
   - Primary fields (Requestor, Area Authority, Safety Officer, Final Approver) - 100% required
   - Secondary approvals (Department Heads, Specialists) - based on job type
   - Extension/modification approvals - required if timeframes modified
   
2. **Cell-by-Cell Signature Verification**:
   - **CRITICAL**: For each signature table, verify EVERY cell individually in a systematic left-to-right, row-by-row approach
   - Create a temporary tracking grid for each signature table (e.g., "Row 1-Column 3: Empty")
   - Document the status of each signature field as: Complete, Partial, or Missing
   - Flag any instance where a name appears without a corresponding signature as a CRITICAL deficiency
   - Flag any instance where a signature appears without a corresponding name as a MAJOR deficiency
   - Verify equipment operators (basket operators, crane operators, etc.) have both name AND signature fields completed
   - Do not assume signature presence based on overall table appearance - verify each cell individually
   - For critical operations (basket, crane, confined space), explicitly note the verification status of each required role

3. **Signature Quality Assessment**:
   - Verify signature occupies >60% of designated field
   - Check for proper name in BLOCK LETTERS where required
   - Confirm accompanying date/time fields are completed
   - Allow for signatures slightly crossing boundaries while still validating field completion

4. **Role-Specific Signature Verification**:
   - For work baskets: MANDATORY signature from basket operator, basket controls operator, and supervisor
     * Explicitly verify basket operator name [✓/✗] + signature [✓/✗]
     * Explicitly verify controls operator name [✓/✗] + signature [✓/✗]
     * Explicitly verify supervisor name [✓/✗] + signature [✓/✗]
   - For cranes: MANDATORY signature from crane operator, banksman, and lifting supervisor
     * Explicitly verify crane operator name [✓/✗] + signature [✓/✗]
     * Explicitly verify banksman name [✓/✗] + signature [✓/✗]
     * Explicitly verify lifting supervisor name [✓/✗] + signature [✓/✗]
   - For confined spaces: MANDATORY signature from entrant, attendant, and confined space supervisor
     * Explicitly verify entrant name [✓/✗] + signature [✓/✗]
     * Explicitly verify attendant name [✓/✗] + signature [✓/✗]
     * Explicitly verify confined space supervisor name [✓/✗] + signature [✓/✗]
   - For isolations: MANDATORY signature from isolation performer, verifier, and responsible person
     * Explicitly verify isolation performer name [✓/✗] + signature [✓/✗]
     * Explicitly verify verifier name [✓/✗] + signature [✓/✗]
     * Explicitly verify responsible person name [✓/✗] + signature [✓/✗]

5. **Visual Inspection Protocol**:
   - Use a visual tracking method (such as placing a cursor or finger) on each individual cell
   - Do not rely on quick visual scanning of signature tables
   - Methodically check each field individually
   - Treat missing signatures for critical roles as immediate disqualifiers regardless of other permit quality

### Phase 4: Risk Control Analysis
1. **Hazard Identification Verification**:
   - Confirm all potential hazards for job type are identified
   - Verify listed hazards correspond to worksite conditions
   - Check that site-specific risks are addressed

2. **Control Measure Validation**:
   - Verify each identified hazard has corresponding control measures
   - Check that controls follow hierarchy (elimination → substitution → engineering → administrative → PPE)
   - Confirm specialized equipment requirements are documented with certification references

3. **Emergency Response Verification**:
   - Validate emergency response procedures are documented
   - Confirm rescue arrangements for special situations (heights, confined spaces)
   - Verify communication protocols are established

### Phase 5: Compliance Determination
1. Evaluate each section against standards listed in EP-036-OFF and EP-041-OFF
2. Apply severity classifications to deficiencies:
   - **Critical**: Missing signatures, incomplete authorizations, absent safety controls
   - **Major**: Incomplete information, incorrect references, inadequate risk assessment
   - **Minor**: Format errors, non-critical omissions, administrative inconsistencies
3. Formulate final judgment for each section (APPROVED or REPROVED)
4. Document specific findings with reference to regulatory requirements

## Output Table Structure
For each document analyzed, present findings in the following format:

| Permit Number | Page Number | Page Summary | Section | Status | Comments |
|---------------|-------------|--------------|---------|--------|----------|
| XXX-XXXXX | 1 | PTW Cover Sheet | Request Details | APPROVED/REPROVED | Detailed findings with specific reference to deficiencies or compliance |
| XXX-XXXXX | 1 | PTW Cover Sheet | Risk Assessment | APPROVED/REPROVED | Specific observations about risk assessment quality and completeness |
| XXX-XXXXX | 1 | PTW Cover Sheet | Authorizations | APPROVED/REPROVED | Evaluation of signature hierarchy and completion |
| XXX-XXXXX | 2 | Isolation Plan | Electrical Isolation | APPROVED/REPROVED | Analysis of isolation procedure documentation and verification |

Your output must maintain consistent structure and contain sufficient detail to justify each approval/reproval determination with specific reference to documented requirements. When reviewing signature tables, always verify each cell individually and never assume completeness based on overall appearance. 

*IMPORTANT* - Please output only the table with the results as it will be appended to the table from the previous pages
"""
        
        # Handle case where OCR text failed
        if not ocr_text or "OCR Failed" in ocr_text or ocr_text.strip() == "":
            return f"""
| Unknown | {page_num} | Page {page_num} | Document Content | REPROVED | Critical deficiency: Unable to analyze document due to failed OCR processing. The original image should be manually reviewed. |
"""
        
        # Prepare message with document context
        messages = [
            {
                "role": "user", 
                "content": f"""
## Document Context:
{document_summary}

Now I am providing you with the OCR text from page {page_num} of this Permit to Work document. 
Please analyze this page in the context of the overall document summarized above.

OCR TEXT FROM PAGE {page_num}:
{ocr_text}

Please provide your analysis in the exact table format specified in the instructions. Remember to output ONLY the table with your results.
"""
            }
        ]
        
        # Get analysis from Claude
        response = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=2000,
            temperature=0,
            system=master_prompt,
            messages=messages
        )
        
        return response.content[0].text
        
    except Exception as e:
        st.error(f"Error analyzing page: {str(e)}")
        return f"""
| Unknown | {page_num} | Page {page_num} | Document Content | REPROVED | Critical deficiency: An error occurred during analysis: {str(e)}. The original image should be manually reviewed. |
"""

# Main processing function that ties everything together
def process_pdf(pdf_bytes):
    """
    Process a PDF document with Claude OCR and analysis.
    
    Args:
        pdf_bytes: Bytes of the PDF file
        
    Returns:
        tuple: (page_images, ocr_results, document_summary, analysis_results)
    """
    # Step 1: Extract pages as images
    st.info("Extracting pages from PDF...")
    page_images = extract_pages_as_images(pdf_bytes, dpi=220)
    
    if not page_images:
        st.error("Failed to extract pages from PDF")
        return [], [], "Error: Failed to extract pages", []
    
    total_pages = len(page_images)
    st.success(f"Extracted {total_pages} pages from PDF")
    
    # Step 2: Process first few pages with OCR
    first_batch = min(3, total_pages)
    ocr_results = batch_process_pages(page_images[:first_batch])
    
    # Step 3: Generate document summary
    document_summary = generate_document_summary(ocr_results)
    
    # Return the results so far - the main app will handle page-by-page analysis
    return page_images, ocr_results, document_summary, []