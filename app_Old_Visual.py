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
import hashlib
import json
import pickle
from PIL import Image, ImageEnhance, ImageFilter
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
                    model="claude-sonnet-4-20250514",
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
                    model="claude-sonnet-4-20250514",
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
                    model="claude-sonnet-4-20250514",
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

# Document fingerprinting and OCR caching
def generate_document_hash(pdf_bytes):
    """
    Generate a unique hash for a PDF document to use as cache key.
    
    Args:
        pdf_bytes: The PDF content as bytes
        
    Returns:
        str: A hexadecimal hash string unique to this document
    """
    return hashlib.sha256(pdf_bytes).hexdigest()

def cache_ocr_text(doc_hash, page_num, ocr_text):
    """
    Cache OCR text for a specific document page.
    
    Args:
        doc_hash: Document hash identifier
        page_num: Page number (1-based)
        ocr_text: The OCR text to cache
    """
    # Initialize OCR cache if it doesn't exist
    if 'ocr_cache' not in st.session_state:
        st.session_state.ocr_cache = {}
    
    # Create document entry if it doesn't exist
    if doc_hash not in st.session_state.ocr_cache:
        st.session_state.ocr_cache[doc_hash] = {}
    
    # Store OCR text for this page
    st.session_state.ocr_cache[doc_hash][page_num] = ocr_text
    
    # Also try to persist to disk for future sessions
    try:
        cache_dir = Path("./.cache")
        cache_dir.mkdir(exist_ok=True)
        
        cache_file = cache_dir / f"{doc_hash}.pkl"
        with open(cache_file, 'wb') as f:
            pickle.dump(st.session_state.ocr_cache[doc_hash], f)
    except Exception as e:
        # Log but continue if disk caching fails
        print(f"Warning: Could not save OCR cache to disk: {str(e)}")

def get_cached_ocr_text(doc_hash, page_num):
    """
    Retrieve cached OCR text for a specific document page.
    
    Args:
        doc_hash: Document hash identifier
        page_num: Page number (1-based)
        
    Returns:
        str or None: The cached OCR text if available, None otherwise
    """
    # Check memory cache first
    if 'ocr_cache' in st.session_state and doc_hash in st.session_state.ocr_cache:
        return st.session_state.ocr_cache[doc_hash].get(page_num)
    
    # Try to load from disk if not in memory
    try:
        cache_file = Path(f"./.cache/{doc_hash}.pkl")
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                page_cache = pickle.load(f)
                
                # Store in session state for future use
                if 'ocr_cache' not in st.session_state:
                    st.session_state.ocr_cache = {}
                st.session_state.ocr_cache[doc_hash] = page_cache
                
                return page_cache.get(page_num)
    except Exception as e:
        # Log but continue if disk cache loading fails
        print(f"Warning: Could not load OCR cache from disk: {str(e)}")
    
    return None

def standardize_image(image, target_dpi=250):
    """
    Standardize image for consistent OCR results:
    - Resizes to consistent target DPI/resolution
    - Enhances contrast and reduces noise
    - Converts to grayscale (better for text recognition)
    - Ensures size is under Claude's limits
    
    Args:
        image: PIL.Image object
        target_dpi: Target resolution in DPI (250 is good for OCR)
        
    Returns:
        standardized_image: PIL.Image object
        img_base64: Base64 encoded image for API
    """
    # Preserve original colors (especially blue ink for signatures)
    # We'll keep the original color mode instead of converting to grayscale
    # This ensures blue ink signatures remain clearly visible
    
    # Calculate target dimensions (assume 72 DPI source if unknown)
    source_dpi = getattr(image, 'info', {}).get('dpi', (72, 72))[0]
    width, height = image.size
    
    # Calculate scaling factor to reach target DPI
    scale_factor = target_dpi / source_dpi
    target_width = int(width * scale_factor)
    target_height = int(height * scale_factor)
    
    # Limit dimensions to prevent excessively large images (max 2500 pixels in any dimension)
    max_dimension = 2500
    if target_width > max_dimension or target_height > max_dimension:
        ratio = min(max_dimension / target_width, max_dimension / target_height)
        target_width = int(target_width * ratio)
        target_height = int(target_height * ratio)
    
    # Resize using high-quality interpolation
    resized_image = image.resize((target_width, target_height), Image.LANCZOS)
    
    # Apply contrast enhancement
    enhancer = ImageEnhance.Contrast(resized_image)
    enhanced_image = enhancer.enhance(1.5)  # Increase contrast by 50%
    
    # Apply mild sharpening for better text edges
    enhanced_image = enhanced_image.filter(ImageFilter.SHARPEN)
    
    # Save to buffer with consistent settings
    img_buffer = io.BytesIO()
    enhanced_image.save(img_buffer, format='JPEG', optimize=True, quality=85)
    img_buffer.seek(0)
    
    # Check file size and reduce if needed
    img_size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
    final_image = enhanced_image
    
    # If still too large, compress further
    if img_size_mb > 4.5:  # Keep some margin below Claude's 5MB limit
        compression_quality = 75
        while img_size_mb > 4.5 and compression_quality > 30:
            img_buffer = io.BytesIO()
            final_image.save(img_buffer, format='JPEG', optimize=True, quality=compression_quality)
            img_buffer.seek(0)
            img_size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
            compression_quality -= 10
    
    # Base64 encode for Claude
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
    
    return final_image, img_base64

def process_page_with_claude_ocr(page_image, page_num=None, use_cache=True):
    """Process page image with Wonder Wise OCR with caching support."""
    try:
        # Apply standardized image processing for consistent OCR
        if page_num:
            st.info(f"Padronizando imagem da página {page_num} para OCR consistente...")
        else:
            st.info(f"Padronizando imagem para OCR consistente...")
        
        # Use our standardization function for consistent image processing
        standardized_image, img_base64 = standardize_image(page_image)
        
        # Get the size after standardization
        img_buffer = io.BytesIO()
        standardized_image.save(img_buffer, format='JPEG', optimize=True)
        img_size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
        
        if page_num:
            st.info(f"Página {page_num} padronizada para OCR: {img_size_mb:.2f}MB, resolução otimizada")
        else:
            st.info(f"Imagem padronizada para OCR: {img_size_mb:.2f}MB, resolução otimizada")
        
        # Call Wonder Wise for OCR (keeping prompt in English)
        ocr_response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=20000,
            temperature=0,
            system="""You are an expert OCR system for analyzing standardized, pre-processed document images. Your primary responsibilities are:

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

CONSTELLATION VISUAL IDENTIFIERS:
- Logo description: Flame or teardrop shape, often in blue/black
- Logo location: Typically top right corner of JSA forms
- Text markers: "Constellation" written near or below the logo
- Form style: Standardized Constellation safety form layout
- Header pattern: "Job Safety Analysis - JSA" with Constellation branding

COMMON THIRD-PARTY INDICATORS:
- Petrobras logo (green/yellow BR design)
- Modec company headers
- Subsea 7 branding
- TechnipFMC logos
- Any oil & gas company logo that is NOT Constellation
- Generic JSA forms without company branding

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
- Include ALL pre-printed text regardless of color (black, red, blue, etc.)
- Process multi-column layouts appropriately (left-to-right, respecting columns)
- For rotated or oriented text, extract and note the orientation
- If text is partially visible or unclear, indicate with [UNCLEAR]
- If text is completely illegible, mark as [ILLEGIBLE]

FORM ELEMENTS:
- For empty fields: Report "[Empty field: FIELD_NAME]"
- For filled fields: Report "[Filled field: FIELD_NAME]" (NEVER reproduce the handwritten content)
For checkboxes/options:
  * A checkbox is considered [Checked] if it contains ANY of these marks:
    - Clear X mark (even if thin lines)
    - Checkmark (✓)
    - Dot or filled circle
    - Any diagonal, horizontal, or vertical line(s) that clearly cross through the box
    - Scribbles or partial fills that show clear intent to mark
  * Visual detection criteria:
    - The mark does NOT need to be perfectly centered
    - The mark does NOT need to fill 30-50% if it's clearly an X or checkmark
    - Even a single diagonal line crossing the box counts as checked
    - Look for ANY intentional pen/pencil mark within the box boundaries
  * Common checkbox patterns to recognize:
    - [ X ] or [X] = Checked
    - [ ✓ ] or [✓] = Checked  
    - [ • ] or [•] = Checked
    - [ / ] or [ \ ] = Checked (single diagonal line)
    - [   ] = Unchecked (completely empty)
  * What to IGNORE:
    - Faint grid lines or form printing artifacts
    - The checkbox border itself
    - Text proximity (text near a box doesn't mean it's checked)
    - Shadow or scan artifacts OUTSIDE the box
  * If marked: Report "[Checked: OPTION_TEXT]"
  * If unmarked: Report "[Unchecked: OPTION_TEXT]"
  * For forms with Sim/Não (Yes/No) options, check BOTH boxes carefully

HANDWRITTEN CONTENT:
- NEVER transcribe actual handwritten text - use only 'checked', 'filled', or 'signed'
- For filled name fields: Report "[Filled]" (typically occupies ~40% of field)
- Note ink color if distinguishable (typically blue or black)
- Remember: only USER-ADDED content counts as handwritten, not pre-printed colored text

SIGNATURE VERIFICATION:
- For signature fields, apply strict verification criteria:
  * ONLY mark as [Signed] when there are CLEAR pen strokes/marks WITHIN the signature field
  * Look carefully for BLUE INK signatures which are common in these documents
  * For empty or ambiguous signature fields, mark as [Empty]
  * When uncertain about a signature, default to [Empty] or [Unclear signature]
  * Signature characteristics typically include:
    - Distinctive curved/flowing lines
    - Pen strokes with varying pressure/thickness (often in blue ink)
    - Coverage of significant portion of the designated field
  * Differentiate between:
    - Name fields (printed/typed/handwritten name)
    - Signature fields (unique identifying mark/signature)
- After completing document analysis, VERIFY all signature fields a second time
- Note: Adjacent text or marks should not be mistaken for signatures
- IMPORTANT: Check ENTIRE document including bottom sections for safety technician or additional signature fields

STAMPS & SPECIAL MARKINGS:
- For stamps: Report "[Stamp: CONTENT]" (e.g., "Stamp: Name", "Stamp: Function", "Stamp: Approved")
- CRITICAL STAMP RULES FOR MANDATORY SECTIONS:
  * For Section 15 (COEMITENTE/RESPONSIBLE PERSONS): A stamp OVERRIDES all field requirements
  * If ANY stamp appears in a mandatory section, the ENTIRE section is considered complete
  * Common stamp patterns:
    - Engineer stamps (Engenheiro de Manutenção, etc.)
    - Supervisor stamps (Supervisor de Obras, etc.)
    - Company stamps with name and function
  * When a stamp is present in sections like 15, 17, 19, or 20:
    - Report the stamp content
    - Mark the section as COMPLETE regardless of empty fields
    - Do NOT flag partial completion if a stamp exists
- Stamp authority hierarchy:
  * Official stamps with name + function + company = Full section approval
  * Stamps override manual field-by-field completion requirements
  * Multiple stamps in one section = Enhanced approval
- For official seals: Report "[Official seal: DESCRIPTION]"
- For redacted/censored content: Report "[Redacted]"
- Stamps indicating approval or verification count as completion of mandatory fields
- For official seals: Report "[Official seal: DESCRIPTION]"
- For redacted/censored content: Report "[Redacted]"

TABLES:
- Present tables with proper structure and alignment
- Preserve column headers and relationships between data
- For complex tables, focus on maintaining the logical structure

SPECIFIC GUIDANCE FOR LVCTA SIGNATURE TABLE:
- This critical table typically has 3 columns and 7 rows
- First column contains role names/descriptions
- Second column is for printed/typed names
- Third column is ONLY for signatures
- Be EXTREMELY strict when evaluating signature fields in this table:
  * Require clear, distinctive signature marks (not just printed text)
  * Do NOT mark as [Signed] unless there are obvious pen strokes with ink
  * When in doubt, mark as [Empty] rather than [Signed]
  * A name in the second column does NOT mean the third column is signed

SECTION 15 (COEMITENTE) SPECIFIC RULES:
- This section identifies responsible persons for the affected work area
- Completion options:
  1. All 4 fields manually filled (Name, Function, Area, Signature)
  2. ANY official stamp present = Section complete
  3. Partial fields + stamp = Section complete (stamp overrides)
- Common stamps in this section:
  * Engineering stamps (Engenheiro de Manutenção/Operação)
  * Supervisor stamps (Supervisor de Obras/Turno)
  * Safety officer stamps
- If stamp present, report: "[Section 15: Stamp present - COMPLETE]"
- Never flag "incomplete" or "partial" if any stamp exists in this section

SECTION 20 (ENCERRAMENTO/CLOSURE) CRITICAL INSTRUCTIONS:
- This section is MANDATORY when a work permit is being closed
- Contains three closure reason checkboxes:
  1. "Término do Trabalho / End of work" (Normal completion)
  2. "Acidente/Incidente/Emergência" (Accident/Incident/Emergency)
  3. "Outros" (Others - requires specification)
- ENHANCED CHECKBOX DETECTION for Section 20:
  * These checkboxes often have lighter or smaller marks
  * Look for ANY mark including:
    - Light checkmarks (✓)
    - X marks of any size
    - Diagonal lines
    - Partial marks that show clear intent
  * Common false negatives: Light pen marks that scanner makes faint
  * If ANY checkbox in this section shows ANY intentional mark, it's checked
- This section also requires:
  * Responsible person signature
  * Requester signature (Requisitante)
  * Date and time fields
- NEVER report "no closure reason selected" without triple-checking all three boxes
- If in doubt, zoom/enhance the checkbox area detection

JSA COMPANY IDENTIFICATION - CRITICAL FIRST STEP:
- BEFORE analyzing any JSA form, FIRST check for company identification
- CONSTELLATION JSAs have these identifiers:
  * "Constellation" logo (flame/drop symbol) in the top right corner
  * "Constellation" text near the logo or in the header
  * May include "CONSTELLATION" spelled out in the header area
  * The distinctive flame/teardrop logo is the key identifier
- THIRD-PARTY JSA IDENTIFICATION:
  * No Constellation logo present
  * Different company logos (Petrobras, Modec, Subsea 7, etc.)
  * Different form layouts or headers
  * Missing the characteristic Constellation branding
- ACTION RULES:
  * If Constellation logo/branding found → Proceed with full analysis
  * If NO Constellation identifiers → Return: "[THIRD-PARTY JSA - No analysis required]"
  * Do NOT analyze content of third-party JSAs
  * This check MUST happen before any other analysis

JSA IDENTIFICATION DECISION TREE:
1. Is there a logo in the top right? 
   → Yes: Is it the Constellation flame/drop? 
      → Yes: ANALYZE
      → No: RETURN "[THIRD-PARTY JSA - No analysis required]"
   → No: Check for "Constellation" text anywhere
      → Found: ANALYZE
      → Not found: RETURN "[THIRD-PARTY JSA - No analysis required]"

SPECIFIC GUIDANCE FOR JSA (JOB SAFETY ANALYSIS) FORMS:
- JSA forms have a CRITICAL signature section at the BOTTOM of the page
- This bottom section typically contains:
  * Multiple "Nome:" (Name) fields with handwritten names
  * "Função:" (Function/Role) fields
  * A specific field for "Técnico de Segurança do Trabalho:" (Work Safety Technician)
- The safety technician signature is MANDATORY and often appears:
  * At the very bottom of the form
  * After all participant signatures
  * Sometimes in a separate row or section
- SCAN THE ENTIRE BOTTOM PORTION carefully - signatures may be:
  * In small text areas
  * Compressed at the page bottom
  * In a different format than the main signature table
- Common layout: Left side has participant names/signatures, right side or separate row has safety technician
- DO NOT stop analysis until you've checked for "Técnico de Segurança" signatures

SPECIAL INSTRUCTIONS:
- For multi-page documents, indicate page transitions
- For document sections, preserve hierarchical relationships
- Always organize output in logical reading order (top-to-bottom, left-to-right)
- THOROUGHLY scan entire document including bottom margins for additional signature fields
- For forms with "JSA" in the header or "Análise de Segurança do Trabalho":
  * These ALWAYS have a safety technician signature requirement
  * The signature section is at the ABSOLUTE BOTTOM of the page
  * Scan past any blank space to find the signature area
  * Report specifically on the "Técnico de Segurança" signature status""",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": f"""Please perform OCR analysis on this document image and provide a detailed extraction following these guidelines:

