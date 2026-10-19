export type StatusImportacao =
  | "em_andamento"
  | "sucesso"
  | "parcial"
  | "falha"
  | "sem_alteracao";

export interface UltimaImportacao {
  id: number;
  status: StatusImportacao;
  url: string;
  iniciado_em: string;
  finalizado_em: string | null;
  hash_sha256: string | null;
  tamanho_bytes: number | null;
  registros_lidos: number;
  registros_inseridos: number;
  registros_atualizados: number;
  registros_inalterados: number;
  registros_com_erro: number;
  mensagem_erro: string | null;
  parametros: Record<string, unknown>;
}

export interface StatusFonte {
  tipo: string;
  nome: string;
  descricao: string;
  url_referencia: string;
  ultima_importacao: UltimaImportacao | null;
  ultima_importacao_bem_sucedida_em: string | null;
}

export interface StatusFontes {
  gerado_em: string;
  fontes: StatusFonte[];
}

export function urlApi(): string {
  return (
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000"
  ).replace(/\/$/, "");
}

export async function buscarStatusFontes(): Promise<StatusFontes> {
  const resposta = await fetch(`${urlApi()}/api/v1/fontes/status`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!resposta.ok) {
    throw new Error(`API respondeu HTTP ${resposta.status}`);
  }
  return (await resposta.json()) as StatusFontes;
}
