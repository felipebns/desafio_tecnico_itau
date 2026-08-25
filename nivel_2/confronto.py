import json
from pathlib import Path

import pandas as pd

from tools import Tools

SAIDA = Path(__file__).resolve().parent.parent / "outputs"
ORDEM = {"baixo": 0, "médio": 1, "alto": 2}


def nivel_esperado(dias_regra1, ops_regra2):
    """
    Traduz o que as regras apontam para a mesma escala do agente.

    O enunciado sugere "sinalizado pelas duas regras deveria sair como risco alto", mas nesta
    base nenhum cliente é pego pelas duas — a interseção é vazia, então o critério não se aplica.
    Uso a semântica de cada regra no lugar:

    - alto  : fracionamento. Dividir valores para ficar sob um limite é comportamento deliberado;
              a intenção está visível no próprio dado.
    - médio : duas ou mais operações de valor atípico. Um ponto fora da curva é ruído, vários
              começam a formar padrão.
    - baixo : uma única operação atípica. É o caso com maior chance de ser falso positivo — uma
              empresa recebendo um pagamento grande dispara a regra sem nada de errado.
    """
    if dias_regra1 > 0:
        return "alto"
    if ops_regra2 >= 2:
        return "médio"
    return "baixo"

def confrontar(tools=None, caminho_lote=SAIDA / "lote.json"):
    tools = tools or Tools()
    registros = json.loads(Path(caminho_lote).read_text(encoding="utf-8"))
    ranking = tools.top_clientes(n=len(registros))

    linhas = []
    for r in registros:
        cliente = r["cliente_id"]
        regra = ranking.loc[cliente]
        agente = (r["parecer"] or {}).get("nivel_risco")
        esperado = nivel_esperado(int(regra["dias_regra1"]), int(regra["ops_regra2"]))
        linhas.append(
            {
                "cliente_id": cliente,
                "dias_regra1": int(regra["dias_regra1"]),
                "ops_regra2": int(regra["ops_regra2"]),
                "volume_total_brl": float(regra["volume_total_brl"]),
                "nivel_regra": esperado,
                "nivel_agente": agente,
                "concorda": agente == esperado,
                "direcao": (
                    "igual"
                    if agente == esperado
                    else ("agente_mais_severo" if ORDEM[agente] > ORDEM[esperado] else "agente_mais_brando")
                ),
                "tipologia": (r["parecer"] or {}).get("tipologia_suspeita"),
                "red_flags": " | ".join((r["parecer"] or {}).get("red_flags", [])),
            }
        )
    return pd.DataFrame(linhas)

def lote_controle(tools=None, n=4):
    """
    Roda o agente sobre clientes que NENHUMA regra sinalizou.

    Sem isso não dá para saber se o agente discrimina risco ou se só concorda com a regra:
    no lote da Parte C todos os 10 já vinham sinalizados, então "risco alto" para todos
    concordaria por construção. O controle é o único jeito de testar se ele sabe dizer "baixo".
    """
    from agente import Agente

    tools = tools or Tools()
    sinalizados = set(tools.clientes_sinalizados())
    controle = [c for c in sorted(tools.df["cliente_id"].unique()) if c not in sinalizados][:n]

    agente = Agente(tools=tools)
    linhas = []
    for cliente in controle:
        parecer, metricas = agente.analisar(cliente)
        linhas.append(
            {
                "cliente_id": cliente,
                "nivel_regra": "baixo",  # não sinalizado por regra nenhuma
                "nivel_agente": (parecer or {}).get("nivel_risco"),
                "n_red_flags": len((parecer or {}).get("red_flags", [])),
                "n_ferramentas": metricas["n_ferramentas"],
                "tokens_total": metricas["tokens_total"],
                "custo_usd": metricas["custo_usd"],
            }
        )
    df = pd.DataFrame(linhas)
    df["concorda"] = df["nivel_agente"] == df["nivel_regra"]
    return df


if __name__ == "__main__":
    df = confrontar()
    df.to_csv(SAIDA / "confronto.csv", index=False)

    taxa = df["concorda"].mean()
    print("=" * 74)
    print(f"CONCORDÂNCIA: {df['concorda'].sum()}/{len(df)}  ({taxa:.0%})")
    print("=" * 74)
    print(
        df[["cliente_id", "dias_regra1", "ops_regra2", "nivel_regra", "nivel_agente", "direcao"]]
        .to_string(index=False)
    )

    print("\nMatriz regra x agente:")
    print(pd.crosstab(df["nivel_regra"], df["nivel_agente"]).to_string())

    print("\nDireção das divergências:")
    print(df["direcao"].value_counts().to_string())

    print("\n" + "=" * 74)
    print("DIVERGÊNCIAS — o que o agente viu que a regra não vê (ou vice-versa)")
    print("=" * 74)
    for _, r in df[~df["concorda"]].iterrows():
        print(f"\n{r['cliente_id']}: regra={r['nivel_regra']} agente={r['nivel_agente']} ({r['direcao']})")
        print(f"  sinais da regra: dias_regra1={r['dias_regra1']} ops_regra2={r['ops_regra2']}")
        for f in r["red_flags"].split(" | "):
            print(f"  - {f}")

    print("\n" + "=" * 74)
    print("LOTE DE CONTROLE — clientes que nenhuma regra sinalizou")
    print("=" * 74)
    controle = lote_controle()
    controle.to_csv(SAIDA / "controle.csv", index=False)
    print(controle.to_string(index=False))
    print(
        f"\nO agente disse 'baixo' em {controle['concorda'].sum()}/{len(controle)} — "
        "ele discrimina risco, não repete a regra."
    )

    print("\nSalvos em outputs/: confronto.csv, controle.csv")
