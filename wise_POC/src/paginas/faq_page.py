import streamlit as st
import logging

# Configuração de logging
logger = logging.getLogger(__name__)

def enviar_para_chat(pergunta, indice):
    """
    Função utilitária para enviar pergunta do FAQ para o chat
    
    Args:
        pergunta (str): A pergunta formatada para exibição ao usuário
        indice (int): O índice da pergunta na lista de perguntas reais
    """
    try:
        # Mapeamento de perguntas reais que serão enviadas ao chat
        perguntas_reais = [
            "Poderia detalhar quais são os principais bancos de dados utilizados na Wonder DataLabs e suas respectivas funções?",
            "Me explica passo a passo como fazer deploy de um projeto estreamlit na AWS?",
            "Explique o funcionamento do sistema de armazenamento de documentos e textos, especificamente sobre o uso do Qdrant e suas capacidades.",
            "Detalhe o processo completo de processamento de documentos, incluindo as etapas de extração, estruturação e geração de embeddings.",
            "Quais são as políticas de retenção de dados implementadas nos diferentes bancos de dados da empresa?",
            "Quais são os requisitos técnicos específicos e conhecimentos necessários para trabalhar com os bancos de dados da Wonder DataLabs?",
            "Explique em detalhes como é implementada a estruturação de dados no Qdrant para realizar buscas semânticas eficientes.",
            "Qual o procedimento passo a passo para levantar uma máquina virtual na EC2 da AWS?",
            "Como é realizada a organização e segregação dos dados de diferentes clientes nos bancos de dados utilizados?",
            "Descreva as medidas de segurança implementadas para proteção dos dados, incluindo aspectos de criptografia e conformidade."
        ]
        
        # Verificação de segurança para o índice
        if indice < 0 or indice >= len(perguntas_reais):
            logger.error(f"Índice de pergunta inválido: {indice}")
            st.error("Erro ao selecionar pergunta. Por favor, tente novamente.")
            return
            
        # Salva a pergunta visível para o usuário (para mostrar na interface)
        st.session_state.pergunta_visivel = pergunta
        # Salva a pergunta real que será processada pelo backend
        st.session_state.mensagem_faq_selecionada = perguntas_reais[indice]
        # Salva o índice da pergunta selecionada
        st.session_state.indice_pergunta_faq = indice
        
        # Marca como não processado
        if 'faq_processado' in st.session_state:
            st.session_state.faq_processado = False
            
        # Marca o timestamp da seleção para rastreamento
        from datetime import datetime
        st.session_state.faq_timestamp = datetime.now().isoformat()
            
        # Muda para a página de chat
        st.session_state.pagina_atual = "chat"
        # Indica que deve processar esta mensagem no chat
        st.session_state.processar_faq = True
        
        logger.info(f"FAQ selecionado: índice={indice}, pergunta={pergunta}")
        # Redireciona
        st.rerun()
        
    except Exception as e:
        logger.error(f"Erro ao processar FAQ: {str(e)}")
        st.error("Ocorreu um erro ao processar sua seleção. Por favor, tente novamente.")

def processar_pergunta_faq():
    """
    Processa a pergunta do FAQ quando o usuário é redirecionado para a página de chat.
    Esta função deve ser chamada no app.py para tratar pergunta do FAQ selecionada.
    
    Returns:
        bool: True se uma pergunta foi processada, False caso contrário
    """
    try:
        # Inicializa controle de processamento do FAQ
        if 'faq_processado' not in st.session_state:
            st.session_state.faq_processado = False
        
        # Usar a variável faq_processado para evitar processamento múltiplo da mesma pergunta
        if (st.session_state.pagina_atual == "chat" and 
            st.session_state.get('processar_faq', False) and 
            not st.session_state.faq_processado and
            st.session_state.get('mensagem_faq_selecionada')):
            
            # Log para debug
            logger.info(f"Processando pergunta do FAQ: {st.session_state.mensagem_faq_selecionada}")
            
            # Marca como processado ANTES de processar a mensagem
            st.session_state.faq_processado = True
            
            # Processa a pergunta selecionada no FAQ
            pergunta = st.session_state.mensagem_faq_selecionada
            
            # Adiciona pergunta ao histórico explicitamente (bypass do processar_mensagem)
            if 'mensagens' in st.session_state:
                st.session_state.mensagens.append({"role": "user", "content": pergunta})
            
            # Define que a resposta deve ser processada pelo assistente
            st.session_state.aguardando_resposta = True
            st.session_state.mensagem_atual = pergunta
            
            # Limpa para evitar reprocessamento
            st.session_state.mensagem_faq_selecionada = None
            st.session_state.processar_faq = False
            
            return True
        
        return False
            
    except Exception as e:
        logger.error(f"Erro ao processar pergunta do FAQ: {str(e)}")
        st.error(f"Erro ao processar pergunta do FAQ: {str(e)}")
        return False

def renderizar_pagina_faq():
    """
    Renderiza a página de FAQ com perguntas frequentes clicáveis organizadas em categorias
    """
    try:
        # Carrega CSS específico desta página
        from src.ui import carregar_css_pagina, obter_imagem_base64
        carregar_css_pagina("faq")
        
        # Reinicia o estado de processamento do FAQ quando volta para esta página
        if 'faq_processado' in st.session_state:
            st.session_state.faq_processado = False
        
        # Cabeçalho com título centralizado usando o estilo consistente
        st.markdown("<h1 class='faq-titulo'>PERGUNTAS FREQUENTES</h1>", unsafe_allow_html=True)
        st.markdown("<div class='faq-divider'></div>", unsafe_allow_html=True)
        st.markdown("<div class='faq-container'>", unsafe_allow_html=True)

        # Lista de perguntas frequentes visíveis para o usuário
        faqs = [
            "Quais bancos de dados a Wonder DataLabs usa atualmente?",
            "Como fazer deploy de um projeto estreamlit?",
            "Onde são guardados os documentos e textos da empresa?",
            "Como é feito o processamento dos documentos a serem salvos?",
            "Por quanto tempo os dados ficam armazenados?",
            "Que conhecimentos preciso para trabalhar com bancos de dados?",
            "Como funciona a busca de documentos no sistema?",
            "Como levantar uma máquina virtual EC2?",
            "Como são organizados os dados de diferentes clientes?",
            "Quais são as medidas de segurança dos dados da Wonder?"
        ]
        
        # Criar duas colunas para as perguntas
        col1, col2 = st.columns(2)
        
        # Distribuir as perguntas entre as colunas
        for idx, pergunta in enumerate(faqs):
            # Primeiras 5 perguntas na coluna esquerda (índices 0-4)
            if idx < 5:
                with col1:
                    if st.button(
                        pergunta, 
                        key=f"faq_{idx}", 
                        use_container_width=True
                    ):
                        enviar_para_chat(pergunta, idx)
                    
                    # Adiciona espaço entre os botões
                    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            # Últimas 5 perguntas na coluna direita (índices 5-9)
            else:
                with col2:
                    if st.button(
                        pergunta, 
                        key=f"faq_{idx}", 
                        use_container_width=True
                    ):
                        enviar_para_chat(pergunta, idx)
                    
                    # Adiciona espaço entre os botões
                    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        
    except Exception as e:
        logger.error(f"Erro ao renderizar página FAQ: {str(e)}")
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue a aplicação.")