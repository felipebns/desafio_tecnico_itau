## Claude Code (Opus 5 - high effort)

### Nivel 1:
* usei IA para analisar os dados e procurar qualquer anomalia, que eu possa ter deixado passar, nos dados para a limpeza
* Gerar textos mais completos
* Operações com groupby na implementação das regras e comparações de agregações com DF
* Tabelas de validação com explicação
* Geração de prompts e verificação de que o determinístico esta pré-definido (não misturado a interpretação), no prompt fica apenas a interpretação, montagem de dossie
* Texto mais completo na comparação entre prompts
* Iterações sucessivas para garantir que o validador de resposta funciona robustamente

### Onde a IA me levou para um caminho errado e eu percebi:
* Na validação da estrutura ela fazia de modo muito "solto", permitia que campos extras existiam, arrumei e deixei mais robusto
* Fazia operações com groupby e aggregate desnecessariamente complexas, simplifiquei bastante
* Estava montando a parte B de modo muito desorganizado, arrumei em uma classe mais legível
* Estava considerando fazer a normalização de USD para BRL durante o processo de limpeza dos dados, tive que isolar as duas coisas em segmentos diferentes

### Nível 2
* Adaptar o código no Nivel 1 para a parte A de modo mais rápido, evita trabalho repetitivo
* Criação de ferramentas de modo mais eficiente, utilizando o código anterior como base
* Gerando prompt mais robusto para escolha de ferramentas e testes iterativos se as ferramentas estão funcionando de acordo (e escolha correta)

### Onde a IA me levou para um caminho errado e eu percebi:
* Ia tava usando um conceito de "cliente sinalizado" diferente do meu, tive que definir efetivamente