import os
import json
import logging
from pathlib import Path

# Configuração de logging
logger = logging.getLogger(__name__)

# Caminho para o diretório de configuração e arquivo de filtros
CONFIG_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "config"
FILTROS_CONFIG_PATH = CONFIG_DIR / "filtros_config.json"

# Certifique-se de que o diretório de configuração existe
CONFIG_DIR.mkdir(exist_ok=True)

def carregar_configuracao_filtros():
    """
    Carrega a configuração de filtros do arquivo JSON
    
    Returns:
        list: Lista de filtros configurados
    """
    try:
        config_path = Path("Config/filtros_config.json")
        if not config_path.exists():
            # Retorna configuração padrão se o arquivo não existir
            return []
        
        with open(config_path, "r", encoding="utf-8") as file:
            filtros_config = json.load(file)
            
        # Log para diagnóstico - verifica o que foi carregado
        for filtro in filtros_config:
            logging.info(f"Filtro carregado - Nome: {filtro['nome']}, Label: {filtro['label']}")
            
        return filtros_config
    except Exception as e:
        logging.error(f"Erro ao carregar configuração de filtros: {e}")
        return []

def salvar_configuracao_filtros(filtros_config):
    """
    Salva a configuração de filtros no arquivo JSON
    
    Args:
        filtros_config: Lista de filtros configurados
        
    Returns:
        bool: True se a operação foi bem sucedida, False caso contrário
    """
    try:
        config_path = Path("Config/filtros_config.json")
        
        # Criar uma cópia profunda para não modificar o original
        import copy
        filtros_para_salvar = copy.deepcopy(filtros_config)
        
        # Vamos garantir que cada filtro tenha seu label preservado
        for filtro in filtros_para_salvar:
            logger.info(f"Verificando filtro antes de salvar - Nome: {filtro['nome']}, Label: {filtro['label']}")
            
            # Garantir que todos os campos necessários existam
            if "nome" not in filtro or "tipo" not in filtro or "label" not in filtro:
                logger.warning(f"Filtro incompleto: {filtro}")
        
        # Salva a configuração com indentação para melhor legibilidade
        with open(config_path, "w", encoding="utf-8") as file:
            import json
            json.dump(filtros_para_salvar, file, indent=4, ensure_ascii=False)
            
        # Vamos verificar se o filtro foi salvo corretamente
        with open(config_path, "r", encoding="utf-8") as file:
            filtros_salvos = json.load(file)
            
        for idx, filtro in enumerate(filtros_salvos):
            logger.info(f"Filtro {idx} após salvamento - Nome: {filtro['nome']}, Label: {filtro['label']}")
            
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar configuração de filtros: {e}")
        return False

def extrair_campos_disponiveis(client, collection_name):
    """
    Extrai os campos disponíveis nos documentos do Qdrant.
    
    Args:
        client: Cliente Qdrant
        collection_name: Nome da coleção
        
    Returns:
        dict: Dicionário com os campos disponíveis
    """
    try:
        # Busca uma amostra de documentos para analisar os campos
        sample_docs = client.scroll(
            collection_name=collection_name,
            limit=10,
            with_payload=True,
            with_vectors=False
        )[0]
        
        # Conjuntos para armazenar os campos
        campos_raiz = set()
        campos_structured = set()
        campos_duplicados = []
        
        # Analisa cada documento para extrair os campos
        for doc in sample_docs:
            payload = doc.payload
            
            # Coletar campos no nível raiz
            for campo in payload.keys():
                if campo != 'structured_data':
                    campos_raiz.add(campo)
            
            # Coletar campos dentro de structured_data
            if 'structured_data' in payload and isinstance(payload['structured_data'], dict):
                for campo in payload['structured_data'].keys():
                    campos_structured.add(campo)
                    # Verifica se o campo existe em ambos os níveis
                    if campo in campos_raiz:
                        campos_duplicados.append(campo)
        
        # Converter para listas ordenadas
        resultado = {
            'campos_raiz': sorted(list(campos_raiz)),
            'campos_structured': sorted(list(campos_structured)),
            'campos_duplicados': sorted(list(set(campos_duplicados)))  # Remove duplicatas da lista
        }
        
        return resultado
    except Exception as e:
        logger.error(f"Erro ao extrair campos disponíveis: {str(e)}")
        return {'campos_raiz': [], 'campos_structured': [], 'campos_duplicados': []}
