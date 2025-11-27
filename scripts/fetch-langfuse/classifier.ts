import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";
import { CATEGORIES } from "./config";

export interface ClassifiedQuestion {
  category: string;
  question: string;
}

export async function classifyBatch(
  client: OpenAI,
  questions: string[]
): Promise<ClassifiedQuestion[]> {
  const Results = z.object({
    results: z.array(
      z.object({
        category: z.enum(CATEGORIES),
        questions: z.array(z.string()),
      })
    ),
  });

  const response = await client.responses.parse({
    model: process.env.OPENAI_MODEL || "gpt-4o",
    input: [
      {
        role: "system",
        content: `Sei un esperto classificatore di domande per un chatbot interno di un dipartimento digitale collegato a tematiche e servizi legati alle misure PNRR.

Il tuo compito è assegnare a ciascuna domanda UNA delle seguenti categorie PREDEFINITE:
${CATEGORIES.map((c) => `- ${c}`).join("\n")}

REGOLE IMPORTANTI:
- Usa SOLO le categorie elencate sopra, esattamente come scritte
- NON inventare nuove categorie
- Se una domanda NON rientra chiaramente in nessuna delle altre categorie, usa "Altro"
- Classifica TUTTE le domande, nessuna deve essere omessa`,
      },
      {
        role: "user",
        content: `Classifica le seguenti ${
          questions.length
        } domande nelle categorie predefinite:\n\n${questions
          .map((q, i) => `${i + 1}. ${q}`)
          .join("\n")}`,
      },
    ],
    text: { format: zodTextFormat(Results, "Results") },
  });

  const classified: ClassifiedQuestion[] = [];
  for (const item of response?.output_parsed?.results || []) {
    for (const question of item.questions) {
      classified.push({ category: item.category, question });
    }
  }
  return classified;
}

