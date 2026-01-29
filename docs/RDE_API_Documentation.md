# Documentação da API RDE

Esta documentação descreve a implementação da API para consumo dos dados de Registros RDE (Registro Declaratório Eletrônico) do Banco Central do Brasil, focada nos dados do estado do Ceará.

## Visão Geral

A API RDE implementa o consumo dos serviços de dados do Banco Central disponíveis em:
- **Base URL**: `https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata`

## Endpoints Disponíveis

### 1. GET `/rde/todos-registros`

Consulta todos os registros RDE publicados (a partir de novembro de 2011).

#### Parâmetros de Query (todos opcionais):

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `format` | string | `json` | Tipo de conteúdo que será retornado |
| `select` | string | - | Propriedades que serão retornadas |
| `filter` | string | `contains(UfPessoaNacional,'CE')` | Filtro de seleção de entidades para o Ceará |
| `orderby` | string | `Ano desc` | Propriedades para ordenação das entidades |
| `skip` | integer | - | Índice da primeira entidade que será retornada |
| `top` | integer | `100` | Número máximo de entidades que serão retornadas |

#### Exemplo de Uso:
```
GET /rde/todos-registros?top=10&orderby=Ano desc,Mes desc
```

#### Resposta:
```json
{
  "success": true,
  "total": 1,
  "data": [
    {
      "CodigoRDE": "IA293507",
      "NomePessoaNacional": "COCOS KITE HOUSE LTDA",
      "UfPessoaNacional": "CE",
      "NomePessoaEstrangeira": "PABLO ANDRES ASALGADO MARTINEZ",
      "PaisPessoaEstrangeira": "Chile",
      "MoedaOperacao": "",
      "ValorOperacao": null,
      "Sistema": "RDE-IED",
      "Ocorrencia": "REGISTRO EFETUADO",
      "Modalidade": "INVESTIMENTO ESTRANGEIRO DIRETO",
      "Ano": 2022,
      "Mes": 12
    }
  ]
}
```

### 2. GET `/rde/registros-ied`

Consulta registros RDE-IED com CNPJ Base da Receptora (a partir de novembro de 2011).

#### Parâmetros de Query:
Os mesmos parâmetros do endpoint anterior.

#### Exemplo de Uso:
```
GET /rde/registros-ied?top=5&filter=contains(UfPessoaNacional,'CE')
```

#### Resposta:
```json
{
  "success": true,
  "total": 1,
  "data": [
    {
      "CodigoRDE": "IA035654",
      "CnpjBaseReceptora": "04879360",
      "NomePessoaNacional": "INVS. FUTURO LTDA",
      "UfPessoaNacional": "CE",
      "NomePessoaEstrangeira": "CINTRA - URBANIZACOES, TUR.E CONSTS.S A",
      "PaisPessoaEstrangeira": "PORTUGAL",
      "MoedaOperacao": null,
      "ValorOperacao": null,
      "Sistema": "RDE-IED",
      "Ocorrencia": "REGISTRO EFETUADO",
      "Modalidade": "INVESTIMENTO ESTRANGEIRO DIRETO",
      "Ano": 2011,
      "Mes": 11
    }
  ]
}
```

## Filtros OData Suportados

A API suporta os operadores e funções OData conforme documentação do Banco Central:

### Operadores de Comparação
- `eq` - Igual: `Ano eq 2023`
- `ne` - Diferente: `Sistema ne 'RDE-ROF'`
- `gt` - Maior que: `Ano gt 2020`
- `ge` - Maior ou igual: `Ano ge 2020`
- `lt` - Menor que: `Ano lt 2025`
- `le` - Menor ou igual: `Ano le 2024`

### Operadores Lógicos
- `and` - E lógico: `Ano eq 2023 and Mes eq 12`
- `or` - Ou lógico: `Ano eq 2022 or Ano eq 2023`
- `not` - Negação: `not contains(Sistema,'ROF')`

### Funções de String
- `contains` - Contém: `contains(UfPessoaNacional,'CE')`
- `startswith` - Começa com: `startswith(CodigoRDE,'IA')`
- `endswith` - Termina com: `endswith(Sistema,'IED')`

## Campos Retornados

### TodosRegistros
- `CodigoRDE`: Código RDE do registro
- `NomePessoaNacional`: Nome da Pessoa Física Residente ou Jurídica Nacional
- `UfPessoaNacional`: Unidade da Federação da Pessoa Nacional
- `NomePessoaEstrangeira`: Nome da Pessoa Estrangeira
- `PaisPessoaEstrangeira`: País da Pessoa Estrangeira
- `MoedaOperacao`: Moeda da Operação registrada
- `ValorOperacao`: Valor da Operação na moeda registrada
- `Sistema`: Módulo do Sistema RDE (RDE-ROF, RDE-IED ou RDE-PORTFOLIO)
- `Ocorrencia`: Ocorrência do registro
- `Modalidade`: Modalidade do Registro
- `Ano`: Ano da Ocorrência
- `Mes`: Mês da Ocorrência

### RegistrosIED
Todos os campos acima, mais:
- `CnpjBaseReceptora`: CNPJ Base da Receptora

## Cache

- **TTL**: 24 horas
- **Namespace**: `rde`
- **Estratégia**: Cache por query parameters

## Configuração

### Variáveis de Ambiente
- `RDE_ALLOW_INSECURE`: Define se certificados SSL não confiáveis são aceitos (padrão: `true`)
- `REDIS_URL`: URL do Redis para cache distribuído (opcional)

## Exemplos de URLs da API Externa

### Todos os Registros (Ceará)
```
https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata/TodosRegistros?$format=json&$filter=contains(UfPessoaNacional,'CE')&$orderby=Ano desc&$top=100
```

### Registros IED (Ceará)
```
https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata/RegistrosIED?$format=json&$filter=contains(UfPessoaNacional,'CE')&$orderby=Ano desc&$top=100
```

## Tratamento de Erros

A API trata os seguintes tipos de erro:
- **400 Bad Request**: Parâmetros inválidos
- **503 Service Unavailable**: Falha na comunicação com a API do Banco Central
- **502 Bad Gateway**: Erro na resposta da API externa

Todos os erros são logados com detalhes para depuração.

## Observações Importantes

1. **Filtro Padrão**: Por padrão, todos os endpoints filtram apenas dados do Ceará (`UfPessoaNacional` contém 'CE')
2. **Ordenação**: Por padrão, os resultados são ordenados por ano decrescente
3. **Paginação**: Use `skip` e `top` para implementar paginação
4. **Limite**: O parâmetro `top` tem valor padrão de 100 registros
5. **Performance**: Resultados são cacheados por 24 horas para melhor performance