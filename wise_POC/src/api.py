"""
Este módulo implementa um assistente baseado no modelo Claude da Anthropic com sistema RAG,
conectando-se ao Qdrant como banco de dados vetorial para recuperação de documentos.

Funcionalidades principais:
- Comunicação com a API do Claude 3.7 Sonnet
- Recuperação de documentos relevantes via Qdrant (quando configurado)
- Processamento de respostas em streaming
- Gerenciamento de histórico de conversas
- Tratamento de erros e logging completo
"""
import os
import time
from anthropic import Anthropic
import logging
from src.vector_store import VectorStore

# Configuração de logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Assistente:
    """Cliente para comunicação com o Anthropic Claude API com RAG via Qdrant"""
    
    def __init__(self):
        """Inicializa o cliente Anthropic e prepara a conversa"""
        # Tenta obter a API key de várias formas
        api_key = os.getenv('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
        
        if not api_key:
            logging.error("ANTHROPIC_API_KEY não encontrada no arquivo .env ou variáveis de ambiente")
            raise ValueError("ANTHROPIC_API_KEY não encontrada no arquivo .env. Verifique se o arquivo existe e contém a chave correta.")
        
        # Cria o cliente com API key
        try:
            self.client = Anthropic(
                api_key=api_key,
            )
            logging.info("Cliente Anthropic inicializado com sucesso")
        except Exception as e:
            logging.error(f"Erro ao inicializar cliente Anthropic: {str(e)}")
            raise ValueError(f"Erro ao inicializar cliente Anthropic. Verifique se a API key está correta: {str(e)}")
        
        # Usar exclusivamente o modelo Claude 3.7 Sonnet
        self.model = 'claude-3-7-sonnet-20250219'
        logging.info(f"Inicializando com o modelo: {self.model}")
        
        # Inicializa o cliente do banco de dados vetorial
        self.vector_store = None
        try:
            # Verifica se as variáveis do Qdrant estão configuradas
            qdrant_url = os.getenv('QDRANT_URL')
            if qdrant_url and qdrant_url != "https://seu-qdrant-url.com":
                self.vector_store = VectorStore()
                logging.info("Banco de dados vetorial inicializado com sucesso")
            else:
                logging.warning("QDRANT_URL não configurada ou com valor padrão. Funcionando sem RAG.")
        except Exception as e:
            logging.error(f"Erro ao inicializar banco de dados vetorial: {str(e)}")
            logging.info("Continuando sem RAG devido ao erro de inicialização")
        
        # Inicializa outros parâmetros
        self.max_tokens = 20000  # Limite máximo de tokens para a resposta do modelo
        self.messages = []      # Lista para armazenar o histórico de mensagens

    def processar_mensagem_stream(self, pergunta):
        """
        Processa a mensagem usando RAG e retorna a resposta via streaming
        
        Este método realiza as seguintes operações:
        1. Adiciona a pergunta ao histórico de conversas
        2. Consulta o banco de dados vetorial (Qdrant) para encontrar documentos relevantes
        3. Envia a consulta para o modelo Claude com contexto recuperado
        4. Retorna a resposta em formato de streaming
        
        Args:
            pergunta: A pergunta do usuário (string)
            
        Returns:
            Generator que produz chunks de texto da resposta via streaming
        """
        try:
            # Adiciona a pergunta do usuário ao histórico
            self.messages.append({"role": "user", "content": pergunta})
            
            # Cria uma versão do histórico limitada apenas às mensagens mais recentes
            mensagens_limitadas = self._limitar_historico()
            
            # Consulta o Qdrant para obter contexto relevante
            contexto = "Não foi possível encontrar informações relevantes na documentação."
            rag_ativo = False
            
            if self.vector_store:
                try:
                    logging.info(f"Consultando banco de dados vetorial para: {pergunta}")
                    resultados = self.vector_store.query(pergunta)
                    if resultados:
                        # Formata os resultados recuperados em um texto estruturado para contexto
                        contexto = self.vector_store.format_context(resultados)
                        rag_ativo = True
                    logging.info(f"Recuperados {len(resultados)} documentos relevantes")
                except Exception as e:
                    logging.error(f"Erro ao consultar banco de dados vetorial: {str(e)}")
                    logging.info("Continuando sem RAG devido ao erro de conexão com Qdrant")
            
            logging.info(f"Enviando mensagem para o modelo: {self.model}")
            
            # Configura a mensagem para o Claude com o histórico limitado e contexto do Qdrant
            try:
                
                # Prompt personalizado do Wise incluindo contexto recuperado se disponível
                base_prompt = "Você é o Wise, especialista em todos os processos da Wonder DataLabs. Sua função é fornecer suporte preciso e abrangente aos colaboradores, baseando-se exclusivamente na documentação oficial da empresa."
                
                # Seção comum de competências e diretrizes
                competencias_diretrizes = """
COMPETÊNCIAS PRINCIPAIS:
- Domínio completo dos processos, políticas e documentação da Wonder DataLabs
- Fluência em português brasileiro e inglês (responde no idioma da pergunta)
- Especialização em explicações técnicas detalhadas
- Capacidade de estruturar respostas de forma clara e objetiva
- Expertise avançada em desenvolvimento de software, incluindo:
    a) Linguagens: Python, JavaScript, HTML, CSS
    b) Frameworks: React
    c) Boas práticas de programação
    d) Debugging e resolução de problemas
    e) Otimização de código
    f) Arquitetura de software

DIRETRIZES DE RESPOSTA:
1. Base de Conhecimento
- Utilize APENAS informações contidas no CONTEXTO acima
- NÃO invente ou presuma informações que não estão explicitamente no contexto

2. Estrutura Obrigatória das Respostas, sempre que possível:
a) Resumo do contexto
b) Pré-requisitos necessários
c) Procedimento passo a passo numerado
d) Alertas e pontos de atenção
e) Mencionar a documentação relacionada
f) Exemplos práticos relevantes
g) Próximos passos sugeridos
h) Verificação de dúvidas remanescentes

3. Protocolo de Interação:
- Mantenha tom profissional e acolhedor
- Solicite esclarecimentos quando necessário
- Indique claramente quando um assunto requer escalação
- Especifique níveis de aprovação necessários
- Identifique equipes responsáveis quando relevante

4. Validação de Compreensão:
- Confirme entendimento da pergunta
- Verifique se o contexto está claro
- Solicite informações adicionais se necessário
- Pergunte sobre dúvidas específicas ao final

OBJETIVO FINAL:
Garantir que cada colaborador da Wonder DataLabs receba orientação precisa e eficiente para executar suas tarefas, mantendo os padrões de qualidade e conformidade da empresa."""
                
                if rag_ativo:
                    # Versão com RAG - inclui o contexto recuperado do banco de dados
                    system_prompt = f"""{base_prompt}

Use o contexto a seguir para responder à pergunta do usuário:

{contexto}

Se a informação necessária não estiver no contexto fornecido, responda: "Esta informação não consta na documentação atual. Assim que for atualizada, poderei responder adequadamente."

{competencias_diretrizes}
"""
                else:
                    # Versão sem RAG (quando o Qdrant não está disponível)
                    system_prompt = f"""{base_prompt}

IMPORTANTE: Estou funcionando no modo de conhecimento geral, pois o banco de dados da documentação não está acessível no momento.

{competencias_diretrizes}
"""
                
                # Inicia a conexão em streaming com a API do Claude
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=mensagens_limitadas,
                    temperature=0.7,  # Controla a criatividade/determinismo da resposta
                    system=system_prompt,
                ) as stream:
                    resposta_completa = ""
                    
                    # Processa cada parte da resposta em stream
                    for chunk in stream:
                        if chunk.type == "content_block_delta":
                            if chunk.delta.type == "text_delta":
                                text_chunk = chunk.delta.text
                                resposta_completa += text_chunk
                                yield text_chunk  # Envia cada pedaço de texto para o cliente
                    
                    # Adiciona a resposta completa ao histórico de conversa
                    self.messages.append({"role": "assistant", "content": resposta_completa})
                    logging.info(f"Resposta completa recebida do modelo: {self.model}")
            
            except Exception as model_error:
                error_detail = str(model_error)
                logging.error(f"Erro ao usar o modelo {self.model}: {error_detail}")
                
                # Apenas repassa o erro para o usuário
                yield f"Não foi possível processar sua solicitação neste momento. Por favor, tente novamente em instantes."
                raise
                
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Erro ao processar mensagem: {error_msg}")
            yield f"Ocorreu um erro ao processar sua mensagem: {error_msg}"
    
    def _limitar_historico(self, max_mensagens=20):
        """
        Limita o número de mensagens no histórico para garantir que não excedemos os limites da API
        
        Esta função evita que o contexto fique grande demais e exceda limites de tokens da API,
        mantendo apenas as mensagens mais recentes.
        
        Args:
            max_mensagens: Número máximo de mensagens a manter (padrão: 20 pares)
            
        Returns:
            Lista limitada de mensagens para enviar ao modelo
        """
        # Garante que não temos mais que max_mensagens pares de conversas
        if len(self.messages) > max_mensagens * 2:
            # Mantém a primeira mensagem (sistema) se existir e as mensagens mais recentes
            self.messages = self.messages[-(max_mensagens * 2):]
            
        return self.messages

    def limpar_conversa(self):
        """
        Limpa o histórico de mensagens
        
        Utilizado para iniciar uma nova conversa sem contexto anterior.
        
        Returns:
            Boolean indicando sucesso da operação
        """
        try:
            self.messages = []
            logging.info("Nova conversa iniciada - histórico limpo com sucesso")
            return True
        except Exception as e:
            logging.error(f"Erro ao limpar conversa: {str(e)}")
            return False