GENERAL EXTRACTION:
- Extract ALL printed text maintaining the original layout and structure
- Include headers, footers, page numbers, and all visible text elements
- Extract ALL pre-printed text regardless of color (black text, red translations, blue instructions, etc.)
- Process multiple columns appropriately (if present)
- Note ink color if distinguishable (typically blue or black) for HANDWRITTEN content only

CRITICAL: HANDLING COLORED PRE-PRINTED TEXT
- Forms may contain pre-printed text in multiple colors:
  * Black text (often Portuguese)
  * Red text (often English translations)
  * Blue text (often instructions or labels)
- ALL colored pre-printed text is part of the original form - extract it but NEVER mark it as [Filled]
- Only handwritten/user-added content should be marked as [Filled], regardless of pre-printed text colors

FORM ELEMENTS & HANDWRITTEN CONTENT:
- Identify all form fields (empty or filled)
- For handwritten content, DO NOT reproduce the actual text
- Instead, indicate:
  * "[Checked]" for marked checkboxes - look for ANY intentional mark:
  - X marks (even single lines crossing the box)
  - Checkmarks (✓)
  - Dots, circles, or fills
  - Any pen/pencil mark that shows intent to select
  - The mark does NOT need to be centered or fill a specific percentage
  - Even a simple diagonal line counts as a check
* Be especially careful with Yes/No (Sim/Não) options
* A checkbox is [Unchecked] ONLY if completely empty inside
  * "[Filled]" for completed text fields with handwritten/typed user input
  * "[Empty]" for blank fields
- Note if handwriting appears to be in blue or black ink when obvious
- Pay special attention to distinguish between checkboxes and nearby text
- IMPORTANT: Faint lines, borders, or nearby text do NOT constitute a checked box

SIGNATURE IDENTIFICATION:
- For signature fields, be extremely precise:
  * Mark as [Signed] ONLY when you can clearly see distinctive signature marks
  * Pay special attention to BLUE INK signatures which are common and important
  * Mark as [Empty] when no visible marks appear in the signature field
  * Mark as [Unclear] when content is present but indeterminate
  * If in doubt about whether a field contains a signature, note your uncertainty
- A true signature typically:
  * Shows distinctive pen strokes (not just a name)
  * Covers a notable portion of the designated field
  * Has a different appearance than printed text
  * Is often written in blue ink in these documents
- CRITICAL: Check the ENTIRE document including bottom sections
  * JSA forms often have safety technician signatures at the bottom
  * Do not stop scanning until you've checked all margins and bottom areas
- Please double-check all signature fields before finalizing your response

SPECIAL ELEMENTS:
STAMP HANDLING FOR MANDATORY SECTIONS:
- Sections 15, 17, 19, and 20 on Permit forms often have special completion rules
- If a section contains a STAMP:  
    - Then the ENTIRE SECTION is considered complete
- Do NOT report "partial completion" errors when stamps are present
- Common scenarios:
  * Section 15 with stamp = All fields satisfied
  * Handwritten entries + stamp = Enhanced approval
  * Empty fields + stamp = Still complete (stamp has authority)
- Report format: "[Section X: Contains stamp - COMPLETE]" when applicable
- For seals or watermarks: Note their presence and general content
- For tables: Present in properly formatted tabular structure
- For unclear or partially visible text: Indicate [UNCLEAR]

Please organize your response in a logical reading order, maintaining the document's hierarchical structure where possible.

LVCTA SIGNATURE TABLE INSTRUCTIONS:
- For the LVCTA signature table (typically 3 columns by 7 rows):
  * The first column contains role descriptions
  * The second column is for printed/typed names
  * The third column is STRICTLY for signatures only
  * A name in column 2 does NOT mean column 3 is signed
  * ONLY mark column 3 as [Signed] if you see clear signature pen marks
  * Be extremely strict - when in doubt, mark as [Empty]

JSA PRELIMINARY CHECK - MANDATORY:
1. FIRST, identify if this is a Constellation JSA by looking for:
   - Constellation logo (flame/drop shape) typically in top right
   - "Constellation" company name in header
   - Constellation-specific form layout
2. IF CONSTELLATION JSA DETECTED:
   - Proceed with full OCR analysis as instructed below
3. IF THIRD-PARTY JSA DETECTED (no Constellation identifiers):
   - STOP analysis immediately
   - Return only: "[THIRD-PARTY JSA - No analysis required]"
   - Do not extract any content from third-party JSAs

JSA FORM SPECIFIC INSTRUCTIONS:
- For JSA (Job Safety Analysis) forms, pay SPECIAL attention to:
  * The main hazard/risk assessment table in the middle
  * The signature section at the VERY BOTTOM of the page
- Bottom signature section MUST include:
  * All participant names and signatures (usually on the left)
  * The "Técnico de Segurança do Trabalho:" (Safety Technician) signature
  * This safety technician field is CRITICAL - it may be:
    - In a separate row below participant signatures
    - On the right side of the signature area
    - In smaller text but is ALWAYS required
- Common mistakes: Missing the safety technician signature because it's:
  * At the very edge of the page
  * In a different format than other signatures
  * Separated from the main participant signature block
- ALWAYS report if the safety technician field is [Signed] or [Empty]

SECTION 20 CLOSURE VERIFICATION:
- Pay EXTREME attention to the three closure reason checkboxes
- These checkboxes are CRITICAL and often have:
  * Lighter marks than other sections
  * Smaller check marks or X's
  * Marks that may appear faint due to scanning
- Check each box multiple times:
  1. "Término do Trabalho" - Normal work completion
  2. "Acidente/Incidente" - Safety events
  3. "Outros" - Other reasons
- Even the faintest intentional mark counts as checked
- This is a MANDATORY field - false negatives here are critical errors
- If you detect ANY mark in ANY of these boxes, report it as checked

