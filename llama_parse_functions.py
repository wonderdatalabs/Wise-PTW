import streamlit as st
import time
from llama_parse_integration import extract_page_content, has_signatures

def process_pdf_with_llama_parse(llama_parse_client, pdf_bytes, file_name):
    """Process a PDF document with Llama Parse for high-quality extraction.
    
    Args:
        llama_parse_client: The initialized Llama Parse client
        pdf_bytes: The PDF content as bytes
        file_name: Name of the file for reference
        
    Returns:
        Dict containing the parsed document results
    """
    try:
        st.info("Processing document with Llama Parse API...")
        
        # Create a progress indicator
        progress_bar = st.progress(0.1, text="Starting document parsing...")
        
        # Process the document with Llama Parse
        parse_result = llama_parse_client.parse_document(
            file_bytes=pdf_bytes,
            file_name=file_name,
            document_type="pdf",
            include_page_breaks=True
        )
        
        # Update progress
        progress_bar.progress(0.9, text="Parsing complete. Processing results...")
        
        # Check for successful parsing
        if not parse_result.get('content'):
            raise Exception("No content returned from Llama Parse")
        
        # Extract metadata
        metadata = {
            'task_id': parse_result.get('task_id', ''),
            'status': parse_result.get('status', ''),
            'total_pages': len(parse_result.get('content', '').split('--PAGE BREAK--'))
        }
        
        # Log some info for debugging
        print(f"Document parsed successfully. {metadata['total_pages']} pages detected.")
        
        # Update progress and clear
        progress_bar.progress(1.0, text="Document parsing complete!")
        time.sleep(1)
        progress_bar.empty()
        
        # Return the parsing result
        return parse_result
        
    except Exception as e:
        error_msg = f"Error processing document with Llama Parse: {str(e)}"
        st.error(error_msg)
        print(error_msg)
        raise Exception(error_msg)

def format_page_for_analysis(parse_result, page_num):
    """Format page content for analysis.
    
    Args:
        parse_result: The complete parsing result from Llama Parse
        page_num: The page number to analyze (1-indexed)
        
    Returns:
        str: Formatted page content for analysis
    """
    # Extract the content for this page
    page_data = extract_page_content(parse_result, page_num)
    page_content = page_data.get('content', '')
    
    if not page_content:
        error_msg = f"No content found for page {page_num} in parse results"
        print(error_msg)
        return None
    
    # Format the page content with the OCR template
    ocr_text = f"""
    Permit to Work Document Page {page_num}:
    
    {page_content}
    
    Signatures detected: {"Yes" if has_signatures(page_content) else "No"}
    """
    
    return ocr_text