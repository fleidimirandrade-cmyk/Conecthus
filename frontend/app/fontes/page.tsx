import { buscarStatusFontes, type StatusFonte, type StatusFontes } from "@/lib/api";
import {
  formatarBytes,
  formatarDataHora,
  formatarNumero,
  ROTULOS_STATUS,
} from "@/lib/formatar";

export const dynamic = "force-dynamic";
export const metadata = { title: "Status das fontes — Fiscaliza Brasil" };

const CORES_STATUS: Record<string, string> = {
  sucesso: "bg-emerald-100 text-emerald-800",
  sem_alteracao: "bg-emerald-50 text-emerald-700",
  parcial: "bg-amber-100 text-amber-800",
  falha: "bg-red-100 text-red-800",
  em_andamento: "bg-sky-100 text-sky-800",
};

function CartaoFonte({ fonte }: { fonte: StatusFonte }) {
  const ultima = fonte.ultima_importacao;
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="font-semibold">{fonte.nome}</h2>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            ultima ? CORES_STATUS[ultima.status] : "bg-slate-100 text-slate-700"
          }`}
        >
          {ultima ? ROTULOS_STATUS[ultima.status] : "Nunca importada"}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-600">{fonte.descricao}</p>
      <p className="mt-1 break-all text-xs text-slate-500">{fonte.url_referencia}</p>

      {ultima ? (
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
          <Item rotulo="Iniciada em" valor={formatarDataHora(ultima.iniciado_em)} />
          <Item rotulo="Finalizada em" valor={formatarDataHora(ultima.finalizado_em)} />
          <Item
            rotulo="Último sucesso"
            valor={formatarDataHora(fonte.ultima_importacao_bem_sucedida_em)}
          />
          <Item rotulo="Tamanho" valor={formatarBytes(ultima.tamanho_bytes)} />
          <Item rotulo="Lidos" valor={formatarNumero(ultima.registros_lidos)} />
          <Item rotulo="Inseridos" valor={formatarNumero(ultima.registros_inseridos)} />
          <Item rotulo="Atualizados" valor={formatarNumero(ultima.registros_atualizados)} />
          <Item rotulo="Com erro" valor={formatarNumero(ultima.registros_com_erro)} />
          <div className="col-span-2 sm:col-span-4">
            <dt className="text-xs text-slate-500">SHA-256</dt>
            <dd className="break-all font-mono text-xs">{ultima.hash_sha256 ?? "—"}</dd>
          </div>
          {ultima.mensagem_erro && (
            <div className="col-span-2 sm:col-span-4">
              <dt className="text-xs text-slate-500">Erro</dt>
              <dd className="break-words text-xs text-red-700">{ultima.mensagem_erro}</dd>
            </div>
          )}
        </dl>
      ) : (
        <p className="mt-4 text-sm text-slate-500">Nenhuma importação registrada até agora.</p>
      )}
    </article>
  );
}

function Item({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{rotulo}</dt>
      <dd className="font-medium">{valor}</dd>
    </div>
  );
}

export default async function PaginaFontes() {
  let dados: StatusFontes | null = null;
  let erro: string | null = null;
  try {
    dados = await buscarStatusFontes();
  } catch (e) {
    erro = e instanceof Error ? e.message : "Erro desconhecido";
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Status das fontes</h1>
        <p className="mt-1 text-sm text-slate-600">
          Situação da última coleta de cada fonte oficial.
          {dados && <> Atualizado em {formatarDataHora(dados.gerado_em)}.</>}
        </p>
      </div>
      {erro && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Não foi possível consultar a API: {erro}
        </div>
      )}
      <div className="grid gap-4">
        {dados?.fontes.map((fonte) => <CartaoFonte key={fonte.tipo} fonte={fonte} />)}
      </div>
    </div>
  );
}
