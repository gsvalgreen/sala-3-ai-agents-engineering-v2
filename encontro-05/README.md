# Encontro 5 · Evals, observabilidade e custo

**Pergunta do dia:** não existe `assert` em linguagem natural. Como um time ganha confiança para colocar um agente em produção?

No Encontro 4, vocês decidiram a arquitetura com uma rodada do placar. Hoje vocês descobrem quanto esse placar muda quando a mesma coisa roda de novo, e aprendem a decidir um deploy com números que aguentam esse ruído.

## Antes da aula

Não há nada para instalar. Os notebooks rodam no Google Colab, pelo botão no topo de cada um, e só precisam de uma conta Google.

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-05/01-dentro-da-avaliacao.ipynb) `01-dentro-da-avaliacao.ipynb`, que acompanhamos juntos na aula

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-05/02-hands-on-evals.ipynb) `02-hands-on-evals.ipynb`, a atividade do grupo

Abra o notebook 01 e rode só a primeira célula. Se aparecer "Tudo certo, pode seguir", você está pronto.

Também não precisa de chave de API. As respostas do modelo estão gravadas, como no Encontro 4, com uma novidade: cada pergunta foi respondida **cinco vezes**, por três versões do agente. Essa variação é o assunto da aula. Os tokens, o custo e o tempo de espera mostrados são os que cada chamada teve de verdade.

> **Prefere rodar na sua máquina?** Funciona igual. Depois do Sync fork, na raiz do repositório: `pip install -r requirements.txt` e `jupyter notebook encontro-05/`.

## O sistema que vocês vão avaliar

É o agente único da Aula 4, com a mesma busca, o mesmo contrato e a mesma camada, em três versões:

