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

## Limitações

## O que faria com mais tempo
