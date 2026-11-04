# Encontro 6 · Segurança, governança e produção

**Pergunta do dia:** o que precisa ser verdade para este agente entrar em produção?

Hoje vocês constroem um agente de ponta a ponta e tomam, no mesmo sistema, as decisões que cada aula tratou separadamente: agente ou workflow, o contrato das ferramentas, a citação de fonte e o "não sei", e as defesas contra injeção de prompt.

A aula tem duas partes:

1. **Em conjunto.** O agente construído do zero, com todo o código no notebook, em dois casos: férias na Aurora (`00`) e reembolso de despesas internacionais na Boreal (`00b`). Depois, o mesmo percurso na Aurora usando a `oficina.py`, o módulo que reúne essas peças (`01`).
2. **Exercício em grupo.** Cada grupo faz o percurso num de três casos novos, numa de duas alternativas: **A**, em que o grupo escreve o agente no próprio notebook (`02a-<caso>`): as duas ferramentas do caso com `@tool`, o `create_agent`, o workflow, a aprovação humana e o filtro de saída, cada peça com esqueleto, dica, teste e uma versão de referência recolhida; ou **B**, usando a oficina, como no `01` (`02b`), com o foco nas decisões. Os passos, as perguntas e a entrega são os mesmos nas duas.

## Antes da aula

Não há nada para instalar. Os notebooks rodam no Google Colab:

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-06/00-agente-do-zero.ipynb) `00-agente-do-zero.ipynb`, férias na Aurora, do zero

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-06/00b-reembolso-do-zero.ipynb) `00b-reembolso-do-zero.ipynb`, reembolso internacional, do zero

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-06/01-juntos-aurora.ipynb) `01-juntos-aurora.ipynb`, férias na Aurora, com a oficina

O exercício, alternativa A (o grupo constrói o agente), um notebook por caso:

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-06/02a-viagem.ipynb) `02a-viagem.ipynb`

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-06/02a-fornecedor.ipynb) `02a-fornecedor.ipynb`

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-06/02a-entregas.ipynb) `02a-entregas.ipynb`

O exercício, alternativa B (com a oficina), para os três casos:

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-06/02b-exercicio-oficina.ipynb) `02b-exercicio-oficina.ipynb`

Diferente das Aulas 4 e 5, hoje o modelo é chamado de verdade. O professor passa a cada grupo uma chave da OpenAI, com limite de gasto, e a chave do Serper, para a busca na web. Guardem as duas nos **Segredos** do Colab, com os nomes `OPENAI_API_KEY` e `SERPER_API_KEY`. A busca na web só é usada nos casos `viagem` e `fornecedor`. Na alternativa B, a oficina também aceita uma chave do OpenRouter, com o nome `OPENROUTER_API_KEY`.

## Os casos do exercício

- **`viagem` · Lumen Consultoria.** Assistente de viagens corporativas: previsão do tempo, feriados e busca na web. Ação irreversível: submeter o pedido de viagem.
- **`fornecedor` · Vértice Indústria.** Assistente de cadastro de fornecedores: CNPJ e busca na web. Ação irreversível: aprovar o cadastro.
- **`entregas` · Casa Pomar.** Assistente de entregas e trocas: CEP, feriados e previsão do tempo. Ação irreversível: emitir o reembolso.

Cada caso tem uma pasta em `casos/`, com o `caso.json` (o problema, as ferramentas, as perguntas e o ataque de treino) e a política interna da empresa em Markdown. As APIs públicas são chamadas de verdade; o que é interno da empresa é simulado.

## Como escolher a alternativa

- **A, do zero**, para o grupo que quer ver e mexer em todas as peças: dados, política, ferramentas, `create_agent`, placar, ataque e defesas estão no próprio notebook. A primeira parte do notebook é a construção, que se lê e se roda em cerca de 15 minutos.
- **B, com a oficina**, para o grupo que quer gastar o tempo nas decisões: as peças estão na `oficina.py`, e o notebook tem só as decisões do grupo.

Nos dois, as células que o grupo edita estão marcadas com `✏️ EDITE AQUI` e `✏️ ATÉ AQUI`, e cada uma vem com um quadro que diz o que mudar e como saber se deu certo. Cada passo termina numa célula de conferência, que imprime uma linha para o grupo colar no chat da aula. Os termos usados estão no [`GLOSSARIO.md`](GLOSSARIO.md).

## Os quatro passos

1. **Agente ou workflow?** (Aula 1) O formulário precisa de um agente? O agente contra o workflow, no mesmo placar.
2. **O contrato da ferramenta nova.** (Aula 2) Um colega abriu um PR com uma integração nova. Vocês aprovariam?
3. **Fonte, "não sei" e encaminhamento.** (Aulas 3 e 4) O jurídico exige que toda resposta cite a fonte e que o agente saiba não responder.
4. **O ataque.** (tema novo) A trifeta letal, dois ataques de treino (um tenta a ação irreversível, outro tenta vazar dado sensível) e as defesas em camadas.

## A entrega

- `REGISTRO-<caso>.md`, gerado no fim do notebook do exercício: cada decisão do grupo, a alternativa descartada e a evidência.
- O notebook do exercício, salvo com as saídas.

Os dois vão para `encontro-06/`, no fork da equipe.

## Arquivos

- `00-agente-do-zero.ipynb`: o agente de férias da Aurora construído do zero, com todo o código no notebook (ferramentas, `create_agent`, trace, resposta estruturada, placar, ataque e defesas).
- `00b-reembolso-do-zero.ipynb`: o mesmo método aplicado a outro caso, com a cotação PTAX da BrasilAPI. Termina com o que muda e o que se mantém de um caso para outro.
- `01-juntos-aurora.ipynb`: o percurso da Aurora usando a `oficina.py`.
- `02a-viagem.ipynb`, `02a-fornecedor.ipynb`, `02a-entregas.ipynb`: o exercício, alternativa A, em que o grupo escreve as peças do agente do caso no notebook.
- `02b-exercicio-oficina.ipynb`: o exercício, alternativa B, com a oficina, para os três casos.
- `oficina.py`: o módulo com as ferramentas, o placar, o ataque e o registro, generalizado para os quatro casos. É usado pelos notebooks 01 e 02b. O notebook 00 termina com uma tabela que liga cada peça construída à função correspondente da oficina.
- `GLOSSARIO.md`: os termos do encontro, também disponíveis no topo dos notebooks do exercício.
- `casos/`: o caso da Aurora e os três casos dos grupos.
- `preparo/gravar_reserva.py` e `dados/`: as respostas de reserva das APIs, gravadas na véspera.
