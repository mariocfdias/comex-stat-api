# Enhanced States Ranking Endpoint

## Endpoint
`GET /comexstat/national-comparison/states-ranking`

## Descrição
Retorna o ranking completo de todos os estados brasileiros ordenado por valor de exportação ou importação, incluindo informações detalhadas sobre setores, países parceiros e produtos principais de cada estado.

## Query Parameters

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `flow` | `string` | Não | Fluxo comercial: `export` (Exportações) ou `import` (Importações). Padrão: `export` |
| `from` | `string` | Sim | Período inicial no formato `YYYY-MM` (ex: `2024-01`) |
| `to` | `string` | Sim | Período final no formato `YYYY-MM` (ex: `2024-12`) |

## Exemplo de Requisição

```bash
GET /comexstat/national-comparison/states-ranking?flow=export&from=2024-01&to=2024-12
```

## Exemplo de Resposta

```json
{
  "success": true,
  "data": [
    {
      "rank": 1,
      "state": "São Paulo",
      "value": 45678.5,
      "participation": 32.5,
      "topSectors": [
        {
          "code": "C",
          "name": "Indústrias de transformação",
          "value": 25000.0,
          "percentage": 54.7
        },
        {
          "code": "A",
          "name": "Agricultura, pecuária, produção florestal, pesca e aquicultura",
          "value": 12000.0,
          "percentage": 26.3
        },
        {
          "code": "B",
          "name": "Indústrias extrativas",
          "value": 5000.0,
          "percentage": 10.9
        }
      ],
      "topPartners": [
        {
          "country": "Estados Unidos",
          "value": 15000.0,
          "percentage": 32.8
        },
        {
          "country": "China",
          "value": 10000.0,
          "percentage": 21.9
        },
        {
          "country": "Argentina",
          "value": 8000.0,
          "percentage": 17.5
        },
        {
          "country": "Alemanha",
          "value": 5000.0,
          "percentage": 10.9
        },
        {
          "country": "Países Baixos (Holanda)",
          "value": 3000.0,
          "percentage": 6.6
        }
      ],
      "topProducts": [
        {
          "code": "8703",
          "description": "Automóveis de passageiros e outros veículos automóveis",
          "value": 8500.0,
          "percentage": 18.6
        },
        {
          "code": "2401",
          "description": "Fumo (tabaco) não manufaturado; desperdícios de fumo (tabaco)",
          "value": 7200.0,
          "percentage": 15.8
        },
        {
          "code": "1701",
          "description": "Açúcares de cana ou de beterraba e sacarose quimicamente pura",
          "value": 6800.0,
          "percentage": 14.9
        },
        {
          "code": "2709",
          "description": "Óleos brutos de petróleo ou de minerais betuminosos",
          "value": 5400.0,
          "percentage": 11.8
        },
        {
          "code": "8471",
          "description": "Máquinas automáticas para processamento de dados",
          "value": 4200.0,
          "percentage": 9.2
        }
      ]
    },
    {
      "rank": 2,
      "state": "Minas Gerais",
      "value": 28950.3,
      "participation": 20.6,
      "topSectors": [
        {
          "code": "B",
          "name": "Indústrias extrativas",
          "value": 18000.0,
          "percentage": 62.2
        },
        {
          "code": "C",
          "name": "Indústrias de transformação",
          "value": 8000.0,
          "percentage": 27.6
        }
      ],
      "topPartners": [
        {
          "country": "China",
          "value": 12000.0,
          "percentage": 41.4
        },
        {
          "country": "Estados Unidos",
          "value": 6000.0,
          "percentage": 20.7
        }
      ],
      "topProducts": [
        {
          "code": "2601",
          "description": "Minérios de ferro e seus concentrados",
          "value": 15000.0,
          "percentage": 51.8
        },
        {
          "code": "0901",
          "description": "Café, mesmo torrado ou descafeinado",
          "value": 4500.0,
          "percentage": 15.5
        }
      ]
    },
    {
      "rank": 7,
      "state": "Ceará",
      "value": 3452.8,
      "participation": 2.46,
      "topSectors": [
        {
          "code": "C",
          "name": "Indústrias de transformação",
          "value": 2100.0,
          "percentage": 60.8
        },
        {
          "code": "A",
          "name": "Agricultura, pecuária, produção florestal, pesca e aquicultura",
          "value": 800.0,
          "percentage": 23.2
        }
      ],
      "topPartners": [
        {
          "country": "Estados Unidos",
          "value": 1200.0,
          "percentage": 34.7
        },
        {
          "country": "Argentina",
          "value": 650.0,
          "percentage": 18.8
        },
        {
          "country": "Países Baixos (Holanda)",
          "value": 420.0,
          "percentage": 12.2
        }
      ],
      "topProducts": [
        {
          "code": "6403",
          "description": "Calçados com sola exterior de borracha, plástico, couro natural",
          "value": 850.0,
          "percentage": 24.6
        },
        {
          "code": "0306",
          "description": "Crustáceos, congelados, secos, salgados ou em salmoura",
          "value": 620.0,
          "percentage": 18.0
        },
        {
          "code": "5201",
          "description": "Algodão não cardado nem penteado",
          "value": 480.0,
          "percentage": 13.9
        }
      ]
    }
  ]
}
```

## Campos da Resposta

### Nível Principal (StateRankingItemDto)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `rank` | `number` | Posição do estado no ranking nacional |
| `state` | `string` | Nome do estado |
| `value` | `number` | Valor total de exportação/importação em milhões de USD |
| `participation` | `number` | Participação percentual do estado em relação ao total nacional |
| `topSectors` | `array` | Lista dos 5 principais setores ISIC do estado (opcional) |
| `topPartners` | `array` | Lista dos 5 principais países parceiros do estado (opcional) |
| `topProducts` | `array` | Lista dos 5 principais produtos do estado (opcional) |

### Setores (StateRankingSectorDto)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `code` | `string` | Código da seção ISIC |
| `name` | `string` | Nome do setor econômico |
| `value` | `number` | Valor do setor em milhões de USD |
| `percentage` | `number` | Participação percentual do setor em relação ao total do estado |

### Países Parceiros (StateRankingPartnerDto)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `country` | `string` | Nome do país parceiro |
| `value` | `number` | Valor comercializado com o país em milhões de USD |
| `percentage` | `number` | Participação percentual do país em relação ao total do estado |

### Produtos (StateRankingProductDto)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `code` | `string` | Código da posição tarifária (4 dígitos) |
| `description` | `string` | Descrição do produto |
| `value` | `number` | Valor do produto em milhões de USD |
| `percentage` | `number` | Participação percentual do produto em relação ao total do estado |

## Notas Importantes

1. **Valores em Milhões**: Todos os valores monetários são expressos em milhões de dólares americanos (M USD)
2. **Top N**: Os arrays de setores, parceiros e produtos contêm no máximo 5 itens cada, ordenados por valor decrescente
3. **Percentuais**: Os percentuais de setores, parceiros e produtos são calculados em relação ao total do respectivo estado
4. **Ordenação**: Os estados são ordenados pelo valor total (campo `value`) em ordem decrescente
5. **Cache**: Os resultados são cacheados por 24 horas para melhor performance

## Casos de Uso

Este endpoint enriquecido é ideal para:
- Dashboards analíticos de comércio exterior por estado
- Comparações detalhadas entre estados
- Análise de especialização econômica regional
- Identificação de principais parceiros comerciais por região
- Mapeamento de produtos-chave por estado
