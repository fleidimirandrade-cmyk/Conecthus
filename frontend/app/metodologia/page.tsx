export const metadata = { title: "Metodologia — Fiscaliza Brasil" };

export default function Metodologia() {
  return (
    <article className="max-w-3xl space-y-4 text-slate-700">
      <h1 className="text-2xl font-bold text-slate-900">Metodologia</h1>
      <h2 className="pt-2 text-lg font-semibold text-slate-900">Fontes</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>API de Dados Abertos da Câmara dos Deputados (v2), recurso de deputados.</li>
        <li>Arquivos anuais da CEAP publicados pela Câmara.</li>
      </ul>
      <h2 className="pt-2 text-lg font-semibold text-slate-900">O que a CEAP cobre</h2>
      <p>
        A CEAP reembolsa despesas ligadas ao exercício do mandato (passagens, combustível,
        divulgação, entre outras). Ela não inclui salários, verba de gabinete para pessoal nem
        outros gastos da Câmara. Os valores exibidos aqui são sempre identificados pela sua
        origem.
      </p>
      <h2 className="pt-2 text-lg font-semibold text-slate-900">Rastreabilidade</h2>
      <p>
        Cada importação registra URL, data da coleta, hash SHA-256 do conteúdo recebido e
        quaisquer registros que não puderam ser processados. O conteúdo original de cada
        registro é preservado.
      </p>
      <h2 className="pt-2 text-lg font-semibold text-slate-900">Alertas</h2>
      <p>
        Alertas automáticos apontam padrões que merecem revisão humana. Um alerta não é
        acusação, não indica irregularidade comprovada e pode ter explicação legítima.
      </p>
    </article>
  );
}
