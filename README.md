# Desafio Técnico — Estágio em Engenharia de IA

## Como rodar

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # e preencha OPENAI_KEY
```

**Nível 1** — abra `nivel_1/nivel_1.ipynb` e rode de cima para baixo. As saídas já estão
commitadas; a Parte B faz chamadas de API e precisa da chave.

**Nível 2**

**A ordem importa:** `confronto.py` lê `outputs/lote.json`, que é produzido por `agente.py`.
Rodar fora de ordem para com uma mensagem explicando o que falta.

```bash
cd nivel_2
python tools.py       # Parte A: ranking dos 10 clientes mais sinalizados
python agente.py      # Partes A e C: ranking + lote do agente -> outputs/
python confronto.py   # Parte D: confronto e lote de controle -> outputs/  (depende do anterior)
```

Em `agente.py` as chamadas de `parte_a` e `parte_c` ficam no `__main__` e são independentes:
comente qualquer uma para rodar só a outra.

### Com Docker

```bash
docker build -t pld-desafio .

# Parte A — não precisa de chave
docker run --rm pld-desafio python tools.py

# Partes A e C — chave por variável de ambiente, outputs/ montado como volume
docker run --rm --env-file .env -v "$PWD/outputs:/app/outputs" pld-desafio

# Parte D
docker run --rm --env-file .env -v "$PWD/outputs:/app/outputs" pld-desafio python confronto.py
```

A chave nunca entra na imagem: vem por `--env-file` no runtime, e o `.dockerignore` bloqueia o
`.env` local de ser copiado por acidente. O volume em `outputs/` é o que faz os resultados saírem
do container.

## Estrutura

```
dados/          dados_nivel_1.json, dados_nivel_2.json (anexos do e-mail)
nivel_1/        nivel_1.ipynb — limpeza, regras, validação, análise com LLM
nivel_2/        tools.py     — camada de dados: limpeza, regras e as 3 ferramentas
                agente.py    — agente com function calling + execução em lote
                confronto.py — regra x agente, e o lote de controle
outputs/        resultados salvos das execuções
docs/           DECISOES.md, USO_DE_IA.md
Dockerfile      imagem para rodar o Nível 2 sem instalar nada local
```

## O que existe em `outputs/`

| arquivo | o que é |
|---|---|
| `lote.json` | um registro por cliente: parecer estruturado + métricas |
| `lote.csv` | o mesmo, tabular |
| `chamadas.csv` | custo e latência de **cada chamada de API**, não só por cliente |
| `confronto.csv` | nível da regra × nível do agente, com direção da divergência |
| `controle.csv` | agente rodado sobre clientes que nenhuma regra sinalizou |
| `confronto_analise.md` | análise das divergências: critério, quem estava certo em cada caso |
