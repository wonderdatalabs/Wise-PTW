import streamlit as st
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchAny, Range
import os
from dotenv import load_dotenv
import logging
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from datetime import datetime, timedelta
from src.utils_filtros import carregar_configuracao_filtros

@st.cache_resource
def get_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

def gerar_embedding(texto):
    return get_embedding_model().encode(texto).tolist()

# ================================
# CONFIGURAÇÃO CENTRAL DOS FILTROS
# ================================
def configurar_campo_qdrant(nome_campo):
    """
    Configura automaticamente o campo_qdrant baseado no nome do campo,
    seguindo o padrão de dados do banco Qdrant.
    """
    # Campos que podem existir tanto no nível raiz quanto em structured_data
    campos_duplicados = ["process_name", "file_name", "document_type", "departments"]
    
    # Campos que normalmente só existem em structured_data
    campos_structured = [
        "related_systems", "main_objective", "people_responsible",
        "steps", "main_topics", "exec_summary", "detailed_summary", 
        "location", "related_equipment"
    ]
    
    # Campos que normalmente só existem no nível raiz
    campos_raiz = ["upload_timestamp", "upload_date_str", "point_id", "raw_text"]
    
    # Mapeamentos especiais de nomes de filtros para campos do banco
    mapeamentos_especiais = {
        "sistema_relacionado": "related_systems",
        "responsaveis": "people_responsible",
        "nome_arquivo": "file_name",
        "periodo_upload": "upload_timestamp",
        "busca_livre": ["structured_data.detailed_summary", "structured_data.exec_summary", "raw_text"]
    }
    
    # Verifica se é um mapeamento especial
    if nome_campo in mapeamentos_especiais:
        campo_mapeado = mapeamentos_especiais[nome_campo]
        if isinstance(campo_mapeado, list):
            return campo_mapeado
        nome_campo = campo_mapeado
    
    if nome_campo in campos_duplicados:
        return [nome_campo, f"structured_data.{nome_campo}"]
    elif nome_campo in campos_structured:
        return [f"structured_data.{nome_campo}"]
    elif nome_campo in campos_raiz:
        return [nome_campo]
    else:
        # Para campos não mapeados, tentamos nos dois lugares
        return [nome_campo, f"structured_data.{nome_campo}"]

def aplicar_defaults_filtros(filtros):
    import logging
    logger = logging.getLogger(__name__)
    
    for f in filtros:
        # Loga o filtro antes de aplicar defaults
        logger.info(f"[BUSCA] Antes de aplicar defaults - Nome: {f.get('nome')}, Label: {f.get('label', 'não definido')}")
        
        # Define valores default
        if "default" not in f:
            if f["tipo"] == "multiselect":
                f["default"] = []
            elif f["tipo"] == "date_range":
                f["default"] = [None, None]  # Default para date_range
            elif f["tipo"] == "date_input":
                f["default"] = None
            else:
                f["default"] = ""
                
        # Define match_type
        if "match_type" not in f:
            if f["tipo"] == "multiselect":
                f["match_type"] = "any"
            elif f["tipo"] in ["date_input", "date_range"]:
                f["match_type"] = "range"
            else:
                f["match_type"] = "value"
                
        # Define campo_qdrant automaticamente se não estiver definido
        if "campo_qdrant" not in f:
            f["campo_qdrant"] = configurar_campo_qdrant(f["nome"])
        
        # Garante que o label está definido, mas APENAS se não existir
        # Modificado para nunca sobrescrever um label existente
        if "label" not in f or not f["label"]:
            f["label"] = f["nome"].replace('_', ' ').title()
            
        # Loga o filtro após aplicar defaults
        logger.info(f"[BUSCA] Depois de aplicar defaults - Nome: {f['nome']}, Label: {f['label']}")
            
    return filtros

# Função para converter data para timestamp (meia-noite do dia)
def data_para_timestamp(data):
    if not data:
        return None
    # Retorna timestamp em segundos (meia-noite do dia escolhido)
    return int(datetime.combine(data, datetime.min.time()).timestamp())

