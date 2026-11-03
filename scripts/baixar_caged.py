"""Baixa os microdados do Novo CAGED (FTP do MTE) e guarda só o varejo alimentar.

Para cada mês: baixa CAGEDMOVAAAAMM.7z, extrai, filtra as subclasses CNAE de
hiper, super e minimercados e agrega por município. O resultado parcial de
cada mês fica em data/raw/caged_meses/ para retomar se a conexão cair. No fim,
tudo é juntado em data/raw/caged_supermercados.csv.

    pip install py7zr
    python scripts/baixar_caged.py --inicio 2021-04
    python scripts/baixar_caged.py --com-fora-do-prazo   # soma também CAGEDFOR
"""

from __future__ import annotations

import argparse
import ftplib
import io
import sys
import tempfile
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from litoral import config, ingestao  # noqa: E402

FTP = "ftp.mtps.gov.br"
PASTA = "pdet/microdados/NOVO CAGED"
CACHE = config.BRUTOS / "caged_meses"
USAR = {"competenciamov", "municipio", "subclasse", "saldomovimentacao"}


def baixar(ftp: ftplib.FTP, caminho: str) -> bytes | None:
    buf = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {caminho}", buf.write)
    except ftplib.error_perm:
        return None
    return buf.getvalue()


def ler_7z(conteudo: bytes) -> pd.DataFrame:
    import py7zr

    with tempfile.TemporaryDirectory() as tmp:
        with py7zr.SevenZipFile(io.BytesIO(conteudo)) as arq:
            arq.extractall(tmp)
        txt = next(Path(tmp).rglob("*.txt"))
        for codificacao in ("utf-8", "latin-1"):
            try:
                cab = pd.read_csv(txt, sep=";", nrows=0, encoding=codificacao).columns
                manter = [c for c in cab if ingestao._sem_acento(c) in USAR]
                partes = pd.read_csv(
                    txt, sep=";", usecols=manter, encoding=codificacao, chunksize=500_000, dtype=str
                )
                return (
                    pd.concat(ingestao.agregar_microdados_caged(p.dropna()) for p in partes)
                    .groupby(["mes", "municipio6"], as_index=False)
                    .sum()
                )
            except UnicodeDecodeError:
                continue
    raise ValueError("codificação do arquivo não reconhecida")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2021-04")
    ap.add_argument("--fim", default=str(pd.Period.now("M") - 1))
    ap.add_argument("--com-fora-do-prazo", action="store_true")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    tipos = ["MOV"] + (["FOR"] if args.com_fora_do_prazo else [])
    ftp = ftplib.FTP(FTP, timeout=300)
    ftp.login()
    ftp.encoding = "latin-1"
    for mes in pd.period_range(args.inicio, args.fim, freq="M"):
        aaaamm = mes.strftime("%Y%m")
        for tipo in tipos:
            saida = CACHE / f"{tipo}{aaaamm}.csv"
            if saida.exists():
                continue
            conteudo = baixar(ftp, f"{PASTA}/{mes.year}/{aaaamm}/CAGED{tipo}{aaaamm}.7z")
            if conteudo is None:
                print(f"{aaaamm} {tipo}: não encontrado no FTP")
                continue
            df = ler_7z(conteudo)
            df.to_csv(saida, index=False)
            print(f"{aaaamm} {tipo}: {df['admissoes'].sum():,} admissões no varejo alimentar")
    ftp.quit()

    partes = [pd.read_csv(a) for a in sorted(CACHE.glob("*.csv"))]
    total = pd.concat(partes).groupby(["mes", "municipio6"], as_index=False).sum()
    total["mes"] = pd.PeriodIndex(pd.to_datetime(total["mes"].astype(str), format="%Y%m"), freq="M").astype(
        str
    )
    total.to_csv(config.ARQ_CAGED, index=False)
    print(f"{config.ARQ_CAGED.name}: {len(total):,} linhas, {total['mes'].nunique()} meses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