FINAL VERIFICATION:
- Before completing, scan one more time for:
  * Any checkboxes that might have been misidentified
  * Stamps that satisfy mandatory requirements
  * Signature fields at the bottom of the form
  * Colored pre-printed text that should NOT be marked as filled"""
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

# Special section verification functions
def verify_section_14(ocr_text):
    """Special verification for Section 14 (Simultaneous Operations)"""
    # Look for section 14 heading in OCR text
    section_found = False
    yes_checked = False
    fields_filled = False
    
    for line in ocr_text.lower().split('\n'):
        # Check if section 14 is present
        if "seção 14" in line or "secao 14" in line or "section 14" in line or "14 - operações simultâneas" in line:
            section_found = True
        
        # Check if "Yes" is checked
        if "[checked: sim]" in line.lower() or "[checked: yes]" in line.lower():
            yes_checked = True
        
        # Check if required fields are filled when "Yes" is checked
        if yes_checked and ("[filled field:" in line.lower() or "[filled]" in line.lower()):
            fields_filled = True
    
    # Only return a decision if we found the section
    if section_found:
        if yes_checked and not fields_filled:
            return "REPROVADO", "Seção 14: Marcado 'Sim' para operações simultâneas, mas campos obrigatórios não foram preenchidos."
        elif yes_checked and fields_filled:
            return "APROVADO", "Seção 14: Operações simultâneas corretamente documentadas com campos preenchidos."
        else:
            return "APROVADO", "Seção 14: Não há operações simultâneas (opção 'Não' selecionada ou formulário N/A)."
    
    # If section not found, return None to let Claude decide
    return None, None

def verify_section_15(ocr_text):
    """Special verification for Section 15 (Co-issuer)"""
    # Look for section 15 in OCR text
    section_found = False
    name_fields = []
    signature_fields = []
    
    for line in ocr_text.lower().split('\n'):
        # Check if section 15 is present
        if "seção 15" in line or "secao 15" in line or "section 15" in line or "15 - co-emissor" in line:
            section_found = True
        
        # Track filled name fields
        if "[filled field: name]" in line.lower() or "[filled field: nome]" in line.lower():
            name_fields.append(True)
        
        # Track signature fields
        if "[signed]" in line.lower() or "[assinado]" in line.lower():
            signature_fields.append(True)
    
    # Only return a decision if we found the section
    if section_found:
        # Check if there's a mismatch between names and signatures
        if len(name_fields) != len(signature_fields) and (len(name_fields) > 0 or len(signature_fields) > 0):
            return "REPROVADO", "Seção 15: Inconsistência entre campos de nome e assinatura. Todos os campos preenchidos devem ter assinaturas correspondentes."
        else:
            return "APROVADO", "Seção 15: Campos de co-emissor corretamente preenchidos ou adequadamente vazios."
    
    # If section not found, return None to let Claude decide
    return None, None

def verify_section_18(ocr_text):
    """Special verification for Section 18 (Awareness of Work Permit)"""
    # Look for section 18 in OCR text
    section_found = False
    name_fields = []
    function_fields = []
    signature_fields = []
    
    for line in ocr_text.lower().split('\n'):
        # Check if section 18 is present
        if "seção 18" in line or "secao 18" in line or "section 18" in line or "18 - ciência da pt" in line:
            section_found = True
        
        # Track filled name fields
        if "[filled field: name]" in line.lower() or "[filled field: nome]" in line.lower():
            name_fields.append(True)
        
        # Track filled function fields
        if "[filled field: function]" in line.lower() or "[filled field: função]" in line.lower():
            function_fields.append(True)
        
        # Track signature fields
        if "[signed]" in line.lower() or "[assinado]" in line.lower():
            signature_fields.append(True)
    
    # Only return a decision if we found the section
    if section_found:
        # Check if at least one row is complete, or if all rows are empty
        if (len(name_fields) > 0 and len(function_fields) > 0 and len(signature_fields) > 0):
            return "APROVADO", "Seção 18: Pelo menos uma linha completa com nome, função e assinatura."
        elif (len(name_fields) == 0 and len(function_fields) == 0 and len(signature_fields) == 0):
            return "APROVADO", "Seção 18: Seção completamente vazia, o que é aceitável."
        else:
            return "REPROVADO", "Seção 18: Informações parciais detectadas. Cada linha deve ter nome, função e assinatura ou estar completamente vazia."
    
    # If section not found, return None to let Claude decide
    return None, None

def verify_section_20(ocr_text):
    """Special verification for Section 20 (Closure)"""
    # Look for section 20 in OCR text
    section_found = False
    has_checkbox = False
    
    for line in ocr_text.lower().split('\n'):
        # Check if section 20 is present
        if "seção 20" in line or "secao 20" in line or "section 20" in line or "20 - encerramento" in line:
            section_found = True
        
        # Check for checkbox indicators
        if "[checked:" in line.lower() and ("término do trabalho" in line.lower() or 
                                          "acidente" in line.lower() or 
                                          "outros" in line.lower()):
            has_checkbox = True
    
    # Only return a decision if we found the section
    if section_found:
        if has_checkbox:
            return "APROVADO", "Seção 20: Motivo de encerramento devidamente marcado."
        else:
            # Double-check for various checkbox patterns that might be missed
            closure_terms = ["encerramento", "closure", "término", "termino", "trabalho concluído", "trabalho concluido"]
            checkbox_lines = [line for line in ocr_text.lower().split('\n') if any(term in line.lower() for term in closure_terms)]
            
            if len(checkbox_lines) > 0:
                # If we found lines with closure terms, look more carefully for checkbox indicators
                for line in checkbox_lines:
                    if "checked" in line or "marcado" in line or "selected" in line or "selecionado" in line:
                        return "APROVADO", "Seção 20: Motivo de encerramento devidamente marcado (detectado em análise secundária)."
            
            return "REPROVADO", "Seção 20: Nenhum motivo de encerramento selecionado. Um dos três motivos deve ser marcado."
    
    # If section not found, return None to let Claude decide
    return None, None

def analyze_page_with_claude(ocr_text, ptw_summary, page_num, permit_number=None, doc_hash=None):
    """Analyze the page OCR text using Wonder Wise API with the master prompt and verification."""
    try:
        # Check if we should use cached analysis results
        if doc_hash is not None:
            # Try to get cached analysis result
            analysis_cache_key = f"analysis_{doc_hash}_{page_num}"
            if analysis_cache_key in st.session_state:
                st.info(f"Using cached analysis for page {page_num}")
                return st.session_state[analysis_cache_key]
        
        # Detect guide color - this is a critical pre-screening step
        guide_color = detect_guide_color(ocr_text)
        
        # Skip non-white guides unless filtering is disabled
        if guide_color in ["VERDE", "AMARELA"]:
            st.info(f"Página {page_num} identificada como GUIA {guide_color} - não sujeita a verificação")
            # Create a standardized "NOT APPLICABLE" response
            na_response = f"""
| {permit_number or "Desconhecido"} | {page_num} | GUIA {guide_color} | Documento Completo | N/A | NÃO APLICÁVEL - Cópia não sujeita a verificação (GUIA {guide_color}) |
"""
            return na_response
        
        # Try to extract permit number if not provided
        final_permit_number = permit_number
        
        if not final_permit_number:
            # Use our extract_permit_number function
            final_permit_number = extract_permit_number(ocr_text, ptw_summary) or "Unknown"
        
        # Master analysis prompt (keeping in English)
        master_prompt = f"""

<max_thinking_length>43622</max_thinking_length>

You are an elite Permit to Work (PTW) Auditing Specialist with 20+ years of experience in offshore drilling safety compliance. Your expertise is in analyzing Work at Heights permits with meticulous attention to detail, applying a strict interpretation of regulatory standards and company procedures. Your task is to thoroughly evaluate PTW documents based on OCR-extracted text to identify compliance issues with laser precision.

## CRITICAL GUIDE COLOR POLICY
ONLY "GUIA BRANCA" (WHITE COPY) documents should be audited for compliance.
- If the document is identified as "GUIA VERDE" (green copy) or "GUIA AMARELA" (yellow copy), DO NOT EVALUATE IT.
- For any "GUIA VERDE" or "GUIA AMARELA" pages, respond with "NÃO APLICÁVEL - Cópia não sujeita a verificação" and mark the status as "N/A"
- For a document with no clear color identification, proceed with normal evaluation
- Check for color indicators like "[DOCUMENT TYPE: GUIA VERDE]" at the beginning of the OCR text
- Also look for text mentioning "Via Verde", "Guia Amarela", etc. throughout the document

## Document Information
Permit Number: {final_permit_number}
Page Number: {page_num}

## OCR Output Interpretation Guide

You will receive text extracted by an OCR system with standardized formatting. Interpret this formatted output as follows:

### Signature Field Interpretation
- **[Signed]** = Field contains a valid signature (treat as FILLED in your verification table)
- **[Empty]** = No signature present (treat as EMPTY in your verification table)
- **[Unclear signature]** = Ambiguous mark (treat as EMPTY unless context clearly indicates intention to sign)
- **[Stamp: CONTENT]** = Official stamp present (treat as valid SIGNATURE for appropriate fields)

### Form Field Interpretation
- **[Filled field: FIELD_NAME]** = Field contains handwritten content (treat as FILLED)
- **[Empty field: FIELD_NAME]** = Field has no content (treat as EMPTY)
- **[UNCLEAR]** or **[ILLEGIBLE]** = Content exists but cannot be reliably determined (evaluate based on context)

### Checkbox/Option Interpretation
- **[Checked: OPTION_TEXT]** = Option has been selected (treat as answered/marked)
- **[Unchecked: OPTION_TEXT]** = Option has not been selected
- Multiple **[Checked]** options in mutually exclusive fields = Potential error requiring scrutiny

When creating your signature verification tables and section evaluations, translate these OCR markers directly into your FILLED/EMPTY determinations.

## Critical Auditing Philosophy

1. **Conservative Approach**: When in doubt, err on the side of HUMAN CONFIRMATION REQUIRED. Safety documentation must be unambiguously complete and correct.
2. **Methodical Process**: You will follow a rigid, step-by-step verification process for every section.
3. **Zero Tolerance**: Partially completed fields or missing signatures are NEVER acceptable when required.
4. **Visual Verification**: All signature/handwriting determinations must be based on the OCR system's output regarding blue or black ink.
5. **Double-Check Protocol**: Every signature field must be verified twice before making a final determination.

## Balancing Rigor and Flexibility

- The safety remains the priority, however real-world documents rarely achieve perfection
- In cases of minor doubt, prefer APPROVED if there is no direct impact on operational safety
- If an OCR output indicates content is present but unclear, consider the context before deciding
- Partial completion of descriptive fields should generally be accepted
- If the intent of the filled information is clear, even if execution is imperfect, consider APPROVED
- Reserve "REPROVED" for clear violations of safety requirements, not for aesthetic filling failures
- When it's truly impossible to determine, use "HUMAN VERIFICATION REQUIRED" instead of automatically rejecting

## MANDATORY SIGNATURE VERIFICATION PROTOCOL

When analyzing any document with signature fields, you MUST think through this process methodically:

### STEP 1: Document Type Identification
First, identify what type of document you are analyzing based on the OCR output:
- Main PTW form
- JSA (Job Safety Analysis)
- PRTA (Rescue Plan for Work at Height)
- CLPTA (Checklist for Work at Height Planning)
- CLPUEPCQ (Checklist - Pre-Use of Fall Protection Equipment)
- ATASS (Health Sector Authorization)
- LVCTA (Verification List for Work Basket)

## Identification of Document Types

