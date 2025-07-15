import streamlit as st
from src.ui import carregar_css, inicializar_sessao, processar_mensagem, processar_resposta
from src.utils import carregar_variaveis_ambiente, obter_imagem_base64
from src.paginas.chat_page import renderizar_pagina_chat
from src.paginas.busca_page import renderizar_pagina_busca
from src.paginas.faq_page import renderizar_pagina_faq, processar_pergunta_faq
from src.paginas.config_page import renderizar_pagina_config
from src.paginas.dash_page import renderizar_pagina_dashboard  # Importando a página de dashboard

# Configuração da página
st.set_page_config(
    page_title="Wise-AI",
    page_icon="./assets/logo2.png",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Carrega o CSS externo (agora consolidado em um único arquivo)
carregar_css()

# Adiciona a imagem de fundo usando a variável CSS
try:
    # Obtém a imagem de fundo em formato base64
    background_image = obter_imagem_base64('assets/logo4.png')
    
    # Define apenas a URL da imagem de fundo como variável CSS
    st.markdown(f"""
    <style>
        :root {{
            --background-image-url: url("data:image/png;base64,{background_image}");
        }}
    </style>
    <div class="background-logo-container"></div>
    """, unsafe_allow_html=True)
except Exception as e:
    st.warning(f"Não foi possível carregar a imagem de fundo: {str(e)}")

# Inicializa variáveis de sessão
inicializar_sessao()

# Verifica variáveis de ambiente
if not carregar_variaveis_ambiente():
    st.error("Erro: Variáveis de ambiente necessárias não foram configuradas. Verifique o arquivo .env")
    st.stop()

# Renderiza o sidebar com menu de navegação
def renderizar_menu_sidebar():
    from src.ui import obter_imagem_base64
    
    # Logo superior e título no sidebar
    logo3_base64 = obter_imagem_base64('assets/logo2.png', 80)  # Tamanho reduzido de 80 para 60
    st.sidebar.markdown(f"""
    <div class="sidebar-header">
        <img src="data:image/png;base64,{logo3_base64}" class="sidebar-logo sidebar-logo-sm"/>
        <div class="sidebar-title">Wise.AI</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Menu de navegação
    st.sidebar.markdown('<div class="sidebar-menu" style="margin-bottom: 0px;">', unsafe_allow_html=True)
    
    # Verificar a página atual para adicionar a classe apropriada
    pagina_atual = st.session_state.get('pagina_atual', 'chat')
    
    # Menu com botões reais (sem JavaScript)
    def criar_botao_menu(texto, chave, pagina, reset_states=None):
        """Helper function to create menu buttons with active state handling
        reset_states: Optional dict of session states to reset when navigating to this page"""
        is_active = pagina_atual == pagina
        if st.sidebar.button(texto, key=f"menu_{chave}", use_container_width=True):
            st.session_state.pagina_atual = pagina
            
            # Reset any specified session states
            if reset_states:
                for state_key, state_value in reset_states.items():
                    if state_key in st.session_state:
                        st.session_state[state_key] = state_value
            
            st.rerun()
        
        # Add 'active-page' class with JavaScript if this is the current page
        if is_active:
            st.sidebar.markdown(f"""
            <script>
            document.querySelector('[data-testid="stSidebar"] [key="menu_{chave}"]').classList.add('active-page');
            </script>
            """, unsafe_allow_html=True)
    
    # Menu de navegação com botões
    opcoes_menu = [
        {"texto": "📈 Dashboard", "chave": "dashboard", "pagina": "dashboard", "reset_states": None},
        {"texto": "💬 Chat", "chave": "chat", "pagina": "chat", "reset_states": None},
        {"texto": "🔍 Busca Avançada", "chave": "busca", "pagina": "busca_avancada", "reset_states": None},
        {"texto": "❓ FAQ", "chave": "faq", "pagina": "faq", 
         "reset_states": {'faq_processado': False, 'processar_faq': False}},
        {"texto": "⚙️ Configurações", "chave": "config", "pagina": "configuracoes", "reset_states": None}
    ]
    
    # Criação dos botões do menu de forma iterativa
    for opcao in opcoes_menu:
        criar_botao_menu(
            texto=opcao["texto"], 
            chave=opcao["chave"], 
            pagina=opcao["pagina"], 
            reset_states=opcao["reset_states"]
        )
    
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # Renderização das logos no rodapé
    # Logo pequena (ícone intermediário)
    logo2_base64 = obter_imagem_base64('assets/logo.png', 40)
    st.sidebar.markdown(f"""
    <div style="display: flex; justify-content: center; margin-top: 3px; margin-bottom: 3px;">
        <img src="data:image/png;base64,{logo2_base64}" style="width: 40px; height: auto;"/>
    </div>
    """, unsafe_allow_html=True)
    
    # Logo principal no rodapé
    logo4_base64 = obter_imagem_base64('assets/logo3.png', 200)
    st.sidebar.markdown(f"""
    <div class="sidebar-footer" style="margin-top: 10px; padding-top: 20px;">
        <img src="data:image/png;base64,{logo4_base64}" class="sidebar-logo sidebar-logo-lg"/>
    </div>
    """, unsafe_allow_html=True)

# Renderizando menu no sidebar
renderizar_menu_sidebar()

# Verificar e processar perguntas do FAQ quando redirecionado
try:
    # Usa a função de processamento importada do faq_page.py
    processar_pergunta_faq()
except Exception as e:
    st.error(f"Erro ao processar pergunta do FAQ: {str(e)}")

# Renderiza a página atual com base no estado da sessão
if st.session_state.pagina_atual == "chat":
    # Exibe o footer azul apenas na página de chat
    st.markdown("""
    <!-- Background colorido do footer -->
    <div class="footer-background"></div>
    """, unsafe_allow_html=True)
    
    mensagem, enviar = renderizar_pagina_chat()
    # Lógica de processamento para o chat
    if enviar and mensagem:
        processar_mensagem(mensagem)
    if st.session_state.aguardando_resposta:
        processar_resposta()
        st.rerun()  # Recarrega a página para exibir a resposta processada

# Gerenciamento de navegação entre páginas baseado na variável de sessão 'pagina_atual'
elif st.session_state.pagina_atual == "busca_avancada":
    # Não exibe o footer azul na página de busca avançada por questão de design
    renderizar_pagina_busca()  # Chama a função que renderiza a interface de busca avançada

elif st.session_state.pagina_atual == "faq":
    # Não exibe o footer azul na página de FAQ por questão de design
    renderizar_pagina_faq()  # Chama a função que renderiza a página de perguntas frequentes

elif st.session_state.pagina_atual == "configuracoes":
    # Não exibe o footer azul na página de configurações por questão de design
    renderizar_pagina_config()  # Chama a função que renderiza a interface de configurações do sistema

elif st.session_state.pagina_atual == "dashboard":
    # Não exibe o footer azul na página de dashboard por questão de design
    renderizar_pagina_dashboard()  # Chama a função que renderiza a interface de dashboard
    
else:
    # Comportamento padrão: se a página não for reconhecida, redireciona para o chat
    # Isso funciona como um fallback de segurança para garantir que o usuário sempre veja uma interface válida
    st.session_state.pagina_atual = "chat"
    st.rerun()  # Recarrega a aplicação para aplicar a mudança para a página de chat