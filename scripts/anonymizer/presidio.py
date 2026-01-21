#!/usr/bin/env python3
"""
Presidio-based anonymization script for case.csv
Replaces PII with tags, filters noisy rows, and uses AI to validate useful content.

Usage:
    python presidio.py              # Process all rows
    python presidio.py --test 50    # Process only first 50 rows (test mode)
"""

import argparse
import csv
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
INPUT_FILE = SCRIPT_DIR / "input" / "case.csv"
OUTPUT_DIR = SCRIPT_DIR.parent.parent / "data" / "anonymized"

# Entity types to detect and anonymize
ENTITY_TYPES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IBAN_CODE",
    "IT_FISCAL_CODE",
    "LOCATION",
    "IT_IDENTITY_CARD",
    "IT_DRIVER_LICENSE",
    "IT_PASSPORT",
    "IT_VAT_CODE",
    "CREDIT_CARD",
]

# Mapping from Presidio entity types to our tag names
TAG_MAPPING = {
    "PERSON": "FAKE_PERSON",
    "EMAIL_ADDRESS": "FAKE_EMAIL",
    "PHONE_NUMBER": "FAKE_PHONE",
    "IBAN_CODE": "FAKE_IBAN",
    "IT_FISCAL_CODE": "FAKE_CODICE_FISCALE",
    "LOCATION": "FAKE_INDIRIZZO",
    "IT_IDENTITY_CARD": "FAKE_DOCUMENTO",
    "IT_DRIVER_LICENSE": "FAKE_DOCUMENTO",
    "IT_PASSPORT": "FAKE_DOCUMENTO",
    "IT_VAT_CODE": "FAKE_PARTITA_IVA",
    "CREDIT_CARD": "FAKE_CARTA_CREDITO",
}

# Threshold for tag percentage (rows with >= this % of tags will be removed)
TAG_THRESHOLD = 0.6

# Denylist: frasi nella risposta che indicano contenuto non utile
DENYLIST_FRASI_RISPOSTA = [
    # Rinvii al fornitore
    "giro al fornitore",
    "inoltro al fornitore",
    "rivolgersi al fornitore",
    # Attesa generica
    "in lavorazione",
    "in elaborazione",
    "in fase di processamento",
    # Ricontatti
    "la contatteremo",
    "verrà ricontattato",
    "sarà ricontattato",
    # Mancanza di tempistica
    "non esiste una tempistica standard",
    "non esiste un tempo standard",
    "tempistica non definita",
    # Attesa pura
    "attendere",
    "si prega di attendere",
    "rimaniamo in attesa",
    # Rimandi a terzi
    "contatta il tuo account manager",
    "rivolgiti a",
    "contatta il supporto",
    # Impossibilità
    "non è possibile modificare",
    "non è consentito modificare",
    "non è permesso",
    # Fuori perimetro
    "questo è fuori dal perimetro",
    "non rientra nelle nostre competenze",
    "esula dalle nostre competenze",
    # Rimandi a risorse esterne
    "per supporto più operativo",
    "consulta la documentazione",
    "si rimanda alla documentazione",
    # Rimandi a piattaforme
    "contatta ipa",
    "contatta anac",
    "contatta pagopa",
    "contatta pdnd",
    "contatta appio",
    # Genericità su verifiche
    "è in fase di verifica",
    "nessuna azione richiesta",
    "non è richiesta alcuna azione",
    # Genericità varia
    "non abbiamo informazioni",
    "non possiamo fornire dettagli",
    "non sappiamo dirvi",
]


def contains_denylist_phrase(text: str) -> Optional[str]:
    """
    Check if text contains any phrase from the denylist.
    Returns the matched phrase if found, None otherwise.
    """
    if not text:
        return None
    
    text_lower = text.lower()
    for phrase in DENYLIST_FRASI_RISPOSTA:
        if phrase.lower() in text_lower:
            return phrase
    return None


def create_italian_phone_recognizer() -> PatternRecognizer:
    """Create a custom recognizer for Italian phone numbers."""
    patterns = [
        # Cellulari italiani: +39 3xx xxx xxxx o 3xx xxx xxxx
        Pattern(
            name="italian_mobile",
            regex=r"(?:\+39\s?)?3[0-9]{2}[\s.-]?[0-9]{3}[\s.-]?[0-9]{4}",
            score=0.9,
        ),
        # Numeri fissi italiani: +39 0xx xxx xxxx o 0xx xxx xxxx
        Pattern(
            name="italian_landline",
            regex=r"(?:\+39\s?)?0[0-9]{1,3}[\s.-]?[0-9]{5,8}",
            score=0.85,
        ),
        # Formato compatto cellulare
        Pattern(
            name="italian_mobile_compact",
            regex=r"\b3[0-9]{9}\b",
            score=0.9,
        ),
    ]
    
    return PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        patterns=patterns,
        supported_language="it",
    )


