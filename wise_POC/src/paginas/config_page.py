# Importação das bibliotecas necessárias
import streamlit as st  # Framework para criação de aplicações web
import tempfile  # Módulo para criação de arquivos temporários
from pathlib import Path  # Manipulação de caminhos de arquivos
import os
import logging
from dotenv import load_dotenv
# Importação da função que processa PDFs e armazena os dados
from src.paginas.process_pdf import process_and_store_pdf
from src.utils_filtros import (
    carregar_configuracao_filtros, 
    salvar_configuracao_filtros, 
    extrair_campos_disponiveis
)
from src.paginas.busca_page import get_qdrant_client, configurar_campo_qdrant, aplicar_defaults_filtros

# Configuração de logging
logger = logging.getLogger(__name__)

def renderizar_pagina_config():
    """
    Renderiza a página de configurações do sistema
    Esta página contém funcionalidades para upload de relatórios e outras configurações
    """
    # Carrega CSS específico desta página
    from src.ui import carregar_css_pagina
    carregar_css_pagina("config")
    
    # Define o título principal da página com o novo estilo
    st.markdown("<h1 class='config-titulo'>CONFIGURAÇÕES</h1>", unsafe_allow_html=True)
    st.markdown("<div class='config-divider'></div>", unsafe_allow_html=True)
    
    # Cria três abas para organizar diferentes funcionalidades
    tab1, tab2, tab3 = st.tabs(["Upload de documentos", "Filtros", "FAQ"])
    
    # Conteúdo da primeira aba - Upload de documentos
    with tab1:
        # Cabeçalho da seção
        st.markdown('<div class="config-upload-section">', unsafe_allow_html=True)
        st.header("Upload de Documentos")
        
        # Widget para carregar múltiplos arquivos PDF
        uploaded_files = st.file_uploader(
            "Selecione os documentos (PDF)",
            type="pdf",  # Restringe o tipo de arquivo para PDF
            accept_multiple_files=True  # Permite selecionar vários arquivos
        )
        
        # Verifica se arquivos foram carregados
        if uploaded_files:
            # Botão para iniciar o processamento dos arquivos
            if st.button("📤 Processar e Fazer Upload", type="primary", key="config_upload_btn"):
                # Cria uma barra de progresso para acompanhamento visual
                progress_bar = st.progress(0)
                
                st.markdown('<div class="config-processing-results">', unsafe_allow_html=True)
                # Itera sobre cada arquivo carregado
                for idx, uploaded_file in enumerate(uploaded_files):
                    # Mostra um indicador de carregamento durante o processamento
                    with st.spinner(f'Processando {uploaded_file.name}...'):
                        # Processa o arquivo PDF e armazena os dados
                        result = process_and_store_pdf(uploaded_file)
                        
                        # Exibe mensagem de sucesso ou erro com base no resultado
                        if result['success']:
                            st.success(f"✅ {uploaded_file.name}: {result['message']}")
                        else:
                            st.error(f"❌ {uploaded_file.name}: {result['message']}")
                        
                        # Atualiza a barra de progresso
                        progress_bar.progress((idx + 1) / len(uploaded_files))
                
                # Mensagem final quando todos os arquivos são processados
                st.success("🎉 Processamento concluído!")
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Conteúdo da segunda aba - Configuração de Filtros
    with tab2:
        # Carrega as configurações atuais dos filtros
        filtros_config = carregar_configuracao_filtros()
        
        # Carrega configurações do Qdrant
        load_dotenv()
        qdrant_url = os.getenv('QDRANT_URL')
        qdrant_api_key = os.getenv('QDRANT_API_KEY')
        collection_name = os.getenv('QDRANT_COLLECTION_NAME')

        # Verifica se as configurações do Qdrant estão disponíveis
        if not qdrant_url or not qdrant_api_key or not collection_name:
            st.error("Configurações do Qdrant não encontradas. Verifique o arquivo .env")
            return
        
        # Tenta conectar ao Qdrant e extrair os campos disponíveis
        try:
            client = get_qdrant_client(qdrant_url, qdrant_api_key)
            campos_disponiveis = extrair_campos_disponiveis(client, collection_name)
        except Exception as e:
            st.error(f"Erro ao conectar ao Qdrant: {str(e)}")
            return
            
        # Cria uma lista combinada de todos os campos disponíveis, eliminando duplicatas
        # Campos que existem tanto no nível raiz quanto em structured_data
        campos_duplicados = ["process_name", "file_name", "document_type", "departments"]
        
        # Remove os campos duplicados do nível raiz se já existirem em structured_data
        campos_raiz_filtrados = [campo for campo in campos_disponiveis['campos_raiz'] 
                                if campo not in campos_duplicados or campo not in campos_disponiveis['campos_structured']]
        
        # Combina as listas removendo duplicatas
        todos_campos = sorted(set(campos_raiz_filtrados + campos_disponiveis['campos_structured']))
        
        # Lista de campos permitidos (somente estes serão mostrados no selectbox)
        campos_permitidos = [
            "file_name", "process_name", "departments", "document_type", 
            "related_systems", "main_objective", "people_responsible", 
            "steps", "main_topics", "location", "related_equipment", 
            "exec_summary", "detailed_summary", "raw_text",
            "upload_timestamp"  # Campo para filtro de data
        ]
        
        # Campos já utilizados nos filtros atuais (não mostrar novamente)
        campos_ja_utilizados = [filtro["nome"] for filtro in filtros_config]
        
        # Filtra a lista de todos os campos para mostrar somente os permitidos e não utilizados
        campos_disponiveis_para_adicao = [campo for campo in todos_campos 
                                         if campo in campos_permitidos and campo not in campos_ja_utilizados]
               
        # Lista de filtros atuais
        st.subheader("Filtros Atuais")
        
        # Adicionando um espaço após o subtítulo
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not filtros_config:
            st.info("Nenhum filtro configurado.")
        else:
            # Exibir cada filtro com opções para editar/remover
            for i, filtro in enumerate(filtros_config):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
                
                with col1:
                    # Exibe o label (nome visível) do filtro
                    st.markdown(f"**{filtro['label']}**")
                
                with col2:
                    # Exibe o nome do campo no Qdrant
                    st.markdown(f"Campo: `{filtro['nome']}`")
                
                with col3:
                    st.markdown(f"Tipo: `{filtro['tipo']}`")
                
                with col4:
                    # Botão para mover o filtro para cima (desabilitado se for o primeiro)
                    if st.button("⬆️", key=f"up_{i}", disabled=i==0):
                        # Troca a posição do filtro com o anterior
                        filtros_config[i], filtros_config[i-1] = filtros_config[i-1], filtros_config[i]
                        # Salva a nova configuração
                        salvar_configuracao_filtros(filtros_config)
                        st.rerun()
                
                with col5:
                    # Botão para remover o filtro
                    if st.button("🗑️", key=f"del_{i}"):
                        filtros_config.pop(i)
                        # Salva a nova configuração
                        salvar_configuracao_filtros(filtros_config)
                        st.rerun()
                
                # Adiciona um separador entre os filtros com espaço mínimo
                if i < len(filtros_config):
                    st.markdown("<hr style='margin: 0; padding: 0;'>", unsafe_allow_html=True)
        
        # Interface para adicionar novo filtro
        st.subheader("Adicionar Novo Filtro")
        
        # Verifica se ainda existem campos disponíveis para adicionar
        if not campos_disponiveis_para_adicao:
            st.warning("Todos os campos permitidos já foram adicionados aos filtros. Remova algum filtro existente se deseja reconfigurar.")
        else:
            # Formulário para adicionar novo filtro
            with st.form("adicionar_filtro", clear_on_submit=True):
                # Seleção do campo - Começa com uma opção vazia
                campo_nome = st.selectbox(
                    "Campo", 
                    options=[""] + campos_disponiveis_para_adicao,
                    index=0,
                    help="Selecione o campo do Qdrant para criar o filtro"
                )
                
                # Tipo de filtro - Começa vazio
                tipo_filtro = st.selectbox(
                    "Tipo de Filtro",
                    options=["", "selectbox", "multiselect", "text_input", "date_range"],
                    index=0,
                    help="Selecione o tipo de componente para o filtro"
                )
                
                # Campo label SEM valor inicial
                label_filtro = st.text_input(
                    "Nome do Filtro (Label)",
                    value="",
                    key="label_filtro_input",
                    help="Digite o texto que aparecerá para os usuários como nome do filtro"
                )
                
                # Botão para adicionar
                submitted = st.form_submit_button("Adicionar Filtro")
                
                if submitted:
                    if not campo_nome or not tipo_filtro or not label_filtro.strip():
                        st.error("Campo, Tipo de Filtro e Nome do Filtro são obrigatórios.")
                    else:
                        # Abordagem completamente nova - criar filtro diretamente e não usar aplicar_defaults_filtros
                        
                        # Log para diagnóstico
                        logger.info(f"Criando filtro - Campo: {campo_nome}, Tipo: {tipo_filtro}, Label original: {label_filtro.strip()}")
                        
                        # Criar o filtro completo manualmente, sem chamar funções auxiliares
                        if tipo_filtro == "multiselect":
                            default_value = []
                            match_type = "any"
                        elif tipo_filtro == "date_range":
                            default_value = [None, None]
                            match_type = "range"
                        else:
                            default_value = ""
                            match_type = "value"
                            
                        # Define o campo_qdrant manualmente
                        campo_qdrant = []
                        
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
                        
                        # Configurar o campo_qdrant baseado no conhecimento do nome do campo
                        if campo_nome in campos_duplicados:
                            campo_qdrant = [campo_nome, f"structured_data.{campo_nome}"]
                        elif campo_nome in campos_structured:
                            campo_qdrant = [f"structured_data.{campo_nome}"]
                        elif campo_nome in campos_raiz:
                            campo_qdrant = [campo_nome]
                        else:
                            # Para campos não mapeados, tentamos nos dois lugares
                            campo_qdrant = [campo_nome, f"structured_data.{campo_nome}"]
                        
                        # Construir o dicionário completo
                        novo_filtro = {
                            "nome": campo_nome,
                            "tipo": tipo_filtro,
                            "label": label_filtro.strip(),
                            "default": default_value,
                            "match_type": match_type,
                            "campo_qdrant": campo_qdrant
                        }
                        logger.info(f"[ADICIONAR FILTRO] Filtro construído para salvar: {novo_filtro}")
                        
                        logger.info(f"Filtro completo construído: {novo_filtro}")
                        
                        # Adiciona à configuração atual
                        filtros_config.append(novo_filtro)
                        
                        # Também vamos fazer um log da lista completa antes de salvar
                        logger.info(f"Lista de filtros antes de salvar: {filtros_config}")
                        
                        # Salva a nova configuração
                        sucesso = salvar_configuracao_filtros(filtros_config)
                        
                        if sucesso:
                            st.success(f"Filtro '{label_filtro.strip()}' adicionado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Erro ao salvar a configuração. Tente novamente.")
        
        # Botão para restaurar configuração padrão
        if st.button("Restaurar Configuração Padrão"):
            # Cria configuração padrão com labels personalizados
            config_padrao = [
                {
                    "nome": "file_name",
                    "tipo": "selectbox",
                    "label": "Nome do Arquivo",
                    "default": "",
                    "match_type": "value",
                    "campo_qdrant": ["file_name", "structured_data.file_name"]
                },
                {
                    "nome": "main_topics",
                    "tipo": "selectbox",
                    "label": "Tópicos Principais",
                    "default": "",
                    "match_type": "value",
                    "campo_qdrant": ["structured_data.main_topics"]
                },
                {
                    "nome": "departments",
                    "tipo": "selectbox",
                    "label": "Departamento",
                    "default": "",
                    "match_type": "value",
                    "campo_qdrant": ["departments", "structured_data.departments"]
                },
                {
                    "nome": "upload_timestamp",
                    "tipo": "date_range",
                    "label": "Período de Upload",
                    "default": [None, None],
                    "match_type": "range",
                    "campo_qdrant": ["upload_timestamp"]
                },
                {
                    "nome": "raw_text",
                    "tipo": "text_input",
                    "label": "Busca Livre",
                    "default": "",
                    "match_type": "value",
                    "campo_qdrant": ["raw_text"]
                }
            ]
            
            # Não precisa chamar aplicar_defaults_filtros, pois já estamos fornecendo todos os valores
            
            # Salva a configuração padrão
            if salvar_configuracao_filtros(config_padrao):
                st.success("Configuração padrão restaurada com sucesso!")
                # Recarregar a página
                st.rerun()
            else:
                st.error("Erro ao restaurar configuração padrão.")
                
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Informações adicionais
        st.markdown('<div class="config-other-section">', unsafe_allow_html=True)
        st.header("Informações sobre os Campos")
        
        # Adicionar informações sobre os tipos de filtros
        with st.expander("Tipos de Filtros e seus Comportamentos"):
            st.markdown("""
            ### Tipos de Filtros:
            
            - **selectbox**: Cria uma caixa de seleção única com opções pré-carregadas do banco de dados.
            - **multiselect**: Permite selecionar múltiplas opções do banco de dados.
            - **text_input**: Realiza busca semântica usando embeddings - encontra documentos relacionados ao texto digitado.
            - **date_range**: Permite selecionar um intervalo de datas para filtrar documentos.
            
            **Nota importante:** Ao usar filtros do tipo **text_input**, o sistema fará uma busca usando embeddings (vetores semânticos), 
            o que significa que documentos serão encontrados mesmo se não contiverem exatamente o texto digitado, mas sim conteúdo 
            semanticamente relacionado. É ideal para buscas por conceitos e não apenas por palavras exatas.
            """)
        
        with st.expander("Campos Disponíveis no Banco de Dados"):
            st.markdown("### Campos no Nível Raiz")
            st.write(campos_disponiveis['campos_raiz'])
            
            st.markdown("### Campos em Structured Data")
            st.write(campos_disponiveis['campos_structured'])
            
            if 'campos_duplicados' in campos_disponiveis and campos_disponiveis['campos_duplicados']:
                st.markdown("### Campos Duplicados (existem tanto no nível raiz quanto em structured_data)")
                st.info("Estes campos são automaticamente tratados pelo sistema para evitar duplicidade nos filtros.")
                st.write(campos_disponiveis['campos_duplicados'])
            
        with st.expander("Campos com Mapeamentos Especiais"):
            st.markdown("""
            ### Mapeamentos via Configuração do Sistema
            
            Cada campo selecionado para filtragem é automaticamente configurado para buscar nos locais apropriados 
            do banco de dados (nível raiz ou structured_data).
            
            Para campos de busca por texto, o sistema realiza automaticamente uma busca semântica 
            usando embeddings nos campos de texto relevantes.
            """)
                
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab3:
        # Conteúdo da terceira aba - FAQ
        st.markdown("""
        ### Perguntas Frequentes
        
        **Página em construção**
        
        Aqui o usuário poderá configurar as perguntas frequentes que devem aparecer na página FAQ do sistema.
        """)