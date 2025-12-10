# --- Fix compatibilità collections.Hashable su Python 3.11+ ---
import collections
from collections.abc import Hashable
collections.Hashable = Hashable  # type: ignore

# --- Import principali ---
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from faker import Faker

# Inizializza Faker (locale italiano) e motori Presidio
fake = Faker("it_IT")
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Dizionari per mantenere coerenza (stesso valore originale -> stessa sostituzione)
name_map = {}
email_map = {}
phone_map = {}
iban_map = {}
generic_map = {}

def get_or_create(mapping, key, generator):
    if key not in mapping:
        mapping[key] = generator()
    return mapping[key]

def build_operators():
    """
    Configurazione base degli operatori.
    I valori 'new_value' verranno aggiornati dinamicamente per ogni entità trovata.
    """
    return {
        "PERSON": OperatorConfig("replace", {"new_value": None}),
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": None}),
        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": None}),
        "IBAN_CODE": OperatorConfig("replace", {"new_value": None}),
        "DEFAULT": OperatorConfig("replace", {"new_value": None}),
    }

def apply_dynamic_value(entity_type: str, original: str) -> str:
    """
    Sceglie il valore fake in base al tipo di entità
    e mantiene coerenza per lo stesso testo originale.
    """
    et = entity_type.upper()

    if et == "PERSON":
        return get_or_create(name_map, original, lambda: fake.name())
    if et == "EMAIL_ADDRESS":
        return get_or_create(email_map, original, lambda: fake.email())
    if et == "PHONE_NUMBER":
        return get_or_create(phone_map, original, lambda: fake.phone_number())
    if et == "IBAN_CODE":
        return get_or_create(iban_map, original, lambda: fake.iban())

    # Fallback generico per altri tipi (LOCATION, ORGANIZATION, ecc.)
    return get_or_create(generic_map, original, lambda: f"VALORE_{et}_FAKE")

def clean_sensitive_data_with_faker(text: str) -> str:
    """
    Anonimizza i dati sensibili in un testo sostituendoli con valori fittizi ma coerenti.
    Adatto per ticket di help desk che verranno usati come contesto LLM.
    """
    # Rileva tutte le PII supportate
    results = analyzer.analyze(
        text=text,
        entities=None,    # None = tutti i tipi noti a Presidio
        language="en"     # usa "it" se configuri un modello italiano compatibile
    )

    operators = build_operators()

    # Imposta i valori di sostituzione per ogni entità trovata
    for r in results:
        etype = r.entity_type
        original_value = text[r.start:r.end]
        fake_value = apply_dynamic_value(etype, original_value)
        operators[etype] = OperatorConfig("replace", {"new_value": fake_value})

    # Anonimizza il testo
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators
    )

    return anonymized_result.text

# --- Gestione file a blocchi per testi molto grandi ---

CHUNK_SIZE = 80_000  # caratteri per blocco, puoi regolare (50k–100k va bene in genere)

def anonymize_file_chunked(input_path: str, output_path: str):
    """
    Legge un file di testo molto grande, lo spezza in blocchi,
    anonimizza ogni blocco e scrive il risultato su un nuovo file.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

    cleaned_chunks = []
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks, start=1):
        print(f"Anonimizzo chunk {i}/{total_chunks} (len={len(chunk)})...")
        cleaned_chunk = clean_sensitive_data_with_faker(chunk)
        cleaned_chunks.append(cleaned_chunk)

    cleaned_text = "".join(cleaned_chunks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    print(f"File anonimizzato salvato in: {output_path}")

# --- Entry point ---

import os
from datetime import datetime

INPUT_DIR = "scripts/anonymizer/input"
OUTPUT_DIR = "data/anonymized"


def get_timestamp() -> str:
    now = datetime.now()
    return now.strftime("%Y_%m_%d")


def get_output_filename(input_file: str) -> str:
    name, ext = os.path.splitext(input_file)
    timestamp = get_timestamp()
    return f"{name}_anonymized_{timestamp}{ext}"


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def anonymize_first_n_lines(input_path: str, output_path: str, n: int = 100):
    """
    Legge solo le prime n righe del file, le anonimizza e salva il risultato.
    Utile per test (es. prime 100 righe).
    """
    lines = []
    with open(input_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            lines.append(line)

    text = "".join(lines)
    cleaned = clean_sensitive_data_with_faker(text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned)

    print(f"Prime {n} righe anonimizzate salvate in: {output_path}")


def get_input_files() -> list[str]:
    """Trova tutti i file supportati nella cartella input."""
    if not os.path.exists(INPUT_DIR):
        print(f"Input directory not found: {INPUT_DIR}")
        return []
    
    files = os.listdir(INPUT_DIR)
    return [f for f in files if f.endswith(('.csv', '.txt', '.json'))]


def main():
    print("=== Anonymizer (Presidio) ===\n")
    
    ensure_output_dir()
    
    input_files = get_input_files()
    
    if not input_files:
        print(f"No files found in {INPUT_DIR}")
        print("Supported formats: .csv, .txt, .json")
        print(f"\nPlace your files in the '{INPUT_DIR}' folder and run again.")
        return
    
    print(f"Found {len(input_files)} file(s) to process:\n")
    
    for input_file in input_files:
        # Reset le mappe per ogni file
        global name_map, email_map, phone_map, iban_map, generic_map
        name_map = {}
        email_map = {}
        phone_map = {}
        iban_map = {}
        generic_map = {}
        
        input_path = os.path.join(INPUT_DIR, input_file)
        output_file = get_output_filename(input_file)
        output_path = os.path.join(OUTPUT_DIR, output_file)
        
        anonymize_file_chunked(input_path, output_path)
    
    print("\n=== Done! ===")


if __name__ == "__main__":
    import sys
    
    if "--test" in sys.argv:
        # Modalità test
        n = 100
        if "-n" in sys.argv:
            n_index = sys.argv.index("-n")
            if n_index + 1 < len(sys.argv):
                n = int(sys.argv[n_index + 1])
        
        ensure_output_dir()
        input_files = get_input_files()
        
        if input_files:
            for input_file in input_files:
                input_path = os.path.join(INPUT_DIR, input_file)
                name, ext = os.path.splitext(input_file)
                output_file = f"{name}_anonymized_test_{n}{ext}"
                output_path = os.path.join(OUTPUT_DIR, output_file)
                anonymize_first_n_lines(input_path, output_path, n)
    else:
        main()
