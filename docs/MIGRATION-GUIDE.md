# Guia de Migração - Parâmetros Normalizados

## 📋 Resumo das Mudanças

Todos os endpoints que aceitavam objetos aninhados com `from` e `to` foram normalizados para usar parâmetros simples: `periodFrom` e `periodTo`.

## 🔄 Endpoints Atualizados

### 1. `/comexstat/products`

**Antes:**
```
?period[from]=2010-02&period[to]=2010-08
```

**Agora:**
```
?periodFrom=2010-02&periodTo=2010-08
```

**Exemplo completo:**
```bash
# Antes (não funcionava bem)
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&period[from]=2010-02&period[to]=2010-08'

# Agora (funciona perfeitamente!)
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&periodFrom=2010-02&periodTo=2010-08'
```

### 2. `/comexstat/partners`

**Antes:**
```
?period=custom&customPeriod[from]=2010-02&customPeriod[to]=2010-08
```

**Agora:**
```
?period=custom&periodFrom=2010-02&periodTo=2010-08
```

**Exemplo completo:**
```bash
# Antes
curl 'http://localhost:3000/comexstat/partners?period=custom&customPeriod[from]=2010-02&customPeriod[to]=2010-08'

# Agora
curl 'http://localhost:3000/comexstat/partners?period=custom&periodFrom=2010-02&periodTo=2010-08'
```

### 3. `/comexstat/summary`

**Antes:**
```
?period=custom&customPeriod[from]=2010-02&customPeriod[to]=2010-08
```

**Agora:**
```
?period=custom&periodFrom=2010-02&periodTo=2010-08
```

**Exemplo completo:**
```bash
# Antes
curl 'http://localhost:3000/comexstat/summary?period=custom&customPeriod[from]=2010-02&customPeriod[to]=2010-08'

# Agora
curl 'http://localhost:3000/comexstat/summary?period=custom&periodFrom=2010-02&periodTo=2010-08'
```

## ✅ Endpoints que JÁ estavam corretos

Esses endpoints já usavam parâmetros simples e **não precisam de mudanças**:

### `/comexstat/summary-history`
```bash
curl 'http://localhost:3000/comexstat/summary-history?from=2024-01&to=2024-12'
```

### `/comexstat/national-comparison`
```bash
curl 'http://localhost:3000/comexstat/national-comparison?from=2024-01&to=2024-12&flow=export'
```

## 📊 Comparação Visual

| Endpoint | Parâmetro Antigo | Parâmetro Novo | Status |
|----------|------------------|----------------|--------|
| `/products` | `period[from]`, `period[to]` | `periodFrom`, `periodTo` | ✅ Atualizado |
| `/partners` | `customPeriod[from]`, `customPeriod[to]` | `periodFrom`, `periodTo` | ✅ Atualizado |
| `/summary` | `customPeriod[from]`, `customPeriod[to]` | `periodFrom`, `periodTo` | ✅ Atualizado |
| `/summary-history` | `from`, `to` | `from`, `to` | ✅ Já estava OK |
| `/national-comparison` | `from`, `to` | `from`, `to` | ✅ Já estava OK |

## 🎯 Benefícios

1. **Consistência**: Todos os endpoints agora seguem o mesmo padrão
2. **Simplicidade**: Parâmetros planos são mais fáceis de usar
3. **Swagger UI**: Funciona perfeitamente sem objetos aninhados
4. **URLs mais limpas**: Sem colchetes na URL
5. **Menos erros**: Mais intuitivo para os desenvolvedores

## 🧪 Testes

Todos os testes foram atualizados e estão passando:
- ✅ Controller tests (2 testes)
- ✅ Service tests (4 testes)
- ✅ Strategy tests (11 testes)

**Total: 17 testes passando**

## 📝 Notas de Implementação

### Como funciona internamente:

Os parâmetros `periodFrom` e `periodTo` são automaticamente convertidos em um objeto `PeriodDto` no controller:

```typescript
let customPeriod: PeriodDto | undefined;

if (query.periodFrom && query.periodTo) {
  customPeriod = {
    from: query.periodFrom,
    to: query.periodTo,
  };
}
```

### Validações:

- Ambos `periodFrom` e `periodTo` devem ser fornecidos juntos
- Formato esperado: `YYYY-MM` (ex: `2010-02`)
- Se apenas um for fornecido, será ignorado e usará o período padrão

## 🚀 Exemplos de Uso

### Caso 1: Análise trimestral
```bash
# Q1 2020
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&periodFrom=2020-01&periodTo=2020-03'

# Q2 2020
curl 'http://localhost:3000/comexstat/products?periodicity=monthly&periodFrom=2020-04&periodTo=2020-06'
```

### Caso 2: Comparação semestral
```bash
# Primeiro semestre
curl 'http://localhost:3000/comexstat/partners?period=custom&periodFrom=2020-01&periodTo=2020-06'

# Segundo semestre
curl 'http://localhost:3000/comexstat/partners?period=custom&periodFrom=2020-07&periodTo=2020-12'
```

### Caso 3: Período customizado específico
```bash
# Apenas verão (Jun-Ago)
curl 'http://localhost:3000/comexstat/summary?period=custom&periodFrom=2020-06&periodTo=2020-08'
```

## 🔍 Troubleshooting

### Problema: "period: undefined"
**Solução**: Certifique-se de usar `periodFrom` e `periodTo`, não `period[from]` e `period[to]`

### Problema: "Usando default ao invés do período especificado"
**Solução**: Forneça AMBOS `periodFrom` E `periodTo`. Se fornecer apenas um, ambos serão ignorados.

### Problema: "Dados errados sendo retornados"
**Solução**: Limpe o cache com `DELETE /comexstat/cache` ou reinicie o servidor.

## 📚 Referências

- [API Usage Guide](./API-USAGE.md)
- [Period Strategy Pattern](./PERIOD-STRATEGY.md)
- [Query Parameters Guide](./QUERY-PARAMETERS.md)
