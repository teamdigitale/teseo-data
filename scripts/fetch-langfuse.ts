import { LangfuseClient } from "@langfuse/client";

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

	await Bun.write("data/traces.json", JSON.stringify(traces, null, 2));
	console.log("Fetched traces:", traces.length);
	const questions = traces
		.map((trace) => {
			return trace.input?.query;
		})
		.filter((q) => q !== undefined);
	await Bun.write("data/questions.json", JSON.stringify(questions, null, 2));
}

(async () => {
	await main();
})();
