"""Baixa as tabelas de apoio: IPCA (BCB/SGS 433), cadastro de municípios e a lista
de municípios defrontantes com o mar (IBGE).

    python scripts/baixar_referencias.py
"""

from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from litoral import config  # noqa: E402

URL_IPCA = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2020"
URL_MUNICIPIOS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
PASTA_IBGE = "https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/municipios_defrontantes_com_o_mar/"


def ler_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def ipca() -> None:
    dados = json.loads(ler_url(URL_IPCA))
    df = pd.DataFrame(dados)
    df["mes"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.strftime("%Y-%m")
    df = df.rename(columns={"valor": "ipca_variacao_mensal_pct"})[["mes", "ipca_variacao_mensal_pct"]]
    df.to_csv(config.ARQ_IPCA, index=False)
    print(f"IPCA: {df['mes'].iloc[0]} a {df['mes'].iloc[-1]}")


def municipios() -> None:
    config.ARQ_MUNICIPIOS.write_bytes(ler_url(URL_MUNICIPIOS))
    print(f"Municípios: {len(pd.read_csv(config.ARQ_MUNICIPIOS))}")


def defrontantes() -> None:
    """Procura a edição mais recente com planilha e salva um CSV padronizado."""
    anos = sorted(set(re.findall(r'href="(\d{4})/"', ler_url(PASTA_IBGE).decode("latin-1"))), reverse=True)
    for ano in anos:
        pagina = ler_url(f"{PASTA_IBGE}{ano}/").decode("latin-1")
        planilhas = re.findall(r'href="([^"]+\.(?:xlsx?|ods|csv))"', pagina, flags=re.I)
        if not planilhas:
            continue
        nome = planilhas[0]
        conteudo = ler_url(f"{PASTA_IBGE}{ano}/{nome}")
        df = (
            pd.read_csv(io.BytesIO(conteudo), dtype=str)
            if nome.lower().endswith(".csv")
            else pd.read_excel(io.BytesIO(conteudo), dtype=str)
        )
        codigo = next(
            c for c in df.columns if df[c].dropna().astype(str).str.fullmatch(r"\d{7}").mean() > 0.9
        )
        df = df[df[codigo].astype(str).str.fullmatch(r"\d{7}", na=False)]
        out = pd.DataFrame({"codigo_ibge": df[codigo].astype(int)})
        out["edicao"] = int(ano)
        out.to_csv(config.ARQ_DEFRONTANTES, index=False)
        print(f"Defrontantes com o mar ({ano}): {len(out)} municípios")
        return
    print(
        "Não achei planilha da lista de defrontantes no geoftp do IBGE.\n"
        f"Baixe manualmente em {PASTA_IBGE} e salve como {config.ARQ_DEFRONTANTES}\n"
        "com uma coluna de códigos IBGE de 7 dígitos."
    )


if __name__ == "__main__":
    ipca()
    municipios()
    defrontantes()
