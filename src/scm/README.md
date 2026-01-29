# Módulo SCM (Sistema de Cadastro Mineiro)

## Visão Geral
Este módulo fornece acesso aos dados do cadastro mineiro brasileiro da ANM (Agência Nacional de Mineração), **filtrado apenas para o estado do Ceará**. Os dados são automaticamente baixados, processados e armazenados em um banco SQLite para consultas eficientes.

## 🏷️ **Escopo dos Dados: Apenas Ceará**
Para otimizar a performance e reduzir o volume de dados, esta implementação carrega apenas:
- ✅ Processos minerários localizados em municípios do Ceará (CE)
- ✅ Municípios do estado do Ceará
- ✅ Substâncias utilizadas em processos do Ceará
- ✅ Todas as fases e tipos de requerimento (tabelas de referência)

Isso reduz o volume de dados em ~95% mantendo funcionalidade completa para a região do Ceará.

## Funcionalidades
- **Banco SQLite**: Armazenamento rápido e persistente com estrutura relacional adequada
- **Atualizações Automáticas**: Atualizações agendadas diariamente às 2h (horário de Brasília)
- **Carregamento Inicial**: Usa arquivos estáticos como seed se o banco estiver vazio
- **Analytics Avançadas**: Consultas SQL otimizadas para análise de dados
- **API REST**: Endpoints abrangentes para acesso aos dados
- **Busca e Filtragem**: Capacidades avançadas de busca em todas as entidades

## Esquema do Banco de Dados
O módulo cria as seguintes tabelas:
- `processos` - Tabela principal de processos minerários
- `fase_processo` - Referência de fases do processo
- `tipo_requerimento` - Referência de tipos de requerimento
- `municipios` - Referência de municípios
- `substancias` - Referência de minerais/substâncias
- `processo_municipio` - Muitos-para-muitos: Processo ↔ Município
- `processo_substancia` - Muitos-para-muitos: Processo ↔ Substância

## Principais Endpoints

### Acesso aos Dados
- `GET /scm/summary` - Visão geral dos dados com contadores e analytics
- `GET /scm/processos` - Todos os processos minerários
- `GET /scm/fases` - Fases dos processos
- `GET /scm/tipos` - Tipos de requerimento
- `GET /scm/municipios` - Municípios
- `GET /scm/substancias` - Substâncias

### Analytics
- `GET /scm/analytics/by-fase` - Processos agrupados por fase
- `GET /scm/analytics/by-tipo` - Processos agrupados por tipo
- `GET /scm/analytics/by-municipio` - Processos agrupados por município
- `GET /scm/analytics/by-substancia` - Processos agrupados por substância
- `GET /scm/analytics/by-uf` - Processos agrupados por estado

### Busca Avançada
- `GET /scm/search?processo=X&municipio=Y&fase=Z` - Filtrar processos por múltiplos critérios

### Gerenciamento
- `POST /scm/update` - Disparar atualização manual dos dados

## Benefícios de Performance
- **Consultas 10x+ mais rápidas**: Consultas no banco vs. análise de arquivos CSV
- **Eficiência de memória**: Não precisa carregar datasets inteiros na memória
- **Buscas indexadas**: Consultas rápidas por qualquer campo
- **Analytics agregadas**: SQL otimizado para contagem e agrupamento
- **Acesso concorrente**: Múltiplas requisições tratadas eficientemente

## Fontes de Dados
- **Principal**: Downloads diários da API da ANM (https://app.anm.gov.br/dadosabertos/SCM/)
- **Fallback**: Arquivos estáticos em `/static/SCM/`
- **Frequência de atualização**: Uma vez por dia às 2h (configurável)

## Localização do Banco
- Arquivo SQLite: `./data/scm.db`
- Criação automática de tabelas na primeira inicialização
- Dados persistem entre reinicializações da aplicação