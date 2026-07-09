# Organisations listing audit — for CCS sign-off (round-2 feedback #13 & #14)

Date: 2026-07-09. Prepared as part of the CCS round-2 fixes.

CCS asked (item #13) that the **Indian National Congress not appear as a party**, and
(item #14) that the whole Organisations listing be cleaned so it presents only the
liberal ecosystem, not every institution the corpus merely references.

## Standing rule (from the brief)

**Never delete a record.** Orgs like the INC are referenced by thinker affiliations
(Gokhale, Rajaji operated within Congress) and must remain as linkable entities. The
cleanup is about *presentation*, not deletion.

## Mechanism implemented

A new `hide_from_index: true` frontmatter flag (added to the organisations schema and
the authority YAML) removes an org from the `/organisations/` listing **while keeping its
detail page** (`/organisations/<id>/`) building and linkable from affiliations. It is the
non-destructive counterpart to `draft` (which would 404 the page).

## Applied now

| Org | Type | Action | Rationale |
|---|---|---|---|
| Indian National Congress | political_party | **hidden** (`hide_from_index: true`) | Explicitly named by CCS. Not one of "our" liberal parties; kept only as an affiliation target. |

Everything below is a **recommendation for CCS sign-off** — nothing else has been hidden
yet. Confirm which to hide and I will set the flag.

## Political parties (5 → 4 after INC)

| Org | Recommendation | Note |
|---|---|---|
| Swatantra Party | **Keep** | The liberal party. Core. |
| All-India Liberal Federation | **Keep** | The National Liberal Federation; foundational. |
| Liberal Party of Sri Lanka | **Keep** | Liberal party (regional). |
| Congress Socialist Party | **Flag — CCS to decide** | Socialist, not liberal. Present because liberals debated it. Borderline; the brief flags this one specifically. |
| ~~Indian National Congress~~ | Hidden | See above. |

## Other groups — candidates worth a CCS eye (not hidden)

These appear in the corpus mostly as *institutions liberals engaged with*, not as liberal
organisations themselves. Listed for CCS to confirm keep/hide. Default is **keep** unless
CCS says otherwise.

| Org | Type | Why it's a candidate |
|---|---|---|
| Planning Commission of India | academic* | The central economic-planning body — the thing the classical liberals argued *against*. Referenced-only. (*Also mis-typed as `academic`; should be reclassified if kept.) |
| Ford Foundation | international_network | A funder that appears in provenance; not a liberal org per se. |
| John Templeton Foundation | international_network | Funder; borderline. |
| Bharatiya Vidya Bhavan | academic | Cultural/educational publisher; tangential to the liberal tradition. |
| Bombay Stock Exchange | professional_body | A market institution referenced in the corpus; arguably part of the ecosystem — likely **keep**. |

## Groups that read as clean (recommend keep as-is)

- **think_tank**: CCS, Liberty Institute, Forum of Free Enterprise, Indian Liberal Group,
  Council for Liberal Democracy, Project for Economic Education, MEDC, ORF.
- **publisher_org**: the Shroff Memorial Trust, Initiative for Open Society, Libertarian
  Publishers, Tata Sons, The Radical Humanist, etc.
- **reform_society**: Brahmo Samaj, Satyashodhak Samaj, Shetkari Sanghatana and its
  affiliates, PUCL Gujarat.
- **international_network**: FNF, Atlas Network, Mont Pelerin Society, Liberal
  International, Council of Asian Liberals and Democrats.

## Next step

CCS to confirm the Congress Socialist Party call and the "candidates" table. For each
"hide", I set `hide_from_index: true` in `content/authority/organisations.yaml` and the
matching `apps/site/src/content/organisations/<id>.md`. For each reclassification, I change
`type`. No records are deleted.
