# Decisões

## Trade-offs

### Formato dos arquivos em `outputs/`

O enunciado pede "um registro por cliente, com o parecer estruturado" e "analise os totais com
pandas", sem fixar formato. **Escolhi JSON como fonte da verdade e CSV como derivado**, contra
usar só um dos dois.

- **Ganho:** `red_flags` é lista; em CSV ela vira string concatenada e perde a estrutura, o que
  inviabiliza reprocessar o parecer depois. O JSON preserva. O CSV existe porque é o que abre no
  Excel e o que o `ENTREGA.yaml` do enunciado citava.
- **Custo:** os dois arquivos podem divergir se alguém editar um só. `lote.csv` é sempre derivado
  de `lote.json` na mesma execução, nunca escrito à mão.

Criei também `chamadas.csv` (uma linha por chamada de API) e `controle.csv` (lote de controle),
que o enunciado não pede. São suposições minhas sobre o que sustenta as análises exigidas: sem o
primeiro não dá para falar de "custo de cada chamada", sem o segundo a taxa de concordância do
confronto não significa nada.

### Definição de "cliente sinalizado": união das regras

As regras têm granularidade diferente — a 1 marca o cliente, a 2 marca a operação. **Escolhi a
união**, contra usar só a Regra 1 ou exigir as duas.

- **Ganho:** o que importa para a mesa é se o cliente precisa de olho humano, não qual regra o
  trouxe. Usar só a Regra 1 no Nível 2 deixaria 13 dos 17 clientes de fora.
- **Custo:** trata como equivalentes dois sinais de natureza muito diferente. Um cliente pego por
  fracionamento e outro por valor atípico entram na mesma fila com o mesmo rótulo, e só a coluna
  de origem distingue.

### Unidade de "sinalização": o disparo

**Escolhi contar disparos** — um por dia que aciona a Regra 1, um por operação que aciona a Regra 2
— contra contar regras acionadas (0, 1 ou 2) ou linhas com a flag ligada.

- **Ganho:** corresponde a um caso na fila de triagem, e é a única das três que produz ordenação
  útil. As outras achatam: pelo booleano, os 17 empatam; por linhas com flag, o CLI-029 valeria 16
  sinais por ter 16 transações, não por ser suspeito.
- **Custo:** soma coisas que não são comensuráveis. Três operações atípicas contam mais que um
  fracionamento, o que é discutível — fracionamento é comportamento deliberado e valor atípico não.

### SDK nativo, não framework de agente

**Escolhi a Responses API com function calling**, contra LangChain ou LangGraph.

- **Ganho:** zero dependência nova, e o laço fica visível — é o que permitiu instrumentar tokens e
  latência por iteração, que é de onde saiu a descoberta de que a entrada domina o custo. Um
  framework esconderia isso atrás de callbacks.
- **Custo:** portabilidade. Trocar de provedor exige reescrever o laço e o formato de tool call,
  enquanto um framework abstrairia. Como o desafio fixa um provedor, o custo não se realiza aqui —
  mas se realizaria num sistema real que quisesse trocar de modelo.

### Validação própria, não `json_schema` estrito

**Escolhi `json_object` mais validação semântica em Python**, contra `json_schema` com `strict`,
que tornaria o desvio estruturalmente impossível.

- **Ganho:** o caminho de recusa existe e é testável, que é o que o item 9 do Nível 1 pede
  demonstrar. Com `json_schema` a validação vira código morto. E ela pega o que o formato não pega:
  forçando prompts ruins, o modelo devolve JSON perfeitamente válido com campos errados.
- **Custo:** o modelo pode devolver saída inválida, e devolve. Sem retentativa, isso é um parecer
  perdido no lote. Além disso, testei `json_schema` e ele fez o agente entrar em laço chamando
  `operacoes_do_dia` em datas descendentes — não valeu o risco.

### Estrutura do prompt: papel, exemplos-caso, escala qualitativa

O prompt do agente tem quatro camadas: papel e o que cada regra significa; como escolher
ferramentas, com quatro exemplos-caso; como graduar risco, em linguagem qualitativa; e o contrato
de saída. **Escolhi orientar por exemplo**, contra duas alternativas — um prompt curto deixando o
modelo decidir tudo, ou um roteiro fixo por tipo de sinalização.

- **Ganho:** os exemplos-caso produzem escolha diferenciada sem hardcode. Cliente de Regra 1 puxa
  `operacoes_do_dia`, cliente de Regra 2 não — e cliente sem sinalização para na primeira
  ferramenta. Um roteiro fixo daria o mesmo comportamento, mas seria script, não agente.
- **Custo:** prompt longo é caro. A entrada é reenviada inteira a cada iteração e já domina a
  conta — ~1.271 tokens de entrada contra ~71 de saída por chamada. Cada exemplo-caso é pago em
  toda iteração de todo cliente.
- **Limite que encontrei:** prompt é instrumento grosseiro para calibrar julgamento. A primeira
  versão sem escala de risco deu `alto` para 9 de 10; acrescentar "não use alto como padrão"
  inverteu para `médio` em 10 de 10. Só funcionou quando parei de dizer o que não fazer e passei a
  descrever a natureza da evidência — fracionamento é intenção visível, valor atípico isolado não
  é, espécie esconde origem e TED não. Nenhuma versão usou número ou limite.

