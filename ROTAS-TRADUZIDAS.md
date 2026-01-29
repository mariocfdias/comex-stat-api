# 🇧🇷 Rotas SCM - Documentação em Português

## 📋 **Rotas Disponíveis (Traduzidas)**

### **🔍 Monitoramento**
- `GET /scm/health` - **Verificar saúde do sistema SCM e status do banco de dados**
  - Retorna status de conexão, dados carregados e contadores

### **📊 Dados Principais**
- `GET /scm/summary` - **Obter resumo dos dados SCM com contadores e analytics**
- `GET /scm/processos` - **Obter todos os processos minerários**
  - Query: `limit` - Limitar número de resultados
- `GET /scm/fases` - **Obter todas as fases dos processos**
- `GET /scm/tipos` - **Obter todos os tipos de requerimento**
- `GET /scm/municipios` - **Obter todos os municípios**
- `GET /scm/substancias` - **Obter todas as substâncias/minerais**

### **📈 Analytics**
- `GET /scm/analytics/by-fase` - **Obter contagem de processos por fase**
- `GET /scm/analytics/by-tipo` - **Obter contagem de processos por tipo de requerimento**
- `GET /scm/analytics/by-municipio` - **Obter contagem de processos por município**
- `GET /scm/analytics/by-substancia` - **Obter contagem de processos por substância/mineral**
- `GET /scm/analytics/by-uf` - **Obter contagem de processos por estado (UF)**

### **🔗 Relacionamentos**
- `GET /scm/relations/processo-municipios` - **Obter relacionamentos processo-município**
  - Query: `processo` - Filtrar por ID do processo
- `GET /scm/relations/processo-substancias` - **Obter relacionamentos processo-substância**
  - Query: `processo` - Filtrar por ID do processo

### **🔍 Busca Avançada**
- `GET /scm/search` - **Buscar processos com filtros**
  - Query Parameters:
    - `processo` - Filtrar por ID do processo
    - `municipio` - Filtrar por ID do município
    - `substancia` - Filtrar por ID da substância
    - `fase` - Filtrar por ID da fase
    - `tipo` - Filtrar por ID do tipo de requerimento
    - `limit` - Limitar número de resultados

### **⚙️ Gerenciamento**
- `POST /scm/update` - **Disparar atualização manual dos dados da ANM**
  - Retorna: `{ message: 'Atualização dos dados concluída com sucesso' }`

## 🎯 **Exemplos de Uso**

### **Verificar Status do Sistema**
```bash
curl http://localhost:3000/scm/health
```

### **Obter Resumo Completo**
```bash
curl http://localhost:3000/scm/summary
```

### **Listar Processos (Limitado)**
```bash
curl "http://localhost:3000/scm/processos?limit=10"
```

### **Analytics por Município**
```bash
curl http://localhost:3000/scm/analytics/by-municipio
```

### **Busca Filtrada**
```bash
# Buscar processos de Fortaleza na fase 2
curl "http://localhost:3000/scm/search?municipio=2304400&fase=2&limit=5"

# Buscar por tipo de substância específica
curl "http://localhost:3000/scm/search?substancia=100103&limit=20"
```

### **Relacionamentos de um Processo**
```bash
curl "http://localhost:3000/scm/relations/processo-municipios?processo=813.654/1973"
```

### **Atualização Manual**
```bash
curl -X POST http://localhost:3000/scm/update
```

## 📱 **Swagger UI**
Acesse a documentação interativa em: `http://localhost:3000/api`
- Todas as rotas estão documentadas em português
- Interface para testar endpoints diretamente
- Exemplos de responses incluídos

## 🎨 **Códigos de Resposta**

### **Sucesso (200)**
- Todas as operações GET retornam dados com estrutura JSON
- POST /update retorna `{ message: "..." }`

### **Erro (500)**
- Falhas na atualização de dados
- Problemas de conexão com banco
- Erros durante processamento

## 🏷️ **Nota Importante**
Todas as rotas estão **filtradas para dados do Ceará (CE)** apenas, otimizando performance e reduzindo volume de dados em ~95%.