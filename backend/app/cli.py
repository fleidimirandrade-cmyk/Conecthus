"""Linha de comando das importações.

python -m app.cli deputados [--legislatura 57] [--sem-detalhes]
python -m app.cli ceap --ano 2024 [--arquivo caminho/Ano-2024.csv.zip] [--forcar]
"""

import argparse
import logging
import sys
from pathlib import Path

from app.coletores.ceap import importar_ceap
from app.coletores.deputados import importar_deputados
from app.coletores.http import ClienteHttp
from app.config import get_settings
from app.db import get_sessionmaker
from app.logging_config import configurar_logs

logger = logging.getLogger("app.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_dep = sub.add_parser("deputados", help="Importa deputados da API da Câmara")
    p_dep.add_argument("--legislatura", type=int, default=None)
    p_dep.add_argument("--sem-detalhes", action="store_true")
    p_ceap = sub.add_parser("ceap", help="Importa o arquivo anual da CEAP")
    p_ceap.add_argument("--ano", type=int, required=True)
    p_ceap.add_argument("--arquivo", type=Path, default=None, help="Zip local já baixado")
    p_ceap.add_argument("--forcar", action="store_true", help="Reprocessa mesmo sem mudança")
    args = parser.parse_args(argv)

    settings = get_settings()
    configurar_logs(settings.log_level)
    with get_sessionmaker()() as session, ClienteHttp(settings) as cliente:
        try:
            if args.comando == "deputados":
                fonte = importar_deputados(
                    session, cliente, settings, args.legislatura, not args.sem_detalhes
                )
            else:
                fonte = importar_ceap(
                    session, cliente, settings, args.ano, args.arquivo, args.forcar
                )
        except Exception:
            logger.exception("comando_falhou", extra={"comando": args.comando})
            return 1
    print(
        f"Importação {fonte.id} ({fonte.tipo}): {fonte.status} — lidos={fonte.registros_lidos} "
        f"inseridos={fonte.registros_inseridos} atualizados={fonte.registros_atualizados} "
        f"inalterados={fonte.registros_inalterados} erros={fonte.registros_com_erro}"
    )
    return 0 if fonte.status in ("sucesso", "sem_alteracao") else 2


if __name__ == "__main__":
    sys.exit(main())
