import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import sintetico  # noqa: E402
from litoral import transformacao  # noqa: E402


@pytest.fixture(scope="session")
def dados():
    return sintetico.tudo()


@pytest.fixture(scope="session")
def painel(dados):
    p, _ = transformacao.montar_painel(dados["pix"], dados["municipios"], dados["costeiros"], dados["ipca"])
    return p
