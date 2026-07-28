#!/usr/bin/env node
/**
 * The private key has to import into WebCrypto, whichever form it arrived in.
 *
 * This test exists because it did not, and nobody noticed for weeks. GitHub
 * issues App keys as PKCS#1, the format headed "BEGIN RSA PRIVATE KEY".
 * WebCrypto's importKey accepts only PKCS#8. Node's crypto.sign accepts both,
 * so every setup script worked perfectly and the Worker, which is the only
 * thing that uses WebCrypto, could not sign a token at all. The result was a
 * CMS that could not commit anything.
 *
 * Nothing here touches the network or the real key. A throwaway key pair is
 * generated, exported in both formats, and put through the same conversion the
 * Worker uses, then actually used to sign and verify. Runs on every build.
 */

import { generateKeyPairSync, createPublicKey } from 'node:crypto';
import { webcrypto } from 'node:crypto';

// ── The code under test, kept byte-identical to src/lib/github.ts ────────

function derLength(length) {
  if (length < 0x80) return [length];
  const bytes = [];
  let rest = length;
  while (rest > 0) {
    bytes.unshift(rest & 0xff);
    rest >>= 8;
  }
  return [0x80 | bytes.length, ...bytes];
}

function pkcs1ToPkcs8(key) {
  const algorithm = [
    0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00,
  ];
  const version = [0x02, 0x01, 0x00];
  const octet = [0x04, ...derLength(key.length)];
  const inner = version.length + algorithm.length + octet.length + key.length;
  const header = [0x30, ...derLength(inner)];

  const out = new Uint8Array(new ArrayBuffer(header.length + inner));
  out.set(header, 0);
  let at = header.length;
  out.set(version, at);
  at += version.length;
  out.set(algorithm, at);
  at += algorithm.length;
  out.set(octet, at);
  at += octet.length;
  out.set(key, at);
  return out;
}

function pemToPkcs8(pem) {
  const isPkcs1 = /BEGIN RSA PRIVATE KEY/.test(pem);
  const body = pem.replace(/-----(BEGIN|END) (RSA )?PRIVATE KEY-----/g, '').replace(/\s+/g, '');
  const binary = atob(body);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return isPkcs1 ? pkcs1ToPkcs8(bytes) : bytes;
}

// ── The tests ────────────────────────────────────────────────────────────

let failures = 0;
const check = (name, pass, detail = '') => {
  if (!pass) failures++;
  console.log(`${pass ? 'ok  ' : 'FAIL'}  ${name}${detail ? `    ${detail}` : ''}`);
};

/** Sign and verify for real, which is the only proof that matters. */
async function usable(pem, label) {
  let key;
  try {
    key = await webcrypto.subtle.importKey(
      'pkcs8',
      pemToPkcs8(pem),
      { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
      false,
      ['sign'],
    );
  } catch (error) {
    check(`${label}: imports into WebCrypto`, false, String(error.message).slice(0, 80));
    return null;
  }
  check(`${label}: imports into WebCrypto`, true);

  const message = new TextEncoder().encode('the quick brown fox');
  const signature = await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5', key, message);
  check(`${label}: produces a signature`, signature.byteLength > 0, `${signature.byteLength} bytes`);
  return { signature, message };
}

// Two sizes, because DER length encoding switches from short form to long form
// partway up and a 2048-bit key is on the far side of that boundary.
for (const bits of [2048, 4096]) {
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: bits });

  const pkcs1 = privateKey.export({ type: 'pkcs1', format: 'pem' });
  const pkcs8 = privateKey.export({ type: 'pkcs8', format: 'pem' });

  check(`${bits}-bit: the PKCS#1 export is the shape GitHub sends`, pkcs1.includes('BEGIN RSA PRIVATE KEY'));

  const fromPkcs1 = await usable(pkcs1, `${bits}-bit PKCS#1`);
  const fromPkcs8 = await usable(pkcs8, `${bits}-bit PKCS#8`);

  // Both forms are the same key, so both signatures must verify against the
  // one public key. This is what catches a conversion that imports without
  // error but mangles the modulus.
  const spki = publicKey.export({ type: 'spki', format: 'der' });
  const verifier = await webcrypto.subtle.importKey(
    'spki',
    spki,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['verify'],
  );

  for (const [form, result] of [
    ['PKCS#1', fromPkcs1],
    ['PKCS#8', fromPkcs8],
  ]) {
    if (!result) continue;
    const good = await webcrypto.subtle.verify(
      'RSASSA-PKCS1-v1_5',
      verifier,
      result.signature,
      result.message,
    );
    check(`${bits}-bit ${form}: the signature verifies against the public key`, good);
  }
}

// A PKCS#8 key must pass through untouched. Converting one twice would break it.
{
  const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const pkcs8Pem = privateKey.export({ type: 'pkcs8', format: 'pem' });
  const raw = Buffer.from(
    pkcs8Pem.replace(/-----(BEGIN|END) PRIVATE KEY-----/g, '').replace(/\s+/g, ''),
    'base64',
  );
  check(
    'a PKCS#8 key is passed through unchanged',
    Buffer.from(pemToPkcs8(pkcs8Pem)).equals(raw),
  );
}

// The long-form length encoding itself, since a wrong byte here is the kind of
// thing that works at one key size and fails at another.
check('DER short form below 128', JSON.stringify(derLength(0x7f)) === '[127]');
check('DER long form at 128', JSON.stringify(derLength(0x80)) === '[129,128]');
check('DER long form over 255', JSON.stringify(derLength(0x1234)) === '[130,18,52]');

console.log(failures ? `\n${failures} failed` : '\nall cases behave');
process.exit(failures ? 1 : 0);
