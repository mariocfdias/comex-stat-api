# 02 - Mapeamento das Fontes de Dados

Este documento cataloga em detalhe cada fonte de dados consumida pela API atual, incluindo endpoints, formatos, schemas e limitacoes conhecidas.

---

## 1. ComexStat (MDIC)

### Informacoes Gerais

| Campo                  | Valor                                                  |
|------------------------|--------------------------------------------------------|
| Provedor               | Ministerio do Desenvolvimento, Industria e Comercio    |
| URL base               | `https://api-comexstat.mdic.gov.br`                    |
| Endpoint               | `POST /general`                                        |
| Autenticacao            | Nenhuma (API publica)                                  |
| Frequencia de atualizacao | Mensal (dados com ~2 meses de defasagem)            |
| Volume estimado        | Centenas a milhares de registros por consulta           |
| Timeout configurado    | 60 segundos                                            |

### Formato da Requisicao

**Metodo:** POST  
**Content-Type:** `application/json`  
**Query param adicional:** `?language=pt`

**Corpo da requisicao (JSON):**

```json
{
  "flow": "export",
  "monthDetail": true,
  "period": {
    "from": "2024-01",
    "to": "2024-12"
  },
  "filters": [
    {
      "filter": "state",
      "values": [23]
    }
  ],
  "details": ["country", "ISICSection", "heading"],
  "metrics": ["metricFOB", "metricKG", "metricCIF"]
}
```

**Codigo de construcao da requisicao:**

```typescript
// src/comexstat/comexstat.service.ts - queryGeneral()
private async queryGeneral(params: GeneralQueryParams): Promise<ComexStatResponse> {
  const response = await this.http.post<ComexStatResponse>(
    '/general',
    params,
    { params: { language: 'pt' } },
  );
  // ...
}
```

### Parametros do Corpo

| Campo         | Tipo      | Obrigatorio | Descricao                                                             |
|---------------|-----------|-------------|-----------------------------------------------------------------------|
| `flow`        | string    | Sim         | `"export"` ou `"import"`                                              |
| `monthDetail` | boolean   | Sim         | `true` para detalhe mensal, `false` para agregado                     |
| `period`      | object    | Sim         | `{from: "YYYY-MM", to: "YYYY-MM"}`                                   |
| `filters`     | array     | Nao         | Lista de filtros. Ex: `[{filter: "state", values: [23]}]`            |
| `details`     | array     | Nao         | Dimensoes de agrupamento: `state`, `country`, `ISICSection`, `ncm`, `heading`, `chapter` |
| `metrics`     | array     | Nao         | Metricas: `metricFOB`, `metricKG`, `metricCIF`                       |

### Formato da Resposta

```json
{
  "data": {
    "list": [
      {
        "year": 2024,
        "monthNumber": 1,
        "metricFOB": 123456789.00,
        "metricKG": 987654321.00,
        "metricCIF": 130000000.00,
        "country": "Estados Unidos",
        "countryName": "Estados Unidos",
        "state": "Ceara",
        "stateName": "Ceara",
        "ISICSection": "Agricultura",
        "coIsicSection": "A",
        "ISICSectionCode": "A",
        "ncm": "Descricao do NCM",
        "ncmCode": "12345678",
        "heading": "Descricao do Heading",
        "headingCode": "1234",
        "chapter": "Descricao do Capitulo",
        "chapterCode": "12"
      }
    ]
  },
  "success": true,
  "message": null
}
```

### Semantica dos Campos de Resposta

| Campo              | Tipo   | Descricao                                                           |
|--------------------|--------|---------------------------------------------------------------------|
| `year`             | number | Ano de referencia                                                   |
| `monthNumber`/`month` | number | Mes de referencia (presente quando `monthDetail=true`)          |
| `metricFOB`        | number | Valor FOB em dolares americanos (USD)                               |
| `metricKG`         | number | Peso em quilogramas                                                 |
| `metricCIF`        | number | Valor CIF em dolares americanos (USD)                               |
| `country`/`countryName` | string | Nome do pais parceiro                                        |
| `state`/`stateName` | string | Nome do estado brasileiro                                         |
| `ISICSection`      | string | Nome da secao ISIC                                                  |
| `coIsicSection`/`ISICSectionCode` | string | Codigo da secao ISIC (letra)                     |
| `ncm`/`ncmCode`   | string | Descricao e codigo NCM (8 digitos)                                  |
| `heading`/`headingCode` | string | Descricao e codigo da posicao tarifaria (4 digitos)          |
| `chapter`/`chapterCode` | string | Descricao e codigo do capitulo tarifario (2 digitos)        |

