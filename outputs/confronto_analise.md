# Confronto entre regra e agente — análise das divergências

Refere-se à execução salva em `confronto.csv` e `lote.json`. Como a API não expõe `seed`, outra
execução pode dar números diferentes: já observei concordância de 70% e de 60% sobre o mesmo lote.

## Critério de correspondência

O enunciado sugere "cliente sinalizado pelas duas regras deveria sair como risco alto". Não se
aplica aqui: a interseção entre as regras é vazia nas duas bases. Usei a semântica de cada regra:

| nível esperado | condição | por quê |
|---|---|---|
| alto | fracionamento (Regra 1) | dividir valores para ficar sob um limite é deliberado; a intenção está no dado |
| médio | 2+ operações atípicas (Regra 2) | um ponto fora da curva é ruído, vários formam padrão |
| baixo | 1 operação atípica | é onde mora o falso positivo: empresa recebendo pagamento grande |

## Resultado

**Concordância: 6 de 10 (60%).** As 4 divergências foram todas na mesma direção — o agente mais
severo que a regra, nunca mais brando.

| cliente | regra | agente | direção |
|---|---|---|---|
| CLI-023 | médio | alto | agente mais severo |
| CLI-013 | médio | alto | agente mais severo |
| CLI-001 | médio | alto | agente mais severo |
| CLI-030 | baixo | médio | agente mais severo |

## Quem estava certo

**CLI-001 — o agente.** Subiu para alto porque a operação atípica foi em espécie, e espécie é 52%
do volume do cliente. Nenhuma das duas regras olha `canal`: ele não entra em nenhum critério. O
agente viu um agravante real que a regra é estruturalmente incapaz de ver. É o caso que justifica
ter uma LLM na mesa.

**CLI-023 — o agente, provavelmente.** Razões de 20,18x e 12,89x, as maiores do lote, mais 28% do
volume em espécie. Meu critério trata "2+ operações atípicas" como médio sem olhar magnitude nem
canal, então achata um caso que tem as duas coisas.

**CLI-013 — a regra.** O agente subiu com razões de 9,05x e 8,5x e 68% em TED. Comparado ao
CLI-023, que é mais grave em todas as dimensões, não há critério que sustente os dois no mesmo
nível — e em execuções anteriores o CLI-023 saiu médio enquanto o CLI-013 saiu alto. Não é
divergência informativa, é inconsistência entre casos parecidos.

**CLI-030 — empate.** A regra diz baixo por ser operação única; o agente diz médio porque essa
operação é 16,84x a mediana, a segunda maior razão do lote. Aqui a limitação é do meu critério,
que usa "uma operação" como proxy de falso positivo e ignora magnitude.

## O que isso diz

Com 10 casos não há conclusão estatística. O que se sustenta é o padrão: **o agente agrega valor
onde enxerga dimensão que a regra não modela — canal e contraparte — e atrapalha onde apenas
reordena o que a regra já mediu.**

Duas das quatro divergências apontam para uma falha do meu critério, não do agente: ele não pesa
magnitude nem canal. Uma terceira regra determinística sobre concentração de canal cobriria parte
disso e daria ao confronto uma dimensão a mais para discordar.

## Lote de controle

Os 10 clientes do lote já vinham sinalizados, então concordância alta seria concordância por
construção. Rodei 4 clientes que nenhuma regra pegou (`controle.csv`): **4 de 4 saíram `baixo`,
com zero red flags**, e 3 pararam depois de uma única ferramenta. O agente sabe dizer baixo e sabe
parar de investigar quando não há o que investigar.
