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
        inicio = time.perf_counter()
        bruto = None

        for _ in range(self.max_iteracoes):
            resposta = self.client.responses.create(
                model=self.model,
                temperature=0,
                instructions=INSTRUCOES,
                input=entrada,
                tools=ESQUEMAS,
                text={"format": {"type": "json_object"}},  # impede o ```json em volta
            )
            chamadas_api += 1
            tokens_entrada += resposta.usage.input_tokens
            tokens_saida += resposta.usage.output_tokens

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
            "aceito": erro is None,
            "motivo_recusa": erro,
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