### Dimensoes e Metricas Disponiveis

**Dimensoes (campo `details`):**
- `state` -- Estado brasileiro (UF)
- `country` -- Pais parceiro comercial
- `ISICSection` -- Secao da classificacao industrial ISIC
- `ncm` -- Nomenclatura Comum do Mercosul (8 digitos)
- `heading` -- Posicao tarifaria (4 digitos)
- `chapter` -- Capitulo tarifario (2 digitos)

**Metricas (campo `metrics`):**
- `metricFOB` -- Valor Free On Board (USD)
- `metricKG` -- Peso liquido em quilogramas
- `metricCIF` -- Valor Cost, Insurance and Freight (USD)

### Filtro fixo aplicado pela API

A API sempre filtra pelo estado do Ceara (ID 23):

```typescript
private readonly CEARA_STATE_ID = 23;

// Usado em todas as consultas filtradas:
filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }]
```

Excecao: as consultas de `getNationalComparison()` e `getStatesRanking()` tambem fazem chamadas **sem** o filtro de estado para obter o total nacional e dados de todos os estados.

### Limitacoes e Quirks

- A API retorna campos com nomes duplicados/alternativos (ex: `monthNumber` vs `month`, `country` vs `countryName`). O servico trata ambos com operador `??`
- Nao ha paginacao -- a API retorna todos os registros de uma vez
- Consultas com muitas dimensoes combinadas podem ser lentas (>30s)
- Valores FOB/KG/CIF vem como numeros mas podem conter virgulas em strings (`this.toMillions` trata isso)

---

## 2. RDE (Banco Central do Brasil)

### Informacoes Gerais

| Campo                  | Valor                                                                   |
|------------------------|-------------------------------------------------------------------------|
| Provedor               | Banco Central do Brasil                                                 |
| URL base               | `https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata` |
| Protocolo              | OData v4                                                                |
| Autenticacao            | Nenhuma (API publica)                                                   |
| Frequencia de atualizacao | Mensal                                                               |
| Volume estimado        | Milhares de registros para CE                                           |
| Timeout configurado    | 60 segundos                                                             |

### Endpoints

| Endpoint          | Descricao                                                    |
|-------------------|--------------------------------------------------------------|
| `/TodosRegistros` | Todos os registros RDE publicados (desde novembro de 2011)   |
| `/RegistrosIED`   | Registros de Investimento Estrangeiro Direto com CNPJ Base   |

### Formato da Requisicao

**Metodo:** GET  
**Header:** `Accept: application/json;odata.metadata=minimal`

**Parametros OData (query string):**

```
$format=json
$filter=contains(UfPessoaNacional,'CE')
$orderby=Ano desc,Mes desc
$skip=0
$top=100
```

**Codigo de construcao dos parametros OData:**

```typescript
// src/rde/rde.service.ts - buildODataParams()
private buildODataParams(query: RdeQueryDto): Record<string, string> {
  const params: Record<string, string> = {
    $format: 'json',
    $filter: "contains(UfPessoaNacional,'CE')",
  };

  const orderAno = query.orderAno || 'desc';
  const orderMes = query.orderMes || 'desc';
  const orderbyParts = [`Ano ${orderAno}`, `Mes ${orderMes}`];
  params.$orderby = orderbyParts.join(',');

  if (query.skip !== undefined) {
    params.$skip = query.skip.toString();
  }
  if (query.top !== undefined) {
    params.$top = query.top.toString();
  }
  return params;
}
```

### Formato da Resposta

**Resposta OData:**

