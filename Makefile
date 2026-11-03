.PHONY: instalar baixar dados testes lint notebook servir tudo

instalar:
	pip install -e ".[dev,notebook,download]"

baixar:           ## dados brutos: referências, Pix por município (BCB) e CAGED (MTE)
	python scripts/baixar_referencias.py
	python scripts/baixar_pix.py
	python scripts/baixar_caged.py

dados:            ## validação, métricas e exportação para o site
	python -m litoral

testes:
	pytest --cov=litoral --cov-report=term-missing

lint:
	ruff check src tests scripts

notebook:
	jupyter nbconvert --to notebook --execute --inplace notebooks/analise.ipynb

servir:           ## site em http://localhost:8000
	python -m http.server 8000

tudo: lint testes dados notebook
