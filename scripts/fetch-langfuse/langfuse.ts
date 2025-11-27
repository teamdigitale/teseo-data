import { LangfuseClient } from "@langfuse/client";

const publicKey = process.env.LANGFUSE_PUBLIC_KEY;
const secretKey = process.env.LANGFUSE_SECRET_KEY;
const baseUrl = "https://cloud.langfuse.com";

const langfuse = new LangfuseClient({
  publicKey,
  secretKey,
  baseUrl,
});

async function fetchLangfuseData(
  page: number,
  limit: number,
  fromTimestamp?: string
) {
  const response = await langfuse.api.trace.list({
    page: page,
    limit: limit,
    ...(fromTimestamp && { fromTimestamp }),
  });
  return response;
}

export async function fetchNewTraces(fromTimestamp: string | null) {
  let allTraces: any[] = [];
  let page = 1;
  const limit = 100;

  while (true) {
    const response = await fetchLangfuseData(
      page,
      limit,
      fromTimestamp || undefined
    );
    allTraces = [...allTraces, response.data];
    if (response.data.length < limit) {
      break;
    }
    page++;
  }

  return allTraces.flat();
}

