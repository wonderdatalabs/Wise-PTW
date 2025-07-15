"""
Módulo de Utilitários

Este módulo contém funções utilitárias essenciais para o funcionamento da aplicação.
Inclui funcionalidades como:
- Carregamento de variáveis de ambiente
- Validação de respostas da IA
- Processamento e conversão de imagens para exibição no frontend
- Funções de logging e tratamento de erros

Estas utilidades servem como base para os demais módulos do sistema.
"""

import os
import logging
from dotenv import load_dotenv, find_dotenv
from functools import lru_cache
from PIL import Image
from io import BytesIO
import base64

# Configuração de logging para acompanhamento de execução e depuração
logger = logging.getLogger(__name__)

@lru_cache(maxsize=16)
def carregar_variaveis_ambiente():
    """
    Carrega as variáveis de ambiente do arquivo .env com cache para melhor performance.
    Tenta diferentes métodos de localização do arquivo .env para garantir compatibilidade
    em diferentes ambientes de execução.
    
    Returns:
        bool: True se todas as variáveis foram carregadas, False caso contrário
    """
    # Determina o caminho absoluto para o arquivo .env
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(base_dir, '.env')
    
    # Tenta diferentes abordagens para encontrar e carregar o arquivo .env
    logger.info(f"Tentando carregar .env de: {dotenv_path}")
    loaded = load_dotenv(dotenv_path=dotenv_path)
    
    if not loaded:
        logger.warning(f"Não foi possível carregar {dotenv_path}, tentando find_dotenv()...")
        dotenv_path = find_dotenv()
        if dotenv_path:
            loaded = load_dotenv(dotenv_path)
            logger.info(f"Carregado .env de: {dotenv_path}")
    
    # Verifica se a chave API Anthropic existe
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.error(f"Variável de ambiente não encontrada: ANTHROPIC_API_KEY")
        logger.debug(f"Variáveis disponíveis: {[k for k in os.environ.keys() if not k.startswith('_')]}")
        return False
    
    logger.info(f"Variáveis de ambiente carregadas com sucesso")
    return True

def validar_resposta(resposta, mensagem_erro=None):
    """
    Valida se uma resposta é válida e retorna uma mensagem de erro padrão se não for.
    Utilizada para garantir que respostas vazias ou inválidas sejam tratadas adequadamente
    antes de serem apresentadas ao usuário.
    
    Args:
        resposta: A resposta para validar
        mensagem_erro: Mensagem de erro personalizada (opcional)
        
    Returns:
        str: A resposta original ou mensagem de erro
    """
    if not resposta or resposta.strip() == "":
        return mensagem_erro or "Não foi possível obter uma resposta válida. Por favor, tente novamente."
    return resposta

@lru_cache(maxsize=10)
def obter_imagem_base64(caminho_imagem, largura=None):
    """
    Converte uma imagem para base64 para incorporação em HTML com cache.
    Útil para exibir imagens diretamente em interfaces web sem necessidade
    de servi-las como arquivos estáticos.
    
    Args:
        caminho_imagem: Caminho para o arquivo de imagem
        largura: Largura desejada para a imagem redimensionada (opcional)
        
    Returns:
        str: Representação base64 da imagem
    """
    try:
        # Abre a imagem do caminho especificado
        img = Image.open(caminho_imagem)
        
        # Redimensiona a imagem se a largura for especificada, mantendo a proporção
        if largura:
            ratio = img.width / img.height
            altura = int(largura / ratio)
            img = img.resize((largura, altura), Image.LANCZOS)  # LANCZOS oferece melhor qualidade de redimensionamento
        
        # Converte a imagem para uma string base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        # Registra o erro para facilitar a depuração
        logger.error(f"Erro ao processar imagem {caminho_imagem}: {str(e)}")
        # Retorna uma string vazia em caso de erro para evitar quebrar a aplicação
        return ""