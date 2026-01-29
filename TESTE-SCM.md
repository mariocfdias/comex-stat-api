# Como Testar o Sistema SCM com SQLite (Dados do Ceará)

## 🏷️ **Importante: Scope Limitado ao Ceará**
Este sistema carrega apenas dados de processos minerários do estado do **Ceará (CE)** para otimizar performance e reduzir volume de dados.

## 🚀 Iniciando o Sistema

1. **Inicie o servidor**:
```bash
npm run start:dev
```

2. **Verifique se o sistema está saudável**:
```bash
curl http://localhost:3000/scm/health
```

**Resposta esperada** (primeira vez):
```json
{
  "status": "healthy",
  "database": "connected",
  "dataLoaded": false,
  "counts": {
    "processos": 0,
    "fases": 0,
    "municipios": 0,
    ...
  },
  "timestamp": "2025-01-29T..."
}
```

## 📊 Aguarde o Carregamento Inicial (Ceará Only)

Durante o primeiro startup, o sistema irá:

1. **Criar o banco SQLite** em `./data/scm.db`
2. **Carregar dados estáticos** dos arquivos `/static/SCM/`
3. **Filtrar apenas dados do Ceará** (CE)
4. **Processar e inserir** dados filtrados nas tabelas

**Logs esperados**:
```
[ScmSchedulerService] No data found in database, loading initial data from static files...
[ScmCsvService] Step 1/7: Parsing CSV files...
[ScmCsvService] Step 2/7: Filtering data for Ceará (CE) only...
[ScmCsvService] Found XX municipalities in Ceará
[ScmCsvService] Ceará filter results: - Municípios: XX - Processos: YY
[ScmRepositoryService] Removed X duplicate processos
[ScmRepositoryService] Removed Y duplicate processo-municipio relations
[ScmRepositoryService] Removed Z duplicate processo-substancia relations
[ScmCsvService] Step 7/7: Database loading completed for Ceará!
```

**Volume esperado para Ceará**:
- Municípios: ~184 (total de municípios do CE)
- Processos: ~5.000-15.000 (estimativa)
- Carregamento: ~30-60 segundos

## ✅ Testes de Funcionalidade

### 1. **Verificar Saúde Pós-Carregamento**
```bash
curl http://localhost:3000/scm/health
```

Agora deve mostrar `"dataLoaded": true` e contadores > 0.

### 2. **Sumário Completo**
```bash
curl http://localhost:3000/scm/summary
```

### 3. **Dados Básicos**
```bash
# Fases do processo
curl http://localhost:3000/scm/fases

# Tipos de requerimento  
curl http://localhost:3000/scm/tipos

# Municípios
curl http://localhost:3000/scm/municipios

# Substâncias
curl http://localhost:3000/scm/substancias
```

### 4. **Analytics (Performance Otimizada)**
```bash
# Processos por fase
curl http://localhost:3000/scm/analytics/by-fase

# Processos por tipo
curl http://localhost:3000/scm/analytics/by-tipo

# Processos por município
curl http://localhost:3000/scm/analytics/by-municipio

# Processos por UF
curl http://localhost:3000/scm/analytics/by-uf
```

### 5. **Busca Avançada**
```bash
# Buscar por ID de processo específico
curl "http://localhost:3000/scm/search?processo=813.654/1973"

# Filtrar por município
curl "http://localhost:3000/scm/search?municipio=3304557&limit=10"

# Filtrar por fase + tipo
curl "http://localhost:3000/scm/search?fase=1&tipo=2&limit=5"
```

### 6. **Processos com Limite**
```bash
# Primeiros 100 processos
curl "http://localhost:3000/scm/processos?limit=100"
```

## 🔄 Teste de Atualização Manual

```bash
curl -X POST http://localhost:3000/scm/update
```

Este comando irá:
- Baixar dados frescos da ANM
- Substituir dados do banco
- Retornar confirmação

## 🐛 Debugging

### Verificar Banco SQLite
```bash
# Instalar sqlite3 se necessário
sudo apt install sqlite3

# Conectar ao banco
sqlite3 ./data/scm.db

# Queries úteis
.tables
SELECT COUNT(*) FROM processos;
SELECT COUNT(*) FROM municipios;
SELECT * FROM fase_processo LIMIT 5;
```

### Logs Detalhados
O sistema gera logs para:
- ✅ Carregamento inicial
- ✅ Parsing de arquivos CSV
- ✅ Inserção no banco
- ✅ Queries SQL
- ❌ Erros de processamento

### Performance Esperada
- **Primeira carga**: 30-60s (dependendo do tamanho dos CSVs)
- **Queries subsequentes**: < 100ms
- **Analytics**: < 500ms
- **Busca filtrada**: < 200ms

## 🎯 Indicadores de Sucesso

✅ **Health check** retorna `healthy` + `dataLoaded: true`
✅ **Summary** mostra contadores realistas
✅ **Analytics** retornam em < 1 segundo  
✅ **Busca** funciona com múltiplos filtros
✅ **Banco SQLite** criado em `./data/scm.db`
✅ **Logs** sem erros críticos

## 📁 Arquivos Criados
```
./data/
├── scm.db          # Banco SQLite principal
└── scm/            # Cache de downloads
    ├── microdados-scm.zip
    └── extracted/  # Arquivos extraídos
```