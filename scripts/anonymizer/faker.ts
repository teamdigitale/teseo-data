import { Faker, it, en, base } from "@faker-js/faker";
import type { EntityType } from "./config";

const faker = new Faker({ locale: [it, en, base] });

// Mappe per mantenere coerenza (stesso valore originale -> stessa sostituzione)
const entityMaps: Record<EntityType, Map<string, string>> = {
  PERSON: new Map(),
  EMAIL_ADDRESS: new Map(),
  PHONE_NUMBER: new Map(),
  IBAN_CODE: new Map(),
  FISCAL_CODE: new Map(),
  CREDIT_CARD: new Map(),
};

function generateFakeValue(type: EntityType): string {
  switch (type) {
    case "PERSON":
      return faker.person.fullName();
    case "EMAIL_ADDRESS":
      return faker.internet.email();
    case "PHONE_NUMBER":
      return faker.phone.number();
    case "IBAN_CODE":
      return faker.finance.iban({ countryCode: "IT" });
    case "FISCAL_CODE":
      return generateFakeFiscalCode();
    case "CREDIT_CARD":
      return faker.finance.creditCardNumber();
    default:
      return `[REDACTED_${type}]`;
  }
}

function generateFakeFiscalCode(): string {
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const randomLetter = () =>
    letters[Math.floor(Math.random() * letters.length)] ?? "A";
  const randomDigit = () => Math.floor(Math.random() * 10).toString();

  return (
    randomLetter() +
    randomLetter() +
    randomLetter() +
    randomLetter() +
    randomLetter() +
    randomLetter() +
    randomDigit() +
    randomDigit() +
    randomLetter() +
    randomDigit() +
    randomDigit() +
    randomLetter() +
    randomDigit() +
    randomDigit() +
    randomDigit() +
    randomLetter()
  );
}

export function getFakeValue(type: EntityType, originalValue: string): string {
  const map = entityMaps[type];

  if (!map.has(originalValue)) {
    map.set(originalValue, generateFakeValue(type));
  }

  return map.get(originalValue)!;
}

export function resetMaps(): void {
  for (const map of Object.values(entityMaps)) {
    map.clear();
  }
}

