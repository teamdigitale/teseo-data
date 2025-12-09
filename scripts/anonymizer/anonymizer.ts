import { detectEntities } from "./detector";
import { getFakeValue } from "./faker";
import { CHUNK_SIZE } from "./config";

export function anonymizeText(text: string): string {
  const entities = detectEntities(text);

  let result = text;

  // Le entità sono già ordinate dal fondo, quindi possiamo sostituire senza problemi di indici
  for (const entity of entities) {
    const fakeValue = getFakeValue(entity.type, entity.value);
    result =
      result.substring(0, entity.start) + fakeValue + result.substring(entity.end);
  }

  return result;
}

export function anonymizeTextChunked(text: string): string {
  const chunks: string[] = [];

  for (let i = 0; i < text.length; i += CHUNK_SIZE) {
    chunks.push(text.substring(i, i + CHUNK_SIZE));
  }

  console.log(`Processing ${chunks.length} chunks...`);

  const anonymizedChunks: string[] = [];

  for (const [i, chunk] of chunks.entries()) {
    console.log(
      `Anonymizing chunk ${i + 1}/${chunks.length} (len=${chunk.length})...`
    );
    anonymizedChunks.push(anonymizeText(chunk));
  }

  return anonymizedChunks.join("");
}