def setup_analyzer() -> AnalyzerEngine:
    """Initialize Presidio analyzer with Italian language support."""
    logger.info("Setting up Presidio analyzer with Italian NLP...")
    
    # Configure NLP engine for Italian
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [
            {"lang_code": "it", "model_name": "it_core_news_lg"},
            {"lang_code": "en", "model_name": "en_core_web_lg"},
        ],
    }
    
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
    
    # Create registry with Italian and English support
    registry = RecognizerRegistry(supported_languages=["it", "en"])
    registry.load_predefined_recognizers(
        nlp_engine=nlp_engine,
        languages=["it", "en"],
    )
    
    # Add Italian phone recognizer
    italian_phone_recognizer = create_italian_phone_recognizer()
    registry.add_recognizer(italian_phone_recognizer)
    logger.info("Added custom Italian phone number recognizer")
    
    # Create analyzer with the NLP engine and custom registry
    analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine,
        registry=registry,
        supported_languages=["it", "en"],
    )
    
    logger.info("Presidio analyzer initialized successfully")
    return analyzer


def setup_anonymizer() -> AnonymizerEngine:
    """Initialize Presidio anonymizer."""
    logger.info("Setting up Presidio anonymizer...")
    anonymizer = AnonymizerEngine()
    logger.info("Presidio anonymizer initialized successfully")
    return anonymizer


def anonymize_text(
    text: str,
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
) -> tuple[str, int, int]:
    """
    Anonymize text using Presidio, replacing PII with tags.
    
    Returns:
        tuple: (anonymized_text, num_tags, original_word_count)
    """
    if not text or not text.strip():
        return text, 0, 0
    
    # Analyze text for PII entities
    results = analyzer.analyze(
        text=text,
        entities=ENTITY_TYPES,
        language="it",
    )
    
    # Count original words (approximate)
    original_word_count = len(text.split())
    
    if not results:
        return text, 0, original_word_count
    
    # Create operator configs for each entity type
    operators = {}
    for entity_type in ENTITY_TYPES:
        tag = TAG_MAPPING.get(entity_type, f"FAKE_{entity_type}")
        operators[entity_type] = OperatorConfig("replace", {"new_value": f"[{tag}]"})
    
    # Anonymize
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )
    
    return anonymized_result.text, len(results), original_word_count


def calculate_tag_percentage(text: str) -> float:
    """Calculate the percentage of text that consists of FAKE_ tags."""
    if not text or not text.strip():
        return 0.0
    
    # Find all tags
    tag_pattern = r"\[FAKE_[A-Z_]+\]"
    tags = re.findall(tag_pattern, text)
    
    # Calculate approximate percentage based on word count
    words = text.split()
    if not words:
        return 0.0
    
    # Each tag counts as one "word" in the anonymized text
    tag_word_count = len(tags)
    total_words = len(words)
    
    return tag_word_count / total_words if total_words > 0 else 0.0


def setup_ai_client() -> Optional[OpenAI]:
    """Setup OpenAI client for OVH AI Endpoints."""
    api_url = os.getenv("OVH_API_URL")
    api_key = os.getenv("OVH_API_KEY")
    
    if not api_url or not api_key:
        logger.warning("OVH AI credentials not found in environment (OVH_API_URL, OVH_API_KEY). AI filtering disabled.")
        return None
    
    logger.info(f"Setting up OVH AI client with endpoint: {api_url}")
    
    client = OpenAI(
        base_url=api_url,
        api_key=api_key,
    )
    
    logger.info("OVH AI client initialized successfully")
    return client


AI_BATCH_SIZE = 10  # Number of rows to process in each AI batch


