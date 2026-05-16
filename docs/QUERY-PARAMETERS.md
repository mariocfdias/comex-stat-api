# Como usar Query Parameters para Períodos

## O Problema

A rota `/comexstat/products` é **GET**, não **POST**. Requests GET usam **query parameters**, não body JSON.

## ❌ Errado - Enviar JSON no body

```json
// Isso NÃO funciona em GET requests
{
  "from": "2010-02",
  "to": "2010-08"
}
```

**Resultado:** `period: undefined` ❌

## ✅ Correto - Usar query parameters

### Formato da URL:
```
GET /comexstat/products?period[from]=2010-02&period[to]=2010-08&periodicity=monthly
```

### Exemplos Práticos:

#### 1. Período mensal específico:
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&period[from]=2010-02&period[to]=2010-08&flow=export&aggregation=ncm&topN=20'
```

**Logs esperados:**
```
[DEBUG] Recebido - year: undefined, period: {"from":"2010-02","to":"2010-08"}
[DEBUG] periodInput selecionado: {"from":"2010-02","to":"2010-08"}
[DEBUG] Strategy monthly: queryPeriod={"from":"2010-02","to":"2010-08"}
```

#### 2. Ano específico (anual):
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=annual&year=2010&flow=export&aggregation=ncm&topN=20'
```

#### 3. Sem parâmetros (usa defaults):
```bash
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&flow=export&aggregation=ncm&topN=20'
```

**Resultado:** Usa year-to-date (janeiro até mês atual)

## Como usar no Swagger UI

### Problema no Swagger:
O Swagger UI pode mostrar um campo de "body" para objetos complexos, mas **ignore isso para GET requests**.

### Solução:

1. **Encontre os campos de query parameters** na interface do Swagger
2. Preencha cada campo individualmente:
   - `periodicity`: `monthly`
   - `period.from`: `2010-02`
   - `period.to`: `2010-08`
   - `flow`: `export`
   - `aggregation`: `ncm`
   - `topN`: `20`

3. **OU** use a opção "Try it out" e edite a URL diretamente:
   ```
   /comexstat/products?periodicity=monthly&period[from]=2010-02&period[to]=2010-08&flow=export&aggregation=ncm&topN=20
   ```

## Formato de Query Parameters para Objetos Aninhados

No NestJS, objetos aninhados em query parameters usam a notação de colchetes:

```
?period[from]=2010-02&period[to]=2010-08
```

Isso é automaticamente transformado em:
```typescript
period: {
  from: "2010-02",
  to: "2010-08"
}
```

## Referência Rápida

| Parâmetro | Tipo | Exemplo | Obrigatório |
|-----------|------|---------|-------------|
| `periodicity` | string | `monthly` ou `annual` | Não (default: `annual`) |
| `period[from]` | string | `2010-02` | Somente para períodos customizados |
| `period[to]` | string | `2010-08` | Somente para períodos customizados |
| `year` | number | `2010` | Não (default: ano anterior) |
| `flow` | string | `export` ou `import` | Não (default: `export`) |
| `aggregation` | string | `ncm`, `heading`, `chapter` | Não (default: `heading`) |
| `topN` | number | `20` | Não (default: `20`) |

## Exemplos Completos

### Caso de Uso 1: Comparar trimestres
```bash
# Q1 2020
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&period[from]=2020-01&period[to]=2020-03&flow=export'

# Q2 2020
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&period[from]=2020-04&period[to]=2020-06&flow=export'
```

### Caso de Uso 2: Dados anuais
```bash
# 2019
curl 'http://localhost:3000/comexstat/products?periodicity=annual&year=2019&flow=export'

# 2020
curl 'http://localhost:3000/comexstat/products?periodicity=annual&year=2020&flow=export'
```

### Caso de Uso 3: Year-to-date
```bash
# Do início do ano até agora
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&flow=export'
```
