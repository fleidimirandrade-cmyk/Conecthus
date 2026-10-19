import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Cabecalho } from "@/components/Cabecalho";

import "./globals.css";

export const metadata: Metadata = {
  title: "Fiscaliza Brasil",
  description:
    "Plataforma independente de acompanhamento dos gastos de deputados federais com dados oficiais.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="flex min-h-screen flex-col">
        <Cabecalho />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-slate-200 bg-white">
          <div className="mx-auto max-w-6xl px-4 py-4 text-xs text-slate-500">
            Projeto independente, sem vínculo com a Câmara dos Deputados. Dados de fontes
            oficiais públicas. Alertas são indicadores para revisão e não constituem acusação.
          </div>
        </footer>
      </body>
    </html>
  );
}
