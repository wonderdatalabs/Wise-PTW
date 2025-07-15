# Portuguese Language Support in PTW Analyzer

The PTW Analyzer application has been configured to support Permit to Work (PTW) documents in Portuguese. This is particularly important for analyzing PTWs used in Brazilian offshore operations, which are commonly written in Portuguese.

## How Portuguese Support Works

The application incorporates Portuguese language support through several mechanisms:

### 1. LlamaParse Configuration

The LlamaParse client is configured with:
- `language="pt"` - Sets Portuguese as the default language
- A custom prompt with common Portuguese terms and their translations
- Region set to "us" to ensure proper API connectivity

### 2. Custom Prompts with Portuguese Terminology

Both the LlamaParse and Claude prompts include:
- Common Portuguese PTW terminology and translations
- Instructions to maintain Portuguese text while providing translations when needed
- Knowledge of Portuguese date formats (DD/MM/YYYY)
- Industry-specific terms in Portuguese

### 3. Multilingual AI Analysis

Claude is instructed to:
- Process content in both Portuguese and English
- Understand Portuguese safety terminology
- Analyze form completeness regardless of language
- Maintain consistent analysis across languages

### 4. Terminology Mapping

The application includes mapping for common Portuguese terms:

| Portuguese Term | English Translation |
|-----------------|---------------------|
| Permissão de Trabalho | Permit to Work |
| Assinatura | Signature |
| Autorização | Authorization |
| Trabalho a Quente | Hot Work |
| Espaço Confinado | Confined Space |
| Responsável | Responsible person |
| Data | Date |
| Hora | Time |
| Aprovado | Approved |
| Recusado | Rejected/Denied |

## Section Terminology

Each standard section is recognized in both English and Portuguese:

1. **Request Information**
   - PT: "Informações da Solicitação", "Número da PT", "Data", "Local", "Descrição"

2. **Job Classification**
   - PT: "Classificação do Trabalho", "Tipo de Trabalho", "Categoria de Serviço"

3. **Risk Assessment**
   - PT: "Avaliação de Risco", "Identificação de Perigos", "Medidas de Controle"

4. **Isolation Requirements**
   - PT: "Requisitos de Isolamento", "Isolamento de Energia", "Verificação"

5. **Testing Requirements**
   - PT: "Requisitos de Teste", "Teste Atmosférico", "Teste de Pressão"

6. **Authorization Hierarchy**
   - PT: "Hierarquia de Autorização", "Solicitante", "Preparador", "Revisor", "Aprovador"

7. **Execution Control**
   - PT: "Controle de Execução", "Transferências", "Extensões", "Conclusões"

8. **Closeout Process**
   - PT: "Processo de Encerramento", "Restauração do Local", "Verificação Final"

## Output Format

The application will:
1. Extract text in its original language (Portuguese)
2. Provide English translations in parentheses when needed for clarity
3. Maintain the same analysis structure regardless of language
4. Identify form field completeness and signature presence equally well in both languages

## Troubleshooting

If you encounter issues with Portuguese document processing:

1. Check that the LlamaParse API key has access to Portuguese language processing
2. Ensure the document is clearly scanned and text is legible
3. For handwritten Portuguese content, the analysis may include additional notes about potential uncertainties
4. Check that Claude has access to the latest version that supports strong multilingual capabilities