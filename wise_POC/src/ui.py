"""
Módulo de Interface de Usuário (UI)

Este módulo contém todas as funções relacionadas à interface do usuário do Assistente,
implementada com Streamlit. Ele gerencia:
- Renderização da interface de chat
- Processamento de mensagens do usuário
- Exibição de respostas do assistente em tempo real (streaming)
- Gerenciamento do estado da sessão
- Elementos visuais como cabeçalho, rodapé e estilos personalizados

A estrutura segue um padrão de componentes isolados que trabalham juntos para criar
uma experiência de chat fluida e responsiva.
"""
import streamlit as st
import base64
import logging
from PIL import Image
from io import BytesIO
from src.api import Assistente

def obter_imagem_base64(caminho_imagem, largura=None):
    """
    Converte uma imagem para base64 para incorporação em HTML
    
    Args:
        caminho_imagem: Caminho do arquivo de imagem a ser convertido
        largura: Largura opcional para redimensionar a imagem
        
    Returns:
        String base64 da imagem para uso em tags HTML
    """
    img = Image.open(caminho_imagem)
    
    # Redimensiona a imagem se a largura for especificada
    if largura:
        ratio = img.width / img.height
        altura = int(largura / ratio)
        img = img.resize((largura, altura))
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def carregar_css():
    """
    Carrega o arquivo CSS base para toda a aplicação
    
    Busca o arquivo de estilos principal e o aplica à interface.
    Em caso de erro, exibe uma mensagem apropriada.
    """
    try:
        with open("static/styles.css", encoding="utf-8") as f:
            css_content = f.read()
    except FileNotFoundError:
        st.error("Arquivo de estilos não encontrado. Verifique se o arquivo static/styles.css existe.")
        css_content = ""
    
    # Aplicamos todos os estilos de uma vez só
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

