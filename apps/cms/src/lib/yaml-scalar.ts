/**
 * The scalar half of the CMS's YAML reader, kept here so it can be tested.
 *
 * It used to live inside edit.astro, where nothing could reach it, and that is
 * the direct reason a flow sequence turned into a string and took the site's
 * deploys down for six days. A parser that cannot be tested will eventually be
 * wrong in a way nobody sees until production stops.
 *
 * Covered by scripts/test-yaml-flow.mjs, which runs on every CMS build.
 */

/**
 * Flow style: `[a, b, c]` and `{a: 1, b: 2}`.
 *
 * JSON.parse covers the JSON-shaped subset of this and nothing else, but
 * YAML's flow style does not quote its scalars, so `[philosopher, writer,
 * activist]`, an ordinary three-item list and how 390 thinker files write
 * `vocations`, is rejected outright. The reader used to hand back the raw
 * text when that happened, which turned the list into a string;
 * the writer then correctly quoted the string on the way out, and the
 * site's schema refused an array field holding `"[philosopher, writer,
 * activist]"`. One entry saved in the CMS stopped every deploy after it
 * for six days. So read flow style properly.
 *
 * Returns undefined for anything that is not a well-formed flow
 * collection, which keeps the rule this reader is built on: text it
 * cannot understand is handed back exactly as it was found.
 */
export function flow(input: string): unknown {
  let at = 0;
  const skip = () => {
    while (at < input.length && /\s/.test(input[at])) at += 1;
  };

  /** A quoted scalar, with its escapes resolved. */
  function quoted(): string | undefined {
    const mark = input[at];
    let out = '';
    at += 1;
    while (at < input.length) {
      const ch = input[at];
      if (mark === '"' && ch === '\\') {
        const pair = input.slice(at, at + 2);
        try {
          out += JSON.parse(`"${pair}"`) as string;
        } catch {
          out += pair;
        }
        at += 2;
        continue;
      }
      if (ch === mark) {
        // Inside single quotes YAML writes a literal quote as two of them.
        if (mark === "'" && input[at + 1] === "'") {
          out += "'";
          at += 2;
          continue;
        }
        at += 1;
        return out;
      }
      out += ch;
      at += 1;
    }
    return undefined; // never closed, so not a flow collection
  }

  /** A bare scalar runs until the comma or bracket that ends it. */
  function bare(): unknown {
    const from = at;
    while (at < input.length && !',]}'.includes(input[at])) at += 1;
    return scalar(input.slice(from, at));
  }

  function value(): unknown {
    skip();
    const ch = input[at];
    if (ch === '[') return sequence();
    if (ch === '{') return mapping();
    if (ch === '"' || ch === "'") return quoted();
    return bare();
  }

  function sequence(): unknown {
    at += 1; // past the [
    const out: unknown[] = [];
    skip();
    if (input[at] === ']') {
      at += 1;
      return out;
    }
    for (;;) {
      const item = value();
      if (item === undefined) return undefined;
      out.push(item);
      skip();
      if (input[at] === ',') {
        at += 1;
        skip();
        // A trailing comma before the bracket is sloppy but unambiguous.
        if (input[at] === ']') {
          at += 1;
          return out;
        }
        continue;
      }
      if (input[at] === ']') {
        at += 1;
        return out;
      }
      return undefined;
    }
  }

  function mapping(): unknown {
    at += 1; // past the {
    const out: Record<string, unknown> = {};
    skip();
    if (input[at] === '}') {
      at += 1;
      return out;
    }
    for (;;) {
      skip();
      let key: string | undefined;
      if (input[at] === '"' || input[at] === "'") {
        key = quoted();
      } else {
        const from = at;
        while (at < input.length && !':,}'.includes(input[at])) at += 1;
        key = input.slice(from, at).trim();
      }
      if (key === undefined || key === '') return undefined;
      skip();
      if (input[at] !== ':') return undefined;
      at += 1;
      const held = value();
      if (held === undefined) return undefined;
      out[key] = held;
      skip();
      if (input[at] === ',') {
        at += 1;
        skip();
        if (input[at] === '}') {
          at += 1;
          return out;
        }
        continue;
      }
      if (input[at] === '}') {
        at += 1;
        return out;
      }
      return undefined;
    }
  }

  const parsed = value();
  if (parsed === undefined) return undefined;
  skip();
  // Anything left over means this was never a flow collection to begin
  // with, and guessing at it would be worse than leaving it alone.
  return at === input.length ? parsed : undefined;
}

export function scalar(input: string): unknown {
  const s = input.trim();
  if (s === '' || s === '~' || /^null$/i.test(s)) return null;
  if (/^true$/i.test(s)) return true;
  if (/^false$/i.test(s)) return false;
  if (s === '[]') return [];
  if (s === '{}') return {};
  if (s.length > 1 && s.startsWith('"') && s.endsWith('"')) {
    try {
      return JSON.parse(s) as string;
    } catch {
      return s.slice(1, -1);
    }
  }
  if (s.length > 1 && s.startsWith("'") && s.endsWith("'")) {
    return s.slice(1, -1).replace(/''/g, "'");
  }
  if (s.startsWith('[') || s.startsWith('{')) {
    const parsed = flow(s);
    return parsed === undefined ? s : parsed;
  }
  // A leading zero means somebody meant the characters, not the number.
  if (/^-?\d+$/.test(s) && !/^-?0\d/.test(s) && Math.abs(Number(s)) <= Number.MAX_SAFE_INTEGER) {
    return Number(s);
  }
  if (/^-?\d*\.\d+$/.test(s)) return Number(s);
  return s;
}
