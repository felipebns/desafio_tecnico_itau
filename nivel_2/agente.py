import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from tools import Tools

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ESQUEMAS = [
    {
        "type": "function",
        "name": "historico_cliente",
        "description": (
            "Resumo agregado do cliente: volume, ticket médio, mediana, maior operação, "
            "janela, tipos de operação, principais contrapartes, e quais regras dispararam "
            "com os dias e operações específicos."
        ),
        "parameters": {
            "type": "object",
            "properties": {"cliente_id": {"type": "string"}},
            "required": ["cliente_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "operacoes_do_dia",
        "description": (
            "Lista as operações do cliente em uma data (YYYY-MM-DD), com soma do dia e "
            "se aquele dia aciona a Regra 1."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cliente_id": {"type": "string"},
                "data": {"type": "string", "description": "formato YYYY-MM-DD"},
            },
            "required": ["cliente_id", "data"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "perfil_canal",
        "description": (
            "Distribuição das operações do cliente por canal (pix, ted, boleto, cartao, "
            "especie), com contagem, volume e percentual do volume."
        ),
        "parameters": {
            "type": "object",
            "properties": {"cliente_id": {"type": "string"}},
            "required": ["cliente_id"],
            "additionalProperties": False,
        },
    },
]

INSTRUCOES = """Você é analista de Prevenção à Lavagem de Dinheiro numa mesa de triagem.
Recebe um cliente já sinalizado por regras determinísticas e produz um parecer em json.

As duas regras que sinalizam:
- Regra 1, fracionamento: o cliente fez 3+ operações numa mesma data somando mais de
  R$ 50.000, com nenhuma operação isolada atingindo R$ 20.000. Sinaliza o CLIENTE, e o
  evento tem uma DATA específica.
- Regra 2, valor atípico: uma operação do cliente passou de 5x a mediana dele, entre
  clientes com 4+ operações. Sinaliza a OPERAÇÃO, e não tem nada a ver com data.

COMO ESCOLHER AS FERRAMENTAS

Comece sempre por historico_cliente: ele diz qual regra disparou e em que dia ou operação.
Depois consulte só o que muda o seu parecer. Não chame ferramenta cujo resultado você já
consegue antecipar, e não chame as três por padrão.

Exemplo A — histórico mostra Regra 1 disparada em 2026-05-26, Regra 2 não.
  O fracionamento é um evento de um dia. Chame operacoes_do_dia nessa data para ver as
  transações que o compõem: valores, canais e contrapartes. Só chame perfil_canal se
  aquelas operações sugerirem concentração de canal ou uso de espécie que o dia isolado
  não explica.

Exemplo B — histórico mostra Regra 2 disparada em 3 operações, Regra 1 não.
  Não há dia de interesse: operacoes_do_dia não ajuda aqui. O que falta saber é se as
  operações atípicas vêm por um canal que destoa do resto. Chame perfil_canal.

Exemplo C — histórico mostra as duas regras disparadas.
  Trate como caso composto: operacoes_do_dia no dia do fracionamento e perfil_canal para
  o padrão geral.

Exemplo D — histórico já responde tudo.
  Cliente com 4 operações, uma atípica óbvia, canal único e contraparte única. Nenhuma
  outra ferramenta acrescenta. Emita o parecer direto.

COMO GRADUAR O RISCO

A sinalização por regra é o ponto de partida, não a conclusão. As regras são deliberadamente
simples e geram falsos positivos: elas medem forma, não intenção. Seu trabalho é dizer se o que
está nos dados sustenta a suspeita. O nível deve refletir a força da evidência, não o fato de a
regra ter disparado.

"alto" quando os indícios convergem e o padrão é difícil de explicar por atividade legítima:
vários sinais independentes apontando para o mesmo lado, valores repetidamente logo abaixo de um
limite, concentração em canal que dificulta rastreio, a mesma contraparte recebendo o conjunto,
ou movimentação que não guarda relação com o resto do histórico do cliente.

"médio" quando há indício real mas com explicação alternativa plausível: uma operação grande
isolada que pode ser venda de ativo ou recebimento sazonal, um valor atípico num cliente que de
resto é regular, ou um padrão que só se confirmaria com informação que você não tem.

"baixo" quando o que disparou a regra se explica pelo próprio comportamento do cliente: a operação
destoa da mediana mas é coerente com o porte e o tipo de atividade dele, ou a regra pegou uma
tecnicalidade sem substância atrás.

Gradue pela natureza do que você encontrou, não pelo fato de haver sinalização. Fracionamento é
comportamento deliberado — alguém dividiu valores para ficar sob um limite, e isso é intenção
visível no dado. Um valor atípico isolado é um ponto fora da curva, que sozinho não diz nada sobre
intenção: empresas recebem pagamentos grandes. Vários pontos fora da curva no mesmo cliente já
começam a formar padrão.

Pese também o canal e a contraparte: espécie e saque escondem origem de um jeito que TED e boleto
não escondem, e o mesmo destinatário recebendo o conjunto pesa mais do que destinatários variados.

Os três níveis precisam ser usados. Se você classificar todo cliente sinalizado no mesmo nível,
seu parecer não acrescenta nada ao que a regra já disse.

REGRAS DO PARECER

Os números vêm das ferramentas e já foram calculados e conferidos. Não recalcule somas,
não verifique limites e não questione se a regra disparou. Interprete e redija.
Cite apenas números que apareceram literalmente no retorno de alguma ferramenta. Não divida,
não some e não converta em percentual por conta própria; se o número que você quer citar não
está lá, descreva em palavras em vez de estimar. O limite de uma regra (por exemplo "5x a
mediana") é o corte que a aciona, não a medida do caso: para a medida, use razao_vs_mediana.
Não afirme fato que as ferramentas não mostraram: se precisar de informação que não tem,
diga na justificativa que ela seria necessária, em vez de supor.

Responda com um objeto json, e nada fora dele, com exatamente estes campos:
- "nivel_risco": um entre "baixo", "médio", "alto"
- "tipologia_suspeita": string curta nomeando a tipologia
- "red_flags": lista de strings, cada uma ancorada em algo que você viu nas ferramentas
- "justificativa": string, no máximo 4 frases"""

# Preço por 1M de tokens do gpt-4o-mini, em USD. Confira na tabela vigente do provedor
# antes de citar o custo em qualquer lugar — é parâmetro, não verdade do código.
PRECO_ENTRADA_1M = 0.15
PRECO_SAIDA_1M = 0.60


def custo_usd(tokens_entrada, tokens_saida):
    return tokens_entrada / 1e6 * PRECO_ENTRADA_1M + tokens_saida / 1e6 * PRECO_SAIDA_1M


class Agente:
    NIVEIS_VALIDOS = {"baixo", "médio", "alto"}
    CAMPOS_OBRIGATORIOS = {"nivel_risco", "tipologia_suspeita", "red_flags", "justificativa"}

    def __init__(self, tools=None, model="gpt-4o-mini", max_iteracoes=5):
        self.tools = tools or Tools()
        self.client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
        self.model = model
        self.max_iteracoes = max_iteracoes

    def analisar(self, cliente_id):
        """Devolve (parecer, metricas). parecer é None quando a saída é recusada."""
        entrada = [
            {
                "role": "user",
                "content": f"Analise o cliente {cliente_id} e devolva o parecer em json.",
            }
        ]
        ferramentas_usadas = []
        tokens_entrada = tokens_saida = 0
        chamadas_api = 0
        chamadas = []  # custo e latência de cada chamada de API, não só do total
        inicio = time.perf_counter()
        bruto = None

        for iteracao in range(self.max_iteracoes):
            t0 = time.perf_counter()
            resposta = self.client.responses.create(
                model=self.model,
                temperature=0,
                instructions=INSTRUCOES,
                input=entrada,
                tools=ESQUEMAS,
                text={"format": {"type": "json_object"}},  # impede o ```json em volta
            )
            latencia_chamada = time.perf_counter() - t0
            chamadas_api += 1
            tokens_entrada += resposta.usage.input_tokens
            tokens_saida += resposta.usage.output_tokens
            chamadas.append(
                {
                    "cliente_id": cliente_id,
                    "iteracao": iteracao,
                    "tokens_entrada": resposta.usage.input_tokens,
                    "tokens_saida": resposta.usage.output_tokens,
                    "latencia_s": round(latencia_chamada, 3),
                    "custo_usd": round(
                        custo_usd(resposta.usage.input_tokens, resposta.usage.output_tokens), 6
                    ),
                }
            )

            pedidos = [i for i in resposta.output if i.type == "function_call"]
            if not pedidos:
                bruto = resposta.output_text
                break

            for pedido in pedidos:
                argumentos = json.loads(pedido.arguments)
                resultado = self.tools.executar(pedido.name, argumentos)
                ferramentas_usadas.append({"ferramenta": pedido.name, "argumentos": argumentos})
                entrada.append(pedido.model_dump())
                entrada.append(
                    {
                        "type": "function_call_output",
                        "call_id": pedido.call_id,
                        "output": json.dumps(resultado, ensure_ascii=False, default=str),
                    }
                )
        else:
            bruto = None

        latencia = time.perf_counter() - inicio
        parecer, erro = (None, "limite de iterações atingido sem parecer")
        if bruto is not None:
            parecer, erro = self._valida_estrutura(bruto)

        metricas = {
            "cliente_id": cliente_id,
            "modelo": self.model,
            "chamadas_api": chamadas_api,
            "ferramentas_usadas": [f["ferramenta"] for f in ferramentas_usadas],
            "n_ferramentas": len(ferramentas_usadas),
            "latencia_s": round(latencia, 2),
            "tokens_entrada": tokens_entrada,
            "tokens_saida": tokens_saida,
            "tokens_total": tokens_entrada + tokens_saida,
            "custo_usd": round(custo_usd(tokens_entrada, tokens_saida), 6),
            "aceito": erro is None,
            "motivo_recusa": erro,
            "chamadas": chamadas,
        }
        return parecer, metricas

    def _valida_estrutura(self, bruto):
        """Devolve (parecer, erro). Com erro != None a saída é recusada."""
        try:
            d = json.loads(bruto)
        except json.JSONDecodeError as e:
            return None, f"não é JSON válido ({e})"
        if not isinstance(d, dict):
            return None, "JSON não é um objeto"
        if faltando := self.CAMPOS_OBRIGATORIOS - d.keys():
            return None, f"campos ausentes: {sorted(faltando)}"
        if sobrando := d.keys() - self.CAMPOS_OBRIGATORIOS:
            return None, f"campos não previstos: {sorted(sobrando)}"

        nivel = d["nivel_risco"]
        if not isinstance(nivel, str) or nivel.strip().lower() not in self.NIVEIS_VALIDOS:
            return None, f"nivel_risco fora do domínio: {nivel!r}"
        d["nivel_risco"] = nivel.strip().lower()

        if not isinstance(d["red_flags"], list):
            return None, "red_flags não é lista"
        if not all(isinstance(f, str) and f.strip() for f in d["red_flags"]):
            return None, "red_flags deve conter apenas strings não vazias"
        for campo in ("tipologia_suspeita", "justificativa"):
            if not isinstance(d[campo], str) or not d[campo].strip():
                return None, f"{campo} deve ser texto não vazio"
        return d, None

    def executar_lote(self, clientes):
        """Roda o agente sobre uma lista de clientes; devolve um registro por cliente."""
        registros = []
        for i, cliente in enumerate(clientes, 1):
            parecer, metricas = self.analisar(cliente)
            print(
                f"  [{i}/{len(clientes)}] {cliente}: "
                f"{'ok' if metricas['aceito'] else 'RECUSADO'} | "
                f"{metricas['chamadas_api']} chamadas | {metricas['tokens_total']} tok | "
                f"{metricas['latencia_s']}s"
            )
            registros.append({"cliente_id": cliente, "parecer": parecer, "metricas": metricas})
        return registros

def parte_a(tools, n=10):
    """Parte A — ranking dos clientes mais sinalizados."""
    print(f"{len(tools.df)} operações, {tools.df['cliente_id'].nunique()} clientes, "
          f"{len(tools.clientes_sinalizados())} sinalizados\n")
    ranking = tools.top_clientes(n=n)
    print(ranking.to_string())
    return ranking


def parte_c(tools, clientes, modelo="gpt-4o-mini"):
    """Parte C — roda o agente em lote e salva os resultados em outputs/."""
    import pandas as pd

    saida = Path(__file__).resolve().parent.parent / "outputs"
    saida.mkdir(exist_ok=True)

    print(f"Rodando o agente sobre {len(clientes)} clientes: {clientes}\n")
    registros = Agente(tools=tools, model=modelo).executar_lote(clientes)

    (saida / "lote.json").write_text(
        json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    linhas = []
    for r in registros:
        p, m = r["parecer"] or {}, r["metricas"]
        linhas.append(
            {
                "cliente_id": r["cliente_id"],
                "aceito": m["aceito"],
                "nivel_risco": p.get("nivel_risco"),
                "tipologia_suspeita": p.get("tipologia_suspeita"),
                "n_red_flags": len(p.get("red_flags", [])),
                "red_flags": " | ".join(p.get("red_flags", [])),
                "justificativa": p.get("justificativa"),
                "ferramentas": " -> ".join(m["ferramentas_usadas"]),
                "n_ferramentas": m["n_ferramentas"],
                "chamadas_api": m["chamadas_api"],
                "tokens_entrada": m["tokens_entrada"],
                "tokens_saida": m["tokens_saida"],
                "tokens_total": m["tokens_total"],
                "custo_usd": m["custo_usd"],
                "latencia_s": m["latencia_s"],
            }
        )
    lote = pd.DataFrame(linhas)
    lote.to_csv(saida / "lote.csv", index=False)

    chamadas = pd.DataFrame([c for r in registros for c in r["metricas"]["chamadas"]])
    chamadas.to_csv(saida / "chamadas.csv", index=False)

    print("\n" + "=" * 72)
    print("TOTAIS DO LOTE")
    print("=" * 72)
    print(
        pd.DataFrame(
            {
                "clientes": [len(lote)],
                "aceitos": [int(lote["aceito"].sum())],
                "chamadas_api": [int(lote["chamadas_api"].sum())],
                "tokens_total": [int(lote["tokens_total"].sum())],
                "custo_usd": [round(lote["custo_usd"].sum(), 4)],
                "latencia_total_s": [round(lote["latencia_s"].sum(), 1)],
            }
        ).to_string(index=False)
    )

    print("\nPor chamada de API:")
    print(
        chamadas[["tokens_entrada", "tokens_saida", "latencia_s", "custo_usd"]]
        .describe()
        .round(4)
        .to_string()
    )

    print("\nCusto por cliente:")
    print(
        lote[["cliente_id", "n_ferramentas", "chamadas_api", "tokens_total", "custo_usd", "latencia_s"]]
        .sort_values("custo_usd", ascending=False)
        .to_string(index=False)
    )

    print("\nDistribuição de nivel_risco:")
    print(lote["nivel_risco"].value_counts().to_string())

    print("\nCusto médio por combinação de ferramentas:")
    print(
        lote.groupby("ferramentas")
        .agg(clientes=("cliente_id", "size"), tokens=("tokens_total", "mean"), custo=("custo_usd", "mean"))
        .round(4)
        .to_string()
    )

    print("\nSalvos em outputs/: lote.json, lote.csv, chamadas.csv")
    return registros

if __name__ == "__main__":
    # ORDEM DE EXECUÇÃO: este script produz outputs/lote.json, que confronto.py consome.
    # Rode agente.py antes de confronto.py.
    tools = Tools()

    # Parte A — ranking dos 10 mais sinalizados.
    parte_a(tools)

    # Parte C — roda o agente em lote e salva em outputs/.
    # As duas são independentes: comente qualquer uma das chamadas para rodar só a outra.
    parte_c(tools, tools.top_clientes(n=10).index.tolist())