```json
{
  "@odata.context": "https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata/$metadata#TodosRegistros",
  "value": [
    {
      "CodigoRDE": "ABC123",
      "NomePessoaNacional": "Empresa do Ceara LTDA",
      "UfPessoaNacional": "CE",
      "NomePessoaEstrangeira": "Foreign Company Inc",
      "PaisPessoaEstrangeira": "ESTADOS UNIDOS",
      "MoedaOperacao": "DOLAR DOS EUA",
      "ValorOperacao": 1500000.00,
      "Sistema": "RDE-IED",
      "Ocorrencia": "INGRESSO",
      "Modalidade": "PARTICIPACAO NO CAPITAL",
      "Ano": 2024,
      "Mes": 6
    }
  ]
}
```

### Semantica dos Campos

**TodosRegistros:**

| Campo                    | Tipo    | Obrigatorio | Descricao                                           |
|--------------------------|---------|-------------|-----------------------------------------------------|
| `CodigoRDE`              | string  | Sim         | Codigo unico do registro RDE                        |
| `NomePessoaNacional`     | string  | Nao         | Nome da pessoa fisica ou juridica nacional           |
| `UfPessoaNacional`       | string  | Nao         | UF da pessoa nacional (filtrado para 'CE')          |
| `NomePessoaEstrangeira`  | string  | Nao         | Nome da pessoa/empresa estrangeira                  |
| `PaisPessoaEstrangeira`  | string  | Nao         | Pais da pessoa estrangeira                          |
| `MoedaOperacao`          | string  | Nao         | Moeda da operacao (ex: DOLAR DOS EUA)               |
| `ValorOperacao`          | number  | Nao         | Valor da operacao na moeda registrada               |
| `Sistema`                | string  | Sim         | Modulo: `RDE-ROF`, `RDE-IED` ou `RDE-PORTFOLIO`    |
| `Ocorrencia`             | string  | Sim         | Tipo de ocorrencia do registro                      |
| `Modalidade`             | string  | Sim         | Modalidade do registro                              |
| `Ano`                    | number  | Sim         | Ano da ocorrencia                                   |
| `Mes`                    | number  | Sim         | Mes da ocorrencia                                   |

**RegistrosIED** (campos adicionais):

| Campo                    | Tipo    | Obrigatorio | Descricao                                           |
|--------------------------|---------|-------------|-----------------------------------------------------|
| `CnpjBaseReceptora`     | string  | Sim         | CNPJ Base da empresa receptora do investimento      |

### Serializacao de parametros

O modulo RDE usa um `paramsSerializer` customizado para compatibilidade com OData:

```typescript
// src/rde/rde.module.ts
paramsSerializer: {
  encode: (value: string) => {
    return encodeURIComponent(value).replace(/%2C/g, ',');
  },
},
```

### Filtro fixo

Todas as consultas incluem o filtro `$filter=contains(UfPessoaNacional,'CE')` para retornar apenas registros do Ceara.

### Limitacoes e Quirks

- A API OData do BCB tem limite de registros por pagina (controlado por `$top`)
- Nao ha `$count` implementado -- o total retornado e apenas o `length` do array `value`
- O filtro `contains()` e case-sensitive no lado do BCB
- A ordenacao composta (`Ano desc,Mes desc`) pode nao ser respeitada em todos os cenarios

---

## 3. SCM (ANM - Agencia Nacional de Mineracao)

### Informacoes Gerais

| Campo                  | Valor                                                              |
|------------------------|--------------------------------------------------------------------|
| Provedor               | Agencia Nacional de Mineracao (ANM)                                |
| URL                    | `https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip` |
| Metodo                 | GET (download de arquivo ZIP)                                      |
| Autenticacao            | Nenhuma (dados abertos)                                            |
| Formato                | ZIP contendo 7 arquivos TXT (CSV com separador `;`)               |
| Frequencia de atualizacao | Diaria (cron as 2h, fuso America/Sao_Paulo)                    |
| Volume estimado        | Centenas de MB (ZIP), centenas de milhares de registros            |
| Timeout configurado    | 600 segundos (10 minutos) com 3 retentativas                      |

### Configuracao de Download

```typescript
// src/scm/scm-csv.service.ts
const response = await axios({
  method: 'GET',
  url: this.downloadUrl,
  responseType: 'stream',
  timeout: 600000, // 10 minutos
  httpsAgent,
  headers: {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/zip, */*',
    'Accept-Encoding': 'gzip, deflate, br',
  },
  maxRedirects: 5,
});
```

