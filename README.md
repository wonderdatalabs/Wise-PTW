# Streamlit Document Analyzer

A comprehensive Streamlit application for analyzing documents in the Oil & Gas industry using advanced AI technologies including LlamaParse, Claude, and Mistral APIs. This application provides intelligent document processing, OCR capabilities, and expert analysis across multiple industry domains.

## Features

### Core Functionality
- **Multi-format Document Processing**: Upload and process PDF, image, and scanned documents
- **Advanced OCR**: High-quality text extraction using LlamaParse and Mistral Vision APIs
- **AI-Powered Analysis**: Generate comprehensive summaries and analysis using Claude
- **Expert Domain Knowledge**: Specialized prompts for various industries (Oil & Gas, Manufacturing, Mining, Pharma, etc.)
- **Multi-language Support**: Portuguese language support for documents
- **Interactive Interface**: User-friendly Streamlit interface with real-time processing

### Technical Features
- **Multiple Processing Modes**: Choose between different OCR and analysis engines
- **Page-by-page Analysis**: Detailed analysis of document structure and content
- **Image Enhancement**: Automatic image preprocessing for better OCR results
- **Caching System**: Efficient processing with result caching
- **Mobile Responsive**: Optimized interface for mobile devices
- **Asset Management**: Comprehensive branding and styling system

## Setup

### Prerequisites

- Python 3.8+
- API key for LlamaParse (from cloud.llamaindex.ai)
- API key for Claude (Anthropic)
- AWS S3 bucket (optional)

### Installation

1. Clone this repository
2. Create a virtual environment and install requirements:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy the example environment file and configure your API keys:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### API Key Configuration

Set up your API keys in the `.env` file or as environment variables:

- `LLAMA_CLOUD_API_KEY`: Your LlamaParse API key (starts with "llx-")
- `ANTHROPIC_API_KEY`: Your Claude API key (starts with "sk-ant-")
- `MISTRAL_API_KEY`: Your Mistral API key (optional)

You can get a LlamaParse API key from [LlamaIndex Cloud](https://cloud.llamaindex.ai/api-key).

### AWS S3 Configuration (Optional)

For temporary file storage and sharing, you can configure AWS S3:

1. Create an S3 bucket with appropriate permissions
2. Add your S3 credentials to the `.env` file:
   ```
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   S3_BUCKET_NAME=your-s3-bucket-name
   S3_REGION=your-aws-region
   ```

### Running the App

Start the Streamlit app:
```bash
streamlit run app.py
```

Access the app at http://localhost:8501 or configure a reverse proxy for public access.

## How It Works

1. User uploads a PTW document
2. Document is processed by LlamaParse for high-quality text extraction
3. Claude generates a comprehensive summary
4. Pages are processed individually through:
   - LlamaParse for text structure extraction
   - Claude API for detailed analysis
5. Each page's analysis is displayed in real-time
6. Final report shows compliance status of the entire document

## LlamaParse Integration

The application now uses LlamaParse for document processing:

- LlamaParse provides high-quality text extraction with layout preservation
- Table recognition for structured data
- Maintains document structure for accurate analysis
- For more information on LlamaParse, visit [LlamaIndex](https://docs.llamaindex.ai/en/stable/examples/llama_parse/llama_parse.html)

## Troubleshooting

If experiencing issues:
- Run the `test_llama_parse.py` script to verify your LlamaParse API key and integration
- Check the console output for detailed error messages
- Ensure your API keys are correctly set in the `.env` file
- For LlamaParse issues, check their documentation or status at [cloud.llamaindex.ai](https://cloud.llamaindex.ai)

## Testing LlamaParse

You can test the LlamaParse integration separately:
```bash
python test_llama_parse.py
```

This will attempt to parse a PDF in the current directory and show the results structure.

## License

[Add your license information here]