# =========================
# FUNÇÕES QDRANT E UTILIDADES
# =========================
def formatar_html(tag, content, classe=None):
    class_attr = f' class="{classe}"' if classe else ''
    return f"<{tag}{class_attr}>{content}</{tag}>"

def markdown_html(content, unsafe_allow_html=True):
    st.markdown(content, unsafe_allow_html=unsafe_allow_html)

def limpar_filtros(filtros_config):
    for filtro in filtros_config:
        key = filtro["nome"]
        if key in st.session_state:
            st.session_state[key] = filtro["default"]
        
        # Limpa também os campos de date_range
        if filtro["tipo"] == "date_range":
            if f"{key}_inicial" in st.session_state:
                st.session_state[f"{key}_inicial"] = None
            if f"{key}_final" in st.session_state:
                st.session_state[f"{key}_final"] = None

@lru_cache(maxsize=1)

def get_qdrant_client(url, api_key):
    return QdrantClient(url=url, api_key=api_key)

def extract_field_values(sample_docs, field_name):
    values_set = set([""])
    for doc in sample_docs:
        payload = doc.payload
        # Campo no payload raiz
        if field_name in payload and payload[field_name]:
            if isinstance(payload[field_name], list):
                for item in payload[field_name]:
                    if item:
                        values_set.add(str(item))
            else:
                values_set.add(str(payload[field_name]))
        # Campo em structured_data
        if 'structured_data' in payload and isinstance(payload['structured_data'], dict):
            structured_data = payload['structured_data']
            if field_name in structured_data:
                if isinstance(structured_data[field_name], list):
                    for item in structured_data[field_name]:
                        if item:
                            values_set.add(str(item))
                else:
                    values_set.add(str(structured_data[field_name]))
    return sorted(list(values_set)) if len(values_set) > 1 else [""]

def fetch_select_options(client, collection_name, filtros_config):
    try:
        sample_docs = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )[0]
        opcoes = {}
        for filtro in filtros_config:
            # Ignora filtros de tipo date_range e text_input
            if filtro["tipo"] in ["date_range", "text_input"]:
                continue
                
            # Pega o campo para extrair as opções
            campo = filtro["campo_qdrant"][0]
            # Se for um campo dentro de structured_data, pega só o nome do subcampo
            if campo.startswith("structured_data."):
                campo = campo.split(".", 1)[1]
            
            opcoes[filtro["nome"]] = extract_field_values(sample_docs, campo)
            
            # Certifica-se de que temos pelo menos um valor vazio para os dropdowns
            if not opcoes[filtro["nome"]] or (len(opcoes[filtro["nome"]]) == 1 and opcoes[filtro["nome"]][0] == ""):
                opcoes[filtro["nome"]] = [""]
                
        return opcoes
    except Exception as e:
        logging.error(f"Erro ao obter opções de seleção: {str(e)}")
        return {f["nome"]: [""] for f in filtros_config if f["tipo"] in ["selectbox", "multiselect"]}

def create_search_filter(valores, filtros_config):
    must_conditions = []
    for filtro in filtros_config:
        valor = valores.get(filtro["nome"])
        # Pula filtros vazios
        if filtro["tipo"] == "multiselect" and not valor:
            continue
        if filtro["tipo"] in ["selectbox", "text_input"] and (not valor or valor == ""):
            continue
        if filtro["tipo"] == "date_range" and not any(valor):
            continue
        
        if filtro["match_type"] == "value":
            should_conditions = [FieldCondition(key=campo, match=MatchValue(value=valor)) 
                                for campo in filtro["campo_qdrant"]]
            must_conditions.append(Filter(should=should_conditions))
        elif filtro["match_type"] == "any":
            for campo in filtro["campo_qdrant"]:
                if filtro["tipo"] == "multiselect" and valor:
                    must_conditions.append(FieldCondition(key=campo, match=MatchAny(any=valor)))
                else:
                    must_conditions.append(FieldCondition(key=campo, match=MatchAny(any=[valor])))
        elif filtro["match_type"] == "range" and filtro["tipo"] == "date_range":
            # Filtro por intervalo de datas
            data_inicial, data_final = valor
            
            # Converte as datas para timestamps
            range_params = {}
            if data_inicial:
                # Timestamp da meia-noite do dia inicial
                range_params["gte"] = data_para_timestamp(data_inicial)
            if data_final:
                # Timestamp do final do dia final (23:59:59)
                timestamp_final = data_para_timestamp(data_final)
                if timestamp_final:
                    timestamp_final += 86399  # +23:59:59 em segundos
                    range_params["lte"] = timestamp_final
            
            # Adiciona condição apenas se houver pelo menos um limite (inicial ou final)
            if range_params:
                for campo in filtro["campo_qdrant"]:
                    must_conditions.append(
                        FieldCondition(key=campo, range=Range(**range_params))
                    )
                    
    return Filter(must=must_conditions)

