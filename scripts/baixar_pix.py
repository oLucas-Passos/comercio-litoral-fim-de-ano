"""Baixa as transações Pix por município da API de dados abertos do Banco Central.

Um arquivo por mês em data/raw/pix/AAAAMM.csv.gz. Meses já baixados são
pulados; o último mês é sempre baixado de novo, porque o BCB revisa o mês
mais recente.

    python scripts/baixar_pix.py               # de 2020-11 até o último mês publicado
    python scripts/baixar_pix.py --inicio 2024-01
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "data" / "raw" / "pix"
URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"
    "TransacoesPixPorMunicipio(DataBase=@DataBase)"
)
COLUNAS = [
    "AnoMes",
    "Municipio_Ibge",
    "Municipio",
    "Estado_Ibge",
    "Sigla_Regiao",
    "VL_PagadorPF",
    "QT_PagadorPF",
    "VL_PagadorPJ",
    "QT_PagadorPJ",
    "VL_RecebedorPF",
    "QT_RecebedorPF",
    "VL_RecebedorPJ",
    "QT_RecebedorPJ",
    "QT_PES_PagadorPF",
    "QT_PES_PagadorPJ",
    "QT_PES_RecebedorPF",
    "QT_PES_RecebedorPJ",
]


def baixar_mes(mes: pd.Period, tentativas: int = 4) -> pd.DataFrame:
    params = {
        # O parâmetro DataBase não filtra o mês; o filtro precisa ir em $filter.
        "@DataBase": f"'{mes.strftime('%Y%m')}'",
        "$filter": f"AnoMes eq {mes.strftime('%Y%m')}",
        "$format": "json",
        "$top": "100000",
        "$select": ",".join(COLUNAS),
    }
    url = URL + "?" + urllib.parse.urlencode(params, safe="@$',", quote_via=urllib.parse.quote)
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return pd.DataFrame(json.load(resp)["value"])
        except Exception as erro:  # noqa: BLE001 - a API do BCB falha de forma intermitente
            if i == tentativas - 1:
                raise
            espera = 5 * (i + 1)
            print(f"  {mes}: {erro}; nova tentativa em {espera}s")
            time.sleep(espera)
    raise RuntimeError("inalcançável")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2020-11")
    ap.add_argument("--fim", default=str(pd.Period.now("M") - 1))
    args = ap.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    meses = pd.period_range(args.inicio, args.fim, freq="M")
    ultimo_baixado = None
    for mes in meses:
        arquivo = DESTINO / f"{mes.strftime('%Y%m')}.csv.gz"
        if arquivo.exists() and mes != meses[-1]:
            ultimo_baixado = mes
            continue
        df = baixar_mes(mes)
        if df.empty:
            print(f"{mes}: ainda não publicado, parando aqui")
            break
        df.to_csv(arquivo, index=False)
        ultimo_baixado = mes
        print(
            f"{mes}: {len(df)} municípios, "
            f"R$ {df['VL_RecebedorPJ'].sum() / 1e9:,.1f} bi recebidos por empresas"
        )
    print(f"Último mês disponível: {ultimo_baixado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