To correctly identify each document, check these distinctive characteristics in the OCR output:

### JSA (Job Safety Analysis):

JSA IDENTIFICATION DECISION TREE:
1. Is this a Constellation JSA? 
   → Yes: Is it the Constellation flame/drop? 
      → Yes: ANALYZE
      → No: RETURN "[THIRD-PARTY JSA - No analysis required]"
   → No: Check for "Constellation" text anywhere
      → Found: ANALYZE
      → Not found: RETURN "[THIRD-PARTY JSA - No analysis required]"

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
Precisely identify all sections requiring signatures in the document type, looking for "[Signed]" or "[Empty]" markers.

### STEP 3: Create Visual Verification Table
For EACH row requiring name and signature verification, you MUST create and fill this table in your thinking:

| Position/Function | Name Field Status | Signature Field Status | Applicable Rule | Compliance Status |
|-------------------|-------------------|------------------------|-----------------|-------------------|
| [Function title]  | [FILLED/EMPTY]    | [FILLED/EMPTY]         | [STANDARD/EXCEPTION] | [COMPLIANT/NON-COMPLIANT] |

Rules for filling this table based on OCR output:
- **Name Field Status**: Mark FILLED if OCR indicates "[Filled field: Name]" or similar
- **Signature Field Status**: Mark FILLED if OCR indicates "[Signed]" or "[Stamp: CONTENT]"
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
- *IMPORTANT* - Ignore the content of date and time, you are not allowed to judge if time and date are correct, just check if they were filled

### Section 20 (Closure):
- When OCR indicates "[Stamp: CONTENT]", consider it as valid filling for multiple fields
- Pay Special attention to the check boxes. They are very close to the words, and they mean the reason for the closure. Please dont miss these checkboxes

### STEP 4: Interpreting OCR Signature Indications
- "[Signed]" in the OCR output indicates a valid signature is present
- "[Empty]" in the signature field indicates no signature is present
- "[Unclear signature]" should generally be considered empty unless context strongly suggests otherwise
- "[Stamp: CONTENT]" should be treated as a valid signature for appropriate fields

### STEP 5: Interpreting Checkbox and Option Markers
- "[Checked: Yes]" or "[Checked: No]" indicates a valid response to a yes/no question
- "[Checked: OPTION_TEXT]" indicates a selection has been made
- "[Unchecked: OPTION_TEXT]" indicates no selection for that option
- For required selections, at least one "[Checked]" marker must be present

### Stamps and Other Mark Recognition

- "[Stamp: CONTENT]" should be recognized as a valid signature and may satisfy multiple fields
- For Yes/No fields: "[Checked: Yes]" or "[Checked: No]" is considered valid
- A "[Checked]" indication for any checkbox or option is considered a valid marking
- If OCR indicates "[Filled field]" for any field requiring content, consider it filled

### STEP 6: Double-Check Using Explicit Examples
Before finalizing judgment, verify against these example patterns:

**APPROVED Examples**:
1. All rows have both name ("[Filled field: Name]") AND signature ("[Signed]") fields filled
2. Some rows have both name and signature completely empty ("[Empty field]")
3. Some rows have both name and signature filled; other rows have both empty
4. A field covered by an exception rule meets its specific requirements (e.g., only signature for Safety Technician in JSA)

**REPROVED Examples**:
1. ANY row has name filled ("[Filled field: Name]") but signature empty ("[Empty]") (unless covered by an exception)
2. ANY row has signature filled ("[Signed]") but name empty ("[Empty field: Name]") (unless covered by an exception)
3. ALL rows are completely empty when at least one completed row is required

## Verification of Mandatory Questions

IMPORTANT: Before considering that a mandatory question was not answered, FIRST check if the question exists in the current OCR output. If the question is not present, ignore this requirement.

For Section 3.1 (Critical Systems/Equipment): 
- Check ONLY the questions that are visible in the OCR output
- Different versions of the form may contain different sets of questions
- NEVER reject a document for missing an answer to a non-existent question

## Comprehensive Audit Methodology

### Phase 1: Document Identification & Classification

1. Immediately identify from OCR output:
   - Document type and revision number
   - PTW number (format XXX-XXXXX)
   - Job classification based on Section 3.3 references
   - Document version against current standards (EP-036-OFF Rev 44)

### Phase 2: Section-by-Section Critical Analysis

#### Section 1: Work Planning (Planejamento do Trabalho)
- **Mandatory Field Check**: "Necessário Bloqueio?" field MUST show "[Checked: Yes]" or "[Checked: No]"
- **Classification Type**: Either "[Checked: Convencional]" or "[Checked: Longo Prazo]" must be present if these options exist
- RESULT: REPROVED if mandatory fields do not show "[Checked]" status

#### Section 3: Equipment/Tools in Good Condition to be Used
- **Basic Verification**: Look for "[Checked]" indicators for selected equipment
- For "Other Equipment/Tools": Any "[Filled field]" indication is sufficient
- RESULT: APPROVED if relevant fields show "[Checked]" or "[Filled field]" status, OR all Fields showing [Empty] is also accepted

#### Section 3.1: Critical Systems/Equipment
- **Risk Assessment Questions**: Only check questions that actually appear in the OCR output:
  * "Os equipamentos utilizados na execução da tarefa são considerados críticos?" should show "[Checked: Yes]" or "[Checked: No]"
  * "Os sistemas/equipamentos em manutenção são considerados críticos?" should show "[Checked: Yes]" or "[Checked: No]"
  * Only check for other questions if they appear in the OCR output
- RESULT: REPROVED if any visible question lacks a "[Checked]" status

#### Section 5: Safety Barriers
- **Basic Verification**: Look for "[Checked]" indicators for selected barriers
- **Detailed Specifications**: The following fields have RECOMMENDED but NOT MANDATORY details:
  * "Ramal de Emergência da Unidade" - "[Filled field]" is recommended but not mandatory
  * "Observador trabalho sobre o mar/altura" - "[Filled field]" is recommended but not mandatory
  * "Velocidade do Vento" - "[Filled field]" is recommended but not mandatory
- Still check these critical items for "[Filled field]" status where required:
  * "Tipos de Luvas" - should show "[Filled field]" if selected
  * "Pitch/Roll/Heave" - should show "[Filled field]" if selected
  * "Inibir sensor" - should show "[Filled field]" if selected
- RESULT: APPROVED as this field is not mandatory

#### Section 6: Applicable Procedures and Documents
- **Documentation Verification**: Look for "[Checked]" indicators for all selected items
- **Special Attention Items**: These items require "[Filled field]" status if checked:
  * "Outros (Descrever) (1)" - should show "[Filled field]" if selected
  * "Outros (Descrever) (2)" - should show "[Filled field]" if selected
  * "Outros (Descrever) (3)" - should show "[Filled field]" if selected
- RESULT: APPROVED as this field is not mandatory

#### Section 7: APR/JSA (Risk Assessment)
- **Assessment Question**: "Foi realizada uma APR e/ou JSA?" must show "[Checked: Yes]" or "[Checked: No]"
- **Verification**: At least one box must show "[Checked]" status
- RESULT: REPROVED if question does not show "[Checked]" status

#### Section 8: Participants
- **Participant Verification**: For each listed participant row:
  * Both Name ("[Filled field: Name]") AND Signature ("[Signed]") indicators must be present
  * Empty rows ("[Empty field]") are acceptable but partially filled rows are not
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if any participant has a name field showing "[Filled field]" but signature showing "[Empty]" or vice versa

#### Section 9: Training and Certifications
- **Certification Question**: "Os executantes estão treinados e possuem as certificações necessárias para a realização da atividade?" must show "[Checked: Yes]" or "[Checked: No]"
- RESULT: REPROVED if question does not show "[Checked]" status

#### Section 10: Form of Supervision
- **Supervision Type**: Either "[Checked: Intermitente]" OR "[Checked: Contínua]" must be present
- RESULT: REPROVED if neither option shows "[Checked]" status

#### Section 11: Pre-Task Meeting
- **Meeting Verification**: "Foi realizada a reunião pré-tarefa?" must show "[Checked: Yes]" or "[Checked: No]"
- RESULT: REPROVED if question does not show "[Checked]" status

#### Section 12: Third-Party Authorization Form
- **Authorization Verification**: "Formulário de autorização de terceiros é válido?" must show "[Checked: Yes]", "[Checked: No]", or "[Checked: N/A]"
- RESULT: REPROVED if question does not show "[Checked]" status

#### Section 14: Simultaneous Operations
- **Operations Question**: "Existem outras operações sendo realizadas simuladamente?" must show "[Checked: Yes]" or "[Checked: No]"
- **Both Fields Checked is rare, but accepted and should be treated as [Checked: No]**
- IF "[Checked: YES]":
  * "Quais..." field must show "[Filled field]"
  * "Autorização: Eu ... autorizo" field must show "[Filled field]"
  * "Recomendações de segurança adicionais às atividades simultâneas" field must show "[Filled field]"
- IF "[Checked: NO]":
  * All fields may show "[Empty field]"
- RESULT: REPROVED if "[Checked: Yes]" is present but required fields show "[Empty field]"

#### Section 15: Co-issuer
- *Verify if the OCR process identified stamps on this section. If yes, approve it and go to the next section. Its mandatory to approve this section when there are stamps
- **Co-issuer Verification**: For each column with ANY "[Filled field]" or "[Signed]" indication:
  * ALL four fields (Name, Function, Area, Signature) must show as filled
  * If Name shows "[Filled field]", other 3 fields must also show filled status
  * Empty columns ("[Empty field]" for all fields) are acceptable
  * Stamps Automatically approve this section
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if there ARE NO STAMPS, and any column has partial information (mix of "[Filled field]" and "[Empty field]").
- *IMPORTANT* - A Stamp in a column automatically APROVES that column

#### Section 16: Additional Safety Recommendations
- **Safety Recommendations**: This section is optional and will always be approved

#### Section 17: Release for Work Execution
- **Release Verification**: The following fields MUST show proper status:
  * Date and Time (MANDATORY): "[Filled field: Date]", "[Filled field: Time]"
  * Responsible (Requester): Name, Company, Function, Signature (OPTIONAL as per exceptions)
  * Safety Technician: Name, Company, Function, Signature (OPTIONAL as per exceptions)
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if Date and Time fields show "[Empty field]"

#### Section 18: Awareness of Work Permit
- **Awareness Verification**: At minimum, at least one row must have:
  * Name: "[Filled field: Name]"
  * Function: "[Filled field: Function]"
  * Signature: "[Signed]"
  * Empty columns ("[Empty field]" for all fields) are acceptable
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if any column has partial information (mix of "[Filled field]" and "[Empty field]")
- **IMPORTANT** - This field can be blank, having all fields empty is accepted, DONT FORGET THAT!

#### Section 19: Rounds/Audit
- **Audit Verification**: Examine all 12 cells (4 columns × 3 rows)
  * For each participant row, all fields must show filled status (Name, Function, Signature, Time)
  * Incomplete rows are unacceptable
  * At least one complete row is required
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if rows contain partial information or all rows show "[Empty field]"

