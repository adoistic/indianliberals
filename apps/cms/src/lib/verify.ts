/**
 * Server-side proof that a request came from a signed-in editor.
 *
 * The browser sends its Firebase ID token; this checks the signature against
 * Google's published certificates and the claims against our project. That is
 * all a service account would have given us for this purpose, so the CMS holds
 * no Firebase secret at all. The only credential in the system is the GitHub
 * App key, and that one has to exist.
 *
 * Certificates are cached in the isolate for an hour, which is well inside
 * Google's rotation window and saves a round trip on every request.
 */

const CERT_URL =
  'https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com';

export interface Claims {
  email: string;
  emailVerified: boolean;
  name?: string;
  picture?: string;
  uid: string;
}

let certCache: { at: number; certs: Record<string, string> } | null = null;

async function certificates(): Promise<Record<string, string>> {
  if (certCache && Date.now() - certCache.at < 3_600_000) return certCache.certs;
  const response = await fetch(CERT_URL);
  if (!response.ok) throw new Error(`could not fetch Google signing certificates: ${response.status}`);
  const certs = (await response.json()) as Record<string, string>;
  certCache = { at: Date.now(), certs };
  return certs;
}

function b64urlToBytes(input: string): Uint8Array<ArrayBuffer> {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(padded + '='.repeat((4 - (padded.length % 4)) % 4));
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function pemBodyToBytes(pem: string): Uint8Array<ArrayBuffer> {
  const body = pem.replace(/-----(BEGIN|END) CERTIFICATE-----/g, '').replace(/\s+/g, '');
  const binary = atob(body);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/**
 * Pull the RSA public key out of an X.509 certificate.
 *
 * WebCrypto in Workers will not import a certificate directly, only a
 * SubjectPublicKeyInfo. Rather than pull in an ASN.1 parser for one field, we
 * find the RSA algorithm identifier inside the DER and take the
 * SubjectPublicKeyInfo that starts there. It is a narrow trick but a stable
 * one: that OID appears once, in the key, in every certificate Google issues.
 */
async function publicKeyFromCertificate(pem: string): Promise<CryptoKey> {
  const der = pemBodyToBytes(pem);
  const marker = [0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01];
  let start = -1;
  for (let i = 0; i < der.length - marker.length; i++) {
    let hit = true;
    for (let j = 0; j < marker.length; j++) {
      if (der[i + j] !== marker[j]) { hit = false; break; }
    }
    if (hit) { start = i; break; }
  }
  if (start === -1) throw new Error('no RSA key found in certificate');

  // Walk back to the enclosing SEQUENCE header, which begins the SPKI.
  let spkiStart = start - 4;
  while (spkiStart >= 0 && der[spkiStart] !== 0x30) spkiStart--;
  if (spkiStart < 0) throw new Error('malformed certificate');

  const length = (der[spkiStart + 2] << 8) | der[spkiStart + 3];
  const spki = der.slice(spkiStart, spkiStart + 4 + length);

  return crypto.subtle.importKey(
    'spki',
    spki,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['verify'],
  );
}

/**
 * Verify a Firebase ID token. Returns the claims, or throws with a reason.
 * Every check Google documents is applied: signature, algorithm, issuer,
 * audience, expiry and issue time.
 */
export async function verifyIdToken(token: string, projectId: string): Promise<Claims> {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('token is not a JWT');

  const header = JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[0])));
  const payload = JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[1])));

  if (header.alg !== 'RS256') throw new Error(`unexpected algorithm ${header.alg}`);
  if (payload.aud !== projectId) throw new Error('token was issued for another project');
  if (payload.iss !== `https://securetoken.google.com/${projectId}`) throw new Error('wrong issuer');

  const now = Math.floor(Date.now() / 1000);
  if (payload.exp <= now) throw new Error('token has expired');
  if (payload.iat > now + 300) throw new Error('token is issued in the future');
  if (!payload.sub) throw new Error('token has no subject');

  const certs = await certificates();
  const pem = certs[header.kid];
  if (!pem) throw new Error('token signed with an unknown key');

  const key = await publicKeyFromCertificate(pem);
  const signed = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  const ok = await crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5',
    key,
    b64urlToBytes(parts[2]),
    signed,
  );
  if (!ok) throw new Error('signature does not verify');

  return {
    email: String(payload.email || '').toLowerCase(),
    emailVerified: Boolean(payload.email_verified),
    name: payload.name,
    picture: payload.picture,
    uid: payload.sub,
  };
}
