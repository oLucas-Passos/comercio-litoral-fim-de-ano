"""Checagens de qualidade antes da análise.

Erros interrompem o pipeline. Avisos ficam registrados no relatório e no JSON
exportado, para que as lacunas apareçam no site em vez de sumirem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Estados com litoral. Um município costeiro fora deles indica lista errada.
UFS_LITORAL = {
    "AP",
    "PA",
    "MA",
    "PI",
    "CE",
    "RN",
    "PB",
    "PE",
    "AL",
    "SE",
    "BA",
    "ES",
    "RJ",
    "SP",
    "PR",
    "SC",
    "RS",
}


class ErroValidacao(ValueError):
    """Dados violam uma regra bloqueante."""


@dataclass
class Relatorio:
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erros

    def exigir(self) -> Relatorio:
        if self.erros:
            raise ErroValidacao("; ".join(self.erros))
        return self


def validar_pix(pix: pd.DataFrame, municipios: pd.DataFrame) -> Relatorio:
    r = Relatorio()
    exigidas = {"mes", "municipio", "recebido_pj", "empresas", "pago_pf"}
    faltando = exigidas - set(pix.columns)
    if faltando:
        r.erros.append(f"Pix: colunas ausentes {sorted(faltando)}")
        return r

    dup = int(pix.duplicated(["mes", "municipio"]).sum())
    if dup:
        r.erros.append(f"Pix: {dup} linhas duplicadas para (mes, municipio)")

    desconhecidos = set(pix["municipio"]) - set(municipios["municipio"])
    if desconhecidos:
        # Municípios criados depois do cadastro aparecem aqui; poucos casos viram aviso e saem da análise.
        destino = r.erros if len(desconhecidos) > 10 else r.avisos
        destino.append(
            f"Pix: {len(desconhecidos)} códigos fora do cadastro IBGE {sorted(desconhecidos)[:10]}"
        )

    negativos = int((pix[["recebido_pj", "pago_pf"]] < 0).any(axis=1).sum())
    if negativos:
        r.erros.append(f"Pix: {negativos} linhas com valor negativo")

    meses = pd.period_range(pix["mes"].min(), pix["mes"].max(), freq="M")
    faltam = sorted(set(meses) - set(pix["mes"]))
    if faltam:
        r.erros.append(f"Pix: meses ausentes {[str(m) for m in faltam]}")

    por_mes = pix.groupby("mes")["municipio"].nunique()
    baixos = por_mes[por_mes < 0.95 * len(municipios)]
    if len(baixos):
        r.avisos.append(
            f"Pix: {len(baixos)} meses com menos de 95% dos municípios "
            f"(mínimo {int(baixos.min())} em {baixos.idxmin()})"
        )

    zeros = pix[pix["recebido_pj"] == 0]
    if len(zeros):
        r.avisos.append(
            f"Pix: {len(zeros)} registros com zero recebido por empresas "
            f"em {zeros['municipio'].nunique()} municípios"
        )
    return r


def validar_caged(caged: pd.DataFrame) -> Relatorio:
    r = Relatorio()
    dup = int(caged.duplicated(["mes", "municipio6"]).sum())
    if dup:
        r.erros.append(f"CAGED: {dup} linhas duplicadas para (mes, municipio6)")
    if (caged[["admissoes", "desligamentos"]] < 0).any().any():
        r.erros.append("CAGED: contagem negativa de admissões ou desligamentos")
    inconsistentes = int((caged["admissoes"] - caged["desligamentos"] != caged["saldo"]).sum())
    if inconsistentes:
        r.erros.append(f"CAGED: {inconsistentes} linhas com saldo diferente de admissões menos desligamentos")
    if not caged["municipio6"].between(110000, 539999).all():
        r.erros.append("CAGED: código de município fora do formato de 6 dígitos")
    meses = pd.period_range(caged["mes"].min(), caged["mes"].max(), freq="M")
    faltam = sorted(set(meses) - set(caged["mes"]))
    if faltam:
        r.avisos.append(f"CAGED: meses sem registro {[str(m) for m in faltam]}")
    return r


def validar_litoral(costeiros: set[int], municipios: pd.DataFrame) -> Relatorio:
    r = Relatorio()
    cadastro = municipios.set_index("municipio")
    fora = costeiros - set(cadastro.index)
    if fora:
        # A lista do IBGE inclui lagoas como unidades próprias (ex.: 4300002, Lagoa Mirim).
        r.avisos.append(
            f"Litoral: {len(fora)} códigos fora do cadastro de municípios, ignorados {sorted(fora)}"
        )
    ufs = set(cadastro.loc[sorted(costeiros & set(cadastro.index)), "uf"])
    estranhas = ufs - UFS_LITORAL
    if estranhas:
        r.erros.append(f"Litoral: municípios em UFs sem litoral {sorted(estranhas)}")
    if not 150 <= len(costeiros) <= 600:
        r.avisos.append(f"Litoral: {len(costeiros)} municípios; a lista do IBGE tem cerca de 280")
    faltando = UFS_LITORAL - ufs
    if faltando:
        r.avisos.append(f"Litoral: nenhuma cidade em {sorted(faltando)}")
    return r
