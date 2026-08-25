# Decisões

## Trade-offs

### Definição de "cliente sinalizado"

**Um cliente está sinalizado se qualquer uma das duas regras o alcançou** — seja ele o alvo
direto da regra, seja dono de uma operação alvo.

As duas regras têm granularidade diferente: a Regra 1 marca o cliente, a Regra 2 marca a
operação. Adotar a união resolve isso sem privilegiar nenhuma das duas. 

### Unidade de uma "sinalização"

Cada dia que aciona a Regra 1 conta um sinal, cada operação que aciona a Regra 2 conta um. A
assimetria vem das regras: a 1 sinaliza o cliente, a 2 sinaliza a operação.

Contar linhas com a flag ligada seria errado — `flag_regra1_fracionamento` fica `True` em todas
as operações do cliente, então CLI-029 valeria 16 sinais por ter 16 transações, não por ser
suspeito. E ordenar pelo booleano `cliente_sinalizado` empataria os 17: ele filtra quem entra
na lista, não ordena.

Contar por dia não muda nada nesta base (nenhum cliente tem mais de um dia sinalizado), mas dois
fracionamentos em datas diferentes são dois casos na fila.

### SDK nativo em vez de framework de agente

Usei o SDK da OpenAI direto (Responses API com function calling), sem LangChain ou LangGraph.
O enunciado aceita "SDK nativo do provedor, ou na mão", e o SDK já era dependência do Nível 1 —
um framework acrescentaria uma camada de abstração e uma dependência para um laço de três
ferramentas que cabe em 20 linhas. Também deixa visível, no código, exatamente o que vai e o que
volta em cada chamada, que é o que preciso para medir tokens e latência por iteração na Parte C.

O custo dessa escolha é portabilidade: trocar de provedor exige reescrever o laço, enquanto um
framework abstrairia isso. Como o desafio fixa um provedor, o custo não se realiza aqui.

### Mesma validação de saída do Nível 1

O agente reusa a validação estrutural do Nível 1 em vez de confiar no `json_object` da API: o
conjunto de campos tem que bater exatamente, `nivel_risco` é normalizado e checado contra o
domínio, `red_flags` precisa ser lista de strings não vazias.

Manter o mesmo contrato nos dois níveis significa que o parecer tem o mesmo formato venha de onde
vier, o que é o que permite o confronto da Parte D comparar coisas comparáveis. E a validação
continua necessária mesmo com `json_object` ligado: o formato garante que a resposta é JSON,
não que é o *nosso* JSON — forçando prompts ruins, o modelo devolve JSON perfeitamente válido com
campos errados, e é a validação semântica que barra.


### Custo medido por chamada, não só por cliente

O enunciado pede custo e latência "de cada chamada". Um cliente consome 3 ou 4 chamadas de API,
então instrumentei o laço por iteração e salvo isso separado em `outputs/chamadas.csv`. Sem esse
recorte a média por cliente esconde que as chamadas são muito desiguais: a última — a que redige
o parecer — gasta ~200 tokens de saída, enquanto as intermediárias, que só pedem ferramenta,
gastam 20.

Os preços por 1M de tokens estão em constante no topo de `agente.py`, marcada como parâmetro a
conferir. Não é número que o código tenha como saber sozinho.

### Onde o custo do lote realmente está

10 clientes, 32 chamadas, 42.946 tokens, US$ 0,0075 no total. O que domina é o **prompt**, não a
resposta: 1.271 tokens de entrada contra 71 de saída em média por chamada. A entrada cresce a cada
iteração porque o histórico de tool calls é reenviado inteiro.

Consequência prática: economizar prosa no parecer não muda quase nada; o que muda o custo é o
número de ferramentas chamadas. Cliente de Regra 1 custa US$ 0,00099 (3 ferramentas, 4 chamadas)
contra US$ 0,00069 do de Regra 2 (2 ferramentas, 3 chamadas) — 43% mais caro pela ferramenta extra.

### O agente quase não discrimina risco

9 de 10 clientes saíram `alto`, 1 saiu `médio`. Como todos os 10 já vinham sinalizados por regra,
um agente que responde `alto` para quase tudo concorda com a regra por construção, não por
análise — e o confronto da Parte D vai medir concordância alta sem que isso signifique nada.

Duas causas prováveis, ambas de desenho e não de bug: o prompt não dá critério para separar níveis
(diz o que é cada regra, mas não o que distingue médio de alto), e o agente só vê clientes já
sinalizados, sem base de comparação com quem não foi. Um lote de controle com clientes não
sinalizados diria se ele sabe dizer `baixo`.

### Verificação de que a LLM não calcula

Auditei os 10 pareceres extraindo todo numeral do texto e conferindo contra o retorno literal das
ferramentas: **zero números sem lastro**. Foi essa auditoria que expôs, antes do lote, o caso em
que o modelo escrevia "5x a mediana" para uma operação de 16,84x — corrigido entregando
`razao_vs_mediana` pronta.

Vale registrar que essa auditoria é frágil: ela confere se o número aparece em algum retorno, não
se ele foi usado no contexto certo. Em execuções anteriores ao lote eu vi números órfãos em cerca
de 1 a cada 10 execuções, então a taxa não é zero — o lote é que saiu limpo.

## Limitações

## O que faria com mais tempo
