import { describe, expect, it } from "vitest";
import { login, logout, MAX_FAILED_LOGINS, needsInitialSetup, setupFirstOwner, validateSessionToken } from "@/server/auth";
import { decryptSecret, encryptSecret } from "@/server/crypto";
import { hashPassword, verifyPassword } from "@/server/password";

describe("contraseñas", () => {
  it("guarda un hash y verifica correctamente", async () => {
    const h = await hashPassword("una-clave-larga");
    expect(h).not.toContain("una-clave-larga");
    expect(await verifyPassword("una-clave-larga", h)).toBe(true);
    expect(await verifyPassword("otra-clave", h)).toBe(false);
  });
});

describe("cifrado de credenciales", () => {
  it("cifra y descifra; el texto cifrado no contiene el secreto", () => {
    const enc = encryptSecret("token-secreto-gmail");
    expect(enc).not.toContain("token-secreto-gmail");
    expect(decryptSecret(enc)).toBe("token-secreto-gmail");
  });
  it("detecta si el texto cifrado fue alterado", () => {
    const enc = encryptSecret("abc");
    const parts = enc.split(".");
    parts[3] = Buffer.from("xyz").toString("base64");
    expect(() => decryptSecret(parts.join("."))).toThrow();
  });
});

describe("configuración inicial", () => {
  const base = { workspaceName: "Mi agencia", name: "John", email: "John@Ejemplo.com", password: "clave-muy-segura" };

  it("exige el código de instalación correcto", async () => {
    await expect(setupFirstOwner({ ...base, setupToken: "incorrecto" })).rejects.toThrow(/código/);
    expect(await needsInitialSetup()).toBe(true);
  });

  it("crea el dueño una sola vez", async () => {
    await setupFirstOwner({ ...base, setupToken: "token-de-prueba" });
    expect(await needsInitialSetup()).toBe(false);
    await expect(setupFirstOwner({ ...base, setupToken: "token-de-prueba" })).rejects.toThrow(/ya fue realizada/);
  });

  it("rechaza contraseñas cortas", async () => {
    await expect(setupFirstOwner({ ...base, password: "corta", setupToken: "token-de-prueba" })).rejects.toThrow();
  });
});

describe("inicio de sesión", () => {
  const base = { workspaceName: "Mi agencia", name: "John", email: "john@ejemplo.com", password: "clave-muy-segura" };

  it("inicia sesión (email sin importar mayúsculas), valida y cierra la sesión", async () => {
    await setupFirstOwner({ ...base, setupToken: "token-de-prueba" });
    const { token } = await login({ email: "JOHN@ejemplo.com", password: base.password });
    const user = await validateSessionToken(token);
    expect(user?.role).toBe("owner");
    expect(user?.workspaceName).toBe("Mi agencia");
    await logout(token);
    expect(await validateSessionToken(token)).toBeNull();
  });

  it("rechaza contraseña incorrecta con un mensaje genérico", async () => {
    await setupFirstOwner({ ...base, setupToken: "token-de-prueba" });
    await expect(login({ email: base.email, password: "mal" })).rejects.toThrow("Email o contraseña incorrectos.");
    await expect(login({ email: "noexiste@x.com", password: "mal" })).rejects.toThrow("Email o contraseña incorrectos.");
  });

  it("bloquea temporalmente después de varios intentos fallidos", async () => {
    await setupFirstOwner({ ...base, setupToken: "token-de-prueba" });
    for (let i = 0; i < MAX_FAILED_LOGINS; i++) {
      await expect(login({ email: base.email, password: "mal" })).rejects.toThrow();
    }
    // Aun con la contraseña correcta, queda bloqueado.
    await expect(login({ email: base.email, password: base.password })).rejects.toThrow(/Demasiados intentos/);
  });

  it("un token inventado no da acceso", async () => {
    expect(await validateSessionToken("token-inventado")).toBeNull();
    expect(await validateSessionToken("")).toBeNull();
  });
});
