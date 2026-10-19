"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const LINKS = [
  { href: "/", rotulo: "Início" },
  { href: "/fontes", rotulo: "Status das fontes" },
  { href: "/metodologia", rotulo: "Metodologia" },
];

export function Cabecalho() {
  const caminho = usePathname();
  const [aberto, setAberto] = useState(false);

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-lg font-bold text-marca-700">
          Fiscaliza Brasil
        </Link>
        <button
          type="button"
          className="rounded-md p-2 text-slate-700 hover:bg-slate-100 md:hidden"
          aria-expanded={aberto}
          aria-controls="menu-principal"
          aria-label="Abrir menu"
          onClick={() => setAberto((v) => !v)}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" />
          </svg>
        </button>
        <nav
          id="menu-principal"
          aria-label="Navegação principal"
          className={`${aberto ? "block" : "hidden"} absolute inset-x-0 top-14 z-10 border-b border-slate-200 bg-white md:static md:block md:border-0`}
        >
          <ul className="flex flex-col gap-1 px-4 py-2 md:flex-row md:gap-4 md:p-0">
            {LINKS.map((link) => {
              const ativo = link.href === "/" ? caminho === "/" : caminho.startsWith(link.href);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    onClick={() => setAberto(false)}
                    aria-current={ativo ? "page" : undefined}
                    className={`block rounded-md px-3 py-2 text-sm font-medium ${
                      ativo ? "bg-marca-50 text-marca-700" : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {link.rotulo}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