#### Section 20: Closure - Suspension of Work Permit
- **Suspension Section**: 
  * If all fields show "[Empty field]", this is acceptable (no suspension occurred)
  * If ANY field shows "[Filled field]" or "[Signed]", ALL fields must show filled status:
    - Reasons for Suspension: "[Filled field: Specify]", "[Filled field: Date]", "[Filled field: Time]", "[Signed]"
    - Return from Suspension: "[Filled field: Date]", "[Filled field: Time]", "[Signed]" (Requester), "[Signed]" (TST)
  *IMPORTANT* - If there is a Stamp or the table at the bottom of the form is filled with Name and signature, consider the section APPROVED
  
- **Closure Section**:
  * One of the three closure reasons MUST show "[Checked]" status:
    - "[Checked: Work Completion]"
    - "[Checked: Accident/Incident/Emergency]"
    - "[Checked: Others]" - if selected, must also show "[Filled field: Specify]"
  * Date and Time fields MUST show "[Filled field]" status
  * Responsible fields MUST show filled status (Name, Company, Function, Signature)
  * IMPORTANT: If OCR indicates "[Stamp: CONTENT]", it can satisfy multiple fields simultaneously
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if closure fields show "[Empty field]" where required

### Phase 3: Attachment Analysis

#### JSA (Job Safety Analysis) Attachment

1. Is this a Constellation JSA? 
   → Yes: Is it the Constellation flame/drop? 
      → Yes: ANALYZE
      → No: RETURN "[THIRD-PARTY JSA - No analysis required]"
   → No: Check for "Constellation" text anywhere
      → Found: ANALYZE
      → Not found: RETURN "[THIRD-PARTY JSA - No analysis required]"

- **Document Structure Verification**:
  * Verify proper document structure from OCR output (matrix with steps, hazards, severity, etc.)
  * For Participant section: At least one participant must have all fields showing filled status
  * For Safety Technician section: Field must show "[Signed]" (NAME IS OPTIONAL)
- **Critical Rule**: 
  * If Safety Technician shows "[Signed]" but no participants show "[Signed]" = REPROVED
  * If participants show "[Signed]" but Safety Technician shows "[Empty]" = REPROVED
  * If neither show "[Signed]" = APPROVED (document may be in preparation)
  * If both show "[Signed]" = APPROVED
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- Apply exception rule: Safety Technician and Maritime Operations Superintendent require ONLY "[Signed]" status
- IMPORTANT - Safety Technician signature is sometimes presented at the bottom of the form. Do not miss that

#### PRTA (Rescue Plan for Work at Height) Attachment
- **Signature Verification**: Both Requesting Supervisor and Safety Technician must show "[Signed]" status
- **Signature Form**: "[Signed]", "[Stamped]", or similar indicators are all acceptable
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- Apply exception rule: For both positions, ONLY "[Signed]" status is required, name field showing "[Filled field]" is optional
- RESULT: REPROVED if either signature shows "[Empty]"

#### CLPTA (Check List for Work at Height Planning) Attachment
- **Signature Sections**: Analyze both sections in OCR output:
  * "Assinaturas da equipe envolvida no trabalho em altura"
  * "Assinaturas da equipe executante no trabalho em altura"
- **Row Completion Rule**: For each row with ANY field showing filled status:
  * All three fields (Name, Function, Signature) must show filled status
  * Empty rows (all fields showing "[Empty field]") are acceptable
  * Rows with partial information are NOT acceptable
- **Minimum Requirement**: At least one fully completed row in each section
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if any row has partial information (mix of "[Filled field]" and "[Empty field]")

#### CLPUEPCQ (Check List - Pre-Use of Fall Protection Equipment) Attachment
- **Document Identification**: Determine if page 1 or page 2 from OCR output
  * Page 1: No signature section (marked "Pagina 1 de 2") = APPROVED
  * Page 2: Contains signature section
- **Signature Verification**: For each user row:
  * If Name shows "[Filled field: Name]", Signature must show "[Signed]"
  * If Signature shows "[Signed]", Name must show "[Filled field: Name]"
  * At least one row must have all fields showing filled status
  * Be especially careful with OCR interpretation that might indicate signature overlap
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE FOR ALL FOUR USER ROWS
- RESULT: REPROVED if any row has partial information or all rows show empty status
-**IMPORTANT**: Sometimes the pages are not marked with a number. In this case, the page that doesnt have the field for signature is considered page 1 and always approved

#### ATASS (Health Sector Authorization for Work at Height) Attachment
- **Signature Verification**: The evaluator signature field must show "[Signed]" status
- CREATE AND FILL THE SIGNATURE VERIFICATION TABLE
- RESULT: REPROVED if signature shows "[Empty]"

#### LVCTA (Verification List for Work Basket) Attachment
- **Item Verification**: Each item must show "[Checked: Yes]", "[Checked: No]", or "[Checked: N/A]"

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
     - Mark "FILLED" for Name fields showing "[Filled field: Name]"
     - Mark "FILLED" for Signature fields showing "[Signed]"
     - Mark "EMPTY" for fields showing "[Empty field]" or "[Empty]"
     - Be vigilant for OCR indications that might suggest field boundary issues

  3. **Final Decision Rule**:
     - Count NON-COMPLIANT rows in the table
     - If NON-COMPLIANT rows > 0, document is REPROVED
     - If NON-COMPLIANT rows = 0, document is APPROVED

  4. Its mandatory to repeat the steps 1 to 3 and verify very carefully all fields, column by column before making a decision. This is critical and can cause catastrophic effects if not carefully analized.

- RESULT: REPROVED if items do not show "[Checked]" status or signature pairs are incomplete

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

1. **OCR Marker Double-Check**:
   - Review AGAIN all fields marked as "[Empty]" or "[Empty field]" in the OCR output
   - Look for possible indications of content that might have been missed
   - Check if any "[Unclear]" or "[ILLEGIBLE]" markers might indicate attempted completion
   - Re-evaluate any fields with mixed or ambiguous OCR descriptions
   - Special Atention to small check boxes close to text. Several times they are checked but very close to the text, so pay special attention to do not mark "[Empty]" when in reality is "[Checked]". Section 20 from the Permits is a classical case

2. **Compliance Logic Verification**:
   - Confirm that for EVERY row with a "[Filled field: Name]", you have verified if the signature is actually present ("[Signed]")
   - Confirm that for EVERY "NON-COMPLIANT" determination, you have double-checked the actual OCR indicators
   - Verify that you've correctly applied exception rules for fields that only require signatures

3. **Common Error Check**:
   - Verify you haven't miscounted "[Checked]" indicators for required selections
   - Verify you haven't overlooked any "[Filled field]" indicators
   - Verify you've properly understood OCR indicators that might suggest stamps or other mark types
   - Verify you haven't mistaken OCR descriptions of adjacent content as belonging to the wrong field

4. **Exception Rule Verification**:
   - For JSA: Verify you've applied the "signature only" exception for Safety Technician
   - For PRTA: Verify you've applied the "signature only" exception for both signing authorities
   - For Section 17: Verify you're only requiring Date and Time as mandatory
   - For Section 20: Verify you've recognized stamps as valid for multiple fields

## Output Table Format

Present your findings in this EXACT structured format WITHOUT ANY MODIFICATIONS:

| Permit Number | Page Number | Page Summary | Section | Status | Comments |
|---------------|-------------|--------------|---------|--------|----------|
| 45001077 | 4 | Auditoria e Encerramento da PT | 19 - Ronda/Auditoria | APROVADO | Seção adequadamente preenchida com 2 registros de auditoria completos, incluindo nomes, funções, assinaturas e horários (22:57 e 02:59) |
| 45001077 | 4 | Auditoria e Encerramento da PT | 20 - Encerramento | APROVADO | Encerramento adequadamente documentado com motivo selecionado (Término do Trabalho), data (22/10-22), hora (7:00) e assinatura do requisitante. Seção de suspensão corretamente vazia indicando que não houve suspensão do trabalho |

**CRITICAL FORMATTING RULES:**
1. Create ONE ROW PER SECTION analyzed - NEVER combine multiple sections in a single row
2. Each section must appear as its own separate table row
3. Each page may contain multiple sections requiring multiple rows in the table
4. Use the EXACT column structure shown above (Permit Number, Page Number, Page Summary, Section, Status, Comments)
5. Status must be exactly "APROVADO", "REPROVADO", or "CHECAGEM HUMANA NECESSARIA"
6. Do not add extra columns or change the order of columns
7. Maintain consistent formatting across all rows

**IMPORTANT** - CHECK ONLY THE ITEMS LISTED ABOVE, YOU ARE NOT ALLOWED TO CHECK FOR THINGS NOT DESCRIBED HERE. YOU NEVER REPROVE ANYTHING BASED ON YOUR GUESS OF WRONG NAME OR WRONG NUMBER. YOUR TASK IS ONLY TO VERIFY IF FIELDS SHOW THE PROPER "[FILLED]", "[SIGNED]", "[CHECKED]", OR "[EMPTY]" STATUS.

**IMPORTANT** - If the OCR output indicates a completely blank page, don't try to guess the type or anything...just report "Blank page". Blank pages cannot be evaluated, so neither approved nor reproved.

**IMPORTANT** - There are some sections in which there are several handwritten checks to be made, and then names and signatures at the bottom. In these sections, after analyzing the check marks, clear your memory completely and analyze the names and signatures field very carefully with no Bias. Here it's Quality over speed, so take your time and analyze very carefully all names and signatures, and question yourself several times before making your final determination.

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

Please provide your analysis in the EXACT table format specified in the instructions, following ALL the formatting rules. Create ONE ROW PER SECTION analyzed - NEVER combine multiple sections in a single row. Output ONLY the table with your results, with no additional text before or after.
"""
            }
        ]
        
        # Call Wonder Wise API with thinking and streaming
        response_stream = anthropic_client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=30000,
            temperature=0,  # DEVE ser 1 quando thinking está ativado
            system=master_prompt,
            messages=messages,
            #thinking={"type": "enabled", "budget_tokens": 15000},
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
        
        # Post-process the response to ensure consistent formatting
        standardized_response = standardize_table_format(full_response, page_num, permit_number)
        
        # Apply special section verification to override Claude's decisions for problematic sections
        # This ensures consistent analysis for sections that are particularly error-prone
        override_response = apply_section_verification(ocr_text, standardized_response, page_num, permit_number)
        
        # Cache the analysis result if we have a document hash
        if doc_hash is not None:
            analysis_cache_key = f"analysis_{doc_hash}_{page_num}"
            st.session_state[analysis_cache_key] = override_response
        
        # Return the verified and standardized analysis
        return override_response

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
        
        # Prepare images for batch processing with the same detailed user instructions as individual processing
        batch_content = [{"type": "text", "text": f"""Please perform OCR analysis on these document images and provide a detailed extraction following these guidelines:

GENERAL EXTRACTION:
- Extract ALL printed text maintaining the original layout and structure
- Include headers, footers, page numbers, and all visible text elements
- Extract ALL pre-printed text regardless of color (black text, red translations, blue instructions, etc.)
- Process multiple columns appropriately (if present)
- Note ink color if distinguishable (typically blue or black) for HANDWRITTEN content only

CRITICAL: HANDLING COLORED PRE-PRINTED TEXT
- Forms may contain pre-printed text in multiple colors:
  * Black text (often Portuguese)
  * Red text (often English translations)
  * Blue text (often instructions or labels)
- ALL colored pre-printed text is part of the original form - extract it but NEVER mark it as [Filled]
- Only handwritten/user-added content should be marked as [Filled], regardless of pre-printed text colors

