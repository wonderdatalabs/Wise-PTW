import streamlit as st
import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import random

# Configuração de logging
logger = logging.getLogger(__name__)

def gerar_dados_fake():
    """
    Gera dados fictícios para demonstração do dashboard
    """
    # Dados para métricas principais
    metricas = {
        "total_documentos": 1342,
        "documentos_processados_hoje": 27,
        "tempo_resposta_medio": "2.3s",
        "taxa_precisao": "94.8%"
    }
    
    # Dados para gráfico de linha - documentos processados por dia
    dias = 14
    datas = [(datetime.now() - timedelta(days=i)).strftime('%d/%m') for i in range(dias)]
    datas.reverse()  # Invertendo para ordem cronológica correta
    
    # Valores simulando tendência crescente com alguma variação
    base_valores = [60, 58, 67, 75, 72, 80, 85, 79, 90, 89, 95, 102, 108, 112]
    valores = base_valores.copy()
    
    df_linha = pd.DataFrame({
        'Data': datas,
        'Documentos': valores
    })
    
    # Dados para gráfico de pizza - distribuição por departamento
    departamentos = ['TI', 'RH', 'Financeiro', 'Marketing', 'Operações']
    valores_depto = [35, 15, 25, 10, 15]  # Percentuais
    
    df_pizza = pd.DataFrame({
        'Departamento': departamentos,
        'Percentual': valores_depto
    })
    
    # Dados para gráfico de barras - tipos de documentos
    tipos_docs = ['PDFs', 'Word', 'Excel', 'Apresentações', 'Textos', 'Outros']
    qtd_por_tipo = [480, 320, 280, 150, 92, 20]
    
    df_barras = pd.DataFrame({
        'Tipo': tipos_docs,
        'Quantidade': qtd_por_tipo
    })
    
    # Dados para gráfico de área - uso de tokens ao longo do tempo
    tokens_embedding = [random.randint(3500, 4800) for _ in range(dias)]
    tokens_completions = [random.randint(7500, 9800) for _ in range(dias)]
    
    df_tokens = pd.DataFrame({
        'Data': datas,
        'Embeddings': tokens_embedding,
        'Completions': tokens_completions
    })
    
    # Dados para tabela de atividades recentes
    atividades = [
        {"usuario": "Maria Silva", "documento": "Política de Segurança v2.3", "acao": "Upload", "horario": "Hoje, 14:35"},
        {"usuario": "João Oliveira", "documento": "Relatório Q3", "acao": "Consulta", "horario": "Hoje, 13:22"},
        {"usuario": "Ana Costa", "documento": "Manual do Usuário", "acao": "Download", "horario": "Hoje, 11:47"},
        {"usuario": "Pedro Santos", "documento": "Processo de Vendas 2023", "acao": "Consulta", "horario": "Hoje, 10:15"},
        {"usuario": "Carla Mendes", "documento": "Análise de Mercado", "acao": "Upload", "horario": "Ontem, 16:40"}
    ]
    
    return {
        "metricas": metricas,
        "df_linha": df_linha,
        "df_pizza": df_pizza,
        "df_barras": df_barras,
        "df_tokens": df_tokens,
        "atividades": atividades
    }