def renderizar_filtro(filtro, opcoes_filtros):
    """
    Renderiza um único filtro e retorna seus valores
    """
    valores = {}
    key = filtro["nome"]
    label = filtro["label"]  # Usar o label definido pelo usuário, não o nome do campo
    tipo = filtro["tipo"]
    opcoes = opcoes_filtros.get(key, [filtro["default"]])
    
    if tipo == "selectbox":
        valores[key] = st.selectbox(
            label, opcoes,
            index=opcoes.index(st.session_state[key]) if st.session_state[key] in opcoes else 0,
            key=key, placeholder=f"Selecione {label.lower()}"
        )
    elif tipo == "multiselect":
        valores[key] = st.multiselect(
            label, options=opcoes, key=key, placeholder=f"Selecione {label.lower()}"
        )
    elif tipo == "text_input":
        valores[key] = st.text_input(
            label, value=st.session_state[key], key=key, placeholder=f"Digite {label.lower()}"
        )
    elif tipo == "date_range":
        # Interface para seleção de período (duas datas)
        # Usamos o label personalizado para o título
        col1, col2 = st.columns(2)
        with col1:
            data_inicial = st.date_input(
                f"{label} (início)", 
                value=st.session_state.get(f"{key}_inicial", None),
                key=f"{key}_inicial", 
                format="DD/MM/YYYY"
            )
        with col2:
            data_final = st.date_input(
                f"{label} (fim)",
                value=st.session_state.get(f"{key}_final", None),
                key=f"{key}_final",
                format="DD/MM/YYYY"
            )
        valores[key] = [data_inicial, data_final]
        
    return valores

