/** Error con un mensaje pensado para mostrarle a la persona (en español, sin detalles técnicos). */
export class UserError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UserError";
  }
}

export class ForbiddenError extends UserError {
  constructor(message = "No tenés permiso para hacer esto.") {
    super(message);
    this.name = "ForbiddenError";
  }
}
