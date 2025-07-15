import streamlit as st

def renderizar_pagina_chat():
    """
    Renderiza a página de chat com a interface do usuário
    
    Returns:
        tuple: (mensagem, enviar) - A mensagem digitada e o estado do botão de envio
    """
    # Carrega CSS específico desta página
    from src.ui import carregar_css_pagina
    carregar_css_pagina("chat")
    
    # Injetar CSS adicional para garantir visibilidade
    st.markdown("""
        <style>
        /* Garantir que as mensagens sejam exibidas corretamente */
        .element-container {
            opacity: 1 !important;
            visibility: visible !important;
        }
        [data-testid="stChatMessageContent"] > * {
            opacity: 1 !important;
            visibility: visible !important;
        }
        /* Remover qualquer estilo que possa estar escondendo o conteúdo */
        .wonder-chat-user-message, .wonder-chat-assistant-message {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            position: relative !important;
            z-index: 1000 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Renderiza a interface de chat
    st.markdown('<div class="wonder-chat-container">', unsafe_allow_html=True)
    
    # Sempre exibe a tela inicial do chat (independente de ter mensagens ou não)
    st.markdown("""
        <div class="wonder-chat-welcome">
            <div class="wonder-chat-welcome-icon">💬</div>
            <h1 class="wonder-chat-welcome-title">Wonder Assistant</h1>
            <div class="wonder-chat-welcome-divider"></div>
            <p class="wonder-chat-welcome-message">
                Olá! Estou aqui para ajudar com suas dúvidas sobre os bancos de dados, 
                armazenamento, processamento de documentos e muito mais. 
                Como posso ajudar você hoje?
            </p>              
        </div>
    """, unsafe_allow_html=True)
    
    # Inicia a seção de mensagens se existirem mensagens
    if st.session_state.mensagens:
        st.markdown('<div class="wonder-chat-messages-section">', unsafe_allow_html=True)
        # Exibe mensagens usando o componente nativo de chat
        for msg in st.session_state.mensagens:
            if msg['role'] == 'user':
                with st.chat_message("user", avatar="💬"):
                    # Mensagem do usuário com classe CSS específica
                    st.markdown(
                        f"""
                        <div class="wonder-chat-user-message">
                        {msg["content"]}
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    # Mensagem do assistente com classe CSS específica
                    st.markdown(
                        f"""
                        <div class="wonder-chat-assistant-message">
                        {msg["content"]}
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Mostra indicador de digitação
    if st.session_state.aguardando_resposta:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(
                """
                <div class="wonder-chat-typing-indicator">
                <em>Assistente está digitando</em>
                </div>
                """, 
                unsafe_allow_html=True
            )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Botão de limpar chat
    col1, col2 = st.columns([4, 1])
    with col2:
        st.markdown('<div class="wonder-chat-clear-button">', unsafe_allow_html=True)
        st.button(
            "Limpar Chat", 
            on_click=limpar_chat,
            key="limpar_chat_btn",
            disabled=st.session_state.aguardando_resposta,
            use_container_width=True,
            type="primary"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Área de input para novas mensagens
    st.markdown('<div class="wonder-chat-input-container">', unsafe_allow_html=True)
    mensagem = st.chat_input(
        "Digite sua mensagem...",
        key=f"chat_input_{st.session_state.input_key}",
        disabled=st.session_state.aguardando_resposta
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Simula o comportamento de "enviar" quando o usuário digita algo no input
    enviar = mensagem is not None
    
    return mensagem, enviar

def limpar_chat():
    """Limpa o histórico de mensagens e cria uma nova conversa"""
    try:
        # Limpa o histórico de mensagens
        st.session_state.mensagens = []
        
        # Cria nova thread no backend via API
        sucesso = st.session_state.assistente.limpar_conversa()
        
        # Reseta as variáveis de estado da UI
        st.session_state.input_key += 1
        st.session_state.aguardando_resposta = False
        st.session_state.mensagem_atual = ""
        
        if not sucesso:
            st.warning("Erro ao criar nova conversa. Tente recarregar a página.")
            
    except Exception as e:
        import logging
        logging.error(f"Erro ao limpar chat: {e}")
        st.error("Ocorreu um erro ao limpar o histórico.")