# =========================
# VISUALIZAÇÃO DOS RESULTADOS
# =========================
def render_result_item(result, index):
    payload = result.payload
    structured_data = payload.get('structured_data', {})
    processo_nome = structured_data.get('process_name', payload.get('file_name', f'Processo #{index+1}'))
    
    with st.expander(processo_nome, expanded=index == 0):
        markdown_html("<div class='busca-resultado-container'>")
        tabs = st.tabs(["Informações Principais", "Detalhes", "Conteúdo Completo"])
        
        with tabs[0]:
            col1, col2 = st.columns(2)
            with col1:
                markdown_html("<h3 class='busca-info-titulo'>Informações do Documento</h3>")
                markdown_html(f"<p class='busca-info-item'><span class='busca-info-label'>Nome:</span> {processo_nome}</p>")
                
                sistemas = structured_data.get('related_systems', [])
                if sistemas:
                    sistemas_str = ', '.join(sistemas) if isinstance(sistemas, list) else sistemas
                    markdown_html(f"<p class='busca-info-item'><span class='busca-info-label'>Sistemas Relacionados:</span> {sistemas_str}</p>")
                
                objetivo = structured_data.get('main_objective', 'Não especificado')
                markdown_html(f"<p class='busca-info-item'><span class='busca-info-label'>Objetivo:</span> {objetivo}</p>")
            
            with col2:
                markdown_html("<h3 class='busca-info-titulo'>Departamentos e Responsáveis</h3>")
                
                deptos = structured_data.get('departments', [])
                if deptos:
                    deptos_str = ', '.join(deptos) if isinstance(deptos, list) else deptos
                    markdown_html(f"<p class='busca-info-item'><span class='busca-info-label'>Departamentos:</span> {deptos_str}</p>")
                
                resp = structured_data.get('people_responsible', [])
                if resp:
                    resp_str = ', '.join(resp) if isinstance(resp, list) else resp
                    markdown_html(f"<p class='busca-info-item'><span class='busca-info-label'>Responsáveis:</span> {resp_str}</p>")
            
            # Adicionando resumo Executivo na primeira aba
            if 'exec_summary' in structured_data:
                markdown_html("<h3 class='busca-info-titulo'>Resumo Executivo</h3>")
                markdown_html(f"<div class='busca-resumo-exec'>{structured_data['exec_summary']}</div>")
        
        with tabs[1]:
            # Dividindo a segunda aba em duas colunas
            col1, col2 = st.columns(2)
            
            with col1:
                # Tipo de documento
                if 'document_type' in structured_data:
                    markdown_html("<h3 class='busca-detalhe-titulo'>Tipo de Documento</h3>")
                    tipo_doc = structured_data['document_type']
                    markdown_html(f"<p class='busca-info-item'><span class='busca-info-label'>Tipo:</span> {tipo_doc}</p>")
                
                # Etapas do processo
                if 'steps' in structured_data:
                    markdown_html("<h3 class='busca-detalhe-titulo'>Etapas</h3>")
                    etapas = structured_data['steps']
                    if isinstance(etapas, list):
                        for idx, etapa in enumerate(etapas, 1):
                            markdown_html(f"<p class='busca-etapa-item'><span class='busca-etapa-numero'>{idx}.</span> {etapa}</p>")
                    else:
                        markdown_html(f"<p class='busca-etapa-item'>{etapas}</p>")
            
            with col2:
                # Localização (adicionado conforme solicitado)
                if 'location' in structured_data:
                    markdown_html("<h3 class='busca-detalhe-titulo'>Localização</h3>")
                    location = structured_data['location']
                    if isinstance(location, list):
                        for loc in location:
                            markdown_html(f"<p class='busca-info-item'>• {loc}</p>")
                    else:
                        markdown_html(f"<p class='busca-info-item'>{location}</p>")
                
                # Tópicos principais
                if 'main_topics' in structured_data:
                    markdown_html("<h3 class='busca-detalhe-titulo'>Tópicos Principais</h3>")
                    topics = structured_data['main_topics']
                    if isinstance(topics, list):
                        for topic in topics:
                            markdown_html(f"<p class='busca-topico-item'>• {topic}</p>")
                    else:
                        markdown_html(f"<p class='busca-topico-item'>{topics}</p>")
            
            # Resumo detalhado (ocupando toda a largura, abaixo das duas colunas)
            if 'detailed_summary' in structured_data:
                markdown_html("<h3 class='busca-detalhe-titulo'>Resumo Detalhado</h3>")
                markdown_html(f"<div class='busca-resumo-detalhado'>{structured_data['detailed_summary']}</div>")
        
        with tabs[2]:
            markdown_html("<h3 class='busca-detalhe-titulo'>Conteúdo Completo do Documento</h3>")
            if 'raw_text' in payload:
                # Tenta formatar o texto bruto para melhor visualização
                raw_text = payload['raw_text']
                formatted_text = raw_text.replace('\n', '<br>').replace('  ', '&nbsp;&nbsp;')
                
                # Exibir apenas o texto formatado (sem subcampos)
                markdown_html(f"<div class='busca-texto-formatado'>{formatted_text}</div>")
            else:
                markdown_html("<div class='busca-info-msg'>Conteúdo completo não disponível para este documento.</div>")
        
        markdown_html("</div>")