### Escopo do contexto enviado ao modelo: o cliente inteiro

**Escolhi mandar todas as operações do cliente analisado**, contra mandar só as linhas sinalizadas
ou a base inteira.

- **Ganho:** sem as operações normais o modelo não tem baseline para dizer que três transações de
  ~R$ 18.000 num dia destoam do padrão daquele cliente. E o recorte por cliente é o que faz o custo
  escalar: mandar a base inteira a cada chamada seria ~30x mais caro no Nível 2, pelo mesmo parecer.
- **Custo:** o modelo não consegue comparar o cliente com a carteira. Nada nele é "mais grave que"
  outro cliente, e é provavelmente daí que vem a inconsistência entre casos parecidos.

### Critério do confronto: semântica da regra

A sugestão do enunciado — sinalizado pelas duas regras vira risco alto — é inaplicável, porque a
interseção é vazia. **Escolhi traduzir a semântica de cada regra para a escala do agente**
(fracionamento → alto; 2+ atípicas → médio; 1 atípica → baixo), contra usar volume ou contagem
bruta de sinalizações.

- **Ganho:** o critério carrega significado. Fracionamento é comportamento deliberado e sai como
  alto; operação única é onde o falso positivo mora e sai como baixo.
- **Custo:** ignora magnitude e canal, e isso apareceu — duas das quatro divergências foram o
  agente reagindo a razões muito altas ou a uso de espécie, dimensões que o critério não pesa. A
  análise caso a caso está em `outputs/confronto_analise.md`.

## Limitações

### Onde a solução quebraria com dados reais

**O dedupe assume que id repetido é sempre recarga.** Nas duas bases as duplicatas são linhas
idênticas nos 9 campos. Num legado real o mesmo id apareceria com campos divergentes — valor
corrigido, data reprocessada — e a pergunta viraria qual versão vale. `drop_duplicates()` manteria
as duas e contaria duas operações.

**A Regra 1 não tem memória.** Olha um único dia. Fracionamento real se espalha por dias
consecutivos justamente para escapar de regra assim: quatro operações de R$ 15.000 em quatro dias
seguidos não disparam nada.

**A mediana da Regra 2 inclui a própria operação atípica.** Com poucas operações por cliente isso
puxa a mediana para cima, tornando a regra mais conservadora conforme o cliente é mais suspeito.

**O corte de 4+ operações nunca foi exercitado.** Nenhum cliente inelegível teria sido sinalizado de
todo modo, então não sei se está calibrado — só sei que não barrou nada.

**Nenhuma regra olha canal, contraparte ou tipo.** Espécie, saque e concentração num único
destinatário são sinais clássicos de PLD e estão fora do escopo determinístico.

### Onde a solução com LLM é frágil

**Não há reprodutibilidade.** A Responses API não expõe `seed`, e mesmo com `temperature=0` a saída
varia. Não é hipotético: duas execuções do mesmo lote deram 6 médio/4 alto e 5 médio/5 alto, e a
concordância do confronto foi de 70% para 60%. Os números em `outputs/` são de uma execução, não de
uma medida estável.

**O agente é inconsistente entre casos parecidos.** CLI-013 saiu alto com razões de 9,05x e 8,5x
enquanto CLI-023, mais grave em todas as dimensões, já saiu médio. Ele avalia um cliente por vez.

**A auditoria de lastro numérico é fraca.** Confere se o numeral aparece em algum retorno, não se
foi usado no contexto certo. O lote saiu limpo, mas em execuções avulsas vi números sem lastro em
cerca de 1 a cada 10.

**O custo escala com ferramentas, não com tamanho do parecer.** A entrada é reenviada inteira a
cada iteração. Numa base de milhares de clientes isso domina.


## O que faria com mais tempo

### Loop de feedback na validação

**Arquitetura:** ao recusar, devolver o erro de validação ao modelo numa segunda chamada, com o
parecer inválido e a mensagem específica ("campos ausentes: [...]"), teto de 2 tentativas.
**Ferramenta:** o próprio laço do agente, que já acumula `input` — basta anexar o erro como turno.
**Validação:** rodar o mesmo lote com e sem o loop e comparar taxa de aceitação e custo médio. Só
vale se a recuperação custar menos que a chamada perdida.

### Nível 3 — Trilha A, fluxo multiagente

**Arquitetura:** três papéis encadeados sobre o que já existe. **Triador** recebe cliente e dossiê
e decide se o caso segue — cliente sem sinalização para aqui, que é o que o lote de controle já
mostra o agente fazendo. **Investigador** é o agente atual, com as três ferramentas. **Redator**
recebe as evidências e escreve o parecer validado, sem acesso a ferramentas, para não reabrir
investigação na hora de redigir.


### Utilização de LangChain como framework para agente de IA. 

A curto prazo, o SDK da OpenAI funciona perfeitamente, mas falta robustez ao longo prazo, gostaria de utilizar um framework mais completo para criar uma solução que funciona melhor para esse cenário
