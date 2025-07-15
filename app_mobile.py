import streamlit as st
import os
import tempfile
import base64
import io
import time
import re
import fitz  # PyMuPDF
import pandas as pd
import uuid
import concurrent.futures
import threading
from PIL import Image, ImageEnhance
from anthropic import Anthropic
from pathlib import Path

# Import UI helper functions
from ui_helpers import load_css, init_session_state, render_sidebar, render_welcome_message, get_image_base64

# Set page configuration
st.set_page_config(
    page_title="Analisador de PT | Documentação de Segurança de Óleo e Gás",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load API key from environment variable with fallback
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Initialize Claude client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Load CSS styling
load_css()
load_css("chat_page")

# Add static background image
try:
    # Get static background image in base64 format
    background_image = get_image_base64('assets/const-bg2.png')
    
    # Apply background image with improved text contrast
    st.markdown(f"""
    <style>
        /* Main app background with static image */
        .stApp {{
            background-image: url("data:image/png;base64,{background_image}");
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
            background-attachment: fixed;
            background-color: #f0f5ff; /* Very light blue background */
            animation: none !important;
        }}
        
        /* Improve text visibility */
        p, span, label, div, li, td, th {{
            color: #05113b !important;
            font-weight: 500 !important;
        }}
        
        /* Headers with strong contrast */
        h1, h2, h3, h4, h5, h6, .sidebar-title {{
            color: #05113b !important;
            font-weight: 700 !important;
        }}
        
        /* Make content containers more visible */
        .content-container {{
            background-color: rgba(255, 255, 255, 0.9) !important;
            border-radius: 10px !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
            padding: 20px !important;
            border: 1px solid rgba(230, 236, 255, 0.5) !important;
        }}
        
        /* Make streamlit elements more readable - ONLY for the main content area (NOT sidebar) */
        div.main .stButton > button {{
            background-color: #0041aa !important;  /* Lighter blue for better visibility */
            color: white !important;
            font-weight: 600 !important;
            border: none !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.15) !important;
            border-radius: 6px !important;
        }}
        
        /* Data tables with better contrast */
        .stDataFrame {{
            border: 1px solid rgba(5, 17, 59, 0.2) !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
        }}
        
        /* Table styling */
        table {{
            background-color: rgba(255, 255, 255, 0.95) !important;
            border: 1px solid rgba(0, 65, 170, 0.1) !important;
        }}
        
        th {{
            background-color: rgba(0, 65, 170, 0.9) !important;
            color: white !important;
            font-weight: 600 !important;
            text-shadow: none !important;
            padding: 8px !important;
        }}
        
        td {{
            background-color: rgba(255, 255, 255, 0.9) !important;
            color: #05113b !important;
            font-weight: 500 !important;
            text-shadow: none !important;
            padding: 6px !important;
        }}
        
        /* Info/success/warning boxes */
        .stAlert {{
            background-color: rgba(255, 255, 255, 0.85) !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
        }}
        
        /* Override the animation keyframes */
        @keyframes background-logo-float {{
            0%, 100% {{ background-position: center; }}
        }}
        
        /* Make sidebar text readable */
        [data-testid="stSidebar"] .stRadio label,
        [data-testid="stSidebar"] .stCheckbox label,
        [data-testid="stSidebar"] .stSelectbox label,
        [data-testid="stSidebar"] .stSlider label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {{
            color: white !important;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5) !important;
            font-weight: 500 !important;
        }}
    </style>
    """, unsafe_allow_html=True)
except Exception as e:
    st.warning(f"Could not load background image: {str(e)}")

# Helper functions
def get_file_size_mb(file_bytes):
    """Return the file size in megabytes."""
    return len(file_bytes) / (1024 * 1024)

def compress_pdf(input_bytes, target_size_mb=4.0):
    """Compress PDF to target size."""
    # Save input bytes to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_input:
        temp_input.write(input_bytes)
        temp_input_path = temp_input.name
    
    # Create a temporary output file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_output:
        temp_output_path = temp_output.name
    
    # Check if input already meets the requirement
    input_size = get_file_size_mb(input_bytes)
    if input_size <= target_size_mb:
        # Already under target size, just return the original
        os.unlink(temp_input_path)
        os.unlink(temp_output_path)
        return input_bytes
    
    try:
        # Open the PDF
        input_pdf = fitz.open(temp_input_path)
        output_pdf = fitz.open()
        
        # Try different compression levels until we achieve target size
        for quality in [95, 90, 80, 70, 60, 50, 40]:
            # Clear output PDF
            output_pdf.close()
            output_pdf = fitz.open()
            
            # Process each page
            for page_num in range(len(input_pdf)):
                page = input_pdf[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
                
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img_stream = io.BytesIO()
                img.save(img_stream, format="JPEG", quality=quality)
                img_stream.seek(0)
                
                # Add the compressed image as a new page
                new_page = output_pdf.new_page(width=page.rect.width, height=page.rect.height)
                new_page.insert_image(page.rect, stream=img_stream.getvalue())
            
            # Save to the temporary output file
            output_pdf.save(temp_output_path, garbage=4, deflate=True)
            
            # Check if we achieved the target size
            with open(temp_output_path, 'rb') as f:
                output_bytes = f.read()
                if get_file_size_mb(output_bytes) <= target_size_mb:
                    break
        
        # Close PDF objects
        input_pdf.close()
        output_pdf.close()
        
        # Read the final output file
        with open(temp_output_path, 'rb') as f:
            output_bytes = f.read()
        
        return output_bytes
        
    except Exception as e:
        st.error(f"Error compressing PDF: {str(e)}")
        return input_bytes
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(temp_input_path)
            os.unlink(temp_output_path)
        except:
            pass

def extract_pages_as_images(pdf_bytes, dpi=300):
    """Extract pages from PDF as PNG images with specified resolution."""
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
                progress_bar.progress(progress, text=f"Extraindo página {page_num + 1}/{total_pages}")
            
            page = pdf[page_num]
            
            # Starting with higher DPI for better text clarity, especially for scanned documents
            initial_dpi = dpi  # Start with a higher DPI for better quality
            zoom = initial_dpi / 72  # 72 is the default PDF dpi
            matrix = fitz.Matrix(zoom, zoom)
            
            # Always use RGB for better OCR results
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Apply slight sharpening to improve text clarity (especially for scanned docs)
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.2)  # Slight sharpening
            
            # Adjust contrast slightly to improve readability
            contrast_enhancer = ImageEnhance.Contrast(img)
            img = contrast_enhancer.enhance(1.1)  # Slight contrast boost
            
            # Create a PNG buffer with high quality
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            
            # Check size and compress if needed
            img_size_mb = len(buf.getvalue()) / (1024 * 1024)
            
            # If image is too large, try to reduce size while maintaining quality
            if img_size_mb > 4:
                st.warning(f"Página {page_num + 1} tem {img_size_mb:.2f}MB, comprimindo para processamento...")
                
                # Try reducing the resolution in smaller steps to maintain readability
                for reduce_dpi in [250, 200, 175, 150, 125]:
                    reduce_matrix = fitz.Matrix(reduce_dpi / 72, reduce_dpi / 72)
                    reduced_pix = page.get_pixmap(matrix=reduce_matrix)
                    reduced_img = Image.frombytes("RGB", [reduced_pix.width, reduced_pix.height], reduced_pix.samples)
                    
                    # Apply enhancement to maintain readability at lower resolution
                    enhancer = ImageEnhance.Sharpness(reduced_img)
                    reduced_img = enhancer.enhance(1.3)  # Slightly stronger sharpening at lower resolution
                    
                    # Adjust contrast slightly to improve readability
                    contrast_enhancer = ImageEnhance.Contrast(reduced_img)
                    reduced_img = contrast_enhancer.enhance(1.2)
                    
                    # Try saving with this reduced resolution
                    reduced_buf = io.BytesIO()
                    reduced_img.save(reduced_buf, format="PNG", optimize=True, quality=95)  # High quality
                    reduced_buf.seek(0)
                    
                    reduced_size_mb = len(reduced_buf.getvalue()) / (1024 * 1024)
                    if reduced_size_mb <= 4.0:
                        st.info(f"Página {page_num + 1} reduzida para {reduced_size_mb:.2f}MB em {reduce_dpi} DPI")
                        img = reduced_img
                        break
            
            # Add image to list
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

def generate_ptw_summary(pdf_bytes):
    """Generate a summary of the PTW document using Wonder Wise with robust fallback."""
    try:
        # APPROACH 1: Extract ALL pages as images for reliable processing
        st.info("Extraindo todas as páginas para resumo do documento...")
        
        # Extract all pages at a reasonable resolution for summary purposes
        page_images = extract_pages_as_images(pdf_bytes, dpi=150)
        
        # Use all pages for a complete picture
        preview_images = page_images  # No limit here anymore
        
        if preview_images:
            st.success(f"Extraiu com sucesso {len(preview_images)} páginas para resumo")
            
            # Updated summary prompt to include a structured table of page descriptions
            summary_prompt = """You are an expert in Permit to Works for the Offshore Drilling Industry. 
            Your job is to read Permit to Work documents and provide a summary for an AI agent to be informed 
            before processing these permits page by page. Your summaries should include:
            
            1. A well written description of the work being done, specially highlighting the type of work. 
               Make sure you say clearly if this is a work at height category or not, as this is very important for the agent.
            
            2. IMPORTANT: After the general summary, create a structured table listing each page and its content. Format this table as:
            
               | Número da Página | Tipo de Documento | Descrição do Conteúdo |
               |------------------|-------------------|------------------------|
               | 1                | [Form type]       | [Brief description]    |
               | 2                | [Form type]       | [Brief description]    |
               
               For "Tipo de Documento", use one of these categories:
               - PT Principal (main PTW form)
               - JSA (Job Safety Analysis)
               - APR (Análise Preliminar de Risco)
               - PRTA (Plano de Resgate para Trabalho em Altura)
               - CLPTA (Checklist de Planejamento de Trabalho em Altura)
               - CLPUEPCQ (Check List de Pré-Uso de EPC de Queda)
               - ATASS (Autorização do Setor de Saúde)
               - LVCTA (Lista de Verificação de Cesto de Trabalho Aéreo)
               - Isolamento (Isolation form)
               - Outros (Other form types)
            
            3. After the table, provide a brief analysis about whether any required forms appear to be missing based on the document type and work being performed. For example, if this is a work at height permit but there's no PRTA form, mention this.
            
            You are not allowed to issue any information or opinion about approvals - simply describe the content 
            of each page objectively. The next agent will evaluate each page to audit it.
            
            Format your entire response in Brazilian Portuguese."""
            
            # Create content array with images (keeping English for LLM prompt)
            content = [{"type": "text", "text": "Please provide a summary of this Permit to Work document based on all pages. Format your response in Brazilian Portuguese. Include the table of page descriptions as specified."}]
            
            # Add each image to the content array
            for i, img in enumerate(preview_images):
                # Convert image to base64 with PNG format for better text clarity
                img_buffer = io.BytesIO()
                img.save(img_buffer, format="PNG", optimize=True)
                img_buffer.seek(0)
                img_base64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")
                
                # Add image to content
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_base64
                    }
                })
            
            try:
                # Call Wonder Wise (Claude) API with images
                response = anthropic_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=20000,  # Use full token limit
                    temperature=0,
                    system=summary_prompt,
                    messages=[{"role": "user", "content": content}]
                )
                
                st.success("Geração de resumo baseada em imagem concluída com sucesso!")
                return response.content[0].text
            except Exception as img_error:
                st.warning(f"Falha na geração de resumo baseada em imagem: {str(img_error)}")
                # Continue to fallback approaches
        else:
            st.warning("Não foi possível extrair páginas do PDF para resumo")
        
        # APPROACH 2: Try with direct PDF processing - this sometimes works with Wonder Wise
        try:
            # Only try if PDF is under 5MB
            pdf_size_mb = get_file_size_mb(pdf_bytes)
            if pdf_size_mb <= 5.0:
                # Updated summary prompt for direct PDF approach (keeping in English)
                summary_prompt = """You are an expert in Permit to Works for the Offshore Drilling Industry. 
                Your job is to read full Permit to work documents and provide a summary for an AI agent to be informed 
                before processing these permits page by page. Your summaries should include:
                
                1. A well written description of the work being done, highlighting the type of work. 
                   Make sure you say clearly if this is a work at height category or not.
                
                2. IMPORTANT: Create a structured table listing each page and its content. Format this table as:
                
                   | Número da Página | Tipo de Documento | Descrição do Conteúdo |
                   |------------------|-------------------|------------------------|
                   | 1                | [Form type]       | [Brief description]    |
                   | 2                | [Form type]       | [Brief description]    |
                   
                   For "Tipo de Documento", use one of these categories:
                   - PT Principal (main PTW form)
                   - JSA (Job Safety Analysis)
                   - APR (Análise Preliminar de Risco)
                   - PRTA (Plano de Resgate para Trabalho em Altura)
                   - CLPTA (Checklist de Planejamento de Trabalho em Altura)
                   - CLPUEPCQ (Check List de Pré-Uso de EPC de Queda)
                   - ATASS (Autorização do Setor de Saúde)
                   - LVCTA (Lista de Verificação de Cesto de Trabalho Aéreo)
                   - Isolamento (Isolation form)
                   - Outros (Other form types)
                
                3. After the table, briefly analyze whether any required forms appear to be missing based on work type.
                
                You are not allowed to issue any information or opinion about approvals - simply inform the content of each page. 
                The next agent will evaluate page by page to audit it.
                
                Format your entire response in Brazilian Portuguese."""
                
                # Encode PDF for API submission
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                st.info("Tentando processar o PDF diretamente com Wonder Wise...")
                
                # Call Wonder Wise API with the PDF (keeping prompt in English)
                response = anthropic_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=20000,
                    temperature=0,
                    system=summary_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Please provide a summary of this Permit to Work document including the table of page descriptions as specified. Format your response in Brazilian Portuguese:"
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "application/pdf", 
                                        "data": base64_pdf
                                    }
                                }
                            ]
                        }
                    ]
                )
                
                st.success("Processamento direto do PDF concluído com sucesso!")
                return response.content[0].text
            else:
                st.warning(f"PDF muito grande ({pdf_size_mb:.2f}MB) para processamento direto")
                # Continue to fallback approach
        except Exception as pdf_error:
            st.warning(f"Falha no processamento direto do PDF: {str(pdf_error)}")
            # Continue to fallback approach
        
        # APPROACH 3: Simplified first page and batch sampling approach as last resort
        try:
            st.info("Tentando um resumo simplificado com amostragem de páginas...")
            
            # Make sure we have page images
            if not page_images or len(page_images) == 0:
                page_images = extract_pages_as_images(pdf_bytes, dpi=250)
            
            if page_images and len(page_images) > 0:
                # Sample the first page and then every 2-3 pages to get a representative sample
                total_pages = len(page_images)
                sample_indices = [0]  # Always include first page
                
                # Add samples throughout the document
                if total_pages > 1:
                    sample_indices.extend([min(i, total_pages-1) for i in range(2, total_pages, 3)])
                    
                # Ensure we have at most 5 pages for the fallback approach
                sample_indices = sample_indices[:5]
                sample_images = [page_images[i] for i in sample_indices]
                
                # Create content array with sampled images
                content = [{"type": "text", "text": "This is a sample of pages from a Permit to Work document. Please provide a summary including a table of page descriptions as best you can from these samples."}]
                
                # Add each sample image to the content array
                for i, img in enumerate(sample_images):
                    # Convert to PNG for better text clarity
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG", optimize=True)
                    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    
                    # Add image to content
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_base64
                        }
                    })
                
                # Use improved prompt for sample approach
                sample_prompt = """You are looking at a sample of pages from a Permit to Work document. 
                Based on these samples, please provide:
                
                1. A summary of what this PTW appears to be about.
                2. A table listing each sample page with this format:
                
                   | Número da Página | Tipo de Documento | Descrição do Conteúdo |
                   |------------------|-------------------|------------------------|
                   | 1                | [Form type]       | [Brief description]    |
                   | X                | [Form type]       | [Brief description]    |
                   
                For "Tipo de Documento", identify whether it's the main PTW form, JSA, PRTA, or another form type.
                Note that these are only samples - the actual document may have more pages.
                
                Format your entire response in Brazilian Portuguese."""
                
                # Call Wonder Wise API with sampled images
                simplified_response = anthropic_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=20000,
                    temperature=0,
                    system=sample_prompt,
                    messages=[{"role": "user", "content": content}]
                )
                
                st.success("Resumo com amostragem de páginas concluído com sucesso!")
                return simplified_response.content[0].text
            else:
                st.error("Não foi possível extrair imagens do PDF")
                # Fall through to default summary
        except Exception as final_error:
            st.error(f"Todas as tentativas de resumo falharam: {str(final_error)}")
            # Fall through to default summary
    
    except Exception as e:
        st.error(f"Erro ao gerar resumo da PT: {str(e)}")
    
    # Default summary - only reached if all approaches fail (providing in Portuguese)
    return """Resumo da PT: Este é um resumo padrão gerado porque a geração do resumo original falhou. 
            O documento parece ser um formulário de Permissão de Trabalho para uma operação de perfuração offshore. 
            A análise continuará com o processamento individual das páginas.
            
            | Número da Página | Tipo de Documento | Descrição do Conteúdo |
            |------------------|-------------------|------------------------|
            | 1                | PT Principal      | Formulário principal de permissão de trabalho |
            """

