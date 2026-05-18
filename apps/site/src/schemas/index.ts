// Barrel re-export for all shared schema primitives. Import these into
// content.config.ts (and from future scripts that need the same Zod shapes,
// e.g., the synthesis validators in scripts/synthesis/).
//
// Organisation:
//   i18n.ts         — LANG_CODES, i18nFields, multilingualTitle
//   rights.ts       — rightsSchema
//   provenance.ts   — aiProvenance, confidenceFlag
//   people.ts       — thinkerName, organisationName
//   extraction.ts   — LLM extraction shapes (pageSystem, pullQuote, tocEntry, …)
//   synthesis.ts    — readingGuide, intellectualArc
//   mentions.ts     — thinkerMention (Phase B in-prose NER)

export * from './i18n';
export * from './rights';
export * from './provenance';
export * from './people';
export * from './extraction';
export * from './synthesis';
export * from './mentions';
