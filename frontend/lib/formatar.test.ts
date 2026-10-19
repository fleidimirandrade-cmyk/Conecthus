import assert from "node:assert/strict";
import { test } from "node:test";

import { formatarBytes, formatarDataHora, formatarNumero, ROTULOS_STATUS } from "./formatar.ts";

test("formata números no padrão brasileiro", () => {
  assert.equal(formatarNumero(1234567), "1.234.567");
  assert.equal(formatarNumero(null), "—");
});

test("formata bytes", () => {
  assert.equal(formatarBytes(512), "512 B");
  assert.equal(formatarBytes(1536), "1,5 KB");
});

test("formata data/hora em horário de Brasília", () => {
  assert.equal(formatarDataHora("2024-03-05T15:00:00Z"), "05/03/2024, 12:00");
  assert.equal(formatarDataHora(null), "—");
  assert.equal(formatarDataHora("inválida"), "—");
});

test("todos os status têm rótulo", () => {
  assert.equal(ROTULOS_STATUS.parcial, "Concluída com erros");
});