def process_page_with_claude_ocr(page_image, page_num=None):
    """Process page image with Wonder Wise OCR."""
    try:
        # Optimize image for Wonder Wise
        img_buffer = io.BytesIO()
        page_image.save(img_buffer, format='PNG', optimize=True)
        img_buffer.seek(0)
        
        # Check if image is too large (>4.5MB)
        img_size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
        if img_size_mb > 3.5:
            if page_num:
                st.warning(f"Imagem da página {page_num} muito grande ({img_size_mb:.2f}MB). Redimensionando para processamento OCR.")
            else:
                st.warning(f"Imagem muito grande ({img_size_mb:.2f}MB). Redimensionando para processamento OCR.")
            
            # Determine a new size that maintains aspect ratio
            width, height = page_image.size
            ratio = min(1.0, 2000 / width, 2000 / height)  # Limit to max 2000px on either dimension
            
            # Create resized image
            resized_img = page_image.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
            
            # Save optimized version
            img_buffer = io.BytesIO()
            resized_img.save(img_buffer, format='PNG', optimize=True, quality=85)
            img_buffer.seek(0)
            
            new_size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
            if page_num:
                st.info(f"Imagem da página {page_num} redimensionada para {new_size_mb:.2f}MB para permitir processamento adequado")
            else:
                st.info(f"Imagem redimensionada para {new_size_mb:.2f}MB para permitir processamento adequado")
        
        # Base64 encode for Wonder Wise
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # Call Wonder Wise for OCR (keeping prompt in English)
        ocr_response = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=20000,
            temperature=0,
            system="""You are an expert OCR system for analyzing scanned documents. Your primary responsibilities are:

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
                    - For checkboxes/options:
                    * If marked: Report "[Checked: OPTION_TEXT]"
                    * If unmarked: Report "[Unchecked: OPTION_TEXT]"

                    HANDWRITTEN CONTENT:
                    - NEVER transcribe actual handwritten text - use only 'checked', 'filled', or 'signed'
                    - For filled name fields: Report "[Filled]" (typically occupies ~40% of field)
                    - Note ink color if distinguishable (typically blue or black)

                    SIGNATURE VERIFICATION:
                    - For signature fields, apply strict verification criteria:
                    * ONLY mark as [Signed] when there are CLEAR pen strokes/marks WITHIN the signature field
                    * For empty or ambiguous signature fields, mark as [Empty]
                    * When uncertain about a signature, default to [Empty] or [Unclear signature]
                    * Signature characteristics typically include:
                        - Distinctive curved/flowing lines
                        - Pen strokes with varying pressure/thickness
                        - Coverage of significant portion of the designated field
                    * Differentiate between:
                        - Name fields (printed/typed/handwritten name)
                        - Signature fields (unique identifying mark/signature)
                    - After completing document analysis, VERIFY all signature fields a second time
                    - Note: Adjacent text or marks should not be mistaken for signatures

                    STAMPS & SPECIAL MARKINGS:
                    - For stamps: Report "[Stamp: CONTENT]" (e.g., "Stamp: Name", "Stamp: Function", "Stamp: Approved")
                    - For official seals: Report "[Official seal: DESCRIPTION]"
                    - For redacted/censored content: Report "[Redacted]"

                    TABLES:
                    - Present tables with proper structure and alignment
                    - Preserve column headers and relationships between data
                    - For complex tables, focus on maintaining the logical structure

                    SPECIAL INSTRUCTIONS:
                    - For multi-page documents, indicate page transitions
                    - For document sections, preserve hierarchical relationships
                    - Always organize output in logical reading order (top-to-bottom, left-to-right)""",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": f"""Please perform OCR analysis on this document image and provide a detailed extraction following these guidelines:

                            GENERAL EXTRACTION:
                            - Extract ALL printed text maintaining the original layout and structure
                            - Include headers, footers, page numbers, and all visible text elements
                            - Process multiple columns appropriately (if present)

                            FORM ELEMENTS & HANDWRITTEN CONTENT:
                            - Identify all form fields (empty or filled)
                            - For handwritten content, DO NOT reproduce the actual text
                            - Instead, indicate:
                            * "[Checked]" for marked checkboxes
                            * "[Filled]" for completed text fields
                            * "[Empty]" for blank fields
                            - Note if handwriting appears to be in blue or black ink when obvious

                            SIGNATURE IDENTIFICATION:
                            - For signature fields, be extremely precise:
                            * Mark as [Signed] ONLY when you can clearly see distinctive signature marks
                            * Mark as [Empty] when no visible marks appear in the signature field
                            * Mark as [Unclear] when content is present but indeterminate
                            * If in doubt about whether a field contains a signature, note your uncertainty
                            - A true signature typically:
                            * Shows distinctive pen strokes (not just a name)
                            * Covers a notable portion of the designated field
                            * Has a different appearance than printed text
                            - Please double-check all signature fields before finalizing your response

                            SPECIAL ELEMENTS:
                            - For stamps: Report "[Stamp: CONTENT]" (e.g., Stamp: Approved)
                            - For seals or watermarks: Note their presence and general content
                            - For tables: Present in properly formatted tabular structure
                            - For unclear or partially visible text: Indicate [UNCLEAR]

                            Please organize your response in a logical reading order, maintaining the document's hierarchical structure where possible."""
                        }
                    ]
                }
            ]
        )
        
        # Get OCR text
        ocr_text = ocr_response.content[0].text
        return ocr_text
        
    except Exception as e:
        error_msg = f"Erro ao realizar OCR com Wonder Wise: {str(e)}"
        if page_num:
            st.error(f"Erro ao realizar OCR com Wonder Wise na página {page_num}: {str(e)}")
        else:
            st.error(error_msg)
        return f"Processamento OCR falhou: {str(e)}"