# =========================
# FUNÇÃO PRINCIPAL DA PÁGINA
# =========================
def renderizar_pagina_busca():
    from src.ui import carregar_css_pagina
    carregar_css_pagina("busca")
    
    # Renderiza o título
    markdown_html("<h1 class='busca-titulo'>BUSCA AVANÇADA</h1>")
    markdown_html("<div class='busca-divider'></div>")

    # Carrega configurações do Qdrant
    load_dotenv()
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRant_API_KEY')
    collection_name = os.getenv('QDRANT_COLLECTION_NAME')

    if not qdrant_url or not qdrant_api_key:
        markdown_html("<div class='busca-erro'>Configurações do Qdrant não encontradas. Verifique o arquivo .env</div>")
        return

    # Carrega a configuração de filtros do arquivo JSON
    filtros_config = carregar_configuracao_filtros()
    # Loga todos os labels carregados do arquivo de configuração
    for f in filtros_config:
        logging.info(f"[BUSCA] Filtro carregado do arquivo - Nome: {f.get('nome')}, Label: {f.get('label')}")
    
    # Aplica os valores padrão para garantir que todos os filtros tenham configurações necessárias
    filtros_config = aplicar_defaults_filtros(filtros_config)

    # Inicializa opções dinâmicas dos filtros
    opcoes_filtros = {f["nome"]: [f["default"]] for f in filtros_config}
    try:
        client = get_qdrant_client(qdrant_url, qdrant_api_key)
        opcoes_filtros = fetch_select_options(client, collection_name, filtros_config)
    except Exception as e:
        markdown_html(f"<div class='busca-erro'>Erro ao conectar ao Qdrant: {str(e)}</div>")
        return

    # Formulário de busca
    markdown_html("<div class='busca-form-container'>")
    with st.form("form_busca_avancada", clear_on_submit=False):
        markdown_html("<h2 class='busca-subtitulo'>FILTROS DA BUSCA</h2>")
        
        # Inicializa session_state
        for filtro in filtros_config:
            key = filtro["nome"]
            if key not in st.session_state:
                st.session_state[key] = filtro["default"]

        # Distribuição dos filtros em duas colunas
        valores = {}
        total_filtros = len(filtros_config)
        
        # Verifica se o número de filtros é ímpar
        filtros_por_coluna = total_filtros // 2
        tem_filtro_central = total_filtros % 2 == 1
        
        # Se tiver um número ímpar de filtros, identifica qual será o filtro central
        # Vamos usar o último filtro como filtro central
        filtro_central_idx = total_filtros - 1 if tem_filtro_central else None
        
        # Distribui os filtros
        filtros_coluna1 = []
        filtros_coluna2 = []
        
        for i, filtro in enumerate(filtros_config):
            # Se for o filtro central, pula a distribuição entre colunas
            if i == filtro_central_idx:
                continue
                
            # Metade dos filtros na coluna 1, metade na coluna 2
            if i < filtros_por_coluna:
                filtros_coluna1.append(filtro)
            else:
                filtros_coluna2.append(filtro)
               
        
        # Cria as duas colunas
        col1, col2 = st.columns(2)
        
        # Renderiza os filtros da coluna 1
        with col1:
            for filtro in filtros_coluna1:
                valores.update(renderizar_filtro(filtro, opcoes_filtros))
                
        # Renderiza os filtros da coluna 2
        with col2:
            for filtro in filtros_coluna2:
                valores.update(renderizar_filtro(filtro, opcoes_filtros))
        
        # Se houver um filtro central, renderiza-o ocupando as duas colunas
        if filtro_central_idx is not None:
            filtro_central = filtros_config[filtro_central_idx]
            valores.update(renderizar_filtro(filtro_central, opcoes_filtros))

        # Botões do formulário
        markdown_html("<div class='busca-botoes-container'>")
        col1, col2 = st.columns([3, 1])
        with col1:
            markdown_html("<div class='busca-botao-buscar'>")
            submitted = st.form_submit_button("Buscar", use_container_width=True)
            markdown_html("</div>")
        with col2:
            markdown_html("<div class='busca-botao-limpar'>")
            limpar = st.form_submit_button("Limpar Filtros", on_click=limpar_filtros, args=(filtros_config,), use_container_width=True)
            markdown_html("</div>")
        markdown_html("</div>")
    markdown_html("</div>")

    # Processamento da busca quando o formulário é enviado
    if submitted:
        # Verifica se há algum filtro preenchido
        if not any([
            any(valores[k] for k in valores if isinstance(valores[k], list) and valores[k] and k != "periodo_upload"),
            any(valores[k] for k in valores if isinstance(valores[k], str) and valores[k]),
            valores.get("periodo_upload", [None, None])[0] is not None,
            valores.get("periodo_upload", [None, None])[1] is not None
        ]):
            markdown_html("<div class='busca-aviso'>Por favor, preencha pelo menos um campo para realizar a busca.</div>")
            return

        # Feedback visual durante a busca
        search_message = st.empty()
        search_message.markdown("<div class='busca-info'>Iniciando a busca dos documentos...</div>", unsafe_allow_html=True)
        progress_bar = st.progress(0)
        
        # Executa a busca
        with st.spinner("Buscando processos correspondentes..."):
            try:
                # Preparação da busca
                search_message.markdown("<div class='busca-info'>Preparando filtros de busca...</div>", unsafe_allow_html=True)
                progress_bar.progress(20)
                
                # Identifica os filtros de texto preenchidos para busca por embeddings
                filtros_texto = {}
                for filtro in filtros_config:
                    if filtro["tipo"] == "text_input" and valores.get(filtro["nome"], "").strip():
                        filtros_texto[filtro["nome"]] = valores[filtro["nome"]]
                
                # Verifica se existe alguma busca por texto
                if filtros_texto:
                    # Busca semântica com embeddings
                    search_message.markdown("<div class='busca-info'>Realizando busca semântica...</div>", unsafe_allow_html=True)
                    
                    # Cria embedding para cada texto de busca e combina resultados
                    results = []
                    texto_combinado = " ".join(filtros_texto.values())
                    
                    query_vector = gerar_embedding(texto_combinado)
                    search_results = client.search(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        limit=15,
                        with_payload=True,
                        with_vectors=False,
                    )
                    
                    # Filtra por score mínimo
                    score_minimo = 0.2
                    results = [r for r in search_results if getattr(r, "score", 1) >= score_minimo]
                else:
                    # Busca por filtros
                    search_message.markdown("<div class='busca-info'>Aplicando filtros de busca...</div>", unsafe_allow_html=True)
                    search_filter = create_search_filter(valores, filtros_config)
                    
                    scroll_results = client.scroll(
                        collection_name=collection_name,
                        scroll_filter=search_filter,
                        limit=15,
                        with_payload=True,
                        with_vectors=False,
                    )
                    results = scroll_results[0]

                # Renderiza os resultados
                search_message.markdown("<div class='busca-info'>Processando os resultados...</div>", unsafe_allow_html=True)
                progress_bar.progress(80)
                progress_bar.progress(100)
                search_message.empty()
                
                # Exibe resultados
                if results:
                    markdown_html(f"<div class='busca-sucesso'>{len(results)} processo(s) encontrado(s)</div>")
                    for i, result in enumerate(results):
                        render_result_item(result, i)
                else:
                    markdown_html("<div class='busca-aviso'>Nenhum documento encontrado para os filtros informados.</div>")
                    
            except Exception as e:
                markdown_html(f"<div class='busca-erro'>Erro ao realizar a busca: {str(e)}</div>")
                logging.error(f"Erro ao realizar busca no Qdrant: {str(e)}")
                
    # Adiciona uma seção para exibir informações sobre como funciona a busca
    with st.expander("ℹ️ Sobre a Busca Avançada", expanded=False):
        st.markdown("""
        ### Como funciona a busca avançada
        
        - **Filtros de texto (text_input)**: Realizam busca semântica usando embeddings, encontrando documentos 
          relacionados mesmo que não contenham exatamente as mesmas palavras.
          
        - **Filtros de seleção (selectbox/multiselect)**: Buscam valores exatos nos campos correspondentes.
        
        - **Filtros de data (date_range)**: Permitem filtrar documentos por período, selecionando datas de início e fim. 
          O sistema encontrará todos os documentos que foram cadastrados dentro do intervalo escolhido.
        
        Os filtros disponíveis são configurados pelos administradores na página de Configurações.
        """)