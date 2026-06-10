# 🏥 SINAN Agent

Agente de IA para análise inteligente da base **SINAN/SUS** usando linguagem natural.

Faça perguntas em português e receba:
- SQL gerado automaticamente
- Resultados interpretados
- Gráficos interativos
- Auditoria completa

**Stack:** Streamlit · AWS Bedrock (Claude) · LangGraph · ChromaDB (RAG) · PostgreSQL · Plotly

---

## Arquitetura do Agente (LangGraph)

```
Pergunta do usuário
        │
        ▼
 analyze_intent          ← classifica intenção, detecta tabelas
        │
        ▼
   query_rag             ← busca contexto no dicionário SINAN (ChromaDB)
        │
        ▼
  generate_sql           ← gera SQL com Claude via Bedrock
        │
        ▼
  validate_sql           ← bloqueia DELETE/UPDATE/DROP/etc
     │       │
   válido  inválido──────► generate_sql (retry, max 2x)
     │
     ▼
  execute_sql            ← executa no PostgreSQL (com timeout)
     │       │
    OK     erro──────────► fix_sql ──► execute_sql (retry, max 2x)
     │
     ▼
generate_chart           ← Plotly automático (bar/line/pie/heatmap)
        │
        ▼
generate_answer          ← interpreta resultados com Claude
        │
        ▼
    Resposta final
```

---

## Pré-requisitos

- Python 3.11+
- PostgreSQL com a base SUS_SINAN
- Credencial AWS Bedrock (API Key ou Access Key)

---

## Instalação Local

```bash
# 1. Clone o repositório
git clone <repo-url>
cd agente-sus

# 2. Crie e ative o ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
copy .env.example .env
# Edite o .env com suas credenciais

# 5. Inicie o app
streamlit run app.py
```

Acesse em: **http://localhost:8501**

---

## Instalação com Docker

```bash
# Copie e edite o .env
copy .env.example .env

# Suba os containers
docker-compose up -d

# Ver logs
docker-compose logs -f app
```

---

## Configuração do .env

| Variável | Descrição | Exemplo |
|---|---|---|
| `BEDROCK_API_KEY` | Chave única Bedrock *(recomendado)* | `bedrock-api-key-xxx` |
| `BEDROCK_ENDPOINT` | Endpoint Bedrock Runtime | `https://bedrock-runtime.us-east-1.amazonaws.com` |
| `BEDROCK_MODEL_ID` | ID do modelo | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `DB_HOST` | Host PostgreSQL | `localhost` |
| `DB_PORT` | Porta | `5432` |
| `DB_NAME` | Nome do banco | `SUS_SINAN` |
| `DB_USER` | Usuário | `postgres` |
| `DB_PASSWORD` | Senha | `****` |
| `MAX_SQL_ROWS` | Limite de linhas por consulta | `500` |
| `SQL_TIMEOUT` | Timeout em segundos | `30` |

---

## Tabelas Suportadas

| Tabela | Doença | Granularidade |
|---|---|---|
| `sus_sinan_dengue_anual` | Dengue | Anual |
| `sus_sinan_dengue_mensal` | Dengue | Mensal |
| `sus_sinan_dengue_antigo_anual` | Dengue (histórico) | Anual |
| `sus_sinan_dengue_antigo_mensal` | Dengue (histórico) | Mensal |
| `sus_sinan_botulismo_mensal` | Botulismo | Mensal |
| `sus_sinan_chagas_mensal` | Doença de Chagas | Mensal |

---

## Páginas

| Página | Descrição |
|---|---|
| 🏠 Home | Visão geral e acesso rápido |
| 💬 Chat | Chat com IA — pergunta → SQL → resposta + gráfico |
| 📖 Dicionário | Metadados completos das tabelas (busca + export) |
| 🔍 Exploração | Navegação direta nos dados com estatísticas |
| 📊 Monitoramento | Dashboard de consultas, tokens e custo |
| ⚙️ Configurações | Gerenciamento de credenciais e conexões |
| 🧠 Memória | Histórico semântico e preferências |

---

## Segurança SQL

As seguintes operações são **bloqueadas** pelo `sql_validator`:

`DELETE` · `UPDATE` · `DROP` · `ALTER` · `TRUNCATE` · `INSERT` · `CREATE` · `GRANT` · `REVOKE` · `EXEC`

Apenas consultas `SELECT` e `WITH` são permitidas.

---

## Modelos Disponíveis

| Label | Model ID |
|---|---|
| Claude 3.5 Sonnet *(padrão)* | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Claude 3 Opus | `anthropic.claude-3-opus-20240229-v1:0` |
| Claude 3 Haiku | `anthropic.claude-3-haiku-20240307-v1:0` |
| Amazon Nova Pro | `amazon.nova-pro-v1:0` |
| Amazon Nova Lite | `amazon.nova-lite-v1:0` |

Troque o modelo na página ⚙️ Configurações sem alterar código.
