import Link from "next/link";

export default function Inicio() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-2xl font-bold sm:text-3xl">Fiscalização de gastos parlamentares</h1>
        <p className="max-w-3xl text-slate-700">
          O Fiscaliza Brasil reúne dados oficiais publicados pela Câmara dos Deputados sobre
          deputados federais e as despesas reembolsadas pela Cota para o Exercício da Atividade
          Parlamentar (CEAP). Cada registro preserva sua origem para que possa ser auditado.
        </p>
      </section>
      <section className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/fontes"
          className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm hover:border-marca-600"
        >
          <h2 className="font-semibold">Status das fontes</h2>
          <p className="mt-1 text-sm text-slate-600">
            Quando cada fonte oficial foi coletada, com hash e contagem de registros.
          </p>
        </Link>
        <Link
          href="/metodologia"
          className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm hover:border-marca-600"
        >
          <h2 className="font-semibold">Metodologia</h2>
          <p className="mt-1 text-sm text-slate-600">
            Como os dados são coletados, o que a CEAP cobre e como interpretar alertas.
          </p>
        </Link>
      </section>
    </div>
  );
}
