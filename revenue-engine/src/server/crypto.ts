import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

/**
 * Cifrado de credenciales de integraciones (tokens de Gmail, Mercado Pago, etc.).
 * La clave vive solo en la variable de entorno ENCRYPTION_KEY (32 bytes en base64).
 * Se usa a partir de la Etapa 2; queda lista y probada desde ahora.
 */
function getKey(): Buffer {
  const raw = process.env.ENCRYPTION_KEY;
  if (!raw) throw new Error("Falta la variable de entorno ENCRYPTION_KEY.");
  const key = Buffer.from(raw, "base64");
  if (key.length !== 32) throw new Error("ENCRYPTION_KEY debe tener 32 bytes en base64.");
  return key;
}

export function encryptSecret(plain: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", getKey(), iv);
  const data = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `v1.${iv.toString("base64")}.${tag.toString("base64")}.${data.toString("base64")}`;
}

export function decryptSecret(payload: string): string {
  const [version, iv, tag, data] = payload.split(".");
  if (version !== "v1" || !iv || !tag || !data) throw new Error("Formato de secreto inválido.");
  const decipher = createDecipheriv("aes-256-gcm", getKey(), Buffer.from(iv, "base64"));
  decipher.setAuthTag(Buffer.from(tag, "base64"));
  return Buffer.concat([decipher.update(Buffer.from(data, "base64")), decipher.final()]).toString("utf8");
}