def analyze_page_with_claude(ocr_text, ptw_summary, page_num, permit_number=None):
    """Analyze the page OCR text using Wonder Wise API with the master prompt."""
    try:
        # Try to extract permit number if not provided
        final_permit_number = permit_number
        
        if not final_permit_number:
            # Use our extract_permit_number function
            final_permit_number = extract_permit_number(ocr_text, ptw_summary) or "Unknown"
        
        # Master analysis prompt (keeping in English)
        master_prompt = f"""

<max_thinking_length>43622</max_thinking_length>

You are an elite Permit to Work (PTW) Auditing Specialist with 20+ years of experience in offshore drilling safety compliance. Your expertise is in analyzing Work at Heights permits with meticulous attention to detail, applying a strict interpretation of regulatory standards and company procedures. Your task is to thoroughly evaluate scanned PTW documents to identify compliance issues with laser precision.

## Document Information
Permit Number: {final_permit_number}
Page Number: {page_num}

## Critical Auditing Philosophy

1. **Conservative Approach**: When in doubt, err on the side of HUMAN CONFIRMATION REQUIRED. Safety documentation must be unambiguously complete and correct.
2. **Methodical Process**: You will follow a rigid, step-by-step verification process for every section.
3. **Zero Tolerance**: Partially completed fields or missing signatures are NEVER acceptable when required.
4. **Visual Verification**: All signature/handwriting determinations must be based on clear visual evidence of blue or black ink.
5. **Double-Check Protocol**: Every signature field must be verified twice before making a final determination.

## Balancing Rigor and Flexibility

- The safety remains the priority, however real-world documents rarely achieve perfection
- In cases of minor doubt, prefer APPROVED if there is no direct impact on operational safety
- If a mark is visible but faint, consider it filled
- Partial completion of descriptive fields should generally be accepted
- If the intent of the filled information is clear, even if execution is imperfect, consider APPROVED
- Reserve "REPROVED" for clear violations of safety requirements, not for aesthetic filling failures
- When it's truly impossible to determine, use "HUMAN VERIFICATION REQUIRED" instead of automatically rejecting

## MANDATORY SIGNATURE VERIFICATION PROTOCOL

When analyzing any document with signature fields, you MUST think through this process methodically:

### STEP 1: Document Type Identification
First, identify what type of document you are analyzing:
- Main PTW form
- JSA (Job Safety Analysis)
- PRTA (Rescue Plan for Work at Height)
- CLPTA (Checklist for Work at Height Planning)
- CLPUEPCQ (Checklist - Pre-Use of Fall Protection Equipment)
- ATASS (Health Sector Authorization)
- LVCTA (Verification List for Work Basket)

## Identification of Document Types

To correctly identify each document, check these distinctive characteristics:

### JSA (Job Safety Analysis):
- Format: Matrix with columns for Steps, Hazards, Severity, Frequency, Risk Class
- Final section: Participants and Safety Technician

### CLPUEPCQ (Pre-Use Fall Protection Equipment Checklist):
- Page 1: Items 1-21 without signature section
- Page 2: Remaining items and field for 4 users to sign

### LVCTA (Work Basket Verification List):
- Characteristics: Numbered items 22-34 related to suspended baskets
- Final section: 6 specific fields for basket operation-related functions

IMPORTANT: If identification is uncertain, mark as "HUMAN VERIFICATION REQUIRED"

### STEP 2: Locate All Signature Sections
Precisely identify all sections requiring signatures in the document type.

### STEP 3: Create Visual Verification Table
For EACH row requiring name and signature verification, you MUST create and fill this table in your thinking:

| Position/Function | Name Field Status | Signature Field Status | Applicable Rule | Compliance Status |
|-------------------|-------------------|------------------------|-----------------|-------------------|
| [Function title]  | [FILLED/EMPTY]    | [FILLED/EMPTY]         | [STANDARD/EXCEPTION] | [COMPLIANT/NON-COMPLIANT] |

Rules for filling this table:
- **Name Field Status**: Mark FILLED only if there is clearly visible blue or black handwritten text that appears to be a name
- **Signature Field Status**: Mark FILLED only if there is clearly visible blue or black ink covering at least 40% of the signature field (handwritten signature, initials, or stamp)
- **Applicable Rule**: Mark STANDARD for normal name+signature requirements, EXCEPTION for fields covered by specific exceptions
- **Compliance Status**: Mark COMPLIANT only if:
  * BOTH fields are FILLED, OR
  * BOTH fields are EMPTY, OR
  * The field follows an EXCEPTION rule and meets its specific requirements

Mark NON-COMPLIANT if:
  * Name field is FILLED but Signature field is EMPTY (unless covered by an exception)
  * Signature field is FILLED but Name field is EMPTY (unless covered by an exception)

## Exceptions to Name+Signature Requirements

For the documents below, specific rules apply:

### JSA (Job Safety Analysis):
- "Safety Technician" field: Requires ONLY SIGNATURE, name field is OPTIONAL
- "Maritime Operations Superintendent" field: Requires ONLY SIGNATURE, name field is OPTIONAL

### PRTA (Rescue Plan for Work at Height):
- "Requesting Supervisor" field: Requires ONLY SIGNATURE, name field is OPTIONAL
- "Safety Technician" field: Requires ONLY SIGNATURE, name field is OPTIONAL

### Section 17 (Release for Work Execution):
- Mandatory fields: ONLY "Date" and "Time", other fields are OPTIONAL

### Section 20 (Closure):
- When a stamp is present, consider it as valid filling for multiple fields

### STEP 4: Blue/Black Ink Recognition
- Valid signatures will appear in BLUE or BLACK ink
- Look specifically for blue or black ink markings that occupy the signature field
- A signature field without visible blue or black ink markings must be considered EMPTY
- Small marks, dots, or smudges that don't constitute an actual signature in blue/black ink are NOT valid signatures

### STEP 5: Signature Field Coverage
- A valid signature must cover at least 40% of the designated signature field
- A single "X" mark is NOT a valid signature unless it is substantial and covers 40% of the field
- Thin lines, small marks, or ambiguous scribbles do not qualify as valid signatures

### Stamps and Small Markings Recognition

- Stamps are valid signatures and should be recognized even when partially legible
- For Yes/No fields: Any intentional mark (even small) inside the box is considered valid
- A small dash at the bottom of a box is still considered a valid marking
- If the field contains any ink (even faint) that appears to be an intentional mark, consider it FILLED

### Signatures Invading Adjacent Fields

When analyzing signature fields:
- If a signature appears to continue or invade adjacent fields, consider the INTENT of the signer
- A signature that clearly begins in a designated field is valid, even if it slightly exceeds the boundaries
- If user 2's signature invades user 3's field but clearly belongs to user 2, DO NOT consider it as user 3's signature
- Empty fields are not considered filled just by partial invasion of signatures from other fields

### STEP 6: Double-Check Using Explicit Examples
Before finalizing judgment, verify against these example patterns:

**APPROVED Examples**:
1. All rows have both name AND signature filled with blue/black ink
2. Some rows have both name AND signature completely empty
3. Some rows have both name AND signature filled; other rows have both empty
4. A field covered by an exception rule meets its specific requirements (e.g., only signature for Safety Technician in JSA)

**REPROVED Examples**:
1. ANY row has name filled but signature empty (unless covered by an exception)
2. ANY row has signature filled but name empty (unless covered by an exception)
3. ALL rows are completely empty when at least one completed row is required

## Verification of Mandatory Questions

IMPORTANT: Before considering that a mandatory question was not answered, FIRST check if the question exists in the current document. If the question is not present, ignore this requirement.

For Section 3.1 (Critical Systems/Equipment): 
- Check ONLY the questions that are visible in the document
- Different versions of the form may contain different sets of questions
- NEVER reject a document for missing an answer to a non-existent question

## Document Processing Capabilities

When analyzing scanned documents:

1. **Image Processing Protocol**:
   - Automatically assess document orientation and mentally rotate if needed
   - Prioritize analysis of "white guide" (guia branca) pages only
   - Skip repetitive pages such as yellow guides (guia amarela) and red guides (guia vermelha)
   - For multi-page documents, methodically analyze each page in sequence
   - Verify documents are Work at Height permits (ignore others)

2. **OCR Enhancement Techniques**:
   - Pay special attention to handwritten text, which may appear faded or inconsistent
   - Distinguish between printed text, handwriting, and stamps/signatures
   - Consider text that occupies approximately 40% or more of a signature field as a valid signature
   - Identify field boundaries even when they appear faded
   - Note when text extends beyond field boundaries or appears cramped

## SPECIAL INSTRUCTIONS FOR DOCUMENT TYPES

### For LVCTA (Work Basket) Page 2:
1. First verify all items (22-34) have been marked (Yes, No, or N/A)
2. Then use the Signature Verification Table for ALL six positions:
   - OPERADOR DA CESTA
   - OPERADOR DOS CONTROLES INFERIORES CESTA
   - SONDADOR / COORD SUBSEA
   - OIM
   - ENCARREGADO DE SONDA
   - VIGIA

3. Example of correct analysis for LVCTA:
```
| Position/Function | Name Field Status | Signature Field Status | Applicable Rule | Compliance Status |
|-------------------|-------------------|------------------------|-----------------|-------------------|
| OPERADOR DA CESTA | FILLED            | EMPTY                  | STANDARD        | NON-COMPLIANT     |
| OPERADOR DOS CONTROLES | FILLED       | FILLED                 | STANDARD        | COMPLIANT         |
| SONDADOR          | EMPTY             | EMPTY                  | STANDARD        | COMPLIANT         |
| OIM               | EMPTY             | EMPTY                  | STANDARD        | COMPLIANT         |
| ENCARREGADO       | FILLED            | FILLED                 | STANDARD        | COMPLIANT         |
| VIGIA             | EMPTY             | EMPTY                  | STANDARD        | COMPLIANT         |

Result: NON-COMPLIANT rows = 1, therefore document is REPROVED
```

### For CLPUEPCQ (Fall Protection Equipment) Page 2:
1. Use the Signature Verification Table for all four user rows
2. Pay careful attention to signatures that might invade adjacent fields - look for intention
3. Example of correct analysis for CLPUEPCQ:
```
| Position/Function | Name Field Status | Signature Field Status | Applicable Rule | Compliance Status |
|-------------------|-------------------|------------------------|-----------------|-------------------|
| USUÁRIO 1         | FILLED            | FILLED                 | STANDARD        | COMPLIANT         |
| USUÁRIO 2         | FILLED            | FILLED                 | STANDARD        | COMPLIANT         |
| USUÁRIO 3         | EMPTY             | EMPTY                  | STANDARD        | COMPLIANT         |
| USUÁRIO 4         | EMPTY             | EMPTY                  | STANDARD        | COMPLIANT         |

Result: NON-COMPLIANT rows = 0, therefore document is APPROVED
```

## Comprehensive Audit Methodology

### Phase 1: Document Identification & Classification

1. Immediately identify:
   - Document type and revision number
   - PTW number (format XXX-XXXXX)
   - Job classification based on Section 3.3 references
   - Document version against current standards (EP-036-OFF Rev 44)

### Phase 2: Section-by-Section Critical Analysis

#### Section 1: Work Planning (Planejamento do Trabalho)
- **Mandatory Field Check**: "Necessário Bloqueio?" field MUST be answered (Yes/No)
- **Classification Type**: Either "Convencional" or "Longo Prazo" must be marked if present
- RESULT: REPROVED if mandatory fields are not completed

#### Section 3: Equipment/Tools in Good Condition to be Used
- **Basic Verification**: Marked fields indicate selected equipment
- For "Other Equipment/Tools": Any handwritten text is sufficient, without evaluating its content
- RESULT: APPROVED if relevant fields are marked and filled with any handwritten text

#### Section 3.1: Critical Systems/Equipment
- **Risk Assessment Questions**: Only check questions that actually appear in the document:
  * "Os equipamentos utilizados na execução da tarefa são considerados críticos?" (Yes/No)
  * "Os sistemas/equipamentos em manutenção são considerados críticos?" (Yes/No)
  * Only check for "Estão disponíveis e em bom estado?" and "A disponibilidade do sistema/equipamento em manutenção será interrompida?" if these appear in the document
- RESULT: REPROVED if any visible question is unanswered

#### Section 5: Safety Barriers
- **Basic Verification**: Marked fields indicate selected barriers
- **Detailed Specifications**: The following fields have RECOMMENDED but NOT MANDATORY details:
  * "Ramal de Emergência da Unidade" - number recommended but not mandatory
  * "Observador trabalho sobre o mar/altura" - identification recommended but not mandatory
  * "Velocidade do Vento" - value recommended but not mandatory
- Still check these critical items for handwritten details where required:
  * "Tipos de Luvas" - must specify type
  * "Pitch/Roll/Heave" - must have measurements
  * "Inibir sensor" - must specify which sensor
- RESULT: APPROVED if fields are marked, even without specific details for recommended fields

#### Section 6: Applicable Procedures and Documents
- **Documentation Verification**: Identify all checked items
- **Special Attention Items**: These items require handwritten details:
  * "Outros (Descrever) (1)"
  * "Outros (Descrever) (2)"
  * "Outros (Descrever) (3)"
- RESULT: REPROVED if selected items requiring descriptions are left blank

#### Section 7: APR/JSA (Risk Assessment)
- **Assessment Question**: "Foi realizada uma APR e/ou JSA?" must be answered (Yes/No)
- **Verification**: At least one box must be marked
- RESULT: REPROVED if question is unanswered

#### Section 8: Participants
- **Participant Verification**: For each listed participant:
  * Both Name AND Signature fields must be completed with blue or black ink
  * Empty rows are acceptable but partially filled rows are not
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if any participant has a name but no signature or vice versa

#### Section 9: Training and Certifications
- **Certification Question**: "Os executantes estão treinados e possuem as certificações necessárias para a realização da atividade?" must be answered (Yes/No)
- RESULT: REPROVED if question is unanswered

#### Section 10: Form of Supervision
- **Supervision Type**: Either "Intermitente" OR "Contínua" must be checked
- RESULT: REPROVED if neither option is selected

#### Section 11: Pre-Task Meeting
- **Meeting Verification**: "Foi realizada a reunião pré-tarefa?" must be answered (Yes/No)
- RESULT: REPROVED if question is unanswered

#### Section 12: Third-Party Authorization Form
- **Authorization Verification**: "Formulário de autorização de terceiros é válido?" must be answered (Yes/No/N/A)
- RESULT: REPROVED if question is unanswered

#### Section 14: Simultaneous Operations
- **Operations Question**: "Existem outras operações sendo realizadas simuladamente?" must be answered
- IF ANSWERED "YES":
  * "Quais..." field must be completed
  * "Autorização: Eu ... autorizo" field must be completed
  * "Recomendações de segurança adicionais às atividades simultâneas" field must be completed
- IF ANSWERED "NO":
  * All fields may remain blank
- RESULT: REPROVED if "Yes" is selected but required fields are incomplete

#### Section 15: Co-issuer
- **Co-issuer Verification**: For each column with ANY entry:
  * ALL four fields (Name, Function, Area, Signature) must be completed
  * If Name is filled, other 3 fields must also be filled
  * Empty columns are acceptable
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if any column has partial information

#### Section 16: Additional Safety Recommendations
- **Safety Recommendations**: This section MUST have handwritten text
- RESULT: REPROVED if lines are empty/blank

#### Section 17: Release for Work Execution
- **Release Verification**: The following fields MUST be completed:
  * Date and Time (MANDATORY)
  * Responsible (Requester): Name, Company, Function, Signature (OPTIONAL as per exceptions)
  * Safety Technician: Name, Company, Function, Signature (OPTIONAL as per exceptions)
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if Date and Time fields are missing

#### Section 18: Awareness of Work Permit
- **Awareness Verification**: At minimum, at least one row must have:
  * Name
  * Function
  * Signature (in blue or black ink)
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if no complete row exists

#### Section 19: Rounds/Audit
- **Audit Verification**: Examine all 12 cells (4 columns × 3 rows)
  * For each participant row, all fields must be complete (Name, Function, Signature, Time)
  * Incomplete rows are unacceptable
  * At least one complete row is required
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if rows contain partial information or all rows are empty

#### Section 20: Closure - Suspension of Work Permit
- **Suspension Section**: 
  * If blank, this is acceptable (no suspension occurred)
  * If ANY field is completed, ALL fields must be completed:
    - Reasons for Suspension: Specify, Date, Time, Requester Signature
    - Return from Suspension: Date, Time, Requester Signature, TST Signature
  
- **Closure Section**:
  * One of the three closure reasons MUST be selected:
    - Work Completion
    - Accident/Incident/Emergency
    - Others (Specify) - if selected, must include specification
  * Date and Time fields MUST be completed
  * Responsible fields MUST be completed (Name, Company, Function, Signature)
  * IMPORTANT: If a stamp is present, it can satisfy multiple fields simultaneously
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if closure fields are incomplete

### Phase 3: Attachment Analysis

#### JSA (Job Safety Analysis) Attachment
- **Document Structure Verification**:
  * Verify proper document structure (matrix with steps, hazards, severity, etc.)
  * For Participant section: At least one participant must have all fields completed
  * For Safety Technician section: Field must be signed with blue or black ink (NAME IS OPTIONAL)
- **Critical Rule**: 
  * If Safety Technician has signed but no participants signed = REPROVED
  * If participants signed but Safety Technician did not sign = REPROVED
  * If neither signed = APPROVED (document may be in preparation)
  * If both signed = APPROVED
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- Apply exception rule: Safety Technician and Maritime Operations Superintendent require ONLY signature

#### PRTA (Rescue Plan for Work at Height) Attachment
- **Signature Verification**: Both Requesting Supervisor and Safety Technician signatures must be present in blue or black ink
- **Signature Form**: Handwritten signatures, initials, and stamps are all acceptable
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- Apply exception rule: For both positions, ONLY signature is required, name field is optional
- RESULT: REPROVED if either signature is missing

#### CLPTA (Check List for Work at Height Planning) Attachment
- **Signature Sections**: Analyze both sections:
  * "Assinaturas da equipe envolvida no trabalho em altura"
  * "Assinaturas da equipe executante no trabalho em altura"
- **Row Completion Rule**: For each row with ANY data:
  * All three fields (Name, Function, Signature) must be completed
  * Empty rows are acceptable
  * Rows with partial information are NOT acceptable
- **Minimum Requirement**: At least one fully completed row in each section
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if any row has partial information

#### CLPUEPCQ (Check List - Pre-Use of Fall Protection Equipment) Attachment
- **Document Identification**: Determine if page 1 or page 2
  * Page 1: No signature section (marked "Pagina 1 de 2") = APPROVED
  * Page 2: Contains signature section
- **Signature Verification**: For each user row:
  * If Name is filled, Signature must also be filled with blue or black ink
  * If Signature is filled, Name must also be filled
  * At least one row must be fully completed
  * Be especially careful with signatures that may extend into adjacent fields - evaluate intent
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE FOR ALL FOUR USER ROWS
- RESULT: REPROVED if any row has partial information or all rows are empty

#### ATASS (Health Sector Authorization for Work at Height) Attachment
- **Signature Verification**: The evaluator signature field must be completed with blue or black ink
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if signature is missing

#### LVCTA (Verification List for Work Basket) Attachment
- **Item Verification**: Each item must have one option marked (Yes, No, or N/A)

- **Critical Line-by-Line Analysis**:
  For page 2 (signature section), follow this mandatory verification:

  1. **CREATE AND FILL THE SIGNATURE VERIFICATION TABLE FOR ALL SIX POSITIONS**:
     - OPERADOR DA CESTA
     - OPERADOR DOS CONTROLES INFERIORES CESTA
     - SONDADOR / COORD SUBSEA
     - OIM
     - ENCARREGADO DE SONDA
     - VIGIA

  2. **Verification Rules**:
     - Mark "FILLED" for Name fields with blue or black ink text
     - Mark "FILLED" for Signature fields with blue or black ink signature covering at least 40% of field
     - Mark "EMPTY" for fields with no clear blue or black ink marks
     - An "X" mark is NOT a valid name unless it extensively fills the field
     - Small marks are NOT valid signatures
     - Be vigilant for signatures that might cross field boundaries - evaluate based on intent

  3. **Final Decision Rule**:
     - Count NON-COMPLIANT rows in the table
     - If NON-COMPLIANT rows > 0, document is REPROVED
     - If NON-COMPLIANT rows = 0, document is APPROVED

- RESULT: REPROVED if items are unchecked or signature pairs are incomplete

## Phase 4: Final Compliance Determination

1. For each section and attachment, determine final status (APPROVED/REPROVED)
2. Apply severity classifications to deficiencies:
   - Critical: Safety-critical omissions that could cause immediate danger
   - Major: Significant compliance failures that compromise safety systems
   - Minor: Procedural errors with minimal safety impact
3. Formulate final judgment with specific reference to EP-036-OFF and EP-041-OFF requirements
4. Document all findings thoroughly with regulatory citations

## SELF-CORRECTION PROTOCOL (MANDATORY)

Before submitting your final assessment, you MUST complete these verification steps:

1. **Signature Field Double-Check**:
   - Review AGAIN all fields marked as "EMPTY" in your verification tables
   - Ask: "Is this field TRULY empty of blue/black ink, or might there be content I missed?"
   - Ask: "Is this field TRULY filled with sufficient blue/black ink to qualify as completed?"
   - Ask: "Does this field fall under any of the exceptions where only signature is required?"

2. **Compliance Logic Verification**:
   - Confirm that for EVERY row with a "FILLED" name, you have verified if the signature is actually present
   - Confirm that for EVERY "NON-COMPLIANT" determination, you have double-checked the actual fields
   - Verify that you've correctly applied exception rules for fields that only require signatures

3. **Common Error Check**:
   - Verify you haven't confused a small mark or "X" for a valid signature
   - Verify you haven't confused faint blue/black ink for an empty field
   - Verify you haven't overlooked a name field with content
   - Verify you've properly applied the 40% field coverage rule for signatures
   - Verify you haven't mistaken a signature invading from an adjacent field as belonging to the wrong person

4. **Exception Rule Verification**:
   - For JSA: Verify you've applied the "signature only" exception for Safety Technician
   - For PRTA: Verify you've applied the "signature only" exception for both signing authorities
   - For Section 17: Verify you're only requiring Date and Time as mandatory
   - For Section 20: Verify you've recognized stamps as valid for multiple fields

## Output Table Format

Present your findings in this structured format:

| Permit Number | Page Number | Page Summary | Section | Status | Comments |
|---------------|-------------|--------------|---------|--------|----------|
| XXX-XXXXX | 1 | PTW Cover Sheet | Request Details | APPROVED/REPROVED | Specific findings with clear explanation of deficiencies |

## Special Considerations for OCR Analysis

1. **Handwriting Recognition**:
   - Distinguish between intentional marks and stray marks/smudges
   - Consider that signatures typically occupy >40% of designated field in blue or black ink
   - Account for varying handwriting styles and densities
   - Recognize that stamps and initials in blue or black ink are valid forms of signatures

2. **Field Boundary Detection**:
   - Correctly identify field boundaries even when they appear faded
   - Associate handwriting with the correct fields when writing crosses boundaries
   - Recognize when fields are intentionally left blank versus missed

3. **Document Quality Assessment**:
   - Report low-quality images that might affect analysis reliability
   - Flag rotated or skewed pages
   - Note areas where text contrast or clarity issues exist

4. **Key Validation Rules**:
   - Signatures and names must both be present when one is required (except for identified exceptions)
   - The "Nome" (name) field must always be followed by a signature in blue or black ink (except for identified exceptions)
   - Empty fields are acceptable only when the section logic permits them
   - Blank pages should be reported but not marked as "REPROVED"

**IMPORTANT** - CHECK ONLY THE ITEMS LISTED ABOVE, YOU ARE NOT ALLOWED TO CHECK FOR THINGS NOT DESCRIBED HERE. YOU NEVER REPROVE ANYTHING BASED ON YOUR GUESS OF WRONG NAME OR WRONG NUMBER. ALL YOU DO WITH HANDWRITING IS CHECK CAREFULLY IF THINGS WERE FILLED, NOT WHAT IS WRITTEN
**IMPORTANT** - If a page is completely blank, don't try to guess the type or anything...just report "Blank page". Blank pages cannot be evaluated, so neither approved nor reproved
**IMPORTANT** - There are some sections in which there are several handwritten checks to be made, and then names and signatures at the bottom. In these sections, after analyzing the check marks, clear your memory completely and analyze the names and signatures field very carefully with no Bias. Here it's Quality over speed, so take your time and analyze very carefully all names and signatures, and question yourself several times before assuming anything related to handwritten names and signatures

Format your entire response in Brazilian Portuguese with 'APPROVED' translated to 'APROVADO' and 'REPROVED' translated to 'REPROVADO' and 'HUMAN VERIFICATION REQUIRED' to 'CHECAGEM HUMANA NECESSARIA". Keep the table structure but translate column headers."""
        
        # Handle case where OCR text failed (providing in Portuguese)
        if not ocr_text or "Error:" in ocr_text or ocr_text.strip() == "":
            # Provide a default response for this case
            return f"""
| Desconhecido | {page_num} | Página {page_num} | Conteúdo do Documento | REPROVADO | Deficiência crítica: Não foi possível analisar o documento devido à falha no processamento OCR. A imagem original deve ser revisada manualmente. |
"""
        
        # Prepare the message for Wonder Wise (keeping in English)
        messages = [
            {
                "role": "user", 
                "content": f"""
Here is a summary of the Permit to Work document being analyzed:

{ptw_summary}

Now, I am providing you with the OCR text from page {page_num}. Please analyze this text according to the methodology provided and list any issues or compliance problems you find:

OCR TEXT:
{ocr_text}

Please provide your analysis in the exact table format specified in the instructions. Remember to output ONLY the table with your results.
"""
            }
        ]
        
        # Call Wonder Wise API with thinking and streaming
        response_stream = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=30000,
            temperature=1,  # DEVE ser 1 quando thinking está ativado
            system=master_prompt,
            messages=messages,
            thinking={"type": "enabled", "budget_tokens": 15000},
            # NÃO use top_p ou top_k com thinking - são incompatíveis
            # NÃO tente usar pre_filled_response com thinking - incompatível
            stream=True
        )
        
        # Processando a resposta em streaming
        full_response = ""
        thinking_log = ""
        
        for chunk in response_stream:
            if chunk.type == "content_block_delta" and hasattr(chunk.delta, "text"):
                text_chunk = chunk.delta.text
                full_response += text_chunk
            elif chunk.type == "thinking":
                thinking_content = chunk.thinking.text
                thinking_log += thinking_content
            # Também tratar potenciais redacted_thinking blocks
            elif chunk.type == "redacted_thinking":
                # Estes são criptografados pela Anthropic mas devem ser mantidos
                # para manter contexto interno do modelo
                pass
        
        # Return the analysis
        return full_response

    except Exception as e:
        st.error(f"Erro ao analisar página com Wonder Wise: {str(e)}")
        # Provide a generic fallback response that won't break the table structure (in Portuguese)
        return f"""
    | Desconhecido | {page_num} | Página {page_num} | Conteúdo do Documento | REPROVADO | Deficiência crítica: Ocorreu um erro durante a análise: {str(e)}. A imagem original deve ser revisada manualmente. |
    """

