// Name shapes for people (thinkers) and organisations.
//
// The thinker `name` carries the canonical display form, an optional `full`
// (with middle names / honorifics expanded), a `sort` key for list ordering,
// and the alias arrays used by authority resolution.

import { z } from 'astro:content';

export const thinkerName = z.object({
  canonical: z.string(),
  full: z.string().optional(),
  sort: z.string(),
  also_known_as: z.array(z.string()).default([]),
  honorifics: z.array(z.string()).default([]),
});

export const organisationName = z.object({
  canonical: z.string(),
  full: z.string().optional(),
  sort: z.string(),
  also_known_as: z.array(z.string()).default([]),
});
