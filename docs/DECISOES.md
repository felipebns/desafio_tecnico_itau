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


## Limitações

## O que faria com mais tempo
