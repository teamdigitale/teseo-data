# teseo-data

Repository per la gestione e l'analisi dei dati del progetto Teseo (PA digitale 2026).

## Requisiti

- [Bun](https://bun.sh) (per gli script TypeScript)
- Python 3.11+ (per l'anonymizer)

```bash
bun install
pip install -r scripts/anonymizer/requirements.txt
python -m spacy download it_core_news_lg
python -m spacy download en_core_web_lg
```

---

## Scripts

### 1. Anonymizer (`scripts/anonymizer/presidio.py`)

Anonimizza i case di assistenza rimuovendo dati personali (PII) e filtrando contenuti non utili per la knowledge base.

**Pipeline:**
1. **Presidio** - Rileva e sostituisce PII (nomi, email, CF, IBAN, telefoni, indirizzi)
2. **Denylist** - Filtra risposte con frasi generiche (es. "attendere", "in lavorazione")
3. **AI (OVH)** - Valida se il contenuto è utile + trova PII mancanti

**Input:**
```
scripts/anonymizer/input/case.csv
```

**Output:**
```
data/anonymized/case_anonymized_YYYY_MM_DD.csv  # File giornaliero
data/anonymized/output_case.csv                  # File master (append, no duplicati)
```

**Esecuzione:**
```bash
# Processa tutto
python3 scripts/anonymizer/presidio.py

# Test con N righe
python3 scripts/anonymizer/presidio.py --test 50
```

**GitHub Action:** `.github/workflows/anonymizer.yml` (manual trigger)

---

### 2. Fetch Langfuse (`scripts/fetch-langfuse/`)

Recupera le domande dal chatbot (via Langfuse) e le classifica in **categorie predefinite**.

**Categorie:** Definite in `scripts/fetch-langfuse/config.ts`

**Output:**
```
data/categories_stats_YYYY_MM_DD.csv  # Stats giornaliere
data/categories_stats.csv             # Aggregato totale
data/uncategorized_questions.csv      # Domande "Altro"
```

**Esecuzione:**
```bash
bun run scripts/fetch-langfuse/index.ts
```

**GitHub Action:** `.github/workflows/langfuse.yml`

---

### 3. Fetch Langfuse Experimental (`scripts/fetch-langfuse-exp.ts`)

Come fetch-langfuse, ma l'AI **genera autonomamente le categorie** analizzando semanticamente le domande.

**Output:**
```
data/exp/categories_stats_YYYY_MM_DD.csv  # Stats giornaliere (categorie auto-generate)
data/exp/categories_stats.csv             # Top 10 categorie aggregate
```

**Esecuzione:**
```bash
bun run scripts/fetch-langfuse-exp.ts
```

---