def ai_batch_anonymize_and_evaluate(
    client: OpenAI, 
    rows_data: list[tuple[int, str]]
) -> dict[int, tuple[Optional[str], bool]]:
    """
    Process multiple rows in a single AI call for efficiency.
    
    Args:
        client: OpenAI client
        rows_data: List of (row_index, text) tuples
    
    Returns:
        dict mapping row_index to (anonymized_text or None, is_useful)
    """
    results = {}
    
    # Filter out empty/short texts
    valid_rows = []
    for row_idx, text in rows_data:
        if not text or not text.strip():
            logger.info(f"  Row {row_idx}: Empty text, removing")
            results[row_idx] = (None, False)
        elif len(text.strip()) < 20:
            logger.info(f"  Row {row_idx}: Text too short, removing")
            results[row_idx] = (None, False)
        else:
            valid_rows.append((row_idx, text))
    
    if not valid_rows:
        return results
    
    # Build batch prompt
    batch_content = []
    for i, (row_idx, text) in enumerate(valid_rows, start=1):
        # Truncate each text to avoid token limits
        truncated = text[:2000] if len(text) > 2000 else text
        batch_content.append(f"[RIGA {row_idx}]\n{truncated}\n[/RIGA {row_idx}]")
    
    batch_text = "\n\n".join(batch_content)
    
    try:
        model = os.getenv("OVH_MODEL", "Meta-Llama-3_3-70B-Instruct")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": """Sei un assistente esperto in anonimizzazione e valutazione di testi per una knowledge base di assistenza PA (Pubblica Amministrazione) italiana, legato alle misure PNRR.

HAI DUE COMPITI PER OGNI RIGA:

## COMPITO 1: ANONIMIZZAZIONE
Trova eventuali dati personali NON ancora anonimizzati (quelli già anonimizzati hanno tag come [FAKE_PERSON], [FAKE_EMAIL], etc.).

Dati da cercare e sostituire:
- Nomi e cognomi di persone → [FAKE_PERSON]
- Email → [FAKE_EMAIL]
- Numeri di telefono → [FAKE_PHONE]
- Codici fiscali → [FAKE_CODICE_FISCALE]
- IBAN → [FAKE_IBAN]
- Indirizzi specifici (via, piazza, numero civico) → [FAKE_INDIRIZZO]
- Partite IVA → [FAKE_PARTITA_IVA]

NON sostituire: nomi di enti pubblici, PA, comuni, misure PNRR, date, codici IPA.

## COMPITO 2: VALUTAZIONE UTILITÀ
UTILE: contiene procedure, istruzioni, risposte informative, soluzioni.
NON UTILE: solo richieste senza risposta, dati personali senza contesto, messaggi generici.

## FORMATO RISPOSTA (per ogni riga)
Rispondi così per OGNI riga, una dopo l'altra:

[RISULTATO n]
UTILE: SI oppure NO
TESTO: <testo corretto con sostituzioni, oppure INVARIATO se non servono modifiche>
[/RISULTATO n]