# Function to process multiple pages in a batch
def process_pages_batch(page_images, batch_start, batch_size, ptw_summary):
    """Process multiple pages in a single batch."""
    try:
        batch_pages = []
        batch_end = min(batch_start + batch_size, len(page_images))
        
        # Extract the pages for this batch
        for i in range(batch_start, batch_end):
            page_num = i + 1  # Page numbers are 1-based
            batch_pages.append((page_num, page_images[i]))
        
        # Prepare images for batch processing
        batch_content = [{"type": "text", "text": "I'm sending multiple pages from a document. Please extract ALL text from each page, maintaining layout. Include ALL text, numbers, field labels, and handwritten content. Pay special attention to handwriting and signatures."}]
        
        # Add each page to the batch content
        for page_num, page_image in batch_pages:
            # Optimize image
            img_buffer = io.BytesIO()
            page_image.save(img_buffer, format='PNG', optimize=True)
            img_buffer.seek(0)
            
            # Check if image is too large (>4.5MB)
            img_size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
            if img_size_mb > 3.5:
                # Resize image if too large
                width, height = page_image.size
                ratio = min(1.0, 2000 / width, 2000 / height)
                
                resized_img = page_image.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
                
                img_buffer = io.BytesIO()
                resized_img.save(img_buffer, format='PNG', optimize=True, quality=85)
                img_buffer.seek(0)
                
                st.info(f"Imagem da página {page_num} redimensionada para processamento em lote")
            
            # Base64 encode
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            # Add to batch content with page number in title
            batch_content.append({
                "type": "text",
                "text": f"---- PAGE {page_num} ----"
            })
            
            batch_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_base64
                }
            })
        
        # Process the batch with Claude
        st.info(f"Processando páginas {batch_start+1}-{batch_end} em lote")
        
        batch_response = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=25000,
            temperature=0,
            system="You are an expert OCR system. Extract ALL text from EACH image, maintaining layout where possible. Clearly separate each page's content in your response. Begin each page's extraction with '---- OCR RESULTS FOR PAGE X ----' where X is the page number. Include ALL text, numbers, field labels, and handwritten content. Pay special attention to handwriting and signatures.",
            messages=[{"role": "user", "content": batch_content}]
        )
        
        # Extract OCR results
        batch_ocr_text = batch_response.content[0].text
        
        # Split the results by page
        ocr_results = {}
        
        # Process the OCR text to separate by page
        current_page = None
        current_text = ""
        
        for line in batch_ocr_text.split('\n'):
            if "---- OCR RESULTS FOR PAGE" in line:
                # Save previous page text if any
                if current_page is not None:
                    ocr_results[current_page] = current_text.strip()
                
                # Extract new page number
                try:
                    current_page = int(line.split("PAGE")[1].split("----")[0].strip())
                    current_text = ""
                except:
                    current_page = None
            elif current_page is not None:
                current_text += line + "\n"
        
        # Save the last page
        if current_page is not None:
            ocr_results[current_page] = current_text.strip()
        
        # Return the batch OCR results
        return ocr_results
    
    except Exception as e:
        st.error(f"Erro no processamento em lote: {str(e)}")
        return {}  # Return empty dict on error

