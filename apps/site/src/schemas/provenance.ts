// AI extraction / synthesis provenance shared across content kinds.
//
// `aiProvenance` is the audit trail for any AI-generated content (summaries,
// emit-time fields, etc.). `confidenceFlag` is the per-field self-assessment
// applied to high-stakes fields (title, author, year, publisher, language)
// during the metadata pass — see design doc M3.

import { z } from 'astro:content';

export const aiProvenance = z
  .object({
    extracted_at: z.string().datetime().optional(),
    model: z.string().optional(),
    prompt_version: z.string().optional(),
  })
  .optional();

export const confidenceFlag = z.enum(['high', 'medium', 'low']);
