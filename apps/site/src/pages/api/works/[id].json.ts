import type { APIRoute } from 'astro';
import { getEnWorks, buildWorkDetail, jsonResponse } from '~/lib/agent-api';

// Full structured metadata for one work — summary, key points, TOC,
// contributors, provenance, rights. Backs the MCP get_work_metadata tool.

export async function getStaticPaths() {
  const works = await getEnWorks();
  return works.map((w) => ({ params: { id: w.id }, props: { work: w } }));
}

export const GET: APIRoute = async ({ props }) => {
  return jsonResponse(await buildWorkDetail(props.work));
};