FORM ELEMENTS & HANDWRITTEN CONTENT:
- Identify all form fields (empty or filled)
- For handwritten content, DO NOT reproduce the actual text
- Instead, indicate:
  * "[Checked]" for marked checkboxes - look for ANY intentional mark:
  - X marks (even single lines crossing the box)
  - Checkmarks (✓)
  - Dots, circles, or fills
  - Any pen/pencil mark that shows intent to select
  - The mark does NOT need to be centered or fill a specific percentage
  - Even a simple diagonal line counts as a check
* Be especially careful with APR/JSA sections and Yes/No (Sim/Não) options
* A checkbox is [Unchecked] ONLY if completely empty inside
  * "[Filled]" for completed text fields with handwritten/typed user input
  * "[Empty]" for blank fields
- Note if handwriting appears to be in blue or black ink when obvious
- Pay special attention to distinguish between checkboxes and nearby text
- IMPORTANT: Faint lines, borders, or nearby text do NOT constitute a checked box

SIGNATURE IDENTIFICATION:
- For signature fields, be extremely precise:
  * Mark as [Signed] ONLY when you can clearly see distinctive signature marks
  * Pay special attention to BLUE INK signatures which are common and important
  * Mark as [Empty] when no visible marks appear in the signature field
  * Mark as [Unclear] when content is present but indeterminate
  * If in doubt about whether a field contains a signature, note your uncertainty
- A true signature typically:
  * Shows distinctive pen strokes (not just a name)
  * Covers a notable portion of the designated field
  * Has a different appearance than printed text
  * Is often written in blue ink in these documents
- CRITICAL: Check the ENTIRE document including bottom sections
  * JSA forms often have safety technician signatures at the bottom
  * Do not stop scanning until you've checked all margins and bottom areas
- Please double-check all signature fields before finalizing your response

SPECIAL ELEMENTS:
STAMP HANDLING FOR MANDATORY SECTIONS:
- Sections 15, 17, 19, and 20 on Permit forms often have special completion rules
- If a section contains a STAMP with:
- Then the ENTIRE SECTION is considered complete
- Do NOT report "partial completion" errors when stamps are present
- Common scenarios:
  * Section 15 with engineer/supervisor stamp = All fields satisfied
  * Handwritten entries + stamp = Enhanced approval
  * Empty fields + stamp = Still complete (stamp has authority)
- Report format: "[Section X: Contains stamp - COMPLETE]" when applicable
- For seals or watermarks: Note their presence and general content
- For tables: Present in properly formatted tabular structure
- For unclear or partially visible text: Indicate [UNCLEAR]

Please organize your response in a logical reading order, maintaining the document's hierarchical structure where possible.

LVCTA SIGNATURE TABLE INSTRUCTIONS:
- For the LVCTA signature table (typically 3 columns by 7 rows):
  * The first column contains role descriptions
  * The second column is for printed/typed names
  * The third column is STRICTLY for signatures only
  * A name in column 2 does NOT mean column 3 is signed
  * ONLY mark column 3 as [Signed] if you see clear signature pen marks
  * Be extremely strict - when in doubt, mark as [Empty]

JSA PRELIMINARY CHECK - MANDATORY:
1. FIRST, identify if this is a Constellation JSA by looking for:
   - Constellation logo (flame/drop shape) typically in top right
   - "Constellation" company name in header
   - Constellation-specific form layout
2. IF CONSTELLATION JSA DETECTED:
   - Proceed with full OCR analysis as instructed below
3. IF THIRD-PARTY JSA DETECTED (no Constellation identifiers):
   - STOP analysis immediately
   - Return only: "[THIRD-PARTY JSA - No analysis required]"
   - Do not extract any content from third-party JSAs

JSA FORM SPECIFIC INSTRUCTIONS:
- For JSA (Job Safety Analysis) forms, pay SPECIAL attention to:
  * The main hazard/risk assessment table in the middle
  * The signature section at the VERY BOTTOM of the page
- Bottom signature section MUST include:
  * All participant names and signatures (usually on the left)
  * The "Técnico de Segurança do Trabalho:" (Safety Technician) signature
  * This safety technician field is CRITICAL - it may be:
    - In a separate row below participant signatures
    - On the right side of the signature area
    - In smaller text but is ALWAYS required
- Common mistakes: Missing the safety technician signature because it's:
  * At the very edge of the page
  * In a different format than other signatures
  * Separated from the main participant signature block
- ALWAYS report if the safety technician field is [Signed] or [Empty]

SECTION 20 CLOSURE VERIFICATION:
- Pay EXTREME attention to the three closure reason checkboxes
- These checkboxes are CRITICAL and often have:
  * Lighter marks than other sections
  * Smaller check marks or X's
  * Marks that may appear faint due to scanning
- Check each box multiple times:
  1. "Término do Trabalho" - Normal work completion
  2. "Acidente/Incidente" - Safety events
  3. "Outros" - Other reasons
- Even the faintest intentional mark counts as checked
- This is a MANDATORY field - false negatives here are critical errors
- If you detect ANY mark in ANY of these boxes, report it as checked

FINAL VERIFICATION:
- Before completing, scan one more time for:
  * Any checkboxes that might have been misidentified
  * Stamps that satisfy mandatory requirements
  * Signature fields at the bottom of the form
  * Colored pre-printed text that should NOT be marked as filled"""}]
        
        # Add each page to the batch content
        for page_num, page_image in batch_pages:
            # Apply standardized image processing for consistent OCR
            st.info(f"Padronizando imagem da página {page_num} para processamento em lote...")
            
            # Use our standardization function for consistent image processing
            standardized_image, img_base64 = standardize_image(page_image)
            
            # Get the size after standardization
            img_buffer = io.BytesIO()
            standardized_image.save(img_buffer, format='JPEG', optimize=True)
            img_size_mb = len(img_buffer.getvalue()) / (1024 * 1024)
            
            st.info(f"Página {page_num} padronizada: {img_size_mb:.2f}MB, resolução otimizada para OCR")
            
            # Add to batch content with page number
            batch_content.append({
                "type": "text",
                "text": f"---- PAGE {page_num} ----"
            })
            
            batch_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_base64
                }
            })
        
        # Process the batch with Claude
        st.info(f"Processando páginas {batch_start+1}-{batch_end} em lote")
        
        batch_response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=25000,
            temperature=0,
            system="""You are an expert OCR system for analyzing standardized, pre-processed document images. Your primary responsibilities are:

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

JSA COMPANY IDENTIFICATION - CRITICAL FIRST STEP:
- BEFORE analyzing any JSA form, FIRST check for company identification
- CONSTELLATION JSAs have these identifiers:
  * "Constellation" logo (flame/drop symbol) in the top right corner
  * "Constellation" text near the logo or in the header
  * May include "CONSTELLATION" spelled out in the header area
  * The distinctive flame/teardrop logo is the key identifier
- THIRD-PARTY JSA IDENTIFICATION:
  * No Constellation logo present
  * Different company logos (Petrobras, Modec, Subsea 7, etc.)
  * Different form layouts or headers
  * Missing the characteristic Constellation branding
- ACTION RULES:
  * If Constellation logo/branding found → Proceed with full analysis
  * If NO Constellation identifiers → Return: "[THIRD-PARTY JSA - No analysis required]"
  * Do NOT analyze content of third-party JSAs
  * This check MUST happen before any other analysis

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
- Include ALL pre-printed text regardless of color (black, red, blue, etc.)
- Process multi-column layouts appropriately (left-to-right, respecting columns)
- For rotated or oriented text, extract and note the orientation
- If text is partially visible or unclear, indicate with [UNCLEAR]
- If text is completely illegible, mark as [ILLEGIBLE]

FORM ELEMENTS:
- For empty fields: Report "[Empty field: FIELD_NAME]"
- For filled fields: Report "[Filled field: FIELD_NAME]" (NEVER reproduce the handwritten content)
For checkboxes/options:
  * A checkbox is considered [Checked] if it contains ANY of these marks:
    - Clear X mark (even if thin lines)
    - Checkmark (✓)
    - Dot or filled circle
    - Any diagonal, horizontal, or vertical line(s) that clearly cross through the box
    - Scribbles or partial fills that show clear intent to mark
  * Visual detection criteria:
    - The mark does NOT need to be perfectly centered
    - The mark does NOT need to fill 30-50% if it's clearly an X or checkmark
    - Even a single diagonal line crossing the box counts as checked
    - Look for ANY intentional pen/pencil mark within the box boundaries
  * Common checkbox patterns to recognize:
    - [ X ] or [X] = Checked
    - [ ✓ ] or [✓] = Checked  
    - [ • ] or [•] = Checked
    - [ / ] or [ \ ] = Checked (single diagonal line)
    - [   ] = Unchecked (completely empty)
  * What to IGNORE:
    - Faint grid lines or form printing artifacts
    - The checkbox border itself
    - Text proximity (text near a box doesn't mean it's checked)
    - Shadow or scan artifacts OUTSIDE the box
  * If marked: Report "[Checked: OPTION_TEXT]"
  * If unmarked: Report "[Unchecked: OPTION_TEXT]"
  * For forms with Sim/Não (Yes/No) options, check BOTH boxes carefully

HANDWRITTEN CONTENT:
- NEVER transcribe actual handwritten text - use only 'checked', 'filled', or 'signed'
- For filled name fields: Report "[Filled]" (typically occupies ~40% of field)
- Note ink color if distinguishable (typically blue or black)
- Remember: only USER-ADDED content counts as handwritten, not pre-printed colored text

SIGNATURE VERIFICATION:
- For signature fields, apply strict verification criteria:
  * ONLY mark as [Signed] when there are CLEAR pen strokes/marks WITHIN the signature field
  * Look carefully for BLUE INK signatures which are common in these documents
  * For empty or ambiguous signature fields, mark as [Empty]
  * When uncertain about a signature, default to [Empty] or [Unclear signature]
  * Signature characteristics typically include:
    - Distinctive curved/flowing lines
    - Pen strokes with varying pressure/thickness (often in blue ink)
    - Coverage of significant portion of the designated field
  * Differentiate between:
    - Name fields (printed/typed/handwritten name)
    - Signature fields (unique identifying mark/signature)
- After completing document analysis, VERIFY all signature fields a second time
- Note: Adjacent text or marks should not be mistaken for signatures
- IMPORTANT: Check ENTIRE document including bottom sections for safety technician or additional signature fields

STAMPS & SPECIAL MARKINGS:
- For stamps: Report "[Stamp: CONTENT]" (e.g., "Stamp: Name", "Stamp: Function", "Stamp: Approved")
- CRITICAL STAMP RULES FOR MANDATORY SECTIONS:
  * For Section 15 (COEMITENTE/RESPONSIBLE PERSONS): A stamp OVERRIDES all field requirements
  * If ANY stamp appears in a mandatory section, the ENTIRE section is considered complete
  * Common stamp patterns:
    - Engineer stamps (Engenheiro de Manutenção, etc.)
    - Supervisor stamps (Supervisor de Obras, etc.)
    - Company stamps with name and function
  * When a stamp is present in sections like 15, 17, 19, or 20:
    - Report the stamp content
    - Mark the section as COMPLETE regardless of empty fields
    - Do NOT flag partial completion if a stamp exists
