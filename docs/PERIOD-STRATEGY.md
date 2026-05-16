# Period Strategy Pattern

Este documento explica como funciona o padrão Strategy implementado para lidar com períodos mensais e anuais.

## Visão Geral

O padrão Strategy foi implementado para separar claramente a lógica de:
- **Periodicidade Anual**: usa anos inteiros (janeiro a dezembro)
- **Periodicidade Mensal**: usa períodos específicos (ex: junho a julho)

## Estratégias Disponíveis

### 1. AnnualPeriodStrategy

Usada quando `periodicity=annual`

**Comportamento:**
- ✅ Aceita um **ano** (número): `year=2020` → `{from: "2020-01", to: "2020-12"}`
- ✅ Aceita **undefined**: usa ano anterior → `{from: "2023-01", to: "2023-12"}` (se ano atual é 2024)
- ❌ **NÃO aceita** PeriodDto (lança erro)
- 📊 `monthDetail = false`

**Exemplos de uso:**
```bash
# Produtos de 2020 (ano inteiro)
GET /comexstat/products?periodicity=annual&year=2020

# Produtos do ano anterior (padrão)
GET /comexstat/products?periodicity=annual
```

### 2. MonthlyPeriodStrategy

Usada quando `periodicity=monthly`

**Comportamento:**
- ✅ Aceita **PeriodDto** (objeto): `period[from]=2020-06&period[to]=2020-07` → `{from: "2020-06", to: "2020-07"}`
- ✅ Aceita **ano** (backward compatibility): `year=2020` → `{from: "2020-01", to: "2020-12"}`
- ✅ Aceita **undefined**: usa year-to-date → `{from: "2024-01", to: "2024-06"}` (se mês atual é junho)
- 📊 `monthDetail = true`

**Exemplos de uso:**
```bash
# Produtos de junho a julho de 2020 (meses específicos)
GET /comexstat/products?periodicity=monthly&period[from]=2020-06&period[to]=2020-07

# Produtos de 2020 com detalhamento mensal (ano inteiro)
GET /comexstat/products?periodicity=monthly&year=2020

# Produtos do ano-até-agora com detalhamento mensal
GET /comexstat/products?periodicity=monthly
```

## Cache

A chave de cache **sempre inclui o período exato** que será consultado:

**Antes (bugado):**
```json
{
  "period": 2020,  // ❌ Ambíguo! Não inclui os meses
  "periodicity": "monthly"
}
```

**Agora (correto):**
```json
{
  "period": {
    "from": "2020-06",
    "to": "2020-07"
  },
  "periodicity": "monthly"
}
```

## Diferenças entre Anual e Mensal

| Aspecto | Annual | Monthly |
|---------|--------|---------|
| **Parâmetro preferido** | `year` (número) | `period` (objeto) |
| **Default (sem params)** | Ano anterior inteiro | Year-to-date |
| **monthDetail na API** | `false` | `true` |
| **Retorno da API** | Dados agregados | Dados separados por mês |
| **Cache** | Um por ano | Um por período específico |

## Exemplos Práticos

### Caso 1: Comparar exportações de dois trimestres

```bash
# Q1 2020 (jan-mar)
GET /comexstat/products?periodicity=monthly&period[from]=2020-01&period[to]=2020-03

# Q2 2020 (abr-jun)
GET /comexstat/products?periodicity=monthly&period[from]=2020-04&period[to]=2020-06
```

✅ Cada trimestre terá seu próprio cache
✅ Retorna dados mensais separados

### Caso 2: Dados anuais consolidados

```bash
# 2019
GET /comexstat/products?periodicity=annual&year=2019

# 2020
GET /comexstat/products?periodicity=annual&year=2020
```

✅ Cada ano terá seu próprio cache
✅ Retorna dados consolidados do ano inteiro

## Benefícios da Implementação

1. **Separação de Responsabilidades**: Cada estratégia cuida apenas da sua lógica específica
2. **Testabilidade**: Estratégias podem ser testadas isoladamente
3. **Manutenibilidade**: Fácil adicionar novos tipos de periodicidade (trimestral, semestral, etc.)
4. **Cache Correto**: Períodos diferentes sempre geram caches diferentes
5. **Código Limpo**: Sem if/else aninhados para cada caso
