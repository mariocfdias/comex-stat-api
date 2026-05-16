# Migracao da API ComexStat para Plataforma de Engenharia de Dados

## Publico-alvo

Este documento e destinado a **engenheiros de dados** e **desenvolvedores backend** responsaveis pela migracao da API atual para uma plataforma de engenharia de dados.

---

## Declaracao do Problema

A API atual, construida em NestJS, processa todos os dados **sob demanda a cada requisicao**. Para cada chamada, o sistema:

- Faz requisicoes HTTP para APIs externas (ComexStat MDIC, BCB OData) com timeouts de 60 segundos
- Realiza agregacoes pesadas em memoria (somas, rankings, percentuais, ordenacoes)
- No endpoint `getStatesRanking()`, dispara **5 chamadas HTTP paralelas** para a API externa, cada uma com timeout de 60s
- O download dos dados SCM da ANM possui timeout de **10 minutos** com 3 retentativas
- O cache Redis e opcional -- sem ele, o processo Node.js corre risco de OOM sob carga

Esse modelo causa **timeouts**, **lentidao** e **instabilidade** em consultas pesadas, especialmente nos endpoints de ranking de estados e comparacao nacional.

## Solucao Proposta

Migrar para uma **plataforma de engenharia de dados** que pre-computa todas as agregacoes:

| Componente       | Tecnologia   | Responsabilidade                                      |
|------------------|--------------|-------------------------------------------------------|
| Orquestracao     | Airflow      | DAGs para ingestao e transformacao de dados            |
| Processamento    | Spark         | Processamento distribuido de grandes volumes           |
| Transformacao    | dbt          | Modelagem dimensional e agregacoes pre-computadas      |
| Data Lake        | MinIO        | Armazenamento de dados brutos (raw) e intermediarios   |
| Data Warehouse   | PostgreSQL   | Tabelas analiticas pre-computadas para servir a API    |
| API              | FastAPI      | Camada de servico leve, apenas leitura do PostgreSQL   |

## Restricao Critica

> **Os contratos da API (parametros de requisicao e formato de resposta) DEVEM permanecer identicos.**
>
> Todos os DTOs de entrada (`SummaryQueryDto`, `TimeSeriesQueryDto`, `RdeQueryDto`, etc.) e DTOs de saida (`SummaryResponseDto`, `TimeSeriesDataDto`, `PartnerCountryDto`, etc.) devem manter exatamente a mesma estrutura JSON. Consumidores existentes nao devem precisar de nenhuma alteracao.

---

## Glossario

| Termo     | Definicao                                                                                                     |
|-----------|---------------------------------------------------------------------------------------------------------------|
| ComexStat | Sistema de estatisticas de comercio exterior do MDIC (Ministerio do Desenvolvimento, Industria e Comercio)     |
| RDE       | Registro Declaratorio Eletronico do Banco Central do Brasil, com dados de investimentos estrangeiros           |
| SCM       | Sistema de Cadastro Mineiro da ANM (Agencia Nacional de Mineracao)                                            |
| Sigmine   | Sistema de Informacoes Geograficas da Mineracao -- shapefiles com areas de processos minerarios                |
| FOB       | Free On Board -- valor da mercadoria sem incluir frete e seguro internacional                                 |
| CIF       | Cost, Insurance and Freight -- valor da mercadoria incluindo frete e seguro ate o porto de destino             |
| NCM       | Nomenclatura Comum do Mercosul -- codigo de 8 digitos para classificacao de mercadorias                       |
| ISIC      | International Standard Industrial Classification -- classificacao industrial internacional por secoes           |
| OData     | Open Data Protocol -- protocolo de consulta usado pela API do BCB para o RDE                                  |
| Heading   | Posicao tarifaria -- codigo de 4 digitos na nomenclatura NCM                                                  |
| Chapter   | Capitulo tarifario -- codigo de 2 digitos na nomenclatura NCM                                                 |
| MinIO     | Sistema de armazenamento de objetos compativel com S3, usado como data lake                                   |
| dbt       | Data Build Tool -- ferramenta de transformacao SQL para modelagem dimensional                                  |
| Airflow   | Apache Airflow -- plataforma de orquestracao de workflows (DAGs)                                              |
| DAG       | Directed Acyclic Graph -- grafo aciclico direcionado que define a sequencia de tarefas no Airflow              |

---

## Indice dos Documentos

| #  | Documento                                                                       | Descricao                                                                               |
|----|---------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| 01 | [01-arquitetura-atual.md](./01-arquitetura-atual.md)                            | Documentacao detalhada da arquitetura atual: stack, modulos, fluxos de dados e problemas |
| 02 | [02-mapeamento-fontes-dados.md](./02-mapeamento-fontes-dados.md)                | Catalogo completo de cada fonte de dados: endpoints, formatos, schemas e limitacoes      |
| 03 | 03-modelo-dados-analitico.md                                                    | Modelo dimensional proposto para o data warehouse (fatos e dimensoes)                    |
| 04 | 04-pipeline-ingestao.md                                                         | Arquitetura das DAGs do Airflow para ingestao de cada fonte de dados                     |
| 05 | 05-transformacoes-dbt.md                                                        | Modelos dbt para transformacao e pre-computacao de todas as agregacoes                   |
| 06 | 06-api-fastapi.md                                                               | Especificacao da nova API FastAPI com mapeamento endpoint-por-endpoint                   |
| 07 | 07-plano-migracao.md                                                            | Plano de migracao faseado com estrategia de rollback e validacao de paridade             |
