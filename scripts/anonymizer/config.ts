export const INPUT_DIR = "scripts/anonymizer/input";
export const OUTPUT_DIR = "data/anonymized";
export const CHUNK_SIZE = 80_000;

export const ENTITY_TYPES = [
  "PERSON",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "IBAN_CODE",
  "FISCAL_CODE",
  "CREDIT_CARD",
] as const;

export type EntityType = (typeof ENTITY_TYPES)[number];

