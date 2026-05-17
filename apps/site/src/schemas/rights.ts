// Rights metadata. Applied to primary-works and periodicals (where copyright
// status matters for whether we can host the body / clean markdown), and to
// any other content kind that needs takedown-on-request semantics.

import { z } from 'astro:content';

export const rightsSchema = z
  .object({
    status: z.enum([
      'public_domain',
      'fair_use_educational',
      'permission_granted',
      'takedown_on_request',
      'unknown',
    ]),
    pd_year: z.number().int().optional(),
    editorial_review_flag: z.boolean().default(false),
    notes: z.string().optional(),
  })
  .optional();