def renderizar_metricas(metricas):
    """Renderiza os cards de métricas principais"""
    st.markdown("<div class='dashboard-metricas-container'>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class='dashboard-metrica-card'>
            <div class='dashboard-metrica-titulo'>Total de Documentos</div>
            <div class='dashboard-metrica-valor'>{metricas['total_documentos']}</div>
            <div class='dashboard-metrica-desc'>Total na base</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class='dashboard-metrica-card'>
            <div class='dashboard-metrica-titulo'>Docs Processados</div>
            <div class='dashboard-metrica-valor'>{metricas['documentos_processados_hoje']}</div>
            <div class='dashboard-metrica-desc'>Hoje</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class='dashboard-metrica-card'>
            <div class='dashboard-metrica-titulo'>Tempo de Resposta</div>
            <div class='dashboard-metrica-valor'>{metricas['tempo_resposta_medio']}</div>
            <div class='dashboard-metrica-desc'>Médio</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class='dashboard-metrica-card'>
            <div class='dashboard-metrica-titulo'>Taxa de Precisão</div>
            <div class='dashboard-metrica-valor'>{metricas['taxa_precisao']}</div>
            <div class='dashboard-metrica-desc'>Respostas corretas</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

def renderizar_pagina_dashboard():
    """
    Renderiza a página de dashboard com métricas e gráficos
    """
    # Carrega CSS específico desta página
    from src.ui import carregar_css_pagina
    carregar_css_pagina("dash_page")
    
    # Renderiza título usando o estilo consistente
    st.markdown("<h1 class='dashboard-titulo'>DASHBOARD</h1>", unsafe_allow_html=True)
    st.markdown("<div class='dashboard-divider'></div>", unsafe_allow_html=True)
    
    try:
        # Carrega CSS específico desta página
        from src.ui import carregar_css_pagina
        carregar_css_pagina("dash")  # Usa o dash_page.css
                
        # Gerar dados fictícios para demonstração
        dados = gerar_dados_fake()
        
        # Renderiza os cards de métricas principais
        renderizar_metricas(dados["metricas"])
        
        # Espaçamento
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        
        # Primeira linha de gráficos - Linha e Pizza
        st.markdown("<div class='dashboard-graficos-container'>", unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("<div class='dashboard-grafico-card'>", unsafe_allow_html=True)
            st.subheader("Documentos Processados nos Últimos 14 Dias")
            
            # Gráfico de linha
            fig_linha = px.line(
                dados["df_linha"], 
                x='Data', 
                y='Documentos', 
                markers=True,
                line_shape='spline',
                template='plotly_white'
            )
            fig_linha.update_traces(
                line=dict(width=3, color='#005ef2'), 
                marker=dict(size=8, color='#05113B')
            )
            fig_linha.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis_title=None,
                xaxis_title=None,
                height=300,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            st.plotly_chart(fig_linha, use_container_width=True, config={'displayModeBar': False})
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("<div class='dashboard-grafico-card'>", unsafe_allow_html=True)
            st.subheader("Distribuição por Departamento")
            
            # Gráfico de pizza
            cores = ['#005ef2', '#0076f6', '#0090fa', '#00a7fd', '#00c2ff']
            fig_pizza = px.pie(
                dados["df_pizza"], 
                values='Percentual', 
                names='Departamento',
                hole=0.4,
                color_discrete_sequence=cores
            )
            fig_pizza.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hoverinfo='label+percent'
            )
            fig_pizza.update_layout(
                showlegend=False,
                height=300,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            st.plotly_chart(fig_pizza, use_container_width=True, config={'displayModeBar': False})
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Espaçamento
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        
        # Segunda linha de gráficos - Barras e Área
        st.markdown("<div class='dashboard-graficos-container'>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("<div class='dashboard-grafico-card'>", unsafe_allow_html=True)
            st.subheader("Tipos de Documentos")
            
            # Gráfico de barras
            fig_barras = px.bar(
                dados["df_barras"],
                x='Tipo',
                y='Quantidade',
                color_discrete_sequence=['#005ef2']
            )
            fig_barras.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis_title=None,
                xaxis_title=None,
                height=300,
                margin=dict(l=20, r=20, t=20, b=20)
            )
            st.plotly_chart(fig_barras, use_container_width=True, config={'displayModeBar': False})
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("<div class='dashboard-grafico-card'>", unsafe_allow_html=True)
            st.subheader("Consumo de Tokens (últimos 14 dias)")
            
            # Gráfico de área
            fig_area = go.Figure()
            
            fig_area.add_trace(
                go.Scatter(
                    x=dados["df_tokens"]['Data'],
                    y=dados["df_tokens"]['Completions'],
                    name='Completions',
                    line=dict(width=0.5, color='#005ef2'),
                    fill='tonexty',
                    fillcolor='rgba(0, 94, 242, 0.2)'
                )
            )
            
            fig_area.add_trace(
                go.Scatter(
                    x=dados["df_tokens"]['Data'],
                    y=dados["df_tokens"]['Embeddings'],
                    name='Embeddings',
                    line=dict(width=0.5, color='#05113B'),
                    fill='tozeroy',
                    fillcolor='rgba(5, 17, 59, 0.1)'
                )
            )
            
            fig_area.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis_title=None,
                xaxis_title=None,
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.15,
                    xanchor="center",
                    x=0.5
                )
            )
            st.plotly_chart(fig_area, use_container_width=True, config={'displayModeBar': False})
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Espaçamento
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        
        # Tabela de atividades recentes
        st.markdown("<div class='dashboard-tabela-container'>", unsafe_allow_html=True)
        st.subheader("Atividades Recentes")
        
        atividades = dados["atividades"]
        
        st.markdown("<div class='dashboard-tabela'>", unsafe_allow_html=True)
        st.markdown("<table>", unsafe_allow_html=True)
        
        # Cabeçalho da tabela
        st.markdown("""
        <thead>
            <tr>
                <th>Usuário</th>
                <th>Documento</th>
                <th>Ação</th>
                <th>Horário</th>
            </tr>
        </thead>
        """, unsafe_allow_html=True)
        
        # Corpo da tabela
        st.markdown("<tbody>", unsafe_allow_html=True)
        for atividade in atividades:
            acao_classe = ""
            if atividade["acao"] == "Upload":
                acao_classe = "dashboard-upload"
            elif atividade["acao"] == "Download":
                acao_classe = "dashboard-download"
            else:
                acao_classe = "dashboard-consulta"
                
            st.markdown(f"""
            <tr>
                <td>{atividade['usuario']}</td>
                <td>{atividade['documento']}</td>
                <td><span class="{acao_classe}">{atividade['acao']}</span></td>
                <td>{atividade['horario']}</td>
            </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody>", unsafe_allow_html=True)
        st.markdown("</table>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    except Exception as e:
        logger.error(f"Erro ao renderizar página Dashboard: {str(e)}")
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue a aplicação.")
