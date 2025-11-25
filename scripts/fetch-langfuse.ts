import { LangfuseClient } from "@langfuse/client";
import OpenAI from "openai";

const publicKey = process.env.LANGFUSE_PUBLIC_KEY;
const secretKey = process.env.LANGFUSE_SECRET_KEY;
const baseUrl = "https://cloud.langfuse.com";
const langfuse = new LangfuseClient(publicKey, secretKey, baseUrl);

async function fetchLangfuseData(page, limit) {
	const response = await langfuse.api.trace.list({
		page: page,
		limit: limit,
	});
	return response;
}

async function fetchAllTraces() {
	let allTraces = [];
	let page = 1;
	const limit = 100; // Number of traces per page

	while (true) {
		const response = await fetchLangfuseData(page, limit);
		allTraces = [...allTraces, response.data];
		if (response.data.length < limit) {
			break; // No more pages to fetch
		}
		page++;
	}

	return allTraces.flat();
}

async function main() {
	console.log("Fetching Langfuse data...");
	// Add your fetching logic here

	// Fetch list of traces, supports filters and pagination
	// const traces = await langfuse.api.trace.list();
	const traces = await fetchAllTraces();

	// await Bun.write("data/traces.json", JSON.stringify(traces, null, 2));
	console.log("Fetched traces:", traces.length);
	const questions = traces
		.map((trace) => {
			return trace.input?.query;
		})
		.filter((q) => q !== undefined);
	const name = `questions.json`; //${Date.now()}-
	await Bun.write(`data/${name}`, JSON.stringify(questions, null, 2));

	const client = new OpenAI();

	const response = await client.responses.create({
		model: process.env.OPENAI_MODEL || "gpt-4o",
		input: [
			{
				role: "system",
				content:
					"Sei un esperto classificatore di domande per un chatbot interno di un dipartimento digitale collegato a tematiche e servizi legati alle misure PNRR. Il tuo compito è assegnare a ciascuna domanda UNA categoria che riassuma il suo tema principale. Cerca di aggregare e raggruppare il più possibile i temi simili sotto la stessa categoria generale. Evita di usare categorie troppo specifiche: cerca di normalizzare i titoli, utilizzando etichette che possano raggruppare domande anche diverse ma simili (ad esempio: 'Pagamenti', 'Digitalizzazione', 'Assistenza', 'Contratti', 'Cloud', 'Ruoli/Governance', ecc.)",
			},
			{
				role: "user",
				content: `Lista delle domande:  
						${questions.join("\n- ")}`,
			},
		],
	});

	console.log(response.output_text);

	// results = await model.invoke("Summarize the following questions into categories:", questions);
}

(async () => {
	await main();
})();