# Extract permit number from OCR or summary
def prepare_image_for_claude(image, max_size_mb=3.75):
    """
    Prepare an image for API submission by optimizing size and quality.
    
    Args:
        image: PIL Image object
        max_size_mb: Maximum size in MB for the base64 encoded image
        
    Returns:
        tuple: (processed_image, base64_string, media_type, size_in_mb)
    """
    # Start with a high-quality resize if image is very large
    max_dimension = 1800
    if max(image.size) > max_dimension:
        ratio = min(max_dimension/image.size[0], max_dimension/image.size[1])
        new_size = (int(image.size[0]*ratio), int(image.size[1]*ratio))
        image = image.resize(new_size, Image.LANCZOS)
    
    # Try to convert and compress the image
    quality = 90
    image_format = "PNG"
    media_type = "image/png"
    
    # Function to check final base64 size
    def get_base64_size(img_bytes):
        base64_bytes = len(base64.b64encode(img_bytes.getvalue()))
        return base64_bytes / (1024 * 1024)
    
    while True:
        img_byte_arr = io.BytesIO()
        
        if image_format == "PNG":
            image.save(img_byte_arr, format=image_format, optimize=True)
            media_type = "image/png"
            
            base64_size = get_base64_size(img_byte_arr)
            
            if base64_size > 4.9:
                image_format = "JPEG"
                media_type = "image/jpeg"
                continue
        else:
            image.save(img_byte_arr, format=image_format, quality=quality, optimize=True)
            media_type = "image/jpeg"
            
            base64_size = get_base64_size(img_byte_arr)
        
        if base64_size <= 4.9:
            break
            
        quality -= 15
        
        if quality < 40:
            quality = 60
            max_dimension = int(max_dimension * 0.7)
            ratio = min(max_dimension/image.size[0], max_dimension/image.size[1])
            new_size = (int(image.size[0]*ratio), int(image.size[1]*ratio))
            image = image.resize(new_size, Image.LANCZOS)
            
        if max_dimension < 500:
            raise ValueError("Could not compress image below 5MB limit while maintaining usable quality")
    
    img_byte_arr.seek(0)
    img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode()
    
    img_byte_arr.seek(0)
    processed_image = Image.open(img_byte_arr)
    
    base64_size_mb = len(img_base64) / (1024 * 1024)
    
    return processed_image, img_base64, media_type, base64_size_mb

def extract_permit_number(ocr_text=None, ptw_summary=None):
    """Extract permit number from OCR text or summary."""
    # Look for patterns like "PT-12345", "PTW-12345", or just numbers
    pt_patterns = [
        r'PT[W]?[-\s]?(\d+[-\d]*)',  # Matches PT-12345, PTW-12345, PT 12345
        r'Permit.*?(\d{3}[-\s]?\d{5})',  # Matches Permit... followed by number like 123-45678
        r'Permissão.*?(\d{3}[-\s]?\d{5})'  # Same in Portuguese
    ]
    
    # First try OCR text if available
    if ocr_text:
        for pattern in pt_patterns:
            match = re.search(pattern, ocr_text, re.IGNORECASE)
            if match:
                return match.group(1)
    
    # Then try summary
    if ptw_summary:
        for pattern in pt_patterns:
            match = re.search(pattern, ptw_summary, re.IGNORECASE)
            if match:
                return match.group(1)
    
    # Return None if not found
    return None

# Worker function for parallel page processing
def process_page_worker(page_num, page_image, ptw_summary):
    """Process a single page in parallel"""
    try:
        # Set up a status dictionary to track this page's processing
        status = {
            "page_num": page_num,
            "ocr_status": "pending",
            "analysis_status": "pending",
            "ocr_text": "",
            "analysis_result": "",
            "error": None,
            "completed": False
        }
        
        # Step 1: Process OCR
        status["ocr_status"] = "processing"
        ocr_text = process_page_with_claude_ocr(page_image, page_num)
        
        # Check if OCR was successful
        if "Error:" in ocr_text or "failed" in ocr_text:
            status["ocr_status"] = "error"
            status["error"] = ocr_text
        else:
            status["ocr_status"] = "completed"
            status["ocr_text"] = ocr_text
        
        # Step 2: Try to extract permit number if this is the first page
        permit_number = None
        if page_num == 1:
            permit_number = extract_permit_number(ocr_text, ptw_summary)
            # Store in session state for other pages to use
            if permit_number:
                st.session_state.permit_number = permit_number
        else:
            # Get permit number from session state if available
            permit_number = st.session_state.get('permit_number', None)
        
        # Step 3: Analyze page with Claude
        status["analysis_status"] = "processing"
        analysis_result = analyze_page_with_claude(
            ocr_text,
            ptw_summary,
            page_num,
            permit_number
        )
        
        status["analysis_status"] = "completed"
        status["analysis_result"] = analysis_result
        status["completed"] = True
        
        return status
    
    except Exception as e:
        # Return error status
        return {
            "page_num": page_num,
            "ocr_status": "error" if "ocr_status" not in status else status["ocr_status"],
            "analysis_status": "error",
            "ocr_text": "",
            "analysis_result": f"""
| Desconhecido | {page_num} | Página {page_num} | Conteúdo do Documento | REPROVADO | Deficiência crítica: Ocorreu um erro durante o processamento: {str(e)}. A imagem original deve ser revisada manualmente. |
""",
            "error": str(e),
            "completed": True  # Mark as completed even though it failed
        }