- Stamp authority hierarchy:
  * Official stamps with name + function + company = Full section approval
  * Stamps override manual field-by-field completion requirements
  * Multiple stamps in one section = Enhanced approval
- For official seals: Report "[Official seal: DESCRIPTION]"
- For redacted/censored content: Report "[Redacted]"

TABLES:
- Present tables with proper structure and alignment
- Preserve column headers and relationships between data
- For complex tables, focus on maintaining the logical structure

SPECIFIC GUIDANCE FOR LVCTA SIGNATURE TABLE:
- This critical table typically has 3 columns and 7 rows
- First column contains role names/descriptions
- Second column is for printed/typed names
- Third column is ONLY for signatures
- Be EXTREMELY strict when evaluating signature fields in this table:
  * Require clear, distinctive signature marks (not just printed text)
  * Do NOT mark as [Signed] unless there are obvious pen strokes with ink
  * When in doubt, mark as [Empty] rather than [Signed]
  * A name in the second column does NOT mean the third column is signed

SECTION 15 (COEMITENTE) SPECIFIC RULES:
- This section identifies responsible persons for the affected work area
- Completion options:
  1. All 4 fields manually filled (Name, Function, Area, Signature)
  2. ANY official stamp present = Section complete
  3. Partial fields + stamp = Section complete (stamp overrides)
- Common stamps in this section:
  * Engineering stamps (Engenheiro de Manutenção/Operação)
  * Supervisor stamps (Supervisor de Obras/Turno)
  * Safety officer stamps
- If stamp present, report: "[Section 15: Stamp present - COMPLETE]"
- Never flag "incomplete" or "partial" if any stamp exists in this section

JSA PRELIMINARY CHECK - MANDATORY:
1. FIRST, identify if this is a Constellation JSA by looking for:
   - Constellation logo (flame/drop shape) typically in top right
   - "Constellation" company name in header
   - Constellation-specific form layout
2. IF CONSTELLATION JSA DETECTED:
   - Proceed with full OCR analysis as instructed below
3. IF THIRD-PARTY JSA DETECTED (no Constellation identifiers):
   - STOP analysis immediately
   - Return only: "[THIRD-PARTY JSA - No analysis required]"
   - Do not extract any content from third-party JSAs

JSA IDENTIFICATION DECISION TREE:
1. Is there a logo in the top right? 
   → Yes: Is it the Constellation flame/drop? 
      → Yes: ANALYZE
      → No: RETURN "[THIRD-PARTY JSA - No analysis required]"
   → No: Check for "Constellation" text anywhere
      → Found: ANALYZE
      → Not found: RETURN "[THIRD-PARTY JSA - No analysis required]"

SPECIFIC GUIDANCE FOR JSA (JOB SAFETY ANALYSIS) FORMS:
- JSA forms have a CRITICAL signature section at the BOTTOM of the page
- This bottom section typically contains:
  * Multiple "Nome:" (Name) fields with handwritten names
  * "Função:" (Function/Role) fields
  * A specific field for "Técnico de Segurança do Trabalho:" (Work Safety Technician)
- The safety technician signature is MANDATORY and often appears:
  * At the very bottom of the form
  * After all participant signatures
  * Sometimes in a separate row or section
- SCAN THE ENTIRE BOTTOM PORTION carefully - signatures may be:
  * In small text areas
  * Compressed at the page bottom
  * In a different format than the main signature table
- Common layout: Left side has participant names/signatures, right side or separate row has safety technician
- DO NOT stop analysis until you've checked for "Técnico de Segurança" signatures

SECTION 20 (ENCERRAMENTO/CLOSURE) CRITICAL INSTRUCTIONS:
- This section is MANDATORY when a work permit is being closed
- Contains three closure reason checkboxes:
  1. "Término do Trabalho / End of work" (Normal completion)
  2. "Acidente/Incidente/Emergência" (Accident/Incident/Emergency)
  3. "Outros" (Others - requires specification)
- ENHANCED CHECKBOX DETECTION for Section 20:
  * These checkboxes often have lighter or smaller marks
  * Look for ANY mark including:
    - Light checkmarks (✓)
    - X marks of any size
    - Diagonal lines
    - Partial marks that show clear intent
  * Common false negatives: Light pen marks that scanner makes faint
  * If ANY checkbox in this section shows ANY intentional mark, it's checked
- This section also requires:
  * Responsible person signature
  * Requester signature (Requisitante)
  * Date and time fields
- NEVER report "no closure reason selected" without triple-checking all three boxes
- If in doubt, zoom/enhance the checkbox area detection

SPECIAL INSTRUCTIONS:
- For multi-page documents, indicate page transitions
- For document sections, preserve hierarchical relationships
- Always organize output in logical reading order (top-to-bottom, left-to-right)
- THOROUGHLY scan entire document including bottom margins for additional signature fields
- For forms with "JSA" in the header or "Análise de Segurança do Trabalho":
  * These ALWAYS have a safety technician signature requirement
  * The signature section is at the ABSOLUTE BOTTOM of the page
  * Scan past any blank space to find the signature area
  * Report specifically on the "Técnico de Segurança" signature status""",
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

# Function to apply section-specific verification and override Claude's analysis
def apply_section_verification(ocr_text, response, page_num, permit_number="Desconhecido"):
    """
    Apply special verification for problematic sections and override Claude's analysis if needed.
    
    Args:
        ocr_text: The OCR text of the page
        response: The standardized response from Claude
        page_num: The page number
        permit_number: The permit number
        
    Returns:
        str: The verified and potentially modified response
    """
    try:
        # Parse the table from the response
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        # Extract header and separator
        header = None
        separator = None
        data_rows = []
        
        for i, line in enumerate(lines):
            if i == 0 and '|' in line:
                header = line
            elif i == 1 and '-|-' in line:
                separator = line
            elif '|' in line:
                data_rows.append(line)
        
        if not header or not separator or not data_rows:
            # Can't parse the table, return the original response
            return response
        
        # Parse each row into a structured format
        parsed_rows = []
        for row in data_rows:
            cells = row.split('|')
            cells = [cell.strip() for cell in cells if cell.strip()]
            
            if len(cells) >= 6:
                parsed_rows.append({
                    'permit': cells[0],
                    'page': cells[1],
                    'summary': cells[2],
                    'section': cells[3],
                    'status': cells[4],
                    'comments': cells[5]
                })
        
        # Apply section-specific verification for problematic sections
        verified_rows = []
        for row in parsed_rows:
            section = row['section'].strip().lower()
            
            # Section 14 verification
            if "14" in section or "operações simultâneas" in section:
                status, comments = verify_section_14(ocr_text)
                if status:  # Override Claude's decision if we have a specific verification
                    row['status'] = status
                    row['comments'] = comments
            
            # Section 15 verification
            elif "15" in section or "co-emissor" in section:
                status, comments = verify_section_15(ocr_text)
                if status:
                    row['status'] = status
                    row['comments'] = comments
            
            # Section 18 verification
            elif "18" in section or "ciência da pt" in section:
                status, comments = verify_section_18(ocr_text)
                if status:
                    row['status'] = status
                    row['comments'] = comments
            
            # Section 20 verification
            elif "20" in section or "encerramento" in section:
                status, comments = verify_section_20(ocr_text)
                if status:
                    row['status'] = status
                    row['comments'] = comments
            
            verified_rows.append(row)
        
        # Reconstruct the table with verified rows
        reconstructed_rows = []
        for row in verified_rows:
            reconstructed_row = f"| {row['permit']} | {row['page']} | {row['summary']} | {row['section']} | {row['status']} | {row['comments']} |"
            reconstructed_rows.append(reconstructed_row)
        
        # Final verified table
        verified_table = header + "\n" + separator + "\n" + "\n".join(reconstructed_rows)
        return verified_table
    
    except Exception as e:
        # If verification fails, return the original response
        print(f"Error in section verification: {str(e)}")
        return response

# Function to standardize table format in Claude's response
def standardize_table_format(response, page_num, permit_number="Desconhecido"):
    """
    Standardize the table format in Claude's response to ensure consistency.
    
    Args:
        response: The raw response from Claude
        page_num: The current page number
        permit_number: The permit number (optional)
        
    Returns:
        String with standardized table format
    """
    try:
        # If response is empty or doesn't contain a table, return a placeholder
        if not response or "|" not in response:
            return f"""
| {permit_number} | {page_num} | Página {page_num} | Conteúdo do Documento | CHECAGEM HUMANA NECESSARIA | Falha na geração da tabela de análise. A resposta não contém o formato de tabela esperado. |
"""
        
        # Extract table content (everything between the first and last pipe characters)
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        table_lines = [line for line in lines if line.startswith('|') and line.endswith('|')]
        
        # Identify header row and separator row
        header_row = None
        separator_row = None
        data_rows = []
        
        for i, line in enumerate(table_lines):
            if 'Permit Number' in line or 'Número da Permissão' in line:
                header_row = line
                if i+1 < len(table_lines) and '---' in table_lines[i+1]:
                    separator_row = table_lines[i+1]
            elif '---' not in line and not 'Permit Number' in line and not 'Número da Permissão' in line:
                data_rows.append(line)
        
        # If no valid header row is found, create a standard one
        if not header_row:
            header_row = "| Permit Number | Page Number | Page Summary | Section | Status | Comments |"
            separator_row = "|---------------|-------------|--------------|---------|--------|----------|"
        
        # If no data rows found, create a placeholder row
        if not data_rows:
            data_rows = [f"| {permit_number} | {page_num} | Página {page_num} | Conteúdo do Documento | CHECAGEM HUMANA NECESSARIA | Falha na análise. Não foi possível extrair dados estruturados da página. |"]
        
        # For each data row, ensure it has the correct format
        formatted_rows = []
        for row in data_rows:
            # Split the row into cells
            cells = row.split('|')
            cells = [cell.strip() for cell in cells if cell.strip()]
            
            # Check if the row has the correct number of columns (should be 6)
            if len(cells) < 6:
                # Add missing columns
                while len(cells) < 6:
                    cells.append("")
            elif len(cells) > 6:
                # Truncate extra columns
                cells = cells[:6]
            
            # Replace empty permit number with the provided one
            if not cells[0] or cells[0] == "XXX-XXXXX":
                cells[0] = permit_number
            
            # Replace empty page number with the provided one
            if not cells[1] or cells[1] == "X":
                cells[1] = str(page_num)
            
            # Ensure status is one of the accepted values (APROVADO, REPROVADO, CHECAGEM HUMANA NECESSARIA, N/A)
            status_values = ["APROVADO", "REPROVADO", "CHECAGEM HUMANA NECESSARIA", "N/A"]
            if cells[4] not in status_values:
                if "aprovado" in cells[4].lower():
                    cells[4] = "APROVADO"
                elif "reprovado" in cells[4].lower():
                    cells[4] = "REPROVADO"
                elif "n/a" in cells[4].lower() or "não aplicável" in cells[4].lower() or "nao aplicavel" in cells[4].lower():
                    cells[4] = "N/A"
                else:
                    cells[4] = "CHECAGEM HUMANA NECESSARIA"
            
            # Reconstruct the row
            formatted_row = "| " + " | ".join(cells) + " |"
            formatted_rows.append(formatted_row)
        
        # Construct the final table
        final_table = header_row + "\n" + separator_row + "\n" + "\n".join(formatted_rows)
        
        return final_table
    
    except Exception as e:
        # If any error occurs, return a safe fallback
        return f"""