Dove n è il numero della riga originale."""
                },
                {
                    "role": "user",
                    "content": f"Analizza queste {len(valid_rows)} righe:\n\n{batch_text}"
                }
            ],
            max_tokens=8000,
            temperature=0.1,
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Parse batch response
        import re
        pattern = r'\[RISULTATO\s*(\d+)\](.*?)\[/RISULTATO\s*\d+\]'
        matches = re.findall(pattern, answer, re.DOTALL | re.IGNORECASE)
        
        parsed_results = {}
        for match in matches:
            try:
                result_idx = int(match[0])
                content = match[1].strip()
                
                is_useful = False
                anonymized_text = None
                
                for line in content.split("\n"):
                    line = line.strip()
                    if line.upper().startswith("UTILE:"):
                        is_useful = "SI" in line.upper()
                    elif line.upper().startswith("TESTO:"):
                        text_part = line[6:].strip()
                        if text_part.upper() != "INVARIATO" and text_part:
                            anonymized_text = text_part
                
                parsed_results[result_idx] = (anonymized_text, is_useful)
            except (ValueError, IndexError):
                continue
        
        # Log results and merge with pre-filtered results
        for row_idx, text in valid_rows:
            if row_idx in parsed_results:
                anon_text, is_useful = parsed_results[row_idx]
                
                # Count AI corrections
                if anon_text:
                    original_tags = len(re.findall(r"\[FAKE_[A-Z_]+\]", text))
                    new_tags = len(re.findall(r"\[FAKE_[A-Z_]+\]", anon_text))
                    ai_added = new_tags - original_tags
                    if ai_added > 0:
                        logger.info(f"  Row {row_idx}: AI found {ai_added} additional PII")
                
                logger.info(f"  Row {row_idx}: AI = {'KEEP' if is_useful else 'REMOVE'}")
                results[row_idx] = (anon_text, is_useful)
            else:
                # If parsing failed for this row, keep it by default
                logger.warning(f"  Row {row_idx}: AI response parsing failed, keeping")
                results[row_idx] = (None, True)
        
        return results
        
    except Exception as e:
        logger.error(f"AI batch processing failed: {e}. Keeping all rows unchanged.")
        for row_idx, _ in valid_rows:
            results[row_idx] = (None, True)
        return results


def process_csv(
    input_path: Path,
    output_path: Path,
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
    ai_client: Optional[OpenAI],
    limit: Optional[int] = None,
) -> dict:
    """
    Process the CSV file, anonymizing and filtering rows.
    
    Returns:
        dict with processing statistics
    """
    stats = {
        "total_rows": 0,
        "anonymized_rows": 0,
        "filtered_by_tags": 0,
        "filtered_by_denylist": 0,
        "filtered_by_ai": 0,
        "kept_rows": 0,
        "total_entities_found": 0,
    }
    
    logger.info(f"Reading input file: {input_path}")
    
    # Read input CSV
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    total_available = len(rows)
    
    # Apply limit if specified (test mode)
    if limit is not None and limit > 0:
        rows = rows[:limit]
        logger.info(f"TEST MODE: Processing {len(rows)} of {total_available} available rows")
    
    stats["total_rows"] = len(rows)
    logger.info(f"Total rows to process: {stats['total_rows']}")
    
    processed_rows = []
    
    # Columns to anonymize (text columns)
    text_columns = [
        "Subject",
        "Description",
        "Risoluzione__c",
        "Commenti_Ente__c",
        "Ulteriori_informazioni_a_supporto__c",
        "Dettaglio_richiesta__c",
    ]
    
    logger.info("=" * 60)
    logger.info("PHASE 1: Anonymization with Presidio")
    logger.info("=" * 60)
    
    for i, row in enumerate(rows, start=1):
        logger.info(f"Processing row {i}/{stats['total_rows']}...")
        
        row_total_entities = 0
        anonymized_row = row.copy()
        combined_text = ""
        
        # Anonymize each text column
        for col in text_columns:
            if col in row and row[col]:
                original_text = row[col]
                anonymized_text, num_entities, _ = anonymize_text(
                    original_text, analyzer, anonymizer
                )
                anonymized_row[col] = anonymized_text
                row_total_entities += num_entities
                combined_text += " " + anonymized_text
                
                if num_entities > 0:
                    logger.info(f"  Column '{col}': {num_entities} entities anonymized")
        
        stats["total_entities_found"] += row_total_entities
        
        if row_total_entities > 0:
            stats["anonymized_rows"] += 1
            logger.info(f"  Row {i}: Total {row_total_entities} entities anonymized")
        else:
            logger.info(f"  Row {i}: No PII entities found")
        
        # Store combined text for later filtering
        anonymized_row["_combined_text"] = combined_text.strip()
        processed_rows.append(anonymized_row)
    
    logger.info("=" * 60)
    logger.info("PHASE 2: Pre-AI filtering (tag % on Description + denylist on Risoluzione)")
    logger.info("=" * 60)
    
    filtered_rows = []
    
    for i, row in enumerate(processed_rows, start=1):
        combined_text = row.pop("_combined_text", "")
        description_text = row.get("Description", "")
        risoluzione_text = row.get("Risoluzione__c", "")
        
        # Check 1: Tag percentage on Description
        tag_percentage = calculate_tag_percentage(description_text)
        if tag_percentage >= TAG_THRESHOLD:
            logger.info(f"  Row {i}: Description tag % {tag_percentage:.1%} >= {TAG_THRESHOLD:.0%}, REMOVING")
            stats["filtered_by_tags"] += 1
            continue
        
        # Check 2: Denylist phrases in Risoluzione__c
        denylist_match = contains_denylist_phrase(risoluzione_text)
        if denylist_match:
            logger.info(f"  Row {i}: Denylist match in Risoluzione: '{denylist_match}', REMOVING")
            stats["filtered_by_denylist"] += 1
            continue
        
        # Row passed both filters
        logger.info(f"  Row {i}: Tag % {tag_percentage:.1%}, no denylist match, keeping")
        row["_description_text"] = description_text  # Store for AI phase
        filtered_rows.append(row)
    
    logger.info(f"Rows after pre-AI filtering: {len(filtered_rows)} (tag filter: {stats['filtered_by_tags']}, denylist: {stats['filtered_by_denylist']})")
    
    logger.info("=" * 60)
    logger.info("PHASE 3: AI batch anonymization + knowledge base validation")
    logger.info("=" * 60)
    
    if ai_client:
        final_rows = []
        total_ai_corrections = 0
        
        # Prepare data for batch processing (using Description text)
        rows_with_index = []
        for i, row in enumerate(filtered_rows, start=1):
            description_text = row.get("_description_text", "")
            rows_with_index.append((i, row, description_text))
        
        # Process in batches
        num_batches = (len(rows_with_index) + AI_BATCH_SIZE - 1) // AI_BATCH_SIZE
        logger.info(f"Processing {len(rows_with_index)} rows in {num_batches} batches of {AI_BATCH_SIZE}")
        
        for batch_num in range(num_batches):
            start_idx = batch_num * AI_BATCH_SIZE
            end_idx = min(start_idx + AI_BATCH_SIZE, len(rows_with_index))
            batch = rows_with_index[start_idx:end_idx]
            
            logger.info(f"  Batch {batch_num + 1}/{num_batches}: rows {start_idx + 1}-{end_idx}")
            
            # Prepare batch data: (row_index, description_text)
            batch_data = [(idx, desc_text) for idx, row, desc_text in batch]
            
            # Call AI batch processing
            batch_results = ai_batch_anonymize_and_evaluate(ai_client, batch_data)
            
            # Process results
            for idx, row, description_text in batch:
                row.pop("_description_text", None)
                
                if idx not in batch_results:
                    # Fallback: keep row if AI didn't process it
                    final_rows.append(row)
                    continue
                
                ai_corrected_text, is_useful = batch_results[idx]
                
                if is_useful:
                    # If AI made corrections, apply them to Description
                    if ai_corrected_text and ai_corrected_text != description_text:
                        total_ai_corrections += 1
                        row["Description"] = ai_corrected_text
                    
                    final_rows.append(row)
                else:
                    stats["filtered_by_ai"] += 1
        
        if total_ai_corrections > 0:
            logger.info(f"AI found additional PII in {total_ai_corrections} rows")
        logger.info(f"Rows after AI filtering: {len(final_rows)}")
    else:
        logger.warning("AI client not available. Skipping AI validation phase.")
        # Remove _description_text from remaining rows
        final_rows = []
        for row in filtered_rows:
            row.pop("_description_text", None)
            final_rows.append(row)
    
    stats["kept_rows"] = len(final_rows)
    
    # Write output CSV
    logger.info("=" * 60)
    logger.info(f"Writing output file: {output_path}")
    logger.info("=" * 60)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)
    
    logger.info(f"Output file written successfully: {output_path}")
    
    return stats


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Anonymize case.csv using Presidio and AI validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python presidio.py              # Process all rows
    python presidio.py --test 50    # Process only first 50 rows
    python presidio.py --test 10    # Quick test with 10 rows
        """,
    )
    parser.add_argument(
        "--test",
        type=int,
        metavar="N",
        help="Test mode: process only first N rows",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("PRESIDIO ANONYMIZATION SCRIPT")
    if args.test:
        logger.info(f"TEST MODE: Processing only {args.test} rows")
    logger.info("=" * 60)
    
    # Check input file exists
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        sys.exit(1)
    
    logger.info(f"Input file: {INPUT_FILE}")
    
    # Generate output filename with current date
    today = datetime.now().strftime("%Y_%m_%d")
    suffix = f"_test{args.test}" if args.test else ""
    output_file = OUTPUT_DIR / f"case_anonymized_{today}{suffix}.csv"
    logger.info(f"Output file: {output_file}")
    
    # Setup Presidio
    analyzer = setup_analyzer()
    anonymizer = setup_anonymizer()
    
    # Setup AI client (optional)
    ai_client = setup_ai_client()
    
    # Process the CSV
    logger.info("Starting CSV processing...")
    stats = process_csv(INPUT_FILE, output_file, analyzer, anonymizer, ai_client, limit=args.test)
    
    # Print summary
    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETE - SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total rows processed:     {stats['total_rows']}")
    logger.info(f"Rows with PII entities:   {stats['anonymized_rows']}")
    logger.info(f"Total entities found:     {stats['total_entities_found']}")
    logger.info(f"Filtered by tag %:        {stats['filtered_by_tags']}")
    logger.info(f"Filtered by denylist:     {stats['filtered_by_denylist']}")
    logger.info(f"Filtered by AI:           {stats['filtered_by_ai']}")
    logger.info(f"Final rows kept:          {stats['kept_rows']}")
    logger.info(f"Output file:              {output_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