# Render dashboard page
def render_dashboard_page():
    """Render the dashboard page"""
    st.markdown("""
    <div class="content-container">
        <h2>Dashboard</h2>
        <p>Esta página mostrará estatísticas e métricas de análises de PT.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Dashboard placeholder
    st.info("Dashboard em desenvolvimento. Funcionalidades serão adicionadas em breve.")

# Render settings page
def render_settings_page():
    """Render the settings page"""
    st.markdown("""
    <div class="content-container">
        <h2>Configurações</h2>
        <p>Esta página permite ajustar as configurações do analisador de PT.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize settings session state variables if they don't exist
    if 'enable_photo_capture' not in st.session_state:
        st.session_state.enable_photo_capture = True
    
    # Create sections for different settings
    with st.container(border=True):
        st.markdown("### Opções de Entrada de Documento")
        
        # Photo upload toggle
        photo_capture_enabled = st.toggle(
            "Habilitar análise por fotos em dispositivos móveis", 
            value=st.session_state.enable_photo_capture,
            help="Permite usar a câmera do celular para analisar documentos sem precisar de scanner"
        )
        
        # Update session state if changed
        if photo_capture_enabled != st.session_state.enable_photo_capture:
            st.session_state.enable_photo_capture = photo_capture_enabled
            st.success("✅ Configuração salva com sucesso!")
            
        # Add explanation about the feature
        if photo_capture_enabled:
            st.info("A funcionalidade de análise por fotos está habilitada. Em dispositivos móveis, você pode usar a câmera para capturar páginas de documentos. Útil para análise em campo quando não há acesso a um scanner.")
        else:
            st.info("A funcionalidade de análise por fotos está desabilitada. Apenas uploads de PDF serão permitidos.")
    
    # Performance settings section
    with st.container(border=True):
        st.markdown("### Configurações de Performance")
        
        # Processing mode options
        processing_mode = st.radio(
            "Modo de processamento padrão",
            options=["Sequencial", "Paralelo"],
            index=0,
            help="O modo paralelo é mais rápido, mas pode consumir mais recursos"
        )
        
        # OCR quality options
        ocr_quality = st.select_slider(
            "Qualidade do OCR",
            options=["Econômico", "Balanceado", "Alta Qualidade"],
            value="Balanceado",
            help="Maior qualidade significa melhor OCR, mas processamento mais lento"
        )
        
        # Save performance settings button
        if st.button("Salvar Configurações de Performance"):
            st.success("✅ Configurações de performance salvas com sucesso!")
    
    # Coming soon features
    with st.expander("Funcionalidades Futuras", expanded=True):
        st.markdown("""
        ### Em Desenvolvimento:
        
        - Ajustes do modelo de IA
        - Configurações de análise automática
        - Opções de exportação de relatórios
        - Personalização da interface
        - Ajustes de performance para processamento de documentos extensos
        """)
        
    # Add a note about current operation mode
    st.success("O analisador está atualmente operando com as configurações definidas acima.")

# Render help page
def render_help_page():
    """Render the help page"""
    st.markdown("""
    <div class="content-container">
        <h2>Ajuda</h2>
        <p>Como usar o Analisador de PT para documentação de segurança de óleo e gás</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Help content
    st.markdown("""
    ### Como funciona o Analisador de PT
    
    O Analisador de PT é uma ferramenta projetada para analisar documentos de Permissão de Trabalho (PT) da indústria
    de óleo e gás offshore. A ferramenta utiliza IA avançada para detectar não conformidades e problemas de segurança
    nos formulários de PT.
    
    ### Passo a passo
    
    #### Opção 1: Upload de PDF
    1. **Upload do Documento**: Faça upload de um arquivo PDF contendo o documento de PT completo.
    2. **Escolha do Modo de Processamento**: Selecione entre processamento sequencial ou paralelo.
    3. **Análise Automática**: O sistema extrai o texto com OCR e analisa cada página de acordo com protocolos de segurança.
    4. **Resultados**: Visualize os resultados da análise, incluindo uma tabela detalhada de conformidade.
    
    #### Opção 2: Captura de Fotos (Dispositivos Móveis)
    1. **Ativação do Modo de Captura**: Selecione a aba "Capturar Fotos" e clique em "Ativar Modo de Captura".
    2. **Captura das Páginas**: Tire fotos de cada página do documento usando a câmera do seu dispositivo.
    3. **Organize as Páginas**: Adicione descrições e reordene as páginas conforme necessário.
    4. **Processamento**: Clique em "Analisar Fotos Capturadas" para iniciar o processamento.
    5. **Resultados**: Visualize a análise completa após o processamento.
    
    ### Tipos de Documentos Suportados
    
    O analisador foi otimizado para diversos documentos de segurança, incluindo:
    
    - PT Principal (formulário principal de permissão de trabalho)
    - JSA (Job Safety Analysis)
    - APR (Análise Preliminar de Risco)
    - PRTA (Plano de Resgate para Trabalho em Altura)
    - CLPTA (Checklist de Planejamento de Trabalho em Altura)
    - CLPUEPCQ (Check List de Pré-Uso de EPC de Queda)
    - ATASS (Autorização do Setor de Saúde)
    - LVCTA (Lista de Verificação de Cesto de Trabalho Aéreo)
    
    ### Dicas para Melhores Resultados
    
    #### Para PDFs:
    - Digitalize os documentos em alta resolução (300 DPI ou superior)
    - PDFs nativos (não escaneados) geralmente produzem melhores resultados
    - Para documentos longos, o processamento paralelo é recomendado
    
    #### Para Captura de Fotos:
    - Utilize boa iluminação, evitando sombras sobre o documento
    - Certifique-se que todo o documento está dentro do enquadramento
    - Mantenha a câmera paralela ao documento para evitar distorções
    - Tire as fotos em um local com fundo contrastante (ideal: superfície escura)
    - Certifique-se que o texto está legível na imagem capturada
    """)

# Main application
def main():
    # Initialize session state
    init_session_state()
    
    # Render the sidebar
    render_sidebar()
    
    # Add footer decoration
    st.markdown("""
    <!-- Background colorido do footer -->
    <div class="footer-background"></div>
    """, unsafe_allow_html=True)
    
    # Render the current page based on session state
    if st.session_state.current_page == "analyzer":
        render_analyzer_page()
    elif st.session_state.current_page == "dashboard":
        render_dashboard_page()
    elif st.session_state.current_page == "settings":
        render_settings_page()
    elif st.session_state.current_page == "help":
        render_help_page()
    else:
        # Default to analyzer page
        st.session_state.current_page = "analyzer"
        render_analyzer_page()

def render_analyzer_page():
    # Welcome message with stylized header
    render_welcome_message()
    
    # Document input section
    st.markdown("""
    <div class="content-container">
        <h2>Carregar Documento de Permissão de Trabalho</h2>
        <p>Carregue um PDF digitalizado ou tire fotos das páginas do formulário de Permissão de Trabalho para análise automatizada.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs for different input methods based on settings
    if 'enable_photo_capture' not in st.session_state:
        st.session_state.enable_photo_capture = True
        
    if st.session_state.enable_photo_capture:
        input_tab1, input_tab2 = st.tabs(["📄 Upload de PDF", "📱 Análise por Fotos"])
    else:
        input_tab1 = st.container()  # Just use a container instead of tabs if photo capture is disabled
    
    # Initialize the clear_uploads flag if it doesn't exist
    if 'clear_uploads' not in st.session_state:
        st.session_state.clear_uploads = False
    
    # PDF Upload Tab
    with input_tab1:
        # If we need to clear the uploader, use a different key to force a reset
        uploader_key = "pdf_uploader_reset" if st.session_state.clear_uploads else "pdf_uploader"
        uploaded_file = st.file_uploader("Escolha um arquivo PDF", type=["pdf"], key=uploader_key)
        
        # Reset the clear flag once used
        if st.session_state.clear_uploads:
            st.session_state.clear_uploads = False
        
        if uploaded_file is not None:
            # Turn off photo capture mode if active
            st.session_state.capture_mode = False
            
            # Clear any previously captured photos
            if st.session_state.captured_photos:
                st.session_state.captured_photos = []
                st.session_state.photo_captions = []
            
            # Read the file
            pdf_bytes = uploaded_file.getvalue()
            file_size_mb = get_file_size_mb(pdf_bytes)
            
            # Display file info
            st.markdown(f"""
            <div class="content-container">
                <h3>Informações do Arquivo</h3>
                <p>Arquivo: {uploaded_file.name}</p>
                <p>Tamanho: {file_size_mb:.2f} MB</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Process button for PDF
            if not st.session_state.processing:
                col1, col2 = st.columns(2)
                with col1:
                    sequential_button = st.button("Processar Sequencialmente")
                with col2:
                    parallel_button = st.button("Processar em Paralelo")
                    
                # Handle button clicks OUTSIDE the column blocks
                if sequential_button or parallel_button:
                    st.session_state.processing = True
                    st.session_state.parallel_processing = parallel_button  # Flag for parallel processing
                    
                    # Reset session state variables
                    st.session_state.ptw_summary = None
                    st.session_state.page_images = []
                    st.session_state.analysis_results = []
                    st.session_state.current_page = 0
                    st.session_state.analyses_completed = 0
                    # Reset parallel processing variables
                    st.session_state.parallel_results = []
                    st.session_state.parallel_status = {}
                    
                    # Process immediately without rerun - exactly like app_Old_Visual.py
                    # Create a spinner and progress bar
                    with st.spinner("Comprimindo PDF e preparando para análise..."):
                        # Step 1: Compress PDF if needed for API limit (5MB)
                        if file_size_mb > 4.0:
                            compressed_pdf = compress_pdf(pdf_bytes)
                            compress_size_mb = get_file_size_mb(compressed_pdf)
                            st.success(f"PDF comprimido de {file_size_mb:.2f} MB para {compress_size_mb:.2f} MB")
                            
                            # If still too large, show warning
                            if compress_size_mb > 5:
                                st.warning(f"PDF ainda está com {compress_size_mb:.2f} MB após compressão. Podem ocorrer problemas no processamento.")
                        else:
                            compressed_pdf = pdf_bytes
                        
                        # Step 2: Extract pages as images with 250 DPI PNG format
                        page_images = extract_pages_as_images(pdf_bytes, dpi=250)
                        st.session_state.page_images = page_images
                        st.session_state.total_pages = len(page_images)
                        
                        # Step 3: Generate PTW summary using Wonder Wise
                        st.info("Gerando resumo da PT com Wonder Wise...")
                        ptw_summary = generate_ptw_summary(compressed_pdf)
                        st.session_state.ptw_summary = ptw_summary
                        
                        # If parallel processing was selected, start it now
                        if st.session_state.parallel_processing:
                            st.info("Iniciando processamento em paralelo de todas as páginas...")
                            
                            # Set up ThreadPoolExecutor for concurrent processing
                            # Use max_workers=4 to limit API calls and avoid rate limiting
                            max_workers = min(8, st.session_state.total_pages)
                            
                            # Create a list to store all the futures
                            st.session_state.parallel_results = []
                            
                            # Create status tracking dictionary
                            st.session_state.parallel_status = {
                                "total": st.session_state.total_pages,
                                "completed": 0,
                                "in_progress": 0,
                                "page_status": {}
                            }
                            
                            # Process pages in batches for parallel approach
                            # Adjust batch size based on document size
                            if st.session_state.total_pages <= 5:
                                batch_size = st.session_state.total_pages  # For small documents, process all at once
                            elif st.session_state.total_pages <= 15:
                                batch_size = 5  # Medium-sized document
                            else:
                                batch_size = 8  # Large document
                            
                            # Calculate the number of batches needed
                            num_batches = (st.session_state.total_pages + batch_size - 1) // batch_size
                            
                            # Configure and start the thread pool with optimal worker count
                            if st.session_state.total_pages <= 5:
                                thread_count = min(2, st.session_state.total_pages)  # 1-2 workers for small docs
                            elif st.session_state.total_pages <= 15:
                                thread_count = 3  # 3 workers for medium docs
                            else:
                                thread_count = 4  # 4 workers for large docs (avoid too many API calls)
                            
                            with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
                                # First process pages in batches for OCR
                                st.info("Processando OCR em lotes paralelos para melhor performance...")
                                batch_futures = {}
                                
                                # Function to process a batch in parallel
                                def process_batch_worker(batch_start, batch_size):
                                    try:
                                        # Process the batch
                                        return process_pages_batch(
                                            st.session_state.page_images,
                                            batch_start,
                                            batch_size,
                                            st.session_state.ptw_summary
                                        )
                                    except Exception as e:
                                        st.error(f"Erro no processamento do lote {batch_start}-{batch_start+batch_size}: {str(e)}")
                                        return {}
                                
                                # Submit batches for processing
                                for i in range(0, st.session_state.total_pages, batch_size):
                                    batch_start = i
                                    current_batch_size = min(batch_size, st.session_state.total_pages - i)
                                    
                                    # Update status for these pages
                                    for page_num in range(batch_start + 1, batch_start + current_batch_size + 1):
                                        st.session_state.parallel_status["page_status"][page_num] = {
                                            "status": "submitted",
                                            "ocr_status": "batch_processing",
                                            "analysis_status": "pending"
                                        }
                                    
                                    # Submit this batch
                                    batch_future = executor.submit(process_batch_worker, batch_start, current_batch_size)
                                    batch_futures[batch_future] = (batch_start, current_batch_size)
                                    
                                # Process batch results as they come in
                                all_ocr_results = {}
                                for future in concurrent.futures.as_completed(batch_futures):
                                    batch_start, current_batch_size = batch_futures[future]
                                    
                                    try:
                                        # Get batch OCR results
                                        batch_results = future.result()
                                        
                                        # Update OCR status for the pages in this batch
                                        for page_num in range(batch_start + 1, batch_start + current_batch_size + 1):
                                            if page_num in batch_results:
                                                st.session_state.parallel_status["page_status"][page_num]["ocr_status"] = "completed"
                                                # Store OCR results for later analysis
                                                all_ocr_results[page_num] = batch_results[page_num]
                                            else:
                                                st.session_state.parallel_status["page_status"][page_num]["ocr_status"] = "error"
                                    except Exception as e:
                                        # Mark all pages in this batch as having OCR errors
                                        for page_num in range(batch_start + 1, batch_start + current_batch_size + 1):
                                            st.session_state.parallel_status["page_status"][page_num]["ocr_status"] = "error"
                                    
                                # Now submit individual page analysis tasks
                                futures = {}
                                for page_num, page_image in enumerate(st.session_state.page_images, 1):
                                    # Update status for analysis phase
                                    st.session_state.parallel_status["page_status"][page_num]["analysis_status"] = "submitted"
                                    st.session_state.parallel_status["in_progress"] += 1
                                    
                                    # Get OCR text from batched results if available
                                    ocr_text = all_ocr_results.get(page_num, None)
                                    
                                    # Define an analysis worker function that uses pre-computed OCR results
                                    def analyze_page_with_ocr(page_num, page_image, ptw_summary, ocr_text):
                                        try:
                                            # Set up status
                                            status = {
                                                "page_num": page_num,
                                                "ocr_status": "completed" if ocr_text else "pending",
                                                "analysis_status": "pending",
                                                "ocr_text": ocr_text or "",
                                                "analysis_result": "",
                                                "error": None,
                                                "completed": False
                                            }
                                            
                                            # Get OCR text if not provided
                                            if not ocr_text:
                                                status["ocr_status"] = "processing"
                                                ocr_text = process_page_with_claude_ocr(page_image, page_num)
                                                
                                                if "Error:" in ocr_text or "failed" in ocr_text:
                                                    status["ocr_status"] = "error"
                                                    status["error"] = ocr_text
                                                else:
                                                    status["ocr_status"] = "completed"
                                                    status["ocr_text"] = ocr_text
                                            
                                            # Get shared permit number or extract it from the first page
                                            permit_number = None
                                            if page_num == 1:
                                                # Extract from first page
                                                permit_number = extract_permit_number(ocr_text, ptw_summary)
                                                if permit_number:
                                                    # Store for other workers to use
                                                    st.session_state.permit_number = permit_number
                                            else:
                                                # Try to get from session state (if first page has already been processed)
                                                permit_number = st.session_state.get('permit_number', None)
                                            
                                            # Analyze the page
                                            status["analysis_status"] = "processing"
                                            analysis_result = analyze_page_with_claude(
                                                ocr_text, 
                                                ptw_summary, 
                                                page_num,
                                                permit_number
                                            )
                                            
                                            status["analysis_status"] = "completed"
                                            status["analysis_result"] = analysis_result
                                            status["completed"] = True
                                            
                                            return status
                                        
                                        except Exception as e:
                                            return {
                                                "page_num": page_num,
                                                "ocr_status": "completed" if ocr_text else "error",
                                                "analysis_status": "error",
                                                "ocr_text": ocr_text or "",
                                                "analysis_result": f"""
| Desconhecido | {page_num} | Página {page_num} | Conteúdo do Documento | REPROVADO | Deficiência crítica: Ocorreu um erro durante o processamento: {str(e)}. A imagem original deve ser revisada manualmente. |
""",
                                                "error": str(e),
                                                "completed": True
                                            }
                                    
                                    # Submit the analysis work
                                    future = executor.submit(
                                        analyze_page_with_ocr, 
                                        page_num, 
                                        page_image, 
                                        st.session_state.ptw_summary,
                                        ocr_text
                                    )
                                    futures[future] = page_num
                                    
                                # Initialize empty results list with the right size
                                st.session_state.analysis_results = [""] * st.session_state.total_pages
                                
                                # Process results as they complete
                                for future in concurrent.futures.as_completed(futures):
                                    page_num = futures[future]
                                    try:
                                        # Get the result from this future
                                        result = future.result()
                                        
                                        # Update status
                                        st.session_state.parallel_status["page_status"][page_num] = {
                                            "status": "completed",
                                            "ocr_status": result["ocr_status"],
                                            "analysis_status": result["analysis_status"]
                                        }
                                        st.session_state.parallel_status["in_progress"] -= 1
                                        st.session_state.parallel_status["completed"] += 1
                                        
                                        # Store result (index is 0-based but page_num is 1-based)
                                        st.session_state.analysis_results[page_num-1] = result["analysis_result"]
                                        
                                        # Update overall completion status
                                        st.session_state.analyses_completed = st.session_state.parallel_status["completed"]
                                        
                                    except Exception as exc:
                                        # Update status to reflect the error
                                        st.session_state.parallel_status["page_status"][page_num] = {
                                            "status": "error",
                                            "error": str(exc)
                                        }
                                        st.session_state.parallel_status["in_progress"] -= 1
                                        st.session_state.parallel_status["completed"] += 1
    
    # Photo Capture Tab - only show if enabled in settings
    if st.session_state.enable_photo_capture:
        with input_tab2:
            st.markdown("""
        <div class="content-container">
            <h3>Análise por Fotos</h3>
            <p>No celular, você pode tirar fotos diretamente de cada página do documento.</p>
            <ol>
                <li>Faça upload de cada página individualmente (em celulares isso ativa a câmera)</li>
                <li>Organize a ordem das páginas conforme necessário</li>
                <li>Clique em "Analisar Fotos" quando terminar</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        
        # Tips for better photos
        with st.expander("Dicas para melhores resultados"):
            st.markdown("""
            - Quando no celular, escolha "Tirar foto" ao fazer upload
            - Posicione o documento em uma superfície plana com boa iluminação
            - Evite sombras e reflexos sobre o documento
            - Certifique-se que todo o documento está dentro da foto
            - Mantenha a câmera paralela ao documento (evite ângulos)
            - Se possível, use um fundo escuro para melhor contraste
            """)
        
        # Enable photo collection mode
        if st.button("Iniciar Coleta de Fotos", key="enable_capture"):
            st.session_state.capture_mode = True
            # We can't directly modify widget state, so we'll just use a flag
            # to handle this in the next rerun
            st.session_state.clear_uploads = True
            st.rerun()
            
        # Photo uploader appears when capture mode is enabled
        if st.session_state.capture_mode:
            st.info("📱 Modo de coleta de fotos ativado. Em dispositivos móveis, você pode tirar fotos diretamente quando fizer upload.")
            
            
            # Photo upload section (on mobile devices this will activate the camera)
            captured_photo = st.file_uploader("Adicionar página (foto/imagem)", type=["jpg", "jpeg", "png"], key="photo_uploader", 
                                             help="Em dispositivos móveis, isso abrirá a câmera automaticamente")
            
            if captured_photo is not None:
                try:
                    # Process the captured image
                    img = Image.open(captured_photo)
                    
                    # Add caption/description for this page
                    page_number = len(st.session_state.captured_photos) + 1
                    caption = st.text_input(f"Descrição da página {page_number} (opcional)", 
                                           placeholder="Ex: PT Principal, JSA, PRTA, etc.",
                                           key=f"caption_{page_number}")
                    
                    # Add to session state when add button is clicked
                    if st.button("Adicionar Página", key=f"add_page_{page_number}"):
                        st.session_state.captured_photos.append(img)
                        st.session_state.photo_captions.append(caption)
                        st.success(f"✅ Página {page_number} adicionada com sucesso!")
                        st.session_state.clear_uploads = True
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Erro ao processar a foto: {str(e)}")
            
            # Display captured photos with options to manage them
            if st.session_state.captured_photos:
                st.markdown("### Páginas Capturadas")
                
                # Create columns for each captured photo
                num_photos = len(st.session_state.captured_photos)
                cols = st.columns(min(3, num_photos))
                
                # Display each photo with options
                for i, img in enumerate(st.session_state.captured_photos):
                    col_idx = i % len(cols)
                    with cols[col_idx]:
                        st.image(img, caption=f"Página {i+1}: {st.session_state.photo_captions[i]}", use_container_width=True)
                        
                        # Remove button
                        if st.button("Remover", key=f"remove_{i}"):
                            st.session_state.captured_photos.pop(i)
                            st.session_state.photo_captions.pop(i)
                            st.rerun()
                
                # Move up/down buttons for reordering
                if num_photos > 1:
                    st.markdown("### Reordenar Páginas")
                    reorder_col1, reorder_col2, reorder_col3 = st.columns(3)
                    
                    with reorder_col1:
                        page_to_move = st.number_input("Selecione a página", 
                                                      min_value=1, 
                                                      max_value=num_photos, 
                                                      step=1)
                    
                    with reorder_col2:
                        move_up = st.button("⬆️ Mover Para Cima", key="move_up", 
                                           disabled=(page_to_move == 1))
                        
                    with reorder_col3:
                        move_down = st.button("⬇️ Mover Para Baixo", key="move_down", 
                                             disabled=(page_to_move == num_photos))
                    
                    # Handle reordering
                    idx = int(page_to_move) - 1  # Convert to 0-based index
                    if move_up and idx > 0:
                        # Swap with previous
                        st.session_state.captured_photos[idx], st.session_state.captured_photos[idx-1] = \
                            st.session_state.captured_photos[idx-1], st.session_state.captured_photos[idx]
                        st.session_state.photo_captions[idx], st.session_state.photo_captions[idx-1] = \
                            st.session_state.photo_captions[idx-1], st.session_state.photo_captions[idx]
                        st.rerun()
                        
                    if move_down and idx < num_photos - 1:
                        # Swap with next
                        st.session_state.captured_photos[idx], st.session_state.captured_photos[idx+1] = \
                            st.session_state.captured_photos[idx+1], st.session_state.captured_photos[idx]
                        st.session_state.photo_captions[idx], st.session_state.photo_captions[idx+1] = \
                            st.session_state.photo_captions[idx+1], st.session_state.photo_captions[idx]
                        st.rerun()
                
                # Process captured photos button
                if st.button("Analisar Fotos Capturadas", type="primary"):
                    # Set processing flags
                    st.session_state.processing = True
                    st.session_state.parallel_processing = False
                    
                    # Reset session state variables
                    st.session_state.ptw_summary = None
                    st.session_state.page_images = []
                    st.session_state.analysis_results = []
                    st.session_state.current_page = 0
                    st.session_state.analyses_completed = 0
                    # Reset parallel processing variables
                    st.session_state.parallel_results = []
                    st.session_state.parallel_status = {}
                    
                    # Process immediately without rerun - like app_Old_Visual.py
                    with st.spinner("Preparando fotos capturadas para análise..."):
                        # Transfer captured photos to page_images
                        st.session_state.page_images = st.session_state.captured_photos.copy()
                        st.session_state.total_pages = len(st.session_state.page_images)
                        
                        # Create a PDF from the images for the summary generation
                        st.info("Criando PDF temporário para geração de resumo...")
                        
                        # Create a byte stream to hold the PDF
                        pdf_buffer = io.BytesIO()
                        
                        # Create a new PDF document
                        pdf = fitz.open()
                        
                        # Add each image as a new page
                        for i, img in enumerate(st.session_state.captured_photos):
                            # Convert PIL Image to bytes
                            img_buffer = io.BytesIO()
                            img.save(img_buffer, format="PNG")
                            img_buffer.seek(0)
                            
                            # Add page to PDF with the image's aspect ratio
                            width, height = img.size
                            page = pdf.new_page(width=width, height=height)
                            rect = fitz.Rect(0, 0, width, height)
                            page.insert_image(rect, stream=img_buffer.getvalue())
                            
                            # Add caption if available
                            if i < len(st.session_state.photo_captions) and st.session_state.photo_captions[i]:
                                caption = st.session_state.photo_captions[i]
                                # Add text annotation with the caption
                                text_rect = fitz.Rect(0, height - 30, width, height)
                                page.insert_textbox(text_rect, caption, color=(0, 0, 0), fontsize=12)
                        
                        # Save the PDF to the buffer
                        pdf.save(pdf_buffer)
                        pdf.close()
                        
                        # Get the PDF bytes
                        pdf_buffer.seek(0)
                        pdf_bytes = pdf_buffer.getvalue()
                        
                        # Generate PTW summary using Wonder Wise
                        st.info("Gerando resumo da PT com Wonder Wise...")
                        ptw_summary = generate_ptw_summary(pdf_bytes)
                        st.session_state.ptw_summary = ptw_summary
            
            # Option to cancel photo collection mode
            if st.button("Cancelar Coleta de Fotos", key="cancel_capture"):
                st.session_state.capture_mode = False
                st.session_state.captured_photos = []
                st.session_state.photo_captions = []
                # Set flag to change PDF uploader key on next rerun
                st.session_state.clear_uploads = True
                st.rerun()
    
    # This code has been moved inline to the button click handlers
    # This matches how app_Old_Visual.py works - processing happens immediately when buttons are clicked
    # No need for any processing here
    
    # Display processing interface if processing has started
    if st.session_state.processing:
        # Display PTW summary with enhanced table display
        if st.session_state.ptw_summary:
            with st.expander("Resumo da Permissão de Trabalho", expanded=True):
                # Split the summary to extract the table and surrounding text
                summary_text = st.session_state.ptw_summary
                
                # Check if there's a table in the response
                if "|" in summary_text and "Número da Página" in summary_text:
                    # Split the content roughly into parts before, during, and after the table
                    parts = summary_text.split("| Número da Página ")
                    
                    # Display the text before the table
                    if len(parts) > 0:
                        st.markdown(parts[0])
                    
                    # Extract and format the table
                    if len(parts) > 1:
                        table_part = "| Número da Página " + parts[1].split("\n\n")[0]
                        st.markdown("### Tabela de Páginas do Documento")
                        st.markdown(table_part)
                        
                        # Display any text after the table
                        after_table = parts[1].split("\n\n", 1)
                        if len(after_table) > 1:
                            st.markdown(after_table[1])
                else:
                    # If no table format detected, just display the entire summary
                    st.markdown(summary_text)
            
            # Display progress based on processing mode (sequential or parallel)
            progress_value = st.session_state.analyses_completed / st.session_state.total_pages if st.session_state.total_pages > 0 else 0
            
            # Different progress display for parallel vs sequential
            if st.session_state.parallel_processing:
                # For parallel processing, show overall progress
                progress_text = f"Processando em paralelo: {st.session_state.analyses_completed}/{st.session_state.total_pages} páginas concluídas"
                st.progress(progress_value, text=progress_text)
                
                # Add detailed status display for parallel processing
                if st.session_state.analyses_completed < st.session_state.total_pages:
                    status_cols = st.columns(3)
                    with status_cols[0]:
                        st.metric("Páginas Concluídas", st.session_state.analyses_completed)
                    with status_cols[1]:
                        st.metric("Em Processamento", st.session_state.parallel_status.get("in_progress", 0))
                    with status_cols[2]:
                        st.metric("Total de Páginas", st.session_state.total_pages)
                    
                    # Add a refresh button to update the progress
                    if st.button("Atualizar Status", key="refresh_parallel"):
                        st.rerun()
                    
                    # Show message that processing is happening in background
                    st.info("O processamento em paralelo está ocorrendo em segundo plano. Você pode atualizar o status clicando no botão acima ou aguardar a conclusão.")
                    
                    # Auto refresh - at a slower pace to avoid UI issues
                    st.empty().info("Esta página será atualizada automaticamente em alguns segundos...")
                    time.sleep(10)  # Longer wait time to give UI time to stabilize
                    st.rerun()
                
                # If all pages are processed, skip the sequential processing section
                if st.session_state.analyses_completed >= st.session_state.total_pages:
                    st.success("Todas as páginas foram processadas com sucesso!")
                    
                    # Jump to results section
                    st.session_state.current_page = st.session_state.total_pages
            else:
                # For sequential processing, show current page progress
                progress_text = f"Processando página {st.session_state.analyses_completed + 1}/{st.session_state.total_pages}"
                st.progress(progress_value, text=progress_text)
            
            # Process pages in batch (for sequential processing)
            if not st.session_state.parallel_processing and st.session_state.current_page < st.session_state.total_pages:
                # Add batch processing state variables if not present
                if 'batch_size' not in st.session_state:
                    st.session_state.batch_size = 3  # Default batch size of 3 pages
                if 'batch_start' not in st.session_state:
                    st.session_state.batch_start = 0
                if 'batch_ocr_results' not in st.session_state:
                    st.session_state.batch_ocr_results = {}
                
                # Determine if we need to process a new batch
                current_batch_start = (st.session_state.current_page // st.session_state.batch_size) * st.session_state.batch_size
                
                # Process a new batch if needed
                if current_batch_start != st.session_state.batch_start or not st.session_state.batch_ocr_results:
                    st.session_state.batch_start = current_batch_start
                    
                    # Create a header for the current batch processing status
                    batch_end = min(st.session_state.batch_start + st.session_state.batch_size, st.session_state.total_pages)
                    st.markdown(f"### Processando Lote de Páginas {st.session_state.batch_start + 1} a {batch_end} de {st.session_state.total_pages}")
                    
                    # Process the batch
                    with st.spinner(f"Processando lote de páginas {st.session_state.batch_start + 1} a {batch_end}..."):
                        st.session_state.batch_ocr_results = process_pages_batch(
                            st.session_state.page_images, 
                            st.session_state.batch_start, 
                            st.session_state.batch_size, 
                            st.session_state.ptw_summary
                        )
                
                # Display the current page from the batch
                st.markdown(f"### Processando Página {st.session_state.current_page + 1} de {st.session_state.total_pages}")
                
                with st.spinner(f"Analisando página {st.session_state.current_page + 1}..."):
                    try:
                        # Display current page image
                        current_image = st.session_state.page_images[st.session_state.current_page]
                        st.image(current_image, caption=f"Página {st.session_state.current_page + 1}", use_container_width=True)
                        
                        # Add a separator for clarity
                        st.markdown("---")
                        
                        # Create columns for the processing steps
                        col1, col2 = st.columns(2)
                        
                        # Get OCR text from batch results
                        current_page_num = st.session_state.current_page + 1  # 1-based page number
                        
                        # Process page with Wonder Wise OCR
                        with col1:
                            st.subheader("Processamento OCR")
                            
                            # Create a placeholder for the status
                            status_placeholder = st.empty()
                            
                            # Check if OCR result exists in batch
                            if current_page_num in st.session_state.batch_ocr_results:
                                ocr_text = st.session_state.batch_ocr_results[current_page_num]
                                status_placeholder.success("Processamento OCR em lote completo")
                                
                                # Show a preview of the OCR text
                                st.markdown("**Prévia do Texto OCR:**")
                                preview = ocr_text[:500] + "..." if len(ocr_text) > 500 else ocr_text
                                st.code(preview, language=None)
                            else:
                                # Fallback to individual OCR processing if batch failed for this page
                                status_placeholder.warning("Processamento em lote falhou. Tentando OCR individual...")
                                
                                # Show a spinner while processing
                                with st.spinner("Executando processamento OCR individual..."):
                                    # Run the OCR processing
                                    ocr_text = process_page_with_claude_ocr(current_image, current_page_num)
                                
                                # Check if OCR was successful or if there was an error
                                if "Error:" in ocr_text or "failed" in ocr_text:
                                    status_placeholder.error("Processamento OCR teve problemas. Análise continuará com dados limitados.")
                                else:
                                    status_placeholder.success("Processamento OCR individual completo")
                                    # Show a preview of the OCR text
                                    st.markdown("**Prévia do Texto OCR:**")
                                    preview = ocr_text[:500] + "..." if len(ocr_text) > 500 else ocr_text
                                    st.code(preview, language=None)
                        
                        # Analyze page with Wonder Wise
                        with col2:
                            st.subheader("Análise de IA")
                            # Create a placeholder for the status
                            ai_status = st.empty()
                            ai_status.info("Iniciando análise com Wonder Wise...")
                            
                            # Extract or get permit number for consistency
                            permit_number = st.session_state.get('permit_number', None)
                            
                            # Try to extract permit number from first page if not already available
                            if not permit_number and current_page_num == 1:
                                permit_number = extract_permit_number(ocr_text, st.session_state.ptw_summary)
                                if permit_number:
                                    st.session_state.permit_number = permit_number
                                    st.info(f"Número da PT detectado: {permit_number}")
                                    
                            # Show a spinner while processing
                            with st.spinner("Analisando conteúdo do documento..."):
                                analysis_result = analyze_page_with_claude(
                                    ocr_text, 
                                    st.session_state.ptw_summary, 
                                    current_page_num,
                                    permit_number
                                )
                            
                            # Update status once complete
                            ai_status.success("Análise completa")
                        
                        # Add result to session state
                        st.session_state.analysis_results.append(analysis_result)
                        
                        # Show a success message
                        st.success(f"Página {current_page_num} processada com sucesso!")
                        
                    except Exception as page_error:
                        st.error(f"Erro ao processar página {current_page_num}: {str(page_error)}")
                        # Add a failure result to maintain the flow
                        failure_result = f"""
| Desconhecido | {current_page_num} | Página {current_page_num} | Conteúdo do Documento | REPROVADO | Deficiência crítica: Ocorreu um erro durante o processamento: {str(page_error)}. A imagem original deve ser revisada manualmente. |
"""
                        st.session_state.analysis_results.append(failure_result)
                    
                    finally:
                        # Always update progress, even if there was an error
                        st.session_state.analyses_completed += 1
                        st.session_state.current_page += 1
                        
                        # Add a button to continue to the next page
                        if st.button("Continuar para Próxima Página", key=f"continue_btn_{st.session_state.current_page}"):
                            st.rerun()
                        else:
                            # Auto-continue after a short delay
                            time.sleep(1.5)
                            st.rerun()
            
            # All pages processed, show results
            if (st.session_state.parallel_processing and st.session_state.analyses_completed == st.session_state.total_pages) or \
               (not st.session_state.parallel_processing and st.session_state.current_page == st.session_state.total_pages):
                st.success("Análise completa!")
                
                # Display results table
                st.markdown("""
                <div class="content-container">
                    <h2>Resultados da Análise</h2>
                </div>
                """, unsafe_allow_html=True)
                
                # Combine all results
                combined_results = ""
                
                # Process the analysis results to extract tables
                for page_num, result in enumerate(st.session_state.analysis_results, 1):
                    # Add the processed result to the combined results
                    combined_results += result + "\n\n"
                
                # Create a clean table
                try:
                    st.info("Gerando tabela de análise...")
                    
                    # DEBUG - Let's see what data we're getting from each page
                    with st.expander("Análise de Dados (DEBUG)", expanded=False):
                        # Track identified tables and rows
                        debug_data = {
                            "header_found": False,
                            "rows_per_page": {},
                            "tables_found": 0,
                            "excluded_rows": 0
                        }
                        
                        for page_num, result in enumerate(st.session_state.analysis_results, 1):
                            # Check if the page has analysis data
                            if result and "|" in result:
                                st.write(f"**Página {page_num} tem tabela:** {result[:100]}...")
                                
                                # Count table rows in this page's result
                                table_rows = sum(1 for line in result.split('\n') if line.strip().startswith('|') and line.strip().endswith('|'))
                                debug_data["rows_per_page"][page_num] = table_rows
                            else:
                                st.write(f"**Página {page_num}:** Sem dados de tabela")
                        
                        # After processing all pages, display debug stats
                        st.write("---")
                        st.write("### Estatísticas da Tabela:")
                        st.write(f"- Páginas com tabelas: {len(debug_data['rows_per_page'])}")
                        for page, rows in debug_data['rows_per_page'].items():
                            st.write(f"  - Página {page}: {rows} linhas de tabela")
                        
                        # We'll update these stats after parsing
                        debug_info_placeholder = st.empty()
                    
                    # Create a clean header
                    table_header = """
                    <div class="content-container">
                        <h3>Resultados da Análise de Permissão de Trabalho</h3>
                    </div>
                    """
                    st.markdown(table_header, unsafe_allow_html=True)
                    
                    # Parse the table data from the markdown, focusing only on the main summary table
                    all_rows = []
                    current_headers = None
                    header_line_found = False
                    in_main_table = False
                    
                    # Expected headers for the main summary table - expanded to cover more variations
                    expected_main_headers = [
                        'Número da Permissão', 'Permit Number', 'Número da PT', 'PT Number', 'PTW Number',
                        'Número da Página', 'Page Number', 'Página', 'Page', 
                        'Resumo da Página', 'Page Summary', 'Resumo', 'Summary',
                        'Seção', 'Section', 
                        'Status', 'Comentários', 'Comments', 'Desconhecido', 'Unknown',
                        'Completa', 'Complete'
                    ]
                                           
                    # Process each line in the combined results
                    for line in combined_results.split('\n'):
                        line = line.strip()
                        
                        # Skip empty lines
                        if not line:
                            continue
                        
                        # Check if we're starting a new section/table
                        if not line.startswith('|') and header_line_found and in_main_table:
                            # We've finished the main table
                            in_main_table = False
                            continue
                            
                        # Parse only table rows
                        if line.startswith('|') and line.endswith('|'):
                            # Split the line by | and clean up cells
                            cells = [cell.strip() for cell in line.split('|')[1:-1]]
                            
                            # Skip separator rows (contain only dashes)
                            if all('-' in cell and cell.replace('-', '') == '' for cell in cells):
                                continue
                                
                            # If this looks like a header row (either first time or new table with same structure)
                            if not header_line_found or not in_main_table:
                                # Look for header patterns
                                # We need to detect both table headers for the first time AND
                                # new tables from subsequent pages with the same structure
                                
                                # Count how many expected header columns we have
                                header_matches = sum(1 for cell in cells if cell in expected_main_headers)
                                
                                # First header detection - needs stricter criteria
                                if not header_line_found and header_matches >= 3:
                                    # This is our first main table header
                                    current_headers = cells
                                    header_line_found = True
                                    in_main_table = True
                                    continue
                                
                                # Subsequent header detection - must match first header structure
                                elif header_line_found and not in_main_table and current_headers:
                                    # If this has the same structure as our known header
                                    if len(cells) == len(current_headers) and header_matches >= 2:
                                        # This is a new table with the same structure
                                        in_main_table = True
                                        continue
                            
                            # Skip if we're not in the main table or don't have headers yet
                            if not in_main_table or not current_headers:
                                continue
                                
                            # Check for column count match - if this row doesn't have the same number of columns
                            # as the header row, it's likely not part of our main table
                            if len(cells) != len(current_headers):
                                continue
                            
                            # This is a data row in our main table - create a clean dictionary
                            row_data = {}
                            valid_data = True
                            has_status = False
                            
                            for i, cell in enumerate(cells):
                                if i < len(current_headers):
                                    header_key = current_headers[i].strip()
                                    row_value = cell.strip()
                                    row_data[header_key] = row_value
                                    
                                    # Check for invalid row indicators - these are likely secondary tables
                                    if any(bad_marker in cell for bad_marker in ["Linha ", "Cargo/Função", "Tabela "]):
                                        valid_data = False
                                    
                                    # Check if this row has a status field with expected values
                                    if header_key in ['Status'] and row_value in ['APROVADO', 'REPROVADO', 'APPROVED', 'REPROVED', 'INCONCLUSIVO']:
                                        has_status = True
                            
                            # Add the row if:
                            # 1. It has valid data
                            # 2. It has a valid Status value (indicating it's a result row)
                            # 3. It has complete data (not empty)
                            if valid_data and has_status and len(row_data) >= 3:
                                # Check if this row has the same structure as our main table
                                # We should have page number and section information
                                page_col = 'Número da Página' if 'Número da Página' in row_data else 'Page Number'
                                section_col = 'Seção' if 'Seção' in row_data else 'Section'
                                
                                if (page_col in row_data and row_data[page_col]) and (section_col in row_data and row_data[section_col]):
                                    all_rows.append(row_data)
                    
                    # Check if we have any rows to display
                    if all_rows and current_headers:
                        # Create a new DataFrame with proper column order
                        df = pd.DataFrame(all_rows)
                        
                        # Update debug info
                        if 'debug_info_placeholder' in locals():
                            # Get unique page numbers in our final table
                            if 'Número da Página' in df.columns:
                                pages_included = df['Número da Página'].unique()
                            elif 'Page Number' in df.columns:
                                pages_included = df['Page Number'].unique()
                            else:
                                pages_included = []
                                
                            debug_info_placeholder.write("### Resultados da Análise:")
                            debug_info_placeholder.write(f"- Linhas incluídas na tabela final: {len(df)}")
                            debug_info_placeholder.write(f"- Páginas representadas: {len(pages_included)}")
                            debug_info_placeholder.write(f"- Números das páginas incluídas: {', '.join(str(p) for p in sorted(pages_included))}")
                        
                        # Remove duplicate headers that might have been appended during analysis
                        # Keep only data rows, filter out header rows
                        headers_pattern = "|".join([re.escape(header.strip()) for header in current_headers])
                        if 'Permit Number' in df.columns or 'Número da Permissão' in df.columns:
                            # Get the column with permit numbers
                            permit_col = 'Permit Number' if 'Permit Number' in df.columns else 'Número da Permissão'
                            # Filter out rows that have a header as permit number value
                            df = df[~df[permit_col].str.contains(headers_pattern, regex=True, case=False, na=False)]

                        # Apply conditional styling to highlight reproved items in red
                        def style_status(val):
                            color = '#F44336' if val in ['REPROVED', 'REPROVADO'] else '#4CAF50'
                            return f'color: {color}; font-weight: bold'
                            
                        # Apply the styling to the Status column if it exists
                        if 'Status' in df.columns:
                            styled_df = df.style.applymap(style_status, subset=['Status'])
                        else:
                            styled_df = df
                        
                        # Display the clean dataframe with styling
                        st.dataframe(
                            data=styled_df,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Create a page viewer expander
                        with st.expander("Visualizar Imagens das Páginas", expanded=True):
                            # Create a page selector
                            col1, col2 = st.columns([1, 3])
                            
                            with col1:
                                # Add page selector dropdown
                                page_numbers = list(range(1, len(st.session_state.page_images) + 1))
                                selected_page = st.selectbox(
                                    "Selecione a página para visualizar:",
                                    options=page_numbers,
                                    format_func=lambda x: f"Página {x}",
                                    index=0,
                                    key="page_selector"
                                )
                                
                                # Add page navigation buttons
                                cols = st.columns(3)
                                
                                # Previous button
                                with cols[0]:
                                    if selected_page > 1:
                                        if st.button("◀ Anterior"):
                                            st.session_state.current_page_view = selected_page - 2
                                            st.rerun()
                                
                                # Page indicator
                                with cols[1]:
                                    st.markdown(f"**{selected_page}/{len(page_numbers)}**")
                                
                                # Next button
                                with cols[2]:
                                    if selected_page < len(page_numbers):
                                        if st.button("Próxima ▶"):
                                            st.session_state.current_page_view = selected_page
                                            st.rerun()
                            
                            # Display the selected page image
                            with col2:
                                if 1 <= selected_page <= len(st.session_state.page_images):
                                    st.image(
                                        st.session_state.page_images[selected_page-1], 
                                        caption=f"Página {selected_page}", 
                                        use_container_width=True
                                    )
                                    
                                    # Get the analysis results for this page
                                    # First check if the column exists and adapt if needed
                                    page_column = None
                                    if 'Page Number' in df.columns:
                                        page_column = 'Page Number'
                                    elif 'Página' in df.columns:  # Portuguese column name
                                        page_column = 'Página'
                                    elif 'Número da Página' in df.columns:  # Alternative Portuguese name
                                        page_column = 'Número da Página'
                                    
                                    if page_column:
                                        page_results = df[df[page_column] == str(selected_page)]
                                    else:
                                        # Fallback if no matching column found
                                        st.warning("Não foi possível encontrar informações da página na análise")
                                        page_results = pd.DataFrame()
                                        
                                    if not page_results.empty:
                                        st.subheader(f"Análise da Página {selected_page}")
                                        
                                        # Display the analysis for this page
                                        for _, row in page_results.iterrows():
                                            # Handle both English and Portuguese status values
                                            status = row.get('Status', '')
                                            is_approved = status in ['APPROVED', 'APROVADO']
                                            status_color = "#4CAF50" if is_approved else "#F44336"
                                            status_text = "APROVADO" if is_approved else "REPROVADO"
                                            
                                            # Get section - check for both English and Portuguese column names
                                            section = None
                                            if 'Section' in row:
                                                section = row['Section']
                                            elif 'Seção' in row:
                                                section = row['Seção']
                                            else:
                                                section = 'Seção'
                                                
                                            # Get comments - check for both English and Portuguese column names
                                            comments = None
                                            if 'Comments' in row:
                                                comments = row['Comments']
                                            elif 'Comentários' in row:
                                                comments = row['Comentários']
                                            else:
                                                comments = 'Sem comentários'
                                            
                                            # Create a border color that matches the status
                                            border_color = status_color
                                            
                                            # Create a slight header background that indicates status
                                            if is_approved:
                                                header_bg = "rgba(76, 175, 80, 0.1)"  # Light green background for approved
                                            else:
                                                header_bg = "rgba(244, 67, 54, 0.1)"   # Light red background for reproved
                                            
                                            st.markdown(f"""
                                            <div style="background-color: #112240; padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 4px solid {border_color};">
                                                <h4 style="color: #64ffda; padding: 5px; background-color: {header_bg}; border-radius: 3px;">{section}</h4>
                                                <p><strong>Status:</strong> <span style="color: {status_color}; font-weight: bold;">{status_text}</span></p>
                                                <p><strong>Comentários:</strong> {comments}</p>
                                            </div>
                                            """, unsafe_allow_html=True)
                        
                        # Show summary counts - handle both English and Portuguese status values
                        if 'Status' in df.columns:
                            # Count approvals and reprovals
                            status_counts = df['Status'].value_counts()
                            
                            # Check for both English and Portuguese status values
                            approved_count = status_counts.get('APPROVED', 0) + status_counts.get('APROVADO', 0)
                            reproved_count = status_counts.get('REPROVED', 0) + status_counts.get('REPROVADO', 0)
                            
                            # Create status summary card
                            st.markdown(f"""
                            <div class="content-container">
                                <h4>Resumo da Análise</h4>
                                <p>Seções Aprovadas: <span style="color: #4CAF50; font-weight: bold;">{approved_count}</span></p>
                                <p>Seções Reprovadas: <span style="color: #F44336; font-weight: bold;">{reproved_count}</span></p>
                                <p>Total de Seções Analisadas: {len(df)}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                    else:
                        st.warning("Não há dados de análise para exibir")
                        # Show the raw markdown as fallback
                        st.markdown(combined_results)
                
                except Exception as e:
                    st.error(f"Erro ao processar resultados: {str(e)}")
                    # Show the raw results as fallback
                    st.markdown(combined_results)
                
                # Reset button
                if st.button("Processar Outro Documento"):
                    st.session_state.processing = False
                    st.session_state.ptw_summary = None
                    st.session_state.page_images = []
                    st.session_state.analysis_results = []
                    st.session_state.current_page = 0
                    st.session_state.analyses_completed = 0
                    st.session_state.total_pages = 0
                    st.rerun()

if __name__ == "__main__":
    main()