- SSL: `rejectUnauthorized: false` (o certificado da ANM pode ser invalido)
- Retentativas: 3, com exponential backoff (1s, 2s, 4s, max 30s)
- Freshness check: arquivos com menos de 48h sao reutilizados sem novo download

### Arquivos no ZIP

O ZIP `microdados-scm.zip` contem os seguintes arquivos no diretorio `microdados-scm/`:

#### 3.1 `Processo.txt`

Tabela principal de processos minerarios.

| Coluna (indice)                   | Nome do Campo                     | Tipo     | Descricao                                |
|-----------------------------------|-----------------------------------|----------|------------------------------------------|
| 0                                 | `DSProcesso`                      | string   | Identificador unico do processo (PK)    |
| 1                                 | `NRProcesso`                      | string   | Numero do processo                       |
| 2                                 | `NRAnoProcesso`                   | string   | Ano do processo (4 digitos)              |
| 3                                 | `BTAtivo`                         | string   | Flag de ativo (`S`/`N`)                 |
| 4                                 | `NRNUP`                           | string   | Numero Unico de Protocolo               |
| 5                                 | `IDTipoRequerimento`              | integer  | FK para TipoRequerimento                |
| 6                                 | `IDFaseProcesso`                  | integer  | FK para FaseProcesso                     |
| 7                                 | `IDUnidadeAdministrativaRegional` | integer  | ID da unidade administrativa regional   |
| 8                                 | `IDUnidadeProtocolizadora`        | integer  | ID da unidade protocolizadora            |
| 9                                 | `DTProtocolo`                     | string   | Data de protocolo                        |
| 10                                | `DTPrioridade`                    | string   | Data de prioridade                       |
| 11                                | `QTAreaHA`                        | string   | Area em hectares                         |

**Parser:**

```typescript
// src/scm/scm-csv.service.ts
private parseProcessoLine(line: string): ProcessoEntity | null {
  const parts = line.split(';');
  if (parts.length < 12) return null;
  const dsProcesso = parts[0]?.trim();
  if (!dsProcesso) return null;
  return {
    DSProcesso: dsProcesso,
    NRProcesso: parts[1]?.trim() || '',
    NRAnoProcesso: parts[2]?.trim() || '',
    BTAtivo: parts[3]?.trim() || '',
    NRNUP: parts[4]?.trim() || '',
    IDTipoRequerimento: parseInt(parts[5]) || 0,
    IDFaseProcesso: parseInt(parts[6]) || 0,
    IDUnidadeAdministrativaRegional: parseInt(parts[7]) || 0,
    IDUnidadeProtocolizadora: parseInt(parts[8]) || 0,
    DTProtocolo: parts[9]?.trim() || '',
    DTPrioridade: parts[10]?.trim() || '',
    QTAreaHA: parts[11]?.trim() || '',
  };
}
```

#### 3.2 `FaseProcesso.txt`

Tabela de dominio com as fases dos processos.

| Coluna | Nome do Campo     | Tipo    | Descricao                      |
|--------|-------------------|---------|--------------------------------|
| 0      | `IDFaseProcesso`  | integer | Identificador da fase (PK)     |
| 1      | `DSFaseProcesso`  | string  | Descricao da fase              |

#### 3.3 `TipoRequerimento.txt`

Tabela de dominio com tipos de requerimento.

| Coluna | Nome do Campo          | Tipo    | Descricao                            |
|--------|------------------------|---------|--------------------------------------|
| 0      | `IDTipoRequerimento`   | integer | Identificador do tipo (PK)           |
| 1      | `DSTipoRequerimento`   | string  | Descricao do tipo de requerimento    |

#### 3.4 `Municipio.txt`

Tabela de municipios brasileiros.

| Coluna | Nome do Campo  | Tipo    | Descricao                    |
|--------|----------------|---------|------------------------------|
| 0      | `IDMunicipio`  | integer | Identificador do municipio (PK) |
| 1      | `NMMunicipio`  | string  | Nome do municipio            |
| 2      | `SGUF`         | string  | Sigla da UF (ex: `CE`)      |

**Filtro aplicado:** Apenas municipios com `SGUF = 'CE'` sao carregados no banco.

#### 3.5 `Substancia.txt`