| {permit_number} | {page_num} | Página {page_num} | Conteúdo do Documento | CHECAGEM HUMANA NECESSARIA | Erro na padronização do formato da tabela: {str(e)}. A página requer verificação manual. |
"""

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

def detect_guide_color(ocr_text):
    """
    Detect the guide color (Branca, Verde, Amarela) from OCR text.
    
    Args:
        ocr_text: The OCR text to analyze
        
    Returns:
        str: "BRANCA", "VERDE", "AMARELA", or "UNKNOWN"
    """
    # Look for explicit document type markers
    doc_type_match = re.search(r'\[DOCUMENT TYPE: GUIA (BRANCA|VERDE|AMARELA)', ocr_text)
    if doc_type_match:
        return doc_type_match.group(1)
    
    # Look for color indicators in text
    color_patterns = {
        "BRANCA": [r'guia\s+branca', r'via\s+branca', r'cópia\s+branca', r'copia\s+branca', r'branca'],
        "VERDE": [r'guia\s+verde', r'via\s+verde', r'cópia\s+verde', r'copia\s+verde', r'verde'],
        "AMARELA": [r'guia\s+amarela', r'via\s+amarela', r'cópia\s+amarela', r'copia\s+amarela', r'amarela']
    }
    
    # Check each color's patterns
    for color, patterns in color_patterns.items():
        for pattern in patterns:
            if re.search(pattern, ocr_text.lower()):
                return color
    
    # Default if no color is detected
    return "UNKNOWN"

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
            
            # Add status filter options before processing
            if not st.session_state.processing:
                # Create status filter selection
                st.markdown("### Filtros de Status")
                st.write("Selecione quais status deseja visualizar nos resultados:")
                
                # Status filter options
                status_options = {
                    "APROVADO": "🟢 Aprovado",
                    "REPROVADO": "🔴 Reprovado",
                    "CHECAGEM HUMANA NECESSARIA": "🟡 Checagem Humana Necessária",
                    "N/A": "⚪ Não Aplicável (Guias Verde/Amarela)"
                }
                
                # Initialize in session state if needed
                if 'status_filter' not in st.session_state:
                    st.session_state.status_filter = list(status_options.keys())
                
                # Create filter checkboxes - use the number of options
                filter_cols = st.columns(len(status_options))
                for i, (status, label) in enumerate(status_options.items()):
                    with filter_cols[i]:
                        st.session_state[f"show_{status}"] = st.checkbox(
                            label, 
                            value=status in st.session_state.status_filter,
                            key=f"initial_filter_{status}"
                        )
                
                # Update status filter based on checkboxes
                st.session_state.status_filter = [
                    status for status in status_options.keys() 
                    if st.session_state.get(f"show_{status}", True)
                ]
                
                # Process buttons
                st.markdown("### Iniciar Processamento")
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
                                    if header_key in ['Status'] and row_value in ['APROVADO', 'REPROVADO', 'APPROVED', 'REPROVED', 'INCONCLUSIVO', 'CHECAGEM HUMANA NECESSARIA', 'HUMAN CHECK REQUIRED']:
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
                        
                        # Clean up page number columns - ensure they only contain numeric values
                        page_columns = ['Número da Página', 'Page Number']
                        for col in page_columns:
                            if col in df.columns:
                                # Extract only numeric characters from the page number column
                                df[col] = df[col].apply(lambda x: ''.join(filter(str.isdigit, str(x))) if x else '')
                                # Drop rows with empty page numbers after cleaning
                                df = df[df[col] != '']
                        
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

                        # Apply conditional styling to highlight status items with appropriate colors
                        def style_status(val):
                            if val in ['REPROVED', 'REPROVADO']:
                                color = '#F44336'  # Red for rejected
                            elif val in ['APPROVED', 'APROVADO']:
                                color = '#4CAF50'  # Green for approved
                            elif val in ['CHECAGEM HUMANA NECESSARIA', 'HUMAN CHECK REQUIRED']:
                                color = '#FFC107'  # Amber for human check needed
                            elif val in ['N/A', 'NÃO APLICÁVEL']:
                                color = '#9E9E9E'  # Gray for not applicable
                            else:
                                color = '#2196F3'  # Blue for other statuses
                            return f'color: {color}; font-weight: bold'
                        
                        # We don't need to show filter UI again since it was selected before running
                        # Just use the filter values from session state
                        if 'status_filter' not in st.session_state:
                            st.session_state.status_filter = ["APROVADO", "REPROVADO", "CHECAGEM HUMANA NECESSARIA"]
                        
                        # Filter the dataframe based on selected statuses
                        if 'Status' in df.columns and st.session_state.status_filter:
                            # Handle both Portuguese and English status values
                            english_equivalents = {
                                "APROVADO": "APPROVED",
                                "REPROVADO": "REPROVED",
                                "CHECAGEM HUMANA NECESSARIA": "HUMAN CHECK REQUIRED",
                                "N/A": "N/A"  # Same in both languages
                            }
                            
                            # Create a list of all status values to filter (in both languages)
                            filter_statuses = []
                            for status in st.session_state.status_filter:
                                filter_statuses.append(status)
                                if status in english_equivalents:
                                    filter_statuses.append(english_equivalents[status])
                            
                            # Apply the filter
                            filtered_df = df[df['Status'].isin(filter_statuses)]
                            
                            # Show filtering information
                            if len(filtered_df) < len(df):
                                # Create a list of the active filters in a user-friendly format
                                status_options = {
                                    "APROVADO": "🟢 Aprovado",
                                    "REPROVADO": "🔴 Reprovado",
                                    "CHECAGEM HUMANA NECESSARIA": "🟡 Checagem Humana Necessária"
                                }
                                active_filters = [status_options.get(status, status) for status in st.session_state.status_filter]
                                active_filters_str = ", ".join(active_filters)
                                
                                st.info(f"Filtrando por: {active_filters_str} - Mostrando {len(filtered_df)} de {len(df)} linhas.")
                        else:
                            filtered_df = df
                            
                        # Apply the styling to the Status column if it exists
                        if 'Status' in filtered_df.columns:
                            styled_df = filtered_df.style.applymap(style_status, subset=['Status'])
                        else:
                            styled_df = filtered_df
                        
                        # Display the filtered dataframe with styling
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
                                        # Filter page results, ensuring we match the page number as a string 
                                        # and handle potentially non-numeric values
                                        page_results = df[df[page_column].astype(str).str.strip() == str(selected_page)]
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
                                            
                                            # Determine status color and text based on status value
                                            if status in ['APPROVED', 'APROVADO']:
                                                status_color = "#4CAF50"  # Green for approved
                                                status_text = "APROVADO"
                                                header_bg = "rgba(76, 175, 80, 0.1)"  # Light green background
                                            elif status in ['REPROVED', 'REPROVADO']:
                                                status_color = "#F44336"  # Red for rejected
                                                status_text = "REPROVADO"
                                                header_bg = "rgba(244, 67, 54, 0.1)"  # Light red background
                                            elif status in ['CHECAGEM HUMANA NECESSARIA', 'HUMAN CHECK REQUIRED']:
                                                status_color = "#FFC107"  # Amber for human check needed
                                                status_text = "CHECAGEM HUMANA NECESSARIA"
                                                header_bg = "rgba(255, 193, 7, 0.1)"  # Light amber background
                                            else:
                                                status_color = "#2196F3"  # Blue for other statuses
                                                status_text = status
                                                header_bg = "rgba(33, 150, 243, 0.1)"  # Light blue background
                                            
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
                                            
                                            st.markdown(f"""
                                            <div style="background-color: #112240; padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 4px solid {border_color};">
                                                <h4 style="color: #64ffda; padding: 5px; background-color: {header_bg}; border-radius: 3px;">{section}</h4>
                                                <p><strong>Status:</strong> <span style="color: {status_color}; font-weight: bold;">{status_text}</span></p>
                                                <p><strong>Comentários:</strong> {comments}</p>
                                            </div>
                                            """, unsafe_allow_html=True)
                        
                        # Show summary counts - handle all possible status values
                        if 'Status' in df.columns:
                            # Show two sets of counts: filtered and total
                            # First, get total counts from the original dataframe
                            total_status_counts = df['Status'].value_counts()
                            
                            # Check for all status types in both English and Portuguese for total
                            total_approved = total_status_counts.get('APPROVED', 0) + total_status_counts.get('APROVADO', 0)
                            total_reproved = total_status_counts.get('REPROVED', 0) + total_status_counts.get('REPROVADO', 0)
                            total_human_check = total_status_counts.get('CHECAGEM HUMANA NECESSARIA', 0) + total_status_counts.get('HUMAN CHECK REQUIRED', 0)
                            total_na = total_status_counts.get('N/A', 0) + total_status_counts.get('NÃO APLICÁVEL', 0)
                            
                            # Now get counts from the filtered dataframe
                            filtered_status_counts = filtered_df['Status'].value_counts()
                            
                            # Check for all status types in both English and Portuguese for filtered
                            filtered_approved = filtered_status_counts.get('APPROVED', 0) + filtered_status_counts.get('APROVADO', 0)
                            filtered_reproved = filtered_status_counts.get('REPROVED', 0) + filtered_status_counts.get('REPROVADO', 0)
                            filtered_human_check = filtered_status_counts.get('CHECAGEM HUMANA NECESSARIA', 0) + filtered_status_counts.get('HUMAN CHECK REQUIRED', 0)
                            filtered_na = filtered_status_counts.get('N/A', 0) + filtered_status_counts.get('NÃO APLICÁVEL', 0)
                            
                            # Create status summary card showing both filtered and total
                            st.markdown(f"""
                            <div class="content-container">
                                <h4>Resumo da Análise</h4>
                                
                                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                    <div style="flex: 1;">
                                        <h5>Resultados Filtrados</h5>
                                        <p>Seções Aprovadas: <span style="color: #4CAF50; font-weight: bold;">{filtered_approved}</span></p>
                                        <p>Seções Reprovadas: <span style="color: #F44336; font-weight: bold;">{filtered_reproved}</span></p>
                                        <p>Seções com Checagem Humana: <span style="color: #FFC107; font-weight: bold;">{filtered_human_check}</span></p>
                                        <p>Seções Não Aplicáveis: <span style="color: #9E9E9E; font-weight: bold;">{filtered_na}</span></p>
                                        <p>Total Filtrado: <span style="font-weight: bold;">{len(filtered_df)}</span></p>
                                    </div>
                                    
                                    <div style="flex: 1; border-left: 1px solid #ddd; padding-left: 20px;">
                                        <h5>Resultados Completos</h5>
                                        <p>Seções Aprovadas: <span style="color: #4CAF50; font-weight: bold;">{total_approved}</span></p>
                                        <p>Seções Reprovadas: <span style="color: #F44336; font-weight: bold;">{total_reproved}</span></p>
                                        <p>Seções com Checagem Humana: <span style="color: #FFC107; font-weight: bold;">{total_human_check}</span></p>
                                        <p>Seções Não Aplicáveis: <span style="color: #9E9E9E; font-weight: bold;">{total_na}</span></p>
                                        <p>Total de Seções Analisadas: <span style="font-weight: bold;">{len(df)}</span></p>
                                    </div>
                                </div>
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