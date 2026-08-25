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

if __name__ == "__main__":
    tools = Tools()
    print(f"{len(tools.df)} operações, {tools.df['cliente_id'].nunique()} clientes")
    print(f"{len(tools.clientes_sinalizados())} clientes sinalizados\n")
    print(tools.top_clientes().to_string())
