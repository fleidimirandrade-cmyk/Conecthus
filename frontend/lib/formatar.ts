import type { StatusImportacao } from "./api.ts";

export const ROTULOS_STATUS: Record<StatusImportacao, string> = {
  em_andamento: "Em andamento",
  sucesso: "Concluída",
  parcial: "Concluída com erros",
  falha: "Falhou",
  sem_alteracao: "Sem alteração na fonte",
};

export function formatarDataHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(data);
}

export function formatarNumero(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return new Intl.NumberFormat("pt-BR").format(valor);
}

export function formatarBytes(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  const unidades = ["B", "KB", "MB", "GB"];
  let v = valor;
  let i = 0;
  while (v >= 1024 && i < unidades.length - 1) {
    v /= 1024;
    i++;
  }
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(v)} ${unidades[i]}`;
}