Tabela de substancias minerais.

| Coluna | Nome do Campo   | Tipo    | Descricao                         |
|--------|-----------------|---------|-----------------------------------|
| 0      | `IDSubstancia`  | integer | Identificador da substancia (PK)  |
| 1      | `NMSubstancia`  | string  | Nome da substancia mineral        |

#### 3.6 `ProcessoMunicipio.txt`

Tabela de relacionamento N:N entre processos e municipios.

| Coluna | Nome do Campo  | Tipo    | Descricao                          |
|--------|----------------|---------|------------------------------------|
| 0      | `DSProcesso`   | string  | FK para Processo                   |
| 1      | `IDMunicipio`  | integer | FK para Municipio                  |

#### 3.7 `ProcessoSubstancia.txt`

Tabela de relacionamento N:N entre processos e substancias.

| Coluna | Nome do Campo                    | Tipo    | Descricao                           |
|--------|----------------------------------|---------|--------------------------------------|
| 0      | `DSProcesso`                     | string  | FK para Processo                     |
| 1      | `IDSubstancia`                   | integer | FK para Substancia                   |
| 2      | `IDTipoUsoSubstancia`            | integer | Tipo de uso da substancia            |
| 3      | `IDMotivoEncerramentoSubstancia` | integer | Motivo de encerramento               |

### Logica de Filtragem para o Ceara

O servico filtra os dados em cascata:

```typescript
// src/scm/scm-csv.service.ts - filterDataForCeara()
// 1. Filtra municipios com SGUF = 'CE'
const municipiosCE = data.municipios.filter(m => m.SGUF === 'CE');
const municipiosCEIds = new Set(municipiosCE.map(m => m.IDMunicipio));

// 2. Filtra relacoes processo-municipio para municipios do CE
const processoMunicipiosCE = data.processoMunicipios.filter(pm =>
  municipiosCEIds.has(pm.IDMunicipio)
);

// 3. Identifica processos vinculados ao CE
const processosIdsNoceara = new Set(processoMunicipiosCE.map(pm => pm.DSProcesso));

// 4. Filtra processos, substancias e relacoes
const processosCE = data.processos.filter(p =>
  processosIdsNoceara.has(p.DSProcesso)
);
```

### Limitacoes e Quirks

- O certificado SSL da ANM pode ser invalido (`rejectUnauthorized: false`)
- Headers de User-Agent simulam um navegador para evitar bloqueio
- O download pode falhar por instabilidade da rede da ANM (por isso 3 retentativas)
- Todos os 7 arquivos sao parseados em memoria antes de filtragem
- O delimitador e ponto-e-virgula (`;`), nao virgula
- Nao ha header com tipos de dados -- os tipos sao inferidos no parse
- Datas (`DTProtocolo`, `DTPrioridade`) sao armazenadas como string, sem validacao de formato

---

## 4. Sigmine (ANM - Shapefiles)

### Informacoes Gerais

| Campo                  | Valor                                                    |
|------------------------|----------------------------------------------------------|
| Provedor               | Agencia Nacional de Mineracao (ANM) / SIGMINE            |
| Formato                | Shapefiles (.shp + .dbf + .shx + .prj)                  |
| Localizacao            | Diretorio `static/` na raiz do projeto                   |
| Autenticacao            | N/A (arquivos estaticos locais)                           |
| Frequencia de atualizacao | Manual (apenas em novo deploy)                        |
| Volume estimado        | Variavel por layer; de dezenas a milhares de features    |

### Layers (Camadas)

| Layer Enum             | Rota da API                    | Arquivo shapefile                              |
|------------------------|--------------------------------|------------------------------------------------|
| `AREA_SERVIDAO`        | `GET /layers/area-servidao`    | `static/AREA_SERVIDAO/AREA_SERVIDAO.shp`       |
| `ARRENDAMENTO`         | `GET /layers/arrendamento`     | `static/ARRENDAMENTO/ARRENDAMENTO.shp`         |
| `BLOQUEIO`             | `GET /layers/bloqueio`         | `static/BLOQUEIO/BLOQUEIO.shp`                 |
| `CE`                   | `GET /layers/ce`               | `static/CE/CE.shp`                             |
| `PROTECAO_FONTE`       | `GET /layers/protecao-fonte`   | `static/PROTECAO_FONTE/PROTECAO_FONTE.shp`     |
| `RESERVAS_GARIMPEIRAS` | `GET /layers/reservas-garimpeiras` | `static/RESERVAS_GARIMPEIRAS/RESERVAS_GARIMPEIRAS.shp` |

