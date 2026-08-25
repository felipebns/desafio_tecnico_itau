from pathlib import Path
import pandas as pd
import json

CAMINHO_BASE = Path(__file__).resolve().parent.parent / "dados" / "dados_nivel_2.json"

class Tools:
    MIN_OP_DIA = 3
    LIM_SOMA_DIA = 50000
    LIM_OP_ISOLADA = 20000
    MULTIPLO_MEDIANA = 5
    MIN_OP_CLIENTE = 4

    def __init__(self, caminho=CAMINHO_BASE):
        self.caminho = Path(caminho)
        self.df = self._carregar_base()

    def _carregar_base(self):
        """Aplica limpeza, normalização e as duas regras; devolve o DataFrame com as flags."""
        dados = json.loads(self.caminho.read_text(encoding="utf-8"))

        taxa_cambio = dados["taxa_cambio_usd_brl"]
        df = pd.json_normalize(dados["operacoes"]).drop_duplicates().reset_index(drop=True)

        df["valor"] = df["valor"].astype(float)
        em_usd = df["moeda"] == "USD"
        df.loc[em_usd, "valor"] *= taxa_cambio
        df.loc[em_usd, "moeda"] = "BRL"

        por_dia = df.groupby(["cliente_id", "data"], dropna=True).agg(
            n_operacoes=("valor", "size"),
            soma_dia=("valor", "sum"),
            maior_operacao=("valor", "max"),
        )
        dia_sinalizado = (
            (por_dia["n_operacoes"] >= self.MIN_OP_DIA)
            & (por_dia["soma_dia"] > self.LIM_SOMA_DIA)
            & (por_dia["maior_operacao"] < self.LIM_OP_ISOLADA)
        )
        df["flag_dia_regra1"] = (
            pd.MultiIndex.from_frame(df[["cliente_id", "data"]])
            .map(dia_sinalizado)
            .fillna(False)
            .astype(bool)
        )
        df["flag_regra1_fracionamento"] = df.groupby("cliente_id")["flag_dia_regra1"].transform("any")

        valores = df.groupby("cliente_id")["valor"]
        df["flag_regra2_valor_atipico"] = (valores.transform("size") >= self.MIN_OP_CLIENTE) & (
            df["valor"] > self.MULTIPLO_MEDIANA * valores.transform("median")
        )

        df["cliente_sinalizado"] = df["flag_regra1_fracionamento"] | df.groupby("cliente_id")[
            "flag_regra2_valor_atipico"
        ].transform("any")

        return df

    def clientes_sinalizados(self):
        return sorted(self.df.loc[self.df["cliente_sinalizado"], "cliente_id"].unique())

    def top_clientes(self, n=10):
        sinalizados = self.df[self.df["cliente_sinalizado"]]

        ranking = sinalizados.groupby("cliente_id").agg(
            ops_regra2=("flag_regra2_valor_atipico", "sum"),
            volume_total_brl=("valor", "sum"),
        )
        # Regra 1: um sinal por DIA que disparou. Dois fracionamentos em datas
        # diferentes sao dois casos na fila, nao um.
        dias = sinalizados[sinalizados["flag_dia_regra1"]].groupby("cliente_id")["data"].nunique()
        ranking["dias_regra1"] = dias.reindex(ranking.index, fill_value=0)
        ranking["sinalizacoes"] = ranking["dias_regra1"] + ranking["ops_regra2"]
        ranking["volume_total_brl"] = ranking["volume_total_brl"].round(2)
        ranking = ranking[["dias_regra1", "ops_regra2", "sinalizacoes", "volume_total_brl"]]

        return ranking.sort_values(["sinalizacoes", "volume_total_brl"], ascending=False).head(n)

    def _ops(self, cliente_id):
        return self.df[self.df["cliente_id"] == cliente_id]

    def historico_cliente(self, cliente_id):
        """Resumo agregado das operações do cliente."""
        ops = self._ops(cliente_id)
        if ops.empty:
            return {"erro": f"cliente {cliente_id} não existe na base"}

        dias_r1 = sorted(ops.loc[ops["flag_dia_regra1"], "data"].dropna().unique())
        com_data = ops["data"].dropna()

        # a razao vai calculada: sem ela o modelo divide sozinho, e ja errou fazendo isso
        mediana = float(ops["valor"].median())
        atipicas = [
            {
                "id": r.id,
                "valor_brl": round(float(r.valor), 2),
                "razao_vs_mediana": round(float(r.valor) / mediana, 2),
            }
            for r in ops[ops["flag_regra2_valor_atipico"]].itertuples()
        ]

        return {
            "cliente_id": cliente_id,
            "total_operacoes": len(ops),
            "janela": f"{com_data.min()} a {com_data.max()}" if not com_data.empty else None,
            "operacoes_sem_data": int(ops["data"].isna().sum()),
            "volume_total_brl": round(float(ops["valor"].sum()), 2),
            "desvio_padrao_brl": round(float(ops["valor"].std()), 2),
            "ticket_medio_brl": round(float(ops["valor"].mean()), 2),
            "mediana_brl": round(float(ops["valor"].median()), 2),
            "maior_operacao_brl": round(float(ops["valor"].max()), 2),
            "tipos": ops["tipo"].value_counts().to_dict(),
            "principais_contrapartes": ops["contraparte"].value_counts().head(5).to_dict(),
            "regra_1_fracionamento": {"disparou": bool(dias_r1), "dias": dias_r1},
            "regra_2_valor_atipico": {"disparou": bool(atipicas), "operacoes": atipicas},
        }

    def operacoes_do_dia(self, cliente_id, data):
        """Recorte das operações do cliente em um dia específico."""
        ops = self._ops(cliente_id)
        if ops.empty:
            return {"erro": f"cliente {cliente_id} não existe na base"}

        do_dia = ops[ops["data"] == data]
        if do_dia.empty:
            return {
                "cliente_id": cliente_id,
                "data": data,
                "n_operacoes": 0,
                "datas_disponiveis": sorted(ops["data"].dropna().unique()),
            }

        return {
            "cliente_id": cliente_id,
            "data": data,
            "n_operacoes": len(do_dia),
            "soma_brl": round(float(do_dia["valor"].sum()), 2),
            "maior_operacao_brl": round(float(do_dia["valor"].max()), 2),
            "aciona_regra_1": bool(do_dia["flag_dia_regra1"].any()),
            "operacoes": do_dia[
                ["id", "valor", "canal", "tipo", "contraparte", "observacao"]
            ].to_dict("records"),
        }

    def perfil_canal(self, cliente_id):
        """Distribuição de uso por canal."""
        ops = self._ops(cliente_id)
        if ops.empty:
            return {"erro": f"cliente {cliente_id} não existe na base"}

        por_canal = ops.groupby("canal").agg(
            operacoes=("valor", "size"), volume_brl=("valor", "sum")
        )
        por_canal["pct_volume"] = (100 * por_canal["volume_brl"] / por_canal["volume_brl"].sum())
        por_canal = por_canal.round(2).sort_values("volume_brl", ascending=False)

        return {
            "cliente_id": cliente_id,
            "total_operacoes": len(ops),
            "canais": por_canal.to_dict("index"),
        }

    def executar(self, nome, argumentos):
        """Despacha uma chamada de ferramenta vinda do modelo."""
        disponiveis = {
            "historico_cliente": self.historico_cliente,
            "operacoes_do_dia": self.operacoes_do_dia,
            "perfil_canal": self.perfil_canal,
        }
        if nome not in disponiveis:
            return {"erro": f"ferramenta desconhecida: {nome}"}
        return disponiveis[nome](**argumentos)

if __name__ == "__main__":
    tools = Tools()
    print(f"{len(tools.df)} operações, {tools.df['cliente_id'].nunique()} clientes")
    print(f"{len(tools.clientes_sinalizados())} clientes sinalizados\n")
    print(tools.top_clientes().to_string())
