# Guia de Uso da API - Parâmetros Simplificados

## ✨ Nova Forma Simplificada

Agora os períodos customizados usam **dois parâmetros simples** ao invés de objetos aninhados!

## Rota: `/comexstat/products`

### ✅ Antes (complicado):
```
?period[from]=2010-02&period[to]=2010-08
```

### ✅ Agora (simplificado):
```
?periodFrom=2010-02&periodTo=2010-08
```

## Exemplos Práticos

### 1. Período mensal customizado
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&periodFrom=2010-02&periodTo=2010-08&flow=export&aggregation=ncm&topN=20'
```

**Logs esperados:**
```
[DEBUG] Recebido - year: undefined, periodFrom: 2010-02, periodTo: 2010-08
[DEBUG] Period construído: {"from":"2010-02","to":"2010-08"}
[DEBUG] Strategy monthly: queryPeriod={"from":"2010-02","to":"2010-08"}
```

### 2. Ano específico
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=annual&year=2010&flow=export&aggregation=ncm'
```

### 3. Default (year-to-date para monthly, ano anterior para annual)
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&flow=export'
```

## Rota: `/comexstat/partners`

### Período customizado
```bash
curl 'http://localhost:3000/comexstat/partners?period=custom&periodFrom=2010-02&periodTo=2010-08&flow=export&topN=10'
```

### Year-to-date
```bash
curl 'http://localhost:3000/comexstat/partners?period=yearToDate&flow=current'
```

### Mês atual
```bash
curl 'http://localhost:3000/comexstat/partners?period=currentMonth&flow=export'
```

## No Swagger UI

Agora é muito mais fácil! Apenas preencha os campos:

### Para `/comexstat/products`:
- `periodicity`: `monthly`
- `periodFrom`: `2010-02`
- `periodTo`: `2010-08`
- `flow`: `export`
- `aggregation`: `ncm`
- `topN`: `20`

### Para `/comexstat/partners`:
- `period`: `custom`
- `periodFrom`: `2010-02`
- `periodTo`: `2010-08`
- `flow`: `export`
- `topN`: `10`

## Referência de Parâmetros

### `/comexstat/products`

| Parâmetro | Tipo | Exemplo | Descrição |
|-----------|------|---------|-----------|
| `periodicity` | enum | `monthly`, `annual` | Tipo de periodicidade (default: `annual`) |
| `periodFrom` | string | `2010-02` | Data inicial (YYYY-MM) para períodos customizados |
| `periodTo` | string | `2010-08` | Data final (YYYY-MM) para períodos customizados |
| `year` | number | `2010` | Ano para consultas anuais |
| `flow` | enum | `export`, `import` | Fluxo comercial (default: `export`) |
| `aggregation` | enum | `ncm`, `heading`, `chapter` | Nível de agregação (default: `heading`) |
| `topN` | number | `20` | Quantidade de resultados (default: `20`) |

### `/comexstat/partners`

| Parâmetro | Tipo | Exemplo | Descrição |
|-----------|------|---------|-----------|
| `period` | enum | `currentMonth`, `yearToDate`, `lastYear`, `custom` | Tipo de período (default: `yearToDate`) |
| `periodFrom` | string | `2010-02` | Data inicial quando `period=custom` |
| `periodTo` | string | `2010-08` | Data final quando `period=custom` |
| `flow` | enum | `export`, `import`, `current` | Fluxo comercial (default: `current`) |
| `topN` | number | `10` | Quantidade de resultados (default: `10`) |

## Prioridade de Parâmetros

### Para `/comexstat/products`:

1. Se `periodFrom` E `periodTo` fornecidos → usa período customizado
2. Senão, se `year` fornecido → usa o ano
3. Senão → usa default (ano anterior para annual, year-to-date para monthly)

### Para `/comexstat/partners`:

1. Se `period=custom` E (`periodFrom` + `periodTo`) → usa período customizado
2. Senão → usa o tipo de período especificado

## Casos de Uso Comuns

### 1. Comparar trimestres de exportação
```bash
# Q1 2020
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&periodFrom=2020-01&periodTo=2020-03&flow=export'

# Q2 2020
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&periodFrom=2020-04&periodTo=2020-06&flow=export'
```

### 2. Top 10 países parceiros em um período específico
```bash
curl 'http://localhost:3000/comexstat/partners?period=custom&periodFrom=2020-06&periodTo=2020-12&flow=current&topN=10'
```

### 3. Produtos mais exportados no ano atual até agora
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&flow=export&aggregation=ncm&topN=20'
```

### 4. Análise anual consolidada
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=annual&year=2020&flow=export'
```

## Benefícios da Nova Abordagem

✅ **Mais simples**: `periodFrom` e `periodTo` ao invés de `period[from]` e `period[to]`
✅ **Funciona no Swagger**: Campos simples que aparecem corretamente na UI
✅ **Fácil de usar no navegador**: URLs mais limpas e intuitivas
✅ **Menos erros**: Não precisa se preocupar com aninhamento de objetos
✅ **Cache correto**: Sempre inclui o período exato na chave de cache