- **v1 · produção:** o agente da Aula 4, como está.
- **v2 · prompt enxuto (PR #42):** um colega encurtou o prompt de sistema para economizar tokens e acabar com os loops.
- **v3 · modelo mais barato:** o mesmo prompt da v1, num modelo que custa menos por token.

## Os conceitos que vocês vão usar

Leiam esta seção antes da atividade. Cada termo aparece em alguma célula do notebook 02 ou na nota.

### Para medir a qualidade

**Golden set.** Uma lista de perguntas com o gabarito de cada uma, escrito por quem conhece o domínio. É o "conjunto de testes" do agente. A turma já tem um, com 25 casos (`golden-aurora.json`), e o grupo vai escrever mais 8.

**Gabarito.** O que torna uma resposta certa. Aqui ele tem quatro partes: o **desfecho** esperado (responder, dizer "não sei" ou encaminhar ao RH), as **fontes** que a resposta precisa citar, os textos que ela **precisa conter** (o valor certo) e os que ela **não pode conter** (o valor errado mais plausível).

**Régua.** O código que compara um atendimento com o gabarito e diz se acertou, com o motivo quando erra ("faltou citar a página X", "trouxe o valor proibido"). É determinística: a mesma resposta sempre recebe a mesma nota.

**Juiz (LLM-as-judge).** Outro modelo que lê a resposta e diz se ela está boa. Serve onde não há gabarito, como em produção. O juiz com evidência recebe também os trechos da wiki que o agente leu e segue uma rubrica. Um juiz também erra, por isso a concordância dele com a régua é medida antes de confiar nele.

**Amostra.** Cada uma das cinco vezes que a mesma pergunta foi feita à mesma versão. O modelo não responde igual duas vezes, então um caso pode acertar em 3 das 5 amostras.

**Acerto (pass@1).** A chance de um atendimento sair certo: a média, entre os casos, da fração de amostras certas. Um caso que acerta 3 de 5 conta 60%.

**pass^k (aqui, pass^5).** A fração de casos que acertaram nas cinco amostras. Mede a confiabilidade: em quantos casos o agente acerta sempre. É sempre menor ou igual ao acerto.

**Caso instável.** Um caso que acertou em algumas amostras e errou em outras.

### Para comparar versões

**Intervalo de confiança de 90% (IC 90%).** A faixa em que o acerto provavelmente está. Com poucos casos e um modelo que varia, um único número engana. "Acerto de 78% (IC 90%: 70% a 85%)" quer dizer: com esta suíte, não dá para afirmar nada mais preciso que essa faixa.

**Teste A/A.** Comparar a mesma versão com ela mesma, amostra contra amostra, sem mudar nada. A diferença que aparece é o **ruído**: o tanto que o placar mexe por acaso.

**Regressão.** Uma versão nova pior que a atual, além do ruído. O notebook compara as duas versões caso a caso e dá um de três vereditos:
- **regressão**: o intervalo da diferença está inteiro abaixo de zero;
- **melhora**: o intervalo está inteiro acima de zero;
- **não dá para afirmar**: o intervalo cruza o zero, e a diferença pode ser só ruído.

**A média esconde.** Uma versão pode melhorar em média e piorar justamente num caso crítico, como dizer que alguém tem direito a um benefício sem consultar o RH. Por isso, olhem sempre os casos que mudaram, e não só o número.

### Para decidir o deploy

**SLI (Service Level Indicator, indicador de nível de serviço).** Uma medida de como o serviço está indo, sempre calculada do mesmo jeito. É o "o que se mede". Exemplos: a fração dos atendimentos certos, o tempo que 95% dos colaboradores esperam, o custo por resposta certa. O notebook calcula doze SLIs; `av.listar_slis()` mostra todos, cada um com uma seta: ↑ quanto maior, melhor; ↓ quanto menor, melhor.

**SLO (Service Level Objective, objetivo de nível de serviço).** O alvo combinado para um SLI. É o "quanto basta". Exemplo: "acerto de pelo menos 80%" ou "p95 de no máximo 10 segundos". O número não sai da engenharia sozinha: ele é combinado com quem responde pelo serviço. Na Aurora, o RH e o jurídico teriam o que dizer sobre o acerto em benefícios. Para cada SLO, o grupo precisa saber responder por que esse número, e quem concordaria com ele.

**SLA (Service Level Agreement, acordo de nível de serviço).** Um SLO prometido num contrato, com consequência se não for cumprido, como multa ou desconto. Não usamos SLA nesta aula, mas é bom não confundir os três: o SLI mede, o SLO é o alvo interno, o SLA é a promessa ao cliente.

**Orçamento de erro.** O quanto o SLO permite errar. Com um SLO de acerto de 80%, o orçamento de erro é de 20%: 1 em cada 5 atendimentos pode sair errado sem quebrar o objetivo. Quando o orçamento acaba, o time para de lançar novidades e conserta o que está errando.

**Gate de deploy.** A checagem que decide se uma versão pode ir para produção: ela precisa cumprir todos os SLOs. No notebook, é `av.checar_slos(...)`, que mostra "✔ passa" ou "✘ FALHA" para cada SLO e versão, e um "SIM" ou "NÃO" no fim.

**p50 e p95.** Percentis da latência. O p50 é a mediana: metade dos atendimentos é mais rápida que ele. O p95 é o tempo que 95% dos atendimentos não ultrapassam. O p95 importa mais, porque mostra a espera dos colaboradores com pior experiência, que a média esconde.

**Custo por acerto (custo por tarefa resolvida).** Quanto custa, em dólares, cada resposta certa: o custo total dividido pelo número de acertos. Um modelo mais barato por token, mas que erra mais ou dá mais passos, pode sair mais caro por acerto.

**Loop (bateu no limite).** Um atendimento em que o agente buscou até atingir o limite de 8 passos sem conseguir responder. É um SLI de operação: cada loop custa caro e termina sem resposta.

### Para olhar um atendimento por dentro

**Trace.** Tudo o que aconteceu num atendimento, da pergunta à resposta: cada chamada ao modelo e cada busca, em ordem.

**Span.** Um pedaço do trace com início e fim, como uma chamada ao modelo ou uma busca.

**Cascata (waterfall).** O desenho dos spans no tempo, um embaixo do outro. Mostra onde o tempo e o dinheiro foram gastos.

## A atividade em grupo

### O cenário

O agente da Aurora está em produção há uma semana. Chegaram 24 perguntas de colaboradores de verdade, no arquivo `banco-producao.json`, e ninguém sabe ainda se as respostas estavam certas. Ao mesmo tempo, duas mudanças esperam aprovação: o PR #42 e a troca para o modelo mais barato. O grupo de vocês é o time que decide se alguma delas vai para produção.

### Como se organizar

Em cada sala, uma pessoa compartilha a tela e roda as células do notebook 02. Outra escreve a nota enquanto o grupo discute. Uma terceira faz o papel de **especialista de domínio**: lê as páginas da wiki da Aurora e decide o gabarito de cada pergunta. Quando o professor perguntar no chat "em que passo vocês estão?", respondam com o número do passo.

Durante a aula, trabalhem só neste notebook. Entregas atrasadas ficam para depois da aula, no prazo combinado.

### Antes de começar: como usar o notebook

1. Abra o `02-hands-on-evals.ipynb` pelo botão "Abrir no Colab" acima.
2. Clique em **Arquivo › Salvar uma cópia no Drive**. Assim, o que o grupo editar não se perde se a página fechar.
3. Rode as células **de cima para baixo, uma por vez**, com Shift+Enter. Cada célula usa o que as anteriores criaram.
4. Se o Colab desconectar ou aparecer um erro como `NameError` (um nome não definido), use **Ambiente de execução › Executar anteriores** a partir da célula onde vocês estavam.
5. O grupo só edita **quatro células**, todas indicadas no notebook:
   - o id da página na célula do `av.mostrar_pagina(...)`, no Passo 2;
   - a lista `GOLDEN_GRUPO`, no Passo 2;
   - `CASO`, `VERSAO` e `AMOSTRA`, no Passo 4;
   - o dicionário `SLOS_GRUPO`, no Passo 5.

   Não mudem os prompts nem o `avaliacao.py`. As respostas do modelo estão gravadas para os prompts como estão; com outra vírgula, o notebook avisa que a resposta não está gravada e para.

### Passo a passo

#### Passo 1 · Olhar a produção (5 minutos)

**Objetivo:** escolher as 8 perguntas do golden set do grupo.

1. Rode a **primeira célula** do notebook (Etapa 0). Esperem a mensagem "Tudo certo, pode seguir".
2. Rode a célula do Passo 1. Ela mostra uma linha por pergunta do banco de produção, com quatro colunas:
   - `id`: o código da pergunta, de B01 a B24;
   - `desfechos nas amostras`: como a v1 encerrou a pergunta nas cinco tentativas. Por exemplo, `responder 3 · escalar 2` quer dizer que ela respondeu três vezes e encaminhou ao RH duas;
   - `juiz`: em quantas das cinco o juiz com evidência aprovou a resposta. Por exemplo, `2/5`;
   - `pergunta`: o começo do texto da pergunta.
3. Leiam a lista em grupo e escolham **8 perguntas**. Entre elas, precisa haver pelo menos:
   - uma que deveria terminar em **"não sei"**, porque a wiki não responde;
   - uma que deveria **ir para o RH**, porque a pessoa pergunta se **ela** tem direito a algo;
   - uma **instável**, com mais de um desfecho nas cinco tentativas;
   - uma que o **juiz reprovou** pelo menos uma vez (menos de `5/5`);
   - **três com um valor que dá para conferir**, como um número, um prazo ou um percentual.

   Uma mesma pergunta pode cobrir mais de um item: a instável pode ser também a que o juiz reprovou.
4. Anotem os 8 ids na nota, para não perdê-los.

**Pronto quando:** o grupo tem 8 ids anotados e cobriu os cinco tipos.

#### Passo 2 · Escrever o gabarito (15 minutos)

**Objetivo:** escrever o gabarito das 8 perguntas na lista `GOLDEN_GRUPO`. É o passo mais importante, e vale cerca de 30% da nota.

1. Rodem a célula `av.paginas()`. Ela lista as páginas da wiki da Aurora, uma por linha: o espaço (RH, TI, benefícios...), o id, o título e, entre parênteses, a autoridade e a vigência da página. Reparem nessas duas últimas: quando duas páginas falam do mesmo assunto, a que vale é a política oficial e vigente, e o valor da outra é um bom candidato a "não pode conter".
2. Para cada pergunta escolhida, a especialista de domínio encontra a página que responde. Para ler uma página inteira, troquem o id na célula seguinte e rodem:

   ```python
   av.mostrar_pagina("beneficios-auxilio-creche")      # troque pelo id da página
   ```

   Rodem essa célula quantas vezes precisarem, uma página por vez.
3. Com a página lida, decidam as quatro partes do gabarito:
   - **o desfecho certo:**
     - `"responder"`, se a wiki responde à pergunta;
     - `"nao_sei"`, se a wiki não tem a informação;
     - `"escalar"`, se a pessoa pergunta sobre o direito **dela** a algo, que só o RH pode confirmar;
   - **as fontes:** os ids das páginas que a resposta precisa citar. Só o mínimo necessário;
   - **o que a resposta precisa conter:** o valor certo, escrito dos jeitos que uma resposta certa escreveria. Por exemplo, `["R$ 600", "600"]` ou `["20 dias", "vinte dias"]`. Basta a resposta trazer um deles;
   - **o que ela não pode conter:** o valor errado mais plausível, como o de uma versão antiga da política ou o de outra página que fala do mesmo assunto.
4. Escrevam um caso por pergunta na célula `GOLDEN_GRUPO`. O primeiro já vem pronto, como exemplo:

   ```python
   GOLDEN_GRUPO = [
       av.caso_da_equipe("B16", "responder", fontes=["beneficios-auxilio-creche"], contem=["600"]),
       av.caso_da_equipe("B__", "responder", fontes=["id-da-pagina"], contem=["valor certo", "outro jeito de escrever"],
                         nao_contem=["valor errado plausível"]),
       av.caso_da_equipe("B__", "nao_sei"),
       av.caso_da_equipe("B__", "escalar"),
       # ... até completar 8
   ]
   ```

   Troquem cada `B__` pelo id de uma das perguntas escolhidas no Passo 1 (o B16 pode ficar ou sair). Com `"nao_sei"` e `"escalar"`, escrevam só o id e o desfecho: a régua olha apenas o desfecho, sem fontes nem textos.
5. Rodem a célula. Ela confere o formato de cada caso e mostra uma linha por caso:
   - `ok`: o caso está bem escrito;
   - `a página '...' não existe`: o id da página está errado. Corrijam com a lista do item 1;
   - `com 'nao_sei' ou 'escalar', a régua só olha o desfecho`: tirem as fontes e os textos desse caso;
   - `sem 'contem', a régua aceita qualquer texto que cite a fonte`: um aviso. Se o caso tem um valor, acrescentem o `contem`.

   No fim, ela mostra quantos casos há e quantos faltam para os 8.
6. Antes de seguir, conversem sobre a pergunta da célula seguinte: um `contem` frouxo, como `["não"]`, aceita "não sei", "não é permitido" e "não há limite". Quanto mais específico o texto, mais a régua vale.

**Três regras para não errar:**
- **O gabarito vem da página da wiki, nunca da resposta do agente.** Copiar o que o agente respondeu faz a suíte aprovar o próprio erro.
- **Anotem na nota a página de onde saiu cada gabarito.**
- **Algumas perguntas são ambíguas de propósito**, e dá para defender dois gabaritos. Se escolherem uma delas, decidam, e registrem na nota as duas leituras e por que ficaram com uma.

**Pronto quando:** a célula mostra 8 casos, todos `ok` ou com um aviso que o grupo decidiu manter.

#### Passo 3 · Rodar a suíte (5 minutos)

**Objetivo:** medir as três versões no golden set da turma mais o do grupo.

1. Rodem a célula que começa com `SUITE = golden + GOLDEN_GRUPO`. Ela junta os 25 casos da turma com os 8 do grupo (33 casos) e roda v1, v2 e v3, cinco vezes cada. Leva alguns segundos, porque as respostas vêm da gravação.
2. Ela mostra o **placar**: uma linha por versão, com o acerto e o intervalo de 90%, o pass^5, os casos instáveis, o custo por acerto, a latência p95 e os loops.
3. Rodem a célula `av.suspeitos(...)`. Ela lista os casos do grupo que **nenhuma** versão acertou em **nenhuma** amostra, com o motivo da régua e o começo da resposta. Para cada um, perguntem:
   - a régua reprovou por quê? O `contem` está escrito de um jeito que uma resposta certa não escreveria? A fonte está certa?
   - se o gabarito estiver errado, corrijam a célula `GOLDEN_GRUPO` do Passo 2, rodem-na de novo e voltem a rodar o Passo 3;
   - se o gabarito estiver certo, o caso é difícil para todas as versões. Isso é um achado: anotem na nota.
4. Rodem a célula `av.mapa_de_casos(...)`. É um mapa de calor com uma linha por caso e uma coluna por versão, colorido pelo acerto nas cinco amostras. Procurem linhas em que a cor muda muito entre as colunas: são os casos que as mudanças afetaram.

Se o grupo travar com um caso problemático, comentem a linha dele em `GOLDEN_GRUPO` (com `#` no começo) e sigam. O golden set da turma, sozinho, também funciona nos Passos 4 e 5.

**Pronto quando:** o placar saiu, os suspeitos foram conferidos e o grupo sabe quais casos mudaram entre as versões.

#### Passo 4 · Regressão ou ruído? (10 minutos)

**Objetivo:** dar um veredito sobre o PR #42 e sobre o modelo barato, comparando com o ruído.

1. Rodem a célula `ruido = av.teste_aa(v1)`. Ela trata cada uma das cinco amostras da v1 como uma rodada completa da suíte e mostra o acerto de cada rodada, com uma barra. Embaixo, aparece a frase "entre duas rodadas quaisquer, o acerto mudou até X%". **Anotem esse X:** é o ruído da suíte, o tanto que o placar mexe sem mudar nada.
2. Rodem a célula seguinte. Ela compara a v1 com a v2 (o PR #42) e a v1 com a v3 (o modelo barato). Para cada comparação, aparecem:
   - a diferença média de acerto e o intervalo de 90% dessa diferença;
   - o veredito: **regressão**, **melhora** ou **não dá para afirmar**;
   - os casos que pioraram e os que melhoraram.

   Anotem os dois vereditos e os casos que mudaram. Perguntem: a diferença é maior que o ruído do item 1? Os casos que pioraram são críticos, como os de "escalar" ou de "não sei"?
3. Rodem a célula da comparação **só com os casos do grupo**. Ela repete a comparação da v1 com a v2 usando só os 8 casos que vocês escreveram. A conclusão muda? Os casos que saíram da produção pegaram algo que o golden set da turma não pegou?
4. Escolham **um atendimento para abrir por dentro**. Na célula com `CASO` e `VERSAO`:

   ```python
   CASO = "X1"     # troque pelo id do caso que o grupo quer abrir
   VERSAO = v2     # v1, v2 ou v3, sem aspas
   ```

   Uma boa escolha é um caso que piorou no item 2 ou um caso instável. Rodem a célula: ela mostra as cinco respostas da versão para esse caso, lado a lado.
5. Escolham uma das cinco amostras e rodem a célula da cascata:

   ```python
   AMOSTRA = 0     # de 0 a 4
   ```

   A cascata mostra cada passo do atendimento no tempo: as barras azuis são chamadas ao modelo, os traços verdes são buscas, e cada passo mostra os tokens e o custo. Respondam na nota: quantos passos o agente deu? Onde foi o tempo? O que a busca devolveu? Em qual camada da pirâmide o problema aparece primeiro: na busca, num passo do agente, no caminho até a resposta ou na resposta final?

**Pronto quando:** o grupo tem o ruído, os dois vereditos com os casos que mudaram e um atendimento aberto na cascata, com o diagnóstico.

#### Passo 5 · SLOs e a decisão (10 minutos)

**Objetivo:** definir os SLOs do grupo, rodar o gate e decidir qual versão vai para produção.

1. Rodem a célula com `av.listar_slis()`. Ela roda o juiz nas três versões (um dos SLIs depende dele) e lista os doze SLIs, com o sentido (↑ ou ↓) e o que cada um mede.
2. Escolham **pelo menos três SLIs**: um de **qualidade** (como `acerto` ou `aprovado_pelo_juiz`), um de **custo** (como `custo_por_acerto`) e um de **operação** (como `p95_segundos` ou `bateu_limite`).
3. Para cada um, decidam o alvo e editem o dicionário `SLOS_GRUPO`:

   ```python
   SLOS_GRUPO = {
       "acerto": 0.80,            # pelo menos 80% dos atendimentos certos
       "custo_por_acerto": 0.002, # no máximo US$ 0,002 por resposta certa
       "p95_segundos": 10.0,      # 95% dos colaboradores esperam no máximo 10 s
       # "bateu_limite": 0.02,    # no máximo 2% dos atendimentos em loop
   }
   ```

   As frações vão em decimal: 80% é `0.80`. Os nomes precisam ser exatamente os da lista do item 1. O sentido vem do SLI: para os de ↑, o alvo é um mínimo; para os de ↓, um máximo.
4. Rodem a célula. O gate mostra, para cada SLO e cada versão, "✔ passa" ou "✘ FALHA", com o valor medido, e no fim um "SIM" ou "NÃO" para "pode ir para produção?".
5. Decidam qual versão vai para produção, juntando o gate com os vereditos do Passo 4:
   - uma versão pode passar no gate e ainda ter piorado num caso crítico, porque a média esconde;
   - uma versão pode falhar num SLO que o grupo, olhando de novo, acha mal calibrado. Mudar o SLO é permitido, desde que a nota diga por quê;
   - se nenhuma versão passar, essa também é uma resposta. Digam o que fariam a seguir.
6. Para cada alvo, escrevam na nota por que esse número e quem na Aurora concordaria com ele.

**Pronto quando:** o grupo tem três ou mais SLOs justificados, o resultado do gate e a decisão escrita.

#### Passo 6 · A nota (5 minutos)

**Objetivo:** fechar a `NOTA-EVAL.md` e salvar o golden set do grupo.

1. Rodem a primeira célula do Passo 6. Ela imprime em markdown, prontas para copiar: a tabela do golden set do grupo, o placar, o ruído e os vereditos, e o gate dos SLOs.
2. Copiem essas tabelas para a `NOTA-EVAL.md`, nas seções correspondentes.
3. Escrevam à mão o que o notebook não escreve: o gabarito difícil de decidir (seção 1), a leitura do placar (seção 2), se os casos do grupo mudaram alguma conclusão (seção 3), o motivo de cada SLO e a decisão (seção 4) e o atendimento aberto na cascata (seção 5). No fim do notebook há um exemplo de decisão fraca e de decisão forte.
4. Rodem a última célula. Ela salva o arquivo `golden-equipe.json` com o gabarito do grupo.
5. No Colab, baixem o `golden-equipe.json`: ícone de pasta na barra lateral, três pontinhos ao lado do arquivo, **Fazer download**. Façam isso antes de fechar o notebook, porque os arquivos do Colab somem quando a sessão termina.
6. Usem a lista "Confiram antes de entregar", no fim do notebook, para conferir a nota.

**Pronto quando:** a nota está preenchida e o `golden-equipe.json` está baixado.

Terminou antes? A seção "Para ir além", no fim do notebook, tem três desafios opcionais.

## O que entregar

No fork da equipe, dentro de `encontro-05/`:

- **`NOTA-EVAL.md`** preenchida, com uma página;
- **`golden-equipe.json`**, o golden set do grupo, baixado no Passo 6 e enviado para o fork.

## Como a atividade será avaliada

O que vale nota é o raciocínio, não o placar: o placar o notebook gera sozinho.

**O golden set (cerca de 30%).** O mínimo são 8 casos, com pelo menos um "não sei" e um "escalar". Uma entrega forte cita a página da wiki de cada gabarito, usa textos específicos para conferir o valor (um "não" sozinho aceita qualquer resposta), pega o valor errado plausível com o "não pode conter" e explica a escolha nos casos ambíguos.

**O placar (cerca de 10%).** As três versões, com o acerto e o intervalo de confiança, e pelo menos uma leitura do grupo sobre o que os números mostram.

**Regressão ou ruído (cerca de 25%).** O veredito sobre cada mudança, comparando a diferença com o ruído do teste A/A, os casos que mudaram e o tipo deles, e se os casos do grupo mudaram alguma conclusão.

**SLOs e decisão (cerca de 25%).** Três SLOs com o motivo de cada número, a versão escolhida, o cuidado com os casos críticos (uma versão pode passar no gate e piorar justamente onde não pode errar) e o que faria o grupo mudar de ideia.

**Um atendimento por dentro (cerca de 10%).** O caso aberto na cascata, o que ela mostra e onde o problema aparece primeiro.

Duas conclusões valem tanto quanto qualquer outra, desde que bem defendidas: "não dá para afirmar", quando a diferença está dentro do ruído, e "nenhuma versão passa no gate", desde que o grupo diga o que faria a seguir.

## Os arquivos desta pasta

- `01-dentro-da-avaliacao.ipynb`: o notebook que acompanhamos juntos. Não tem entrega.
- `02-hands-on-evals.ipynb`: a atividade do grupo.
- `NOTA-EVAL.md`: o modelo da nota.
- `03-langfuse.ipynb`: o mesmo eval numa plataforma de mercado, o Langfuse. É opcional: para rodar, basta uma conta gratuita no Langfuse, sem chave de modelo.
- `avaliacao.py`: o código por trás dos notebooks.
- `golden-aurora.json`: o golden set da turma, com os 19 casos dos Encontros 1 a 4 e mais 6 que vieram da produção (G1 a G6).
- `banco-producao.json`: as 24 perguntas da primeira semana, sem gabarito.
- `dados/`: as respostas gravadas do modelo. Não mexa.