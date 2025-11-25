import os
import time
import requests
import csv
from collections import Counter

# ==========================
# CONFIG LANGFUSE
# ==========================

HOST = "https://cloud.langfuse.com"
PROJECT_ID = "cmgzcrc2v001fad07ruyu7nam"
PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-7f5e1148-4010-45fe-927c-6eb5ab7afc13")
SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-80032470-9994-4964-96b6-b87c7f3bf33e")
TRACE_ENDPOINT = f"{HOST}/api/public/traces"
HEAD_ACCEPT = {"Accept": "application/json"}
DEFAULT_LIMIT = 100

# ==========================
# CONFIG OPENAI
# ==========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-...")
OPENAI_API_URL = os.getenv(OPENAI_API_URL,"https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.getenv(OPENAI_MODEL,"gpt-4o")
SLEEP_BETWEEN_CALLS = 0.2  # secondi

def perform_request(method, url, headers=None, auth=None, params=None,
                    timeout=30, allow_redirects=False):
    return requests.request(
        method,
        url,
        headers=headers,
        auth=auth,
        params=params,
        timeout=timeout,
        allow_redirects=allow_redirects,
    )

def extract_trace_fields(trace):
    input_query = None
    if isinstance(trace.get("input"), dict):
        input_query = trace["input"].get("query")
    else:
        input_query = trace.get("input.query") or trace.get("input_query")
    return input_query

def iterate_all_traces(endpoint, project_id, auth, headers=None, limit=DEFAULT_LIMIT):
    headers = headers or HEAD_ACCEPT
    params = {"projectId": project_id, "limit": limit}
    all_traces = []
    cursor = None
    page = 1

    while True:
        if cursor:
            params = {"projectId": project_id, "limit": limit, "cursor": cursor}
        else:
            params = {"projectId": project_id, "limit": limit, "page": page}

        resp = perform_request(
            "GET",
            endpoint,
            headers=headers,
            auth=auth,
            params=params,
            allow_redirects=True,
        )
        j = resp.json()
        traces = None
        if isinstance(j, dict):
            if "data" in j and isinstance(j["data"], list):
                traces = j["data"]
            elif isinstance(j.get("traces"), list):
                traces = j["traces"]
            elif isinstance(j.get("items"), list):
                traces = j["items"]
            elif isinstance(j.get("results"), list):
                traces = j["results"]
        elif isinstance(j, list):
            traces = j

        if traces is None:
            break

        all_traces.extend(traces)

        meta = j.get("meta") or j.get("pagination") or {}
        next_cursor = None
        if isinstance(meta, dict):
            next_cursor = (
                meta.get("nextCursor")
                or meta.get("next_cursor")
                or meta.get("cursor")
                or meta.get("next")
            )
            if isinstance(next_cursor, int):
                page = int(next_cursor) + 1
                next_cursor = None

        if next_cursor:
            cursor = next_cursor
            continue

        if len(traces) < limit:
            break
        page += 1

    return all_traces

def langfuse_questions():
    auth = (PUBLIC_KEY.strip(), SECRET_KEY.strip())
    traces = iterate_all_traces(
        TRACE_ENDPOINT,
        PROJECT_ID,
        auth,
        headers=HEAD_ACCEPT,
        limit=DEFAULT_LIMIT,
    )
    questions = []
    for t in traces:
        if isinstance(t, dict):
            q = extract_trace_fields(t)
            if isinstance(q, str) and q.strip():
                questions.append(q.strip())
    return questions[:20]  # solo prime 20 domande

def classify_with_chatgpt4(question: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY non impostata nelle variabili d'ambiente."
        )

    system_prompt = (
        "Sei un esperto classificatore di domande per un chatbot interno di un dipartimento digitale collegato a tematiche e servizi legati alle misure PNRR. "
        "Il tuo compito è assegnare a ciascuna domanda UNA categoria che riassuma il suo tema principale. "
        "Cerca di aggregare e raggruppare il più possibile i temi simili sotto la stessa categoria generale. "
        "Evita di usare categorie troppo specifiche: cerca di normalizzare i titoli, utilizzando etichette che possano raggruppare domande anche diverse ma simili (ad esempio: 'Pagamenti', 'Digitalizzazione', 'Assistenza', 'Contratti', 'Cloud', 'Ruoli/Governance', ecc.). "
        "Rispondi solo con il nome della categoria aggregata, senza ulteriori spiegazioni."
    )

    user_prompt = (
        f"Domanda utente:\n{question}\n\n"
        "Rispondi indicando solamente la categoria più adatta per classificare questa domanda."
    )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 16,
        "temperature": 0.0,
        "top_p": 1.0,
    }

    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    return content

def export_classification_to_csv(labels, outfile="classificazione_output.csv"):
    counts = Counter(labels)
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Classe", "Numero di domande"])
        for classe, numero in counts.items():
            writer.writerow([classe, numero])

def main():
    questions = langfuse_questions()
    labels = []
    for q in questions:
        label = classify_with_chatgpt4(q)
        labels.append(label)
        time.sleep(SLEEP_BETWEEN_CALLS)

    export_classification_to_csv(labels, "classificazione_output.csv")

if __name__ == "__main__":
    main()
