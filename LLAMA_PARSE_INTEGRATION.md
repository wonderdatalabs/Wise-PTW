# LlamaParse Integration Guide

This document explains how the PTW Analyzer integrates with LlamaParse for high-quality document processing.

## What is LlamaParse?

LlamaParse is a GenAI-native document parser that can parse complex document data for any downstream LLM use case. It is particularly good at:

- Handling various file types (PDF, PPTX, DOCX, XLSX, HTML)
- Recognizing and preserving tables
- Maintaining document structure
- Processing multimodal content (text and images)

## Setting Up LlamaParse

1. Get an API key from [LlamaIndex Cloud](https://cloud.llamaindex.ai/api-key)
2. Add your API key to the `.env` file or set it as an environment variable:
   ```
   LLAMA_CLOUD_API_KEY=llx-your-key-here
   ```

## How PTW Analyzer Uses LlamaParse

The application uses LlamaParse to:

1. Extract text and structure from PTW documents
2. Preserve page layouts and tables
3. Identify form fields, signatures, and handwritten content
4. Split content by pages for detailed analysis

## Custom Prompting

We use a custom prompt to optimize LlamaParse for PTW documents:

```python
ptw_prompt = """
You are analyzing a Permit to Work (PTW) document from the oil and gas industry.

Pay special attention to:
1. Identify all form fields and whether they are filled out or empty
2. Detect signatures and indicate their presence/absence
3. Maintain clear page structure with explicit page breaks
4. Identify handwritten content, checkboxes, and approval sections
5. Extract dates, times, and location information
6. Preserve relationships between sections (e.g., hazards and their controls)
7. Document all approval hierarchies and verification steps
"""
```

This prompt is set when initializing the LlamaParse client, ensuring that all documents are processed with PTW-specific instructions.

## Testing the Integration

Use the `test_llama_parse.py` script to test the LlamaParse integration:

```bash
python test_llama_parse.py
```

This will:
1. Prompt for your API key if not found in environment variables
2. Find a PDF in the current directory or prompt for a path
3. Process the document with LlamaParse
4. Display the structure of the result and sample content

## Troubleshooting

If you encounter issues with LlamaParse:

1. Verify your API key is correct and has sufficient permissions
2. Check if your document is in a supported format
3. Ensure your account has sufficient quota (free plan allows 1000 pages/day)
4. Check the console output for detailed error messages

For more information on LlamaParse, visit the [official documentation](https://docs.llamaindex.ai/en/stable/examples/llama_parse/).