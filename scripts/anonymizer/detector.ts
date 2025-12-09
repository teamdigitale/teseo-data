import type { EntityType } from "./config";

export interface DetectedEntity {
  type: EntityType;
  value: string;
  start: number;
  end: number;
}

// Pattern regex per rilevare PII
const PATTERNS: Record<EntityType, RegExp> = {
  EMAIL_ADDRESS: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
  PHONE_NUMBER:
    /(?:\+39\s?)?(?:3[0-9]{2}[\s.-]?[0-9]{6,7}|0[0-9]{1,3}[\s.-]?[0-9]{6,8})/g,
  IBAN_CODE: /[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}(?:[A-Z0-9]?){0,16}/gi,
  FISCAL_CODE: /[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]/gi,
  CREDIT_CARD: /(?:\d{4}[\s-]?){3}\d{4}/g,
  // Pattern per nomi (semplificato: due o più parole capitalizzate consecutive)
  PERSON:
    /\b[A-Z][a-zàèéìòù]+(?:\s+[A-Z][a-zàèéìòù]+)+\b/g,
};

export function detectEntities(text: string): DetectedEntity[] {
  const entities: DetectedEntity[] = [];

  for (const [type, pattern] of Object.entries(PATTERNS)) {
    // Reset regex lastIndex
    pattern.lastIndex = 0;

    let match: RegExpExecArray | null;
    while ((match = pattern.exec(text)) !== null) {
      entities.push({
        type: type as EntityType,
        value: match[0],
        start: match.index,
        end: match.index + match[0].length,
      });
    }
  }

  // Ordina per posizione (dal fondo per facilitare la sostituzione)
  return entities.sort((a, b) => b.start - a.start);
}

