# WonderIA - Assistente Inteligente da Wonder DataLabs

![WonderIA Logo](assets/logo3.png)

## 📋 Visão Geral

WonderIA é um assistente virtual corporativo avançado desenvolvido especificamente para a Wonder DataLabs. Construído com base no modelo Claude 3.7 Sonnet da Anthropic, ele fornece suporte preciso e contextualizado aos colaboradores da empresa, consultando a documentação oficial para fornecer respostas detalhadas sobre processos internos, políticas e procedimentos.

## 🔍 Características Principais

- **Consulta de Base de Conhecimento:** Acessa a documentação corporativa em tempo real através de tecnologia RAG (Retrieval-Augmented Generation)
- **Interface Conversacional Intuitiva:** Design elegante e responsivo com streaming de respostas em tempo real
- **Respostas Estruturadas:** Apresenta informações em formato padronizado com contexto, pré-requisitos, procedimentos e pontos de atenção
- **Multilingue:** Responde em português ou inglês conforme o idioma da pergunta
- **Expertise Técnica:** Especializado em desenvolvimento de software, incluindo Python, JavaScript, React e boas práticas de programação

## 🏗️ Arquitetura

O WonderIA utiliza uma arquitetura moderna que combina:

- **Modelo LLM:** Claude 3.7 Sonnet para processamento de linguagem natural avançado
- **Sistema RAG:** Integração com Qdrant para busca vetorial de alta performance
- **Frontend Interativo:** Interface web construída com Streamlit para fácil uso corporativo
- **Backend Escalável:** API Python robusta para processamento de consultas e contextos

## 🔌 Componentes do Sistema

```
WonderIA/
├── app.py                # Aplicação principal e ponto de entrada
├── src/
│   ├── api.py            # Cliente Anthropic e lógica RAG
│   ├── ui.py             # Componentes de interface e renderização
│   ├── utils.py          # Utilitários e funções auxiliares
│   └── vector_store.py   # Interface com banco de dados vetorial Qdrant
├── static/
│   └── styles.css        # Estilos e temas corporativos
├── assets/
│   └── logo.png          # Recursos visuais
└── requirements.txt      # Dependências do projeto
```

## 🚀 Instalação e Configuração

### Pré-requisitos

- Python 3.8+
- Acesso à API da Anthropic (Claude 3.7 Sonnet)
- Instância Qdrant configurada com a base de conhecimento corporativa
- Conexão de rede aos serviços da Anthropic e Qdrant

### Configuração do Ambiente

1. **Clone o repositório e configure o ambiente virtual:**

```bash
git clone <url-do-repositorio>
cd WonderIA
python -m venv venv

# Ativação no Windows
.\venv\Scripts\Activate.ps1

# Ativação no Linux/Mac
source venv/bin/activate
```

2. **Instale as dependências:**

```bash
pip install -r requirements.txt
```

3. **Configure as variáveis de ambiente:**

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```
# Credenciais da API Anthropic
ANTHROPIC_API_KEY=

# Configurações do Qdrant
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=

# LlamaCloud
LLAMA_API_KEY=

# Credenciais do user NR13 da AWS
AWS_ACESS_KEY=
AWS_SECRET_KEY=
AWS_BUCKET_NAME=

# Credenciais do Mistral
MISTRAL_API_KEY=
```

### Execução

Inicie o assistente com:

```bash
streamlit run app.py
```

O aplicativo estará disponível em `http://localhost:8501` por padrão.

## ⚙️ Tecnologias Utilizadas

- **Anthropic Claude 3.7:** Modelo de linguagem avançado com contexto de 200k tokens
- **Streamlit:** Framework para construção de interfaces web com Python
- **Qdrant:** Banco de dados vetorial para busca semântica de alta performance
- **Sentence Transformers:** Geração de embeddings para processamento semântico
- **Python-dotenv:** Gerenciamento de configurações e variáveis de ambiente
- **Pillow:** Processamento de imagens para recursos visuais

## 🔧 Personalização e Ajustes

### Ajustes do Modelo

O WonderIA está configurado para usar o Claude 3.7 Sonnet, mas pode ser ajustado para outros modelos através do arquivo `src/api.py`, modificando o parâmetro `self.model`.

### Configuração RAG

O sistema RAG pode ser ajustado no arquivo `src/vector_store.py`:
- Altere o parâmetro `score_threshold` para modificar a sensibilidade da busca
- Ajuste o valor `limit` para controlar o número de documentos recuperados

### Histórico de Conversas

Por padrão, o sistema mantém um histórico das últimas 10 interações, que pode ser ajustado no método `_limitar_historico()` no arquivo `src/api.py`.

## 📚 Uso e Exemplos

### Testar a Conexão com o Banco de Dados

Para verificar se o sistema está corretamente conectado ao banco de dados Qdrant:

1. No Windows, execute o arquivo `testar_qdrant.bat`
2. Em sistemas Linux/Mac, use o comando:
   ```bash
   source venv/bin/activate && python test_qdrant_simple.py
   ```

O teste mostrará:
- Documentos disponíveis na base de conhecimento
- Estrutura dos dados armazenados
- Confirmação de que a conexão está funcionando

### Exemplo de Consulta

O WonderIA pode responder a perguntas como:

- "Quais são os requisitos da NR-13 para caldeiras?"
- "Qual o procedimento de inspeção para vasos de pressão?"
- "O que são válvulas de segurança e como inspecioná-las?"
- "Quais são os componentes mais críticos em caldeiras industriais?"

### Resposta Estruturada

As respostas seguem um formato padronizado:

1. Resumo do contexto técnico
2. Requisitos normativos aplicáveis
3. Procedimentos de inspeção recomendados
4. Critérios de aceitação e rejeição
5. Alertas e pontos de atenção
6. Referências à documentação técnica

## 🔒 Segurança e Conformidade

- Todas as consultas são processadas através de conexões seguras
- Os dados não são armazenados permanentemente além do escopo da sessão
- O sistema adere às políticas de segurança e privacidade da Wonder DataLabs

## 📞 Suporte e Contato

Para suporte técnico ou questões relacionadas ao WonderIA, entre em contato com a equipe de TI da Wonder DataLabs.

## 📝 Licença

Este produto é propriedade da Wonder DataLabs. Todos os direitos reservados.

---

© 2025 Wonder DataLabs - Desenvolvido pelo time de Tecnologia e Inovação