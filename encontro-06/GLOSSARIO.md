# Glossário · Encontro 6

Os termos usados nos notebooks e nos slides do Encontro 6, em ordem de aparição no percurso.

- **Agente.** Um programa em que o modelo decide, a cada passo, qual ferramenta chamar ou se já pode responder. O plano de execução é gerado na hora, não escrito antes.
- **Workflow.** A alternativa sem modelo: os passos e as regras escritos em código, com `if`. Quando cabe, é mais barato, mais rápido e mais previsível.
- **Ferramenta (tool).** Uma função Python que o modelo pode pedir para executar. O modelo não executa nada: ele devolve um pedido, e o código executa.
- **Contrato da ferramenta.** O que o modelo lê sobre a ferramenta: o nome, a descrição e o schema dos argumentos. É o Tool Contract Sheet da Aula 2.
- **Schema.** A descrição dos argumentos de uma ferramenta: nomes, tipos, formatos e limites (por exemplo, `AAAA-MM-DD` ou um tamanho máximo).
- **Prompt de sistema.** As instruções fixas do agente, enviadas ao modelo em todo atendimento.
- **Loop do agente.** O vai e volta entre o modelo e as ferramentas: o modelo pede, o código executa, o resultado volta ao modelo, até a resposta final. O `create_agent` faz esse loop.
- **Trace.** O registro de um atendimento, passo a passo: a pergunta, cada ferramenta chamada, o que ela devolveu e a resposta. É onde se descobre por que o agente errou.
- **Resposta estruturada.** A resposta final em campos fixos (desfecho, fontes e texto), para poder ser corrigida com uma régua.
- **Desfecho.** O tipo de resposta: `responder`, `nao_sei` (a política não cobre), `escalar` (o caso é de outra área ou precisa de aprovação) ou `acao` (o agente executou uma ação irreversível).
- **Placar e régua.** A régua corrige cada resposta contra o gabarito; o placar junta as correções com o custo e o tempo de cada atendimento.
- **Gabarito.** A resposta certa de cada pergunta. No Passo 1, quem dá o gabarito é o workflow.
- **Perguntas de controle.** Casos legítimos que precisam continuar certos depois de uma mudança. Uma defesa que bloqueia o ataque e também o uso legítimo não resolveu o problema.
- **Regressão.** Rodar de novo as perguntas dos passos anteriores, depois de uma mudança, para ver se algo que funcionava quebrou (Aula 5).
- **Variância.** O mesmo agente, com a mesma pergunta, pode responder diferente em rodadas diferentes. Por isso o ataque roda 3 vezes.
- **p95.** O tempo abaixo do qual ficam 95% dos atendimentos. Mede a espera dos casos lentos, não a média.
- **Token.** A unidade de texto que o modelo lê e escreve. O custo do atendimento sai do número de tokens de entrada e de saída.
- **Checkpoint.** O estado da conversa guardado entre um passo e outro. Permite pausar o agente para uma aprovação e retomar do mesmo ponto (Aula 4).
- **Middleware.** Um comportamento que envolve o loop do agente sem mexer nele, como pausar antes de certas ferramentas.
- **Aprovação humana.** O `HumanInTheLoopMiddleware`: antes de executar uma ferramenta da lista, o agente pausa e espera um humano aprovar ou recusar.
- **Ação irreversível.** Uma ação que o agente não consegue desfazer: submeter um pedido, aprovar um cadastro, emitir um reembolso. É onde a aprovação humana costuma entrar.
- **Entrada não confiável.** Texto escrito por terceiros que chega ao agente dentro do resultado de uma ferramenta: uma página da web, um comentário, a observação de um pedido.
- **Injeção indireta de prompt.** Um ataque em que a instrução maliciosa vem escondida numa entrada não confiável. O modelo não separa com segurança instrução de dado.
- **Trifeta letal.** Entrada não confiável, acesso a dado sensível e capacidade de agir ou de mandar dado para fora, ao mesmo tempo. Com as três, a injeção indireta pode causar dano.
- **Guardrail.** Uma defesa. Pode funcionar dentro do modelo (uma regra no prompt, a marcação de conteúdo externo) ou fora dele, em código (aprovação humana, filtro de saída, escopo mínimo).
- **Escopo mínimo.** Dar ao agente só as ferramentas de que ele precisa. Tirar uma ferramenta pode tirar uma perna da trifeta.
- **Filtro de saída.** Código que confere, antes de uma chamada de saída acontecer, se ela levaria dado pessoal ou iria para um destinatário fora da lista.
- **Marcação de conteúdo externo.** Embrulhar o conteúdo de terceiros num aviso de que aquilo é dado, não instrução. Depende de o modelo respeitar o aviso.
- **Fallback e reserva.** O plano B quando uma API não responde. Aqui, a resposta gravada pelo professor na véspera, que aparece no trace como `(reserva)`.
- **MCP.** Model Context Protocol: o padrão mais usado para ligar agentes a ferramentas e sistemas. Um servidor MCP de terceiros é código de terceiros rodando com as permissões do agente.
