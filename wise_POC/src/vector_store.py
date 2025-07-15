"""
Módulo de Gerenciamento de Banco de Dados Vetorial

Este módulo implementa a integração com o banco de dados vetorial Qdrant para 
armazenamento e recuperação de documentos.

Funcionalidades principais:
- Conexão com o servidor Qdrant
- Geração de embeddings a partir de textos usando SentenceTransformer
- Consulta semântica de documentos baseada em similaridade vetorial
- Formatação de resultados para uso como contexto em modelos LLM

O módulo é projetado para funcionar com diferentes modelos de embeddings e 
configurações de coleção do Qdrant, facilitando a busca semântica em documentos.
"""
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import logging

# Configuração do logger específico para este módulo
logger = logging.getLogger(__name__)

class VectorStore:
    """Classe para interação com o banco de dados vetorial Qdrant"""
    
    def __init__(self):
        """Inicializa o cliente Qdrant e o modelo de embeddings"""
        # Configuração do Qdrant - leitura das variáveis de ambiente
        qdrant_url = os.getenv('QDRANT_URL')
        qdrant_api_key = os.getenv('QDRANT_API_KEY', '')  # Valor vazio como fallback
        self.collection_name = os.getenv('QDRANT_COLLECTION_NAME')
        if not self.collection_name:
            logger.error("QDRANT_COLLECTION_NAME não encontrada no arquivo .env")
            raise ValueError("QDRANT_COLLECTION_NAME não configurada. Verifique o arquivo .env")
       
        if not qdrant_url:
            logger.error("QDRANT_URL não encontrada no arquivo .env")
            raise ValueError("QDRANT_URL não configurada. Verifique o arquivo .env")
        
        # Inicializa o cliente Qdrant - com tratamento para casos sem API key
        try:
            self.client = QdrantClient(
                url=qdrant_url, 
                api_key=qdrant_api_key if qdrant_api_key else None,
                timeout=10.0  # Timeout definido para evitar bloqueios longos
            )
            
            # Verifica conexão listando as collections disponíveis
            collections = self.client.get_collections()
            logger.info(f"Conectado ao Qdrant. Collections disponíveis: {[c.name for c in collections.collections]}")
            
            # Verifica se a collection configurada existe no servidor
            available_collections = [c.name for c in collections.collections]
            if self.collection_name not in available_collections:
                logger.warning(f"Collection '{self.collection_name}' não encontrada no Qdrant! Collections disponíveis: {available_collections}")
                raise ValueError(f"Collection '{self.collection_name}' não encontrada no Qdrant!")
            else:
                # Coleta informações sobre a collection para diagnóstico
                try:
                    collection_info = self.client.get_collection(collection_name=self.collection_name)
                    vector_count = collection_info.vectors_count
                    logger.info(f"Collection '{self.collection_name}' encontrada com {vector_count} vetores")
                except Exception as e:
                    logger.warning(f"Não foi possível obter informações da collection: {str(e)}")
        
        except Exception as e:
            logger.error(f"Erro ao conectar ao Qdrant: {str(e)}")
            raise ValueError(f"Falha ao conectar ao servidor Qdrant: {str(e)}")
        
        # Carregamento do modelo para gerar embeddings
        try:
            logger.info("Carregando modelo de embeddings...")
            
            # Seleção do modelo de embedding apropriado para a collection
            model_name = 'all-MiniLM-L6-v2'  # Modelo padrão com bom equilíbrio entre performance e qualidade
            self.encoder = SentenceTransformer(model_name)
                
            self.vector_size = self.encoder.get_sentence_embedding_dimension()
            logger.info(f"Modelo de embeddings carregado: {model_name} com {self.vector_size} dimensões")
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelo de embeddings: {str(e)}")
            raise ValueError(f"Falha ao inicializar modelo de embeddings: {str(e)}")
        
        logger.info(f"VectorStore inicializado: conectado à coleção {self.collection_name}")
    
    def query(self, question, limit=5):
        """
        Consulta a coleção do Qdrant para encontrar documentos semanticamente similares à pergunta
        
        Args:
            question: A pergunta do usuário ou texto de consulta
            limit: Número máximo de documentos a retornar (padrão: 5)
            
        Returns:
            Lista de documentos relevantes com seus metadados e scores de similaridade
        """
        try:
            # Transforma a pergunta em um vetor de embedding
            question_vector = self.encoder.encode(question)
            
            # Realiza a busca por similaridade vetorial no Qdrant
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=question_vector.tolist(),  # Converte numpy array para lista
                limit=limit,
                score_threshold=0.45  # Limiar de similaridade (0 a 1)
            )
            
            # Processa os resultados para formato padronizado
            results = []
            for result in search_result:
                payload = result.payload
                score = result.score  # Score de similaridade
                
                # Extrai o texto do documento - verifica múltiplos campos possíveis
                document_text = ""
                possible_text_fields = ['text', 'content', 'page_content', 'document']
                
                for field in possible_text_fields:
                    if field in payload:
                        document_text = payload.get(field, '')
                        break
                
                # Fallback: usa todo o payload como texto
                if not document_text and payload:
                    document_text = str(payload)
                
                # Obtém metadados de fonte do documento
                source = payload.get('source', payload.get('title', payload.get('filename', 'Documento interno')))
                
                results.append({
                    'text': document_text,
                    'source': source,
                    'score': score
                })
            
            logger.info(f"Consulta Qdrant retornou {len(results)} documentos relevantes")
            
            # Log detalhado dos resultados para diagnóstico
            if results:
                for i, res in enumerate(results):
                    logger.debug(f"Resultado {i+1}: Fonte={res['source']}, Score={res['score']:.4f}")
                    text_preview = res['text'][:100] + "..." if len(res['text']) > 100 else res['text']
                    logger.debug(f"Preview: {text_preview}")
            
            return results
            
        except Exception as e:
            logger.error(f"Erro ao consultar Qdrant: {str(e)}")
            return []  # Retorna lista vazia em caso de erro
    
    def format_context(self, results):
        """
        Formata os resultados da consulta como um texto de contexto para uso em prompts de LLM
        
        Args:
            results: Lista de documentos retornados pela consulta
            
        Returns:
            String formatada com o contexto para alimentar o modelo de linguagem
        """
        if not results:
            return "Não foi possível encontrar informações relevantes na documentação."
            
        # Formata os documentos em um único texto de contexto estruturado
        context = "CONTEXTO RELEVANTE DA DOCUMENTAÇÃO:\n\n"
        
        for i, doc in enumerate(results, 1):
            context += f"Documento {i}:\n{doc['text']}\n"
            context += f"Fonte: {doc['source']}\n\n"
            
        return context