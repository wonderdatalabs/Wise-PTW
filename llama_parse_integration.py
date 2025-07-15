"""
Llama Parse integration for PTW Analyzer

This module handles document processing using Llama Parse
for high-quality extraction from PTW documents.
"""

import time
import io
from typing import Dict, List, Any, Optional, Union
from llama_cloud_services import LlamaParse

class LlamaParseClient:
    """Client for interacting with the Llama Parse API using the official library."""
    
    def __init__(self, api_key: str):
        """
        Initialize the Llama Parse client.
        
        Args:
            api_key: Llama Parse API key
        """
        self.api_key = api_key
        # Get the PTW prompt instructions
        ptw_prompt = self._get_ptw_prompt_instructions()
        
        # Initialize LlamaParse with the API key, region, and set result_type to markdown
        self.parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",  # Force markdown output
            verbose=True,  # Enable verbose logging
            language="pt",  # Set Portuguese as default language since documents are in Portuguese
            user_prompt=ptw_prompt,  # Use user_prompt for custom instructions
            
        )
    
    def parse_document(self, 
                       file_bytes: bytes, 
                       file_name: str, 
                       document_type: str = "pdf",
                       include_page_breaks: bool = True,
                       max_wait_time_seconds: int = 120) -> Dict[str, Any]:
        """
        Parse a document using official Llama Parse library.
        
        Args:
            file_bytes: The binary content of the file
            file_name: The name of the file
            document_type: The type of document (pdf, docx, etc.)
            include_page_breaks: Whether to include page breaks in the result
            max_wait_time_seconds: Maximum time to wait for parsing to complete
            
        Returns:
            Dict containing the parsed document data
        """
        try:
            # Create a BytesIO object from the file bytes
            file_obj = io.BytesIO(file_bytes)
            
            # Print available methods for debugging
            print(f"Available methods on LlamaParse: {[m for m in dir(self.parser) if not m.startswith('_')]}")
            
            # Based on the provided implementation example, we need to provide extra_info with file_name
            extra_info = {"file_name": file_name}
            
            print(f"Parsing document: {file_name}")
            # Note: We don't pass instructions here as we've already set it in the constructor via user_prompt
            result = self.parser.parse(
                file_obj,
                extra_info=extra_info
            )
            
            print(f"Parse result type: {type(result)}")
            print(f"Result attributes: {[m for m in dir(result) if not m.startswith('_')]}")
            
            # Process the result based on the JobResult object structure
            if hasattr(result, 'get_markdown_documents'):
                # Get the markdown documents, split by page
                markdown_docs = result.get_markdown_documents(split_by_page=True)
                print(f"Got {len(markdown_docs)} markdown documents")
                
                # Join the documents with page break markers
                content = "\n--PAGE BREAK--\n".join([doc.text for doc in markdown_docs])
            elif hasattr(result, 'pages'):
                # Get markdown from each page
                pages = result.pages
                content = "\n--PAGE BREAK--\n".join([page.md if hasattr(page, 'md') else page.text for page in pages])
            elif hasattr(result, 'to_markdown'):
                # Use to_markdown method if available
                content = result.to_markdown()
                
                # Add page breaks if needed
                if include_page_breaks and '\n---\n' in content:
                    content = content.replace('\n---\n', '\n--PAGE BREAK--\n')
            else:
                # Fallback to string representation
                content = str(result)
            
            # Print a sample of the content for debugging
            print(f"Sample of parsed content: {content[:200]}...")
            
            # Build the result dictionary in the expected format
            return {
                'content': content,
                'status': 'COMPLETED',
                'task_id': str(id(result))  # Use object ID as a pseudo task ID
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"Error parsing document with LlamaParse: {str(e)}")
    
    def _get_ptw_prompt_instructions(self) -> str:
        """
        Get the prompt instructions for Permit to Work document parsing.
        
        Returns:
            String containing specialized instructions for PTW documents
        """
        return """
        You are analyzing a Permit to Work (PTW) document from the oil and gas industry. Many of these documents are in Portuguese, so you should be able to understand Portuguese terms and translate them appropriately.

        Pay special attention to:
        1. Identify all form fields and whether they are filled out or empty
        2. Detect signatures and indicate their presence/absence
        3. Maintain clear page structure with explicit page breaks
        4. Identify handwritten content, checkboxes, and approval sections
        5. Extract dates, times, and location information (note that Portuguese date format is DD/MM/YYYY)
        6. Preserve relationships between sections (e.g., hazards and their controls)
        7. Document all approval hierarchies and verification steps

        Common Portuguese terms in these documents:
        - "Permissão de Trabalho" = Permit to Work
        - "Assinatura" = Signature
        - "Autorização" = Authorization
        - "Trabalho a Quente" = Hot Work
        - "Espaço Confinado" = Confined Space
        - "Responsável" = Responsible person
        - "Data" = Date
        - "Hora" = Time
        - "Aprovado" = Approved
        - "Recusado" = Rejected/Denied
        
        For signatures:
        - Indicate if a signature field contains an actual signature
        - Note if signature fields are empty
        - Identify printed names and dates associated with signatures
        
        Ensure the output preserves the document structure with clear page delineation.
        Include page numbers and section headings to maintain context.
        
        For each page, provide a brief summary of its purpose in the document structure.
        Keep extracted text in its original language (Portuguese), but you can provide translations in brackets when needed.
        """

def extract_page_content(parse_result: Dict[str, Any], page_number: int) -> Dict[str, Any]:
    """
    Extract content for a specific page from the Llama Parse results.
    
    Args:
        parse_result: The complete parsing result from Llama Parse
        page_number: The page number to extract (1-indexed)
        
    Returns:
        Dict containing the page-specific content
    """
    # Extract the content
    content = parse_result.get('content', '')
    
    # Split by page breaks
    if content:
        pages = content.split('--PAGE BREAK--')
        
        # Adjust for 0-indexed array but 1-indexed page numbers
        page_idx = page_number - 1
        
        if 0 <= page_idx < len(pages):
            page_content = pages[page_idx].strip()
            
            # Create a structured result
            return {
                'page_number': page_number,
                'content': page_content,
                'metadata': {
                    'total_pages': len(pages)
                }
            }
    
    # Return empty result if page not found
    return {
        'page_number': page_number,
        'content': '',
        'metadata': {
            'error': f'Page {page_number} not found in parse results'
        }
    }

def has_signatures(page_content: str) -> bool:
    """
    Check if a page has signatures based on the parsed content.
    
    Args:
        page_content: The parsed content for a page
        
    Returns:
        Boolean indicating if signatures are detected
    """
    signature_indicators = [
        'signature',
        'signed',
        'approved by',
        'authorized by',
        'endorsed by'
    ]
    
    # Check for signature indicators
    lower_content = page_content.lower()
    for indicator in signature_indicators:
        if indicator in lower_content:
            return True
    
    return False