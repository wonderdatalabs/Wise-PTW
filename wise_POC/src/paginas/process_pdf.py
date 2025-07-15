# =========================================================================
# MÓDULO DE PROCESSAMENTO DE PDF 
# =========================================================================
import os
from pathlib import Path
import pandas as pd
from typing import List, Dict
import logging
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
from dotenv import load_dotenv
import time
import tempfile
import json
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import numpy as np
import warnings
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
os.environ['LLAMA_CLOUD_API_KEY'] = os.getenv('LLAMA_CLOUD_API_KEY')

def clean_extracted_text(text: str) -> str:
    import re
    text = text.replace('Ψ', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[^\w\s\.,;:!?()-]', '', text)
    return text

def process_pdf_with_llama(parser: LlamaParse, file_path: Path) -> Dict:
    try:
        file_extractor = {".pdf": parser}
        documents = SimpleDirectoryReader(
            input_files=[str(file_path)],
            file_extractor=file_extractor,
            filename_as_id=True,
            num_files_limit=1,
            recursive=False,
            required_exts=[".pdf"]
        ).load_data()
        if not documents or len(documents) == 0:
            logger.error(f"Nenhum documento foi extraído do arquivo {file_path}")
            return {
                'raw_text': None,
                'original_text': None,
                'metadata': None,
                'processing_date': pd.Timestamp.now(),
                'processed': False,
                'error': "Nenhum conteúdo extraído do PDF"
            }
        cleaned_text = clean_extracted_text(documents[0].text)
        return {
            'raw_text': cleaned_text,
            'original_text': documents[0].text,
            'metadata': documents[0].metadata,
            'processing_date': pd.Timestamp.now(),
            'processed': True,
            'error': None
        }
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        return {
            'raw_text': None,
            'original_text': None,
            'metadata': None,
            'processing_date': pd.Timestamp.now(),
            'processed': False,
            'error': str(e)
        }

from anthropic import Anthropic
from datetime import datetime
anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def extract_structured_info(nome: str, text: str) -> Dict:
    # mantenha como está (prompt e lógica de extração)
    prompt = """
    You are an expert in company operational procedures. Your main task is to read the text and extract key information in a structured format. The text is in Portuguese, so please provide the analysis in Brazilian Portuguese.

    File Name: {file_name}

    TEXT:
    {text}

    Please extract and provide the following information in a structured format:
    1. Process Name - The process or procedure title
    2. Related Systems - The product, platform, or clients involved (list - up to 3)
    3. Objective - Main purpose of the document (not a list)
    4. Department - Main departments involved (list - up to 2)
    5. Responsible - People responsible for the process or document described (list - up to 2)
    6. Main Steps - Main steps of the process or document described (list - up to 5)
    7. Topics - The main topics of the document (list - up to 3)
    8. Document Type - Type of document (e.g., procedimento, instrução de trabalho, relatório de incidente, checklist, etc.)
    9. Location - The main location(s) related to the document (e.g., unidade, plataforma, navio, planta, setor físico)
    10. Related Equipment - List of equipment or assets involved (list - up to 3)
    11. Executive Summary
    12. Detailed Summary
    

    Provide the response ONLY as a valid JSON object with these exact keys:
    nome_processo, sistemas_relacionados, objetivo_principal, departamentos, pessoal_responsavel, etapas, main_topics, exec_summary, detailed_summary, tipo_documento, localizacao, equipamentos_relacionados.

    *IMPORTANT* - Make sure you return all the content as text, even if the field is empty.
    
    """.format(file_name=nome, text=text)

    try:
        response = anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0,
            system="You are a safety expert analyst. Always respond with valid JSON only.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        print("Got response from Claude")
        if isinstance(response.content, list):
            if len(response.content) > 0:
                response_text = response.content[0].text
                print(response_text)
            else:
                print("Empty response content list")
                return None
        else:
            response_text = response.content
        print("Response text length:", len(response_text))
        try:
            structured_data = json.loads(response_text)
            return structured_data
        except json.JSONDecodeError:
            import re
            json_pattern = r'\{[\s\S]*\}'
            match = re.search(json_pattern, response_text)
            if match:
                try:
                    structured_data = json.loads(match.group())
                    return structured_data
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON after cleaning")
                    return None
            else:
                logger.error("No JSON pattern found in response")
                return None
    except Exception as e:
        logger.error(f"Error in Claude API call: {e}")
        logger.error(f"Response content: {response.content if 'response' in locals() else 'No response'}")
        return None

def build_payload(uploaded_file, structured_data, llama_result, current_timestamp, idx):
    from datetime import datetime
    # Adiciona a data formatada (DD/MM/YYYY)
    upload_date_str = datetime.fromtimestamp(current_timestamp).strftime("%d/%m/%Y")
    
    # Map Portuguese field names to English
    field_mapping = {
        'nome_processo': 'process_name',
        'departamentos': 'departments',
        'tipo_documento': 'document_type',
        'sistemas_relacionados': 'related_systems',
        'objetivo_principal': 'main_objective',
        'pessoal_responsavel': 'people_responsible',
        'etapas': 'steps',
        'main_topics': 'main_topics',  # already in English
        'exec_summary': 'exec_summary',  # already in English
        'detailed_summary': 'detailed_summary',  # already in English
        'localizacao': 'location',
        'equipamentos_relacionados': 'related_equipment'
    }
    
    # Create a new dictionary with English keys
    translated_data = {}
    for pt_key, en_key in field_mapping.items():
        if pt_key in structured_data:
            translated_data[en_key] = structured_data[pt_key]
    
    return {
        'file_name': uploaded_file.name,
        'process_name': structured_data.get('nome_processo', ''),
        'departments': structured_data.get('departamentos', []),
        'document_type': structured_data.get('tipo_documento', ''),
        'structured_data': translated_data,  # Use the translated data
        'raw_text': llama_result.get('raw_text'),
        'upload_timestamp': current_timestamp,      # Para busca (int)
        'upload_date_str': upload_date_str,         # Para exibição (string)
        'point_id': idx
    }

def get_next_point_id(client, collection_name):
    try:
        all_points = []
        offset, limit = 0, 100
        while True:
            batch = client.scroll(collection_name=collection_name, limit=limit, offset=offset, with_payload=False, with_vectors=False)
            points_batch = batch[0]
            if not points_batch: break
            all_points.extend(points_batch)
            offset += len(points_batch)
            if len(points_batch) < limit: break
        point_ids = [point.id for point in all_points]
        return max(point_ids) + 1 if point_ids else 0
    except Exception:
        try:
            count = client.get_collection(collection_name).points_count
            return count + 10 if count > 0 else 0
        except Exception:
            import time
            return int(time.time() * 1000)

def ensure_unique_id(client, collection_name, idx, point):
    while True:
        existing_point = client.retrieve(collection_name=collection_name, ids=[idx], with_payload=False)
        if not existing_point:
            break
        idx += 1
        point.id = idx
        point.payload['point_id'] = idx
    return idx, point

def upsert_with_retry(client, collection_name, point, idx, max_retries=3):
    for retry_count in range(max_retries):
        try:
            client.upsert(collection_name=collection_name, points=[point], wait=True)
            verification = client.retrieve(collection_name=collection_name, ids=[idx], with_payload=True)
            if verification and len(verification) > 0:
                return True
        except Exception as retry_error:
            time.sleep(1)
    return False

def process_and_store_pdf(uploaded_file):
    try:
        import nest_asyncio
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        nest_asyncio.apply()
        logger.info(f"Iniciando processamento do arquivo: {uploaded_file.name}")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file_path = Path(temp_file.name)
            temp_file.write(uploaded_file.getvalue())
        parser = LlamaParse(
            parsing_instruction = "Documents are Company procedures, in most part in portuguese.",
            result_type="text",
            language="pt",
            encoding="utf-8",
            include_metadata=True,
            ocr=True,
            ocr_languages=['pt','en'],
            fast_mode=True,
            process_images=True,
            merge_pages=True,
            all_pages=True,
            max_pages=500,
            split_by_page=False
        )
        logger.info(f"Processando arquivo: {uploaded_file.name}, tamanho: {len(uploaded_file.getvalue())} bytes")
        llama_result = process_pdf_with_llama(parser, temp_file_path)
        if not llama_result['processed']:
            return {
                'success': False, 
                'message': f"Failed to extract text: {llama_result.get('error', 'Unknown error')}"
            }
        structured_data = extract_structured_info(uploaded_file.name, llama_result['raw_text'])
        if not structured_data:
            return {
                'success': False, 
                'message': "Failed to extract structured data from the document"
            }
        try:
            warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")
            client = QdrantClient(
                host=os.getenv('QDRANT_URL').replace('http://', '').split(':')[0],
                port=int(os.getenv('QDRANT_PORT', '6333')),
                api_key=os.getenv('QDRANT_API_KEY'),
                timeout=300,
                prefer_grpc=False,
                https=False
            )
            collection_name = os.getenv('QDRANT_COLLECTION_NAME')
            if not collection_name:
                raise ValueError("A variável de ambiente QDRANT_COLLECTION_NAME não está definida.")
            try:
                client.get_collection(collection_name)
                logger.info(f"Using existing collection: {collection_name}")
            except Exception as e:
                logger.info(f"Creating new collection: {collection_name}. Error: {str(e)}")
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
            # Embedding
            text = " ".join([f"{k}: {str(v)}" for k, v in structured_data.items() if v is not None])
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embedding = model.encode([text])[0]
            idx = get_next_point_id(client, collection_name)
            
            # Salva apenas a data (YYYY-MM-DD) para facilitar o filtro por data
            from datetime import datetime
            current_timestamp = int(datetime.now().timestamp())
            point = PointStruct(
                id=idx,
                vector=embedding.tolist(),
                payload=build_payload(uploaded_file, structured_data, llama_result, current_timestamp, idx)
            )
            idx, point = ensure_unique_id(client, collection_name, idx, point)
            success = upsert_with_retry(client, collection_name, point, idx)
            if success:
                return {
                    'success': True, 
                    'message': f"Documento processado e adicionado com sucesso. ID: {idx} | Collection: {collection_name}",
                }
            else:
                return {
                    'success': False, 
                    'message': f"Falha ao adicionar documento após 3 tentativas | Collection: {collection_name}",
                }
        except Exception as e:
            logger.error(f"Error storing data: {str(e)}")
            return {
                'success': False, 
                'message': f"Erro ao armazenar dados: {str(e)}"
            }
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        return {
            'success': False, 
            'message': f"Erro durante o processamento: {str(e)}"
        }
    finally:
        if 'temp_file_path' in locals():
            try:
                os.unlink(temp_file_path)
            except:
                pass  # Ignora erros na limpeza