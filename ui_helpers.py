"""
UI Helper Functions for PTW Analyzer

This module contains functions for UI components and styling.
"""
import streamlit as st
import base64
from PIL import Image
from io import BytesIO

def get_image_base64(image_path, width=None):
    """
    Convert an image to base64 for embedding in HTML
    
    Args:
        image_path: Path to the image file to convert
        width: Optional width to resize the image
        
    Returns:
        String base64 of the image for use in HTML tags
    """
    try:
        img = Image.open(image_path)
        
        # Resize image if width is specified
        if width:
            ratio = img.width / img.height
            height = int(width / ratio)
            img = img.resize((width, height))
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        st.error(f"Error loading image {image_path}: {str(e)}")
        return ""

def load_css(css_file=None):
    """
    Load CSS files to style the application
    
    Args:
        css_file: Optional specific CSS file to load
    """
    try:
        # Always load the base styles.css file
        with open("static/styles.css", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
        
        # If a specific CSS file is requested, load it too
        if css_file:
            with open(f"static/{css_file}.css", encoding="utf-8") as f:
                css_content = f.read()
                st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError as e:
        st.warning(f"CSS file not found: {str(e)}")

def init_session_state():
    """Initialize session state variables for the application"""
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "analyzer"
    
    if 'page_images' not in st.session_state:
        st.session_state.page_images = []
    
    if 'ptw_summary' not in st.session_state:
        st.session_state.ptw_summary = None
    
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = []
    
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    
    if 'parallel_processing' not in st.session_state:
        st.session_state.parallel_processing = False
    
    if 'analyses_completed' not in st.session_state:
        st.session_state.analyses_completed = 0
    
    if 'total_pages' not in st.session_state:
        st.session_state.total_pages = 0
    
    if 'current_page_view' not in st.session_state:
        st.session_state.current_page_view = 0
    
    if 'parallel_results' not in st.session_state:
        st.session_state.parallel_results = []
    
    if 'parallel_status' not in st.session_state:
        st.session_state.parallel_status = {}
        
    # Photo capture mode related session state variables
    if 'capture_mode' not in st.session_state:
        st.session_state.capture_mode = False
        
    if 'captured_photos' not in st.session_state:
        st.session_state.captured_photos = []
        
    if 'photo_captions' not in st.session_state:
        st.session_state.photo_captions = []
        
    if 'clear_uploads' not in st.session_state:
        st.session_state.clear_uploads = False
        
    # Status filter selection
    if 'status_filter' not in st.session_state:
        st.session_state.status_filter = ["APROVADO", "REPROVADO", "CHECAGEM HUMANA NECESSARIA", "N/A"]

def render_sidebar():
    """Render the navigation sidebar with menu options"""
    # Logo at the top of sidebar
    logo_base64 = get_image_base64('assets/logo2.png', 80)
    st.sidebar.markdown(f"""
    <div class="sidebar-header">
        <img src="data:image/png;base64,{logo_base64}" class="sidebar-logo sidebar-logo-sm"/>
        <div class="sidebar-title">PTW Analyzer</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Menu navigation
    st.sidebar.markdown('<div class="sidebar-menu">', unsafe_allow_html=True)
    
    # Get current page from session state
    current_page = st.session_state.get('current_page', 'analyzer')
    
    # Helper function to create menu buttons with active state
    def create_menu_button(text, key, page_name):
        """Create a menu button with active state handling"""
        is_active = current_page == page_name
        if st.sidebar.button(text, key=f"menu_{key}", use_container_width=True):
            st.session_state.current_page = page_name
            # Reset relevant session states when changing pages
            if page_name == "analyzer":
                st.session_state.processing = False
            st.rerun()
        
        # Add active-page class with JavaScript if this is the current page
        if is_active:
            st.sidebar.markdown(f"""
            <script>
            document.querySelector('[data-testid="stSidebar"] [key="menu_{key}"]').classList.add('active-page');
            </script>
            """, unsafe_allow_html=True)
    
    # Menu navigation with buttons
    menu_options = [
        {"text": "📋 PTW Analyzer", "key": "analyzer", "page": "analyzer"},
        {"text": "📊 Dashboard", "key": "dashboard", "page": "dashboard"},
        {"text": "⚙️ Settings", "key": "settings", "page": "settings"},
        {"text": "❓ Help", "key": "help", "page": "help"}
    ]
    
    # Create the buttons for each menu option
    for option in menu_options:
        create_menu_button(
            text=option["text"],
            key=option["key"],
            page_name=option["page"]
        )
    
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # Add Constellation logo in the middle (50% larger)
    constellation_logo = get_image_base64('assets/LogoBranco.png', 225)
    st.sidebar.markdown(f"""
    <div style="text-align: center; margin: 30px 0; position: relative; z-index: 2;">
        <img src="data:image/png;base64,{constellation_logo}" 
             style="max-width: 270px; 
                    filter: drop-shadow(0 0 5px rgba(0, 94, 242, 0.3));
                    transition: all 0.3s ease;
                    transform: perspective(500px) rotateX(5deg);
                    animation: float 6s ease-in-out infinite;"
        />
    </div>
    """, unsafe_allow_html=True)
    
    # Footer with logo
    logo4_base64 = get_image_base64('assets/logo3.png', 180)
    st.sidebar.markdown(f"""
    <div class="sidebar-footer">
        <img src="data:image/png;base64,{logo4_base64}" class="sidebar-logo sidebar-logo-lg"/>
    </div>
    """, unsafe_allow_html=True)
    
    # Add decorative elements for the sidebar
    st.sidebar.markdown("""
    <!-- Wave decoration -->
    <div class="wave-container">
        <div class="wave"></div>
        <div class="wave"></div>
        <div class="wave"></div>
    </div>
    
    <!-- Energy decoration -->
    <div class="energy-lines">
        <div class="energy-line"></div>
        <div class="energy-line"></div>
        <div class="energy-line"></div>
        <div class="energy-line"></div>
        <div class="energy-orb"></div>
        <div class="energy-orb"></div>
        <div class="energy-orb"></div>
    </div>
    """, unsafe_allow_html=True)

def render_welcome_message():
    """Render the welcome message for the PTW Analyzer"""
    st.markdown("""
    <div class="wonder-chat-welcome">
        <div class="wonder-chat-welcome-icon">📋</div>
        <h1 class="wonder-chat-welcome-title">PTW Analyzer</h1>
        <div class="wonder-chat-welcome-divider"></div>
        <p class="wonder-chat-welcome-message">
            Bem-vindo ao Analisador de PT! Esta ferramenta analisa documentos de Permissão de Trabalho 
            para identificar não conformidades e problemas de segurança em sua documentação.
            Faça upload de um arquivo PDF de PT para começar a análise.
        </p>              
    </div>
    """, unsafe_allow_html=True)