def carregar_css_pagina(nome_pagina):
    """
    Carrega o arquivo CSS específico para uma página
    
    Args:
        nome_pagina: Nome da página cujo CSS será carregado
    """
    try:
        with open(f"static/{nome_pagina}_page.css", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        logging.warning(f"Arquivo de estilos da página {nome_pagina} não encontrado.")

def inicializar_sessao():
    """
    Inicializa as variáveis de sessão necessárias para o funcionamento da aplicação
    
    Configura o estado inicial da aplicação, garantindo que todas as variáveis
    de sessão necessárias existam antes do uso.
    """
    if 'assistente' not in st.session_state:
        st.session_state.assistente = Assistente()  # Instancia o backend do assistente

    if 'mensagens' not in st.session_state:
        st.session_state.mensagens = []  # Histórico de mensagens da conversa

    if 'input_key' not in st.session_state:
        st.session_state.input_key = 0  # Chave para forçar reset do campo de entrada

    if 'aguardando_resposta' not in st.session_state:
        st.session_state.aguardando_resposta = False  # Flag para controle de estado do chat

    if 'mensagem_atual' not in st.session_state:
        st.session_state.mensagem_atual = ""  # Armazena a mensagem em processamento

    if 'resposta_parcial' not in st.session_state:
        st.session_state.resposta_parcial = ""  # Para streaming de respostas
        
    if 'pagina_atual' not in st.session_state:
        st.session_state.pagina_atual = "dashboard"  # Página padrão da aplicação
    
    if 'processar_faq' not in st.session_state:
        st.session_state.processar_faq = False  # Flag para processamento de FAQ
        
    if 'mensagem_faq_selecionada' not in st.session_state:
        st.session_state.mensagem_faq_selecionada = None  # Mensagem FAQ selecionada
        
    if 'faq_processado' not in st.session_state:
        st.session_state.faq_processado = False  # Controle de estado do processamento de FAQ

def processar_mensagem(mensagem):
    """
    Envia a pergunta do usuário e atualiza o estado.
    
    Args:
        mensagem: Texto da mensagem enviada pelo usuário
    """
    if mensagem.strip():
        # Incrementa para resetar o text_input
        st.session_state.input_key += 1
        st.session_state.mensagem_atual = mensagem
        
        # Adiciona pergunta ao histórico
        st.session_state.mensagens.append({"role": "user", "content": mensagem})
        st.session_state.aguardando_resposta = True
        
        # Força atualização para mostrar a pergunta no chat
        st.rerun()

def processar_resposta():
    """
    Recebe a resposta em streaming e atualiza o histórico usando o componente de chat.
    
    Processa a resposta do assistente em tempo real, exibindo-a gradualmente
    enquanto é gerada para melhorar a experiência do usuário.
    """
    try:
        # Cria um placeholder com o componente de chat para a resposta do assistente
        with st.chat_message("assistant", avatar="🤖"):
            placeholder = st.empty()
            resposta_completa = ""
            
            # Inicia o streaming - recebe chunks da resposta e atualiza progressivamente
            for chunk in st.session_state.assistente.processar_mensagem_stream(
                    st.session_state.mensagem_atual):
                resposta_completa += chunk
                # Atualiza a mensagem em tempo real
                placeholder.markdown(resposta_completa)
        
        # Adiciona a resposta completa ao histórico
        st.session_state.mensagens.append(
            {"role": "assistant", "content": resposta_completa}
        )
        
        st.session_state.aguardando_resposta = False
        st.session_state.mensagem_atual = ""
        
    except Exception as e:
        st.error(f"Erro ao processar resposta: {str(e)}")
        st.session_state.aguardando_resposta = False

def limpar_chat():
    """
    Limpa o histórico de mensagens e cria uma nova conversa
    
    Reinicia a conversa atual, apagando todas as mensagens e criando
    uma nova thread no backend.
    """
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
        logging.error(f"Erro ao limpar chat: {e}")
        st.error("Ocorreu um erro ao limpar o histórico.")

def exibir_mensagens():
    """
    Exibe as mensagens salvas no histórico usando o componente nativo de chat.
    
    Renderiza o histórico completo da conversa na interface, diferenciando
    visualmente as mensagens do usuário e do assistente.
    """
    # Exibe mensagens usando o componente nativo de chat
    for msg in st.session_state.mensagens:
        if msg['role'] == 'user':
            with st.chat_message("user", avatar="💬"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(msg["content"])
    
    # Mostra indicador de digitação quando o assistente está "pensando"
    if st.session_state.aguardando_resposta:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("*Assistente está digitando...*")

def renderizar_interface():
    """
    Renderiza a interface principal do aplicativo usando componentes do Streamlit
    
    Cria a estrutura da interface, incluindo cabeçalho, área de chat,
    botões de controle e campo de entrada de mensagens.
    
    Returns:
        tuple: (mensagem, enviar) - mensagem digitada e flag de envio
    """
    # Adiciona o logo
    try:
        # Carrega a logo (as classes CSS serão definidas nos arquivos de estilo)
        logo_base64 = obter_imagem_base64('assets/logo2.png', 200)
        st.markdown(f"""
        <div class="header-container">
            <img src="data:image/png;base64,{logo_base64}" class="logo-image"/>
            <span class="logo-text">Wonder_Assistent</span>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao carregar a logo: {str(e)}")
    
    # Área principal do chat
    chat_container = st.container()
    with chat_container:
        # Exibe histórico de mensagens
        exibir_mensagens()
    
    # Botão de limpar chat - configuração em colunas para melhor layout
    col1, col2 = st.columns([4, 1])
    with col2:
        # Usando o botão nativo do Streamlit
        st.button(
            "Limpar Chat", 
            on_click=limpar_chat,
            key="limpar_chat_btn",
            disabled=st.session_state.aguardando_resposta,
            use_container_width=True
        )
    
    # Área de input para novas mensagens
    mensagem = st.chat_input(
        "Digite sua mensagem...",
        key=f"chat_input_{st.session_state.input_key}",
        disabled=st.session_state.aguardando_resposta
    )
    
    # Simulamos o comportamento de "enviar" quando o usuário digita algo no input
    enviar = mensagem is not None
    
    return mensagem, enviar