### Mapeamento de Shapefiles

```typescript
// src/sigmine/dto/sigmine-layer.dto.ts
export const SIGMINE_LAYER_SHAPEFILES: Record<SigmineLayer, string> = {
  [SigmineLayer.AREA_SERVIDAO]: 'AREA_SERVIDAO/AREA_SERVIDAO.shp',
  [SigmineLayer.ARRENDAMENTO]: 'ARRENDAMENTO/ARRENDAMENTO.shp',
  [SigmineLayer.BLOQUEIO]: 'BLOQUEIO/BLOQUEIO.shp',
  [SigmineLayer.CE]: 'CE/CE.shp',
  [SigmineLayer.PROTECAO_FONTE]: 'PROTECAO_FONTE/PROTECAO_FONTE.shp',
  [SigmineLayer.RESERVAS_GARIMPEIRAS]:
    'RESERVAS_GARIMPEIRAS/RESERVAS_GARIMPEIRAS.shp',
};
```

### Formato da Resposta

Retorna um `FeatureCollection` GeoJSON padrao:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "PROCESSO": "810.000/2020",
        "NOME": "...",
        "FASE": "...",
        "ULT_EVENTO": "..."
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[...], ...]]
      }
    }
  ]
}
```

### Filtragem Geografica

Para todas as layers exceto `CE`, o servico aplica um filtro de bounding box usando `@turf/turf`:

```typescript
// src/sigmine/services/geographic-filter.service.ts
async filterByCearaBounds(geoJson): Promise<FeatureCollection> {
  const cearaGeometry = await this.getCearaGeometry();
  const cearaBounds = this.createCearaBoundingPolygon(cearaGeometry);

  const filteredFeatures = geoJson.features.filter((feature) => {
    if (feature.geometry.type !== 'Polygon' &&
        feature.geometry.type !== 'MultiPolygon') {
      return false;
    }
    // Bounding box overlap check
    const featureBbox = turf.bbox(feature);
    const cearaBbox = turf.bbox(cearaBounds);
    return !(
      featureBbox[2] < cearaBbox[0] ||
      featureBbox[0] > cearaBbox[2] ||
      featureBbox[3] < cearaBbox[1] ||
      featureBbox[1] > cearaBbox[3]
    );
  });

  return { type: 'FeatureCollection', features: filteredFeatures };
}
```

O arquivo de geometria do Ceara usado como referencia esta em `static/geojs-23-mun.json` (GeoJSON de municipios do Ceara com codigo IBGE 23).

### Limitacoes e Quirks

- Os shapefiles sao estaticos -- nao ha mecanismo de atualizacao automatica
- A filtragem usa bounding box (retangulo), nao intersecao geometrica exata -- podem incluir features de estados vizinhos
- A layer `CE` nao passa pelo filtro geografico (ja e especifica do Ceara)
- Apenas geometrias do tipo `Polygon` e `MultiPolygon` sao processadas; `Point` e `LineString` sao descartados
- Em caso de falha na leitura do shapefile, retorna erro 503
- Em caso de falha no filtro geografico, retorna os dados sem filtrar (fallback)

---

## Resumo Comparativo das Fontes

| Fonte     | Protocolo    | Formato Resposta    | Freq. Atualizacao | Filtro CE            | Complexidade Ingestao |
|-----------|-------------|---------------------|-------------------|----------------------|-----------------------|
| ComexStat | REST POST   | JSON                | Mensal            | `state=23` no body   | Alta (agregacoes)     |
| RDE       | OData GET   | JSON                | Mensal            | `contains(UfPessoaNacional,'CE')` | Baixa          |
| SCM       | HTTP GET    | ZIP com CSVs (`;`)  | Diaria            | `SGUF='CE'` pos-parse| Media (ETL completo)  |
| Sigmine   | Arquivo local| Shapefile -> GeoJSON| Manual            | Bounding box turf    | Media (geo-processing)|
