# Endpoint: /comexstat/partners

## Tipos de Período Suportados

O endpoint `/comexstat/partners` agora suporta **4 tipos de período**:

### 1. `currentMonth` (Mês Atual)
Retorna dados do mês anterior mais recente com dados disponíveis.

```bash
curl 'http://localhost:3000/comexstat/partners?period=currentMonth&flow=export'
```

**Período calculado**: Mês anterior (ex: se hoje é Jan/2026, usa Nov/2025)

### 2. `yearToDate` (Ano até Agora) - **DEFAULT**
Retorna dados do início do ano até o mês atual.

```bash
curl 'http://localhost:3000/comexstat/partners?period=yearToDate&flow=export'
```

**Período calculado**: Janeiro até o mês atual (ex: Jan-Nov/2025)

### 3. `lastYear` (Ano Anterior) - **NOVO! ✨**
Retorna dados do ano anterior completo.

```bash
curl 'http://localhost:3000/comexstat/partners?period=lastYear&flow=export'
```

**Período calculado**: Ano anterior completo (ex: Jan-Dez/2024)

### 4. `custom` (Período Customizado)
Permite especificar qualquer período usando `periodFrom` e `periodTo`.

```bash
curl 'http://localhost:3000/comexstat/partners?period=custom&periodFrom=2020-06&periodTo=2020-12&flow=export'
```

**Período calculado**: O período exato especificado

## Parâmetros

| Parâmetro | Tipo | Valores | Default | Obrigatório |
|-----------|------|---------|---------|-------------|
| `period` | enum | `currentMonth`, `yearToDate`, `lastYear`, `custom` | `yearToDate` | Não |
| `periodFrom` | string | `YYYY-MM` (ex: `2020-06`) | - | Sim, se `period=custom` |
| `periodTo` | string | `YYYY-MM` (ex: `2020-12`) | - | Sim, se `period=custom` |
| `flow` | enum | `export`, `import`, `current` | `current` | Não |
| `topN` | number | Qualquer inteiro positivo | `10` | Não |

## Exemplos de Uso

### Exemplo 1: Top 10 parceiros do ano anterior
```bash
curl 'http://localhost:3000/comexstat/partners?period=lastYear&flow=current&topN=10'
```

**Retorna**: Os 10 principais países parceiros (importação + exportação) do ano passado completo.

### Exemplo 2: Exportações do ano até agora
```bash
curl 'http://localhost:3000/comexstat/partners?period=yearToDate&flow=export&topN=15'
```

**Retorna**: Os 15 principais destinos de exportação de janeiro até o mês atual.

### Exemplo 3: Importações de um trimestre específico
```bash
curl 'http://localhost:3000/comexstat/partners?period=custom&periodFrom=2020-01&periodTo=2020-03&flow=import&topN=20'
```

**Retorna**: Os 20 principais países de origem de importação no Q1/2020.

### Exemplo 4: Mês mais recente disponível
```bash
curl 'http://localhost:3000/comexstat/partners?period=currentMonth&flow=current'
```

**Retorna**: Os 10 principais parceiros comerciais do mês anterior mais recente.

## Formato de Resposta

```json
{
  "success": true,
  "data": [
    {
      "country": "Estados Unidos",
      "exports": 150.5,      // em milhões de USD
      "imports": 200.3,      // em milhões de USD
      "current": 350.8,      // soma de exports + imports
      "balance": -49.8,      // exports - imports
      "percentage": 25.5     // % do total
    },
    // ... mais países
  ]
}
```

## Comparação com `/summary`

| Aspecto | `/partners` | `/summary` |
|---------|-------------|------------|
| **Suporta `lastYear`?** | ✅ Sim | ✅ Sim |
| **Suporta `currentMonth`?** | ✅ Sim | ✅ Sim |
| **Suporta `yearToDate`?** | ✅ Sim | ✅ Sim |
| **Suporta `custom`?** | ✅ Sim | ✅ Sim |
| **Dados retornados** | Lista de países | Totais agregados |
| **Parâmetro `flow`** | `export`, `import`, `current` | N/A (sempre retorna ambos) |
| **Parâmetro `topN`** | ✅ Sim (padrão: 10) | ❌ Não |

## Testes

✅ **5 testes passando** para `getPartnerCountries`:
1. ✅ Should be defined
2. ✅ Should generate different queries for different custom periods
3. ✅ Should support LAST_YEAR period type
4. ✅ Should handle CURRENT_MONTH correctly
5. ✅ Should handle YEAR_TO_DATE correctly

## Changelog

### v2.0.0 (2026-01-31)
- ✨ **Novo**: Suporte para `period=lastYear`
- ✨ **Novo**: Parâmetros simplificados `periodFrom` e `periodTo`
- 🐛 **Fix**: Cache agora inclui o período exato
- 🐛 **Fix**: Logs melhorados para debug

### v1.0.0
- Suporte inicial para `currentMonth`, `yearToDate`, `custom`
- Parâmetro `customPeriod` (objeto aninhado - descontinuado)
