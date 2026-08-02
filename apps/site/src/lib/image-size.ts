// Intrinsic pixel dimensions of a file in public/, read at build time.
//
// Needed because the opinion covers are not one shape. They were recovered
// from the Wayback Machine and they range from 192x306 to 1024x329, which is
// a ratio of 0.63 at one end and 3.11 at the other. Forcing that set through
// one fixed aspect box and object-cover is what CCS saw as images "not
// displaying correctly" (round-3 feedback, 7.2): every card was a crop, and
// the wider the original, the more of it was thrown away.
//
// Letting each image keep its own shape fixes that, but an <img> with
// height:auto and no dimensions reflows the page as it loads. Browsers reserve
// the right box from the width and height attributes, so we read the real ones
// out of the file header here and emit them per image.
//
// Only the handful of headers this archive actually stores are parsed. Anything
// unrecognised returns null and the caller falls back to a fixed box, which is
// the old behaviour and safe.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export interface ImageSize {
  width: number;
  height: number;
}

// One build, one read per file.
const cache = new Map<string, ImageSize | null>();

function parsePng(b: Buffer): ImageSize | null {
  if (b.length < 24) return null;
  return { width: b.readUInt32BE(16), height: b.readUInt32BE(20) };
}

function parseWebp(b: Buffer): ImageSize | null {
  const kind = b.subarray(12, 16).toString('ascii');
  // Extended format: 24-bit canvas width and height, each stored minus one.
  if (kind === 'VP8X') {
    return {
      width: (b.readUIntLE(24, 3) & 0xffffff) + 1,
      height: (b.readUIntLE(27, 3) & 0xffffff) + 1,
    };
  }
  // Lossy: dimensions live in the 14 low bits after the start code.
  if (kind === 'VP8 ') {
    return { width: b.readUInt16LE(26) & 0x3fff, height: b.readUInt16LE(28) & 0x3fff };
  }
  // Lossless: 14 bits each, packed into one little-endian word, stored minus one.
  if (kind === 'VP8L') {
    const bits = b.readUInt32LE(21);
    return { width: (bits & 0x3fff) + 1, height: ((bits >> 14) & 0x3fff) + 1 };
  }
  return null;
}

function parseJpeg(b: Buffer): ImageSize | null {
  let at = 2;
  while (at + 9 < b.length) {
    if (b[at] !== 0xff) {
      at += 1;
      continue;
    }
    const marker = b[at + 1];
    const length = b.readUInt16BE(at + 2);
    // SOF0, SOF1, SOF2: the frame headers that carry the size.
    if (marker === 0xc0 || marker === 0xc1 || marker === 0xc2) {
      return { width: b.readUInt16BE(at + 7), height: b.readUInt16BE(at + 5) };
    }
    at += 2 + length;
  }
  return null;
}

/**
 * Read the intrinsic size of a site-absolute public path such as
 * "/opinions/covers/x.webp". Returns null if the file is missing or its format
 * is not one we parse, so a caller can fall back rather than fail the build.
 */
export function imageSize(publicPath: string): ImageSize | null {
  if (cache.has(publicPath)) return cache.get(publicPath) ?? null;

  let size: ImageSize | null = null;
  try {
    const b = readFileSync(join(process.cwd(), 'public', publicPath.replace(/^\//, '')));
    if (b.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) {
      size = parsePng(b);
    } else if (
      b.subarray(0, 4).toString('ascii') === 'RIFF' &&
      b.subarray(8, 12).toString('ascii') === 'WEBP'
    ) {
      size = parseWebp(b);
    } else if (b[0] === 0xff && b[1] === 0xd8) {
      size = parseJpeg(b);
    }
  } catch {
    size = null;
  }

  // A zero in either axis is not usable as an aspect ratio.
  if (size && (size.width < 1 || size.height < 1)) size = null;
  cache.set(publicPath, size);
  return size;
}
