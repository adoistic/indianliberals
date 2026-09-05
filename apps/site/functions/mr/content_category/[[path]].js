import { sectionHandler } from '../../_legacy/core.js';
export const onRequestGet = sectionHandler('/primary-works/');
// A redirect that answers GET but not HEAD reads as a dead link to every
// crawler and link checker that asks with HEAD, which is most of them. The
// response carries no body, so the same handler serves both.
export const onRequestHead = onRequestGet;
