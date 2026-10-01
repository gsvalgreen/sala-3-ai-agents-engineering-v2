# Encontro 2 · Contexto e ferramentas

**Hands-on: contratar, construir e quebrar**
Em grupos · 60 minutos

---

## Sumário

1. [A pergunta do dia](#1-a-pergunta-do-dia)
2. [O que vocês vão fazer](#2-o-que-vocês-vão-fazer)
3. [O material da pasta](#3-o-material-da-pasta)
4. [As seis ferramentas do caso](#4-as-seis-ferramentas-do-caso)
5. [Os 17 casos e a correção](#5-os-17-casos-e-a-correção)
6. [Roteiro, passo a passo](#6-roteiro-passo-a-passo)
7. [O placar](#7-o-placar)
8. [Depois do intervalo: o desafio da idempotência](#8-depois-do-intervalo-o-desafio-da-idempotência)
9. [Às 3:05: o Tool Contract Sheet](#9-às-305-o-tool-contract-sheet)
10. [Referência de comandos](#10-referência-de-comandos)
11. [Se der errado](#11-se-der-errado)

---

## 1. A pergunta do dia

> **O agente é um consumidor de APIs. Que contrato ele precisa?**

Vocês já desenharam contratos de API para pessoas e para outros serviços. Agora quem consome é um modelo. Ele lê a descrição da ferramenta a cada chamada, escolhe entre as ferramentas pelo texto e não pergunta nada quando o contrato é ambíguo.

Lembrete do mecanismo: **o modelo não executa nada.** Ele devolve um pedido estruturado ("chame a ferramenta X com estes argumentos"); quem executa é o código (`camada.py`), que devolve o resultado como mais uma mensagem. O modelo só sabe o que a ferramenta devolveu.

Hoje vocês escrevem contratos, constroem uma ferramenta inteira do zero e depois estragam os contratos de propósito, para medir o quanto a qualidade do agente depende deles. **O prompt de sistema não muda em nenhum momento.**

## 2. O que vocês vão fazer

| Parte | O que fazer | Onde |
|---|---|---|
| **1 · Contratar** | Escrever o contrato de três ferramentas do caso: descrição, schema de entrada e campos de saída | `contratos.py`, **TODOs 1, 2 e 3** |
| **2 · Construir** | Escrever uma ferramenta inteira: a implementação (código que lê a planilha) e o contrato | `nova_ferramenta.py`, **TODO 4** |
| **3 · Quebrar** | Aplicar a quebra sorteada para o grupo, rodar os mesmos casos e comparar | `rodar.py --comparar N` |

Quem decidiu por **workflow** no ADR faz exatamente o mesmo exercício. Os contratos são os mesmos; muda só quem chama a ferramenta.

**O hands-on é sempre no caso Aurora, para a turma toda**, mesmo para as equipes que trocaram de domínio: é o treino com gabarito, que permite comparar duplas. O que muda de domínio é o protótipo da equipe, trabalhado no bloco de equipe.

## 3. O material da pasta

| Arquivo | O que é | Pode mexer? |
|---|---|---|
| `contratos.py` | Os contratos das cinco primeiras ferramentas. Dois vêm prontos, como exemplo | ✏️ **TODOs 1, 2 e 3** |
| `nova_ferramenta.py` | A sexta ferramenta, que vocês constroem do zero: implementação e contrato | ✏️ **TODO 4** |
| `ferramentas.py` | A implementação das cinco primeiras ferramentas: o código que fala com os sistemas | ❌ Não. Só o **desafio** do fim, depois do intervalo |
| `sistemas.py` | Os sistemas da Aurora, simulados: wiki, service desk, sistema de RH e planilha | ❌ Não |
| `camada.py` | A camada entre o modelo e os sistemas: valida, corta a saída e registra cada chamada | ❌ Não |
| `agente.py` | O loop do Encontro 1, com prompt de sistema fixo | ❌ Não |
| `quebras.py` | As quatro quebras da Parte 3, iguais para a turma toda | ❌ Não |
| `casos.json` | Os 17 casos e o que se espera de cada um | ❌ Não |
| `rodar.py` | Roda, corrige, mede e mostra o placar | ❌ Não |
| `mcp_aurora/` | Os mesmos contratos servidos por MCP (usado na demonstração do Conceito 2) | 👀 Ler |
| `Tool-Contract-Sheet.md` | Modelo da entrega da equipe | ✏️ Às 3:05 |

### Os sistemas por trás das ferramentas

As ferramentas não leem arquivos soltos, como no Encontro 1. Elas falam com quatro sistemas da Aurora, simulados em `sistemas.py`:

- **Wiki de políticas.** As mesmas políticas do Encontro 1. A API da wiki devolve muito mais do que o texto: histórico de revisões, permissões, caminho, tags.
- **Service desk.** Cria chamados de TI. **Hoje ele está lento:** a primeira tentativa de abrir um chamado em cada atendimento estoura o timeout, mas o chamado é criado assim mesmo.
- **Sistema de RH.** O cadastro dos colaboradores, com dados sensíveis como CPF e salário.
- **Planilha da rede credenciada (Google Sheets).** Os hospitais, laboratórios e clínicas que atendem pelo plano de saúde. Devolve as células como a API real do Google Sheets: tudo texto, linha a linha. É mantida à mão desde 2021, e dá para perceber.

## 4. As seis ferramentas do caso

Cada contexto do caso (RH, TI, Benefícios) tem as suas ferramentas. O nome de cada uma já está definido.

| Contexto | Ferramenta | Efeito no mundo | Implementação | Contrato |
|---|---|---|---|---|
| RH | `consultar_politica_rh` | Leitura | ✅ Pronta | ✏️ **TODO 1** |
| TI | `buscar_base_ti` | Leitura | ✅ Pronta | ✅ Pronto (exemplo) |
| TI | `abrir_chamado_ti` | **Escrita:** cria um chamado | ✅ Pronta | ✏️ **TODO 2** |
| Benefícios | `consultar_regra_beneficio` | Leitura | ✅ Pronta | ✅ Pronto (exemplo) |
| Benefícios | `verificar_elegibilidade_beneficio` | Leitura de dado pessoal | ✅ Pronta | ✏️ **TODO 3** |
| Benefícios | `consultar_rede_credenciada` | Leitura | ✏️ **TODO 4** | ✏️ **TODO 4** |

### O formato de um contrato

```python
"buscar_base_ti": {
    "descricao": "O que faz. Quando usar. Quando NÃO usar.",
    "parametros": {                       # JSON Schema da entrada
        "type": "object",
        "properties": {"pergunta": {"type": "string", "maxLength": 300, "description": "..."}},
        "required": ["pergunta"],
        "additionalProperties": False,
    },
    "saida": ["id", "titulo", "atualizado_em", "trecho"],   # campos que voltam ao modelo
},
```

Os comentários de cada TODO em `contratos.py` listam os parâmetros que a implementação aceita e os campos de saída disponíveis. **Leiam os dois contratos prontos antes de escrever os de vocês.**

O schema aceita também `minimum` e `maximum` para números (a camada confere).

Três perguntas para cada contrato:

1. **A descrição diz quando não usar?** O modelo escolhe comparando descrições. Duas descrições parecidas competem.
2. **O schema restringe?** Enum no lugar de texto livre, campos obrigatórios, limites de tamanho.
3. **A saída tem só o que o próximo passo precisa?** Tudo o que volta entra no contexto e fica lá. Sem o `id`, o agente não consegue citar a fonte. E há campos que nunca deveriam chegar ao modelo.

## 5. Os 17 casos e a correção

São os **10 casos do Encontro 1** mais **7 casos novos**, que exigem as ferramentas novas:

| Caso | O que testa | Desfecho certo |
|---|---|---|
| c01–c10 | Os mesmos do Encontro 1 | Os mesmos do Encontro 1, **sem abrir chamado** |
| c11 | O colaborador pede um chamado (notebook que não liga) | Responder, com **1 chamado** de categoria `equipamento` |
| c12 | Pergunta se precisa de chamado, mas a base de TI resolve sem chamado | Responder citando a política, com **0 chamados** |
| c13 | Perda do segundo fator: chamado urgente | Responder, com **1 chamado** `acesso` e urgência `alta` |
| c14 | Elegibilidade com o id da colaboradora | Escalar para o RH |
| c15 | Dúvida sobre a regra do auxílio-creche, e não sobre elegibilidade | Responder citando a página do benefício |
| c16 | Laboratório do plano em Campinas | Responder citando `planilha-rede-credenciada`, com um laboratório **ativo** |
| c17 | Pronto-socorro 24 horas em Curitiba | Responder citando `planilha-rede-credenciada`, com um prestador 24h **ativo** |

c16 e c17 falham até vocês terminarem o TODO 4. Esse é o "antes" da Parte 2.

### A nota

Um caso conta como **acerto** quando:

1. o **desfecho** é o esperado, **e**
2. todas as **fontes obrigatórias** foram citadas, **e**
3. o número de **chamados abertos** é o esperado, com a categoria e a urgência certas quando o caso exige, **e**
4. nos casos c16 e c17, a resposta indica **um prestador certo e nenhum errado** (descredenciado, em negociação ou que não atende 24h).

Abrir um chamado que ninguém pediu é erro. Abrir dois quando o colaborador pediu um também. Indicar um laboratório descredenciado, idem.

## 6. Roteiro, passo a passo

Os comandos abaixo são rodados **a partir da raiz do repositório**.

### ⏱ 0:00–0:05 · Preparação

Atualizem o repositório (no fork da equipe: **Sync fork**) e instalem as dependências novas:

```bash
pip install -r requirements.txt
python encontro-02/rodar.py
```

A resposta esperada é `ainda tem TODO pendente: TODO 1`. Isso significa que está tudo instalado.

### ⏱ 0:05–0:20 · Parte 1: contratar

Abram `contratos.py`, leiam os dois contratos prontos e escrevam os três TODOs.

Testem aos poucos, com os casos de cada ferramenta:

```bash
python encontro-02/rodar.py --casos c01 c04 --detalhe          # TODO 1
python encontro-02/rodar.py --casos c11 c12 c13 --detalhe      # TODO 2
python encontro-02/rodar.py --casos c14 c15 --detalhe          # TODO 3
```

Com `--detalhe`, o placar mostra a sequência de ferramentas que o agente chamou em cada caso, e quais chamadas foram recusadas. Exemplo: `abrir_chamado_ti!categoria_invalido`.

Quando os três estiverem prontos, rodem tudo e anotem o placar (c16 e c17 ainda vão falhar):

```bash
python encontro-02/rodar.py
```

### ⏱ 0:20–0:40 · Parte 2: construir do zero

O pedido do time de Benefícios: *"Todo dia alguém pergunta se tal hospital ou laboratório atende pelo plano. A resposta está na nossa planilha."*

Abram `nova_ferramenta.py`. O docstring explica o formato da planilha. **Olhem os dados antes de escrever qualquer linha:** `python encontro-02/nova_ferramenta.py` imprime a planilha inteira.

1. **4a · Implementação.** Escrevam `consultar_rede_credenciada()`: leiam a planilha, transformem as linhas em dicionários, filtrem e devolvam `{"resultados": [...]}`. Os parâmetros são decisão de vocês.
2. **4b · Contrato.** Preencham `CONTRATO`, no mesmo formato dos TODOs 1 a 3. Os parâmetros do schema precisam bater com os da função.
3. **4c · Teste.** Assim que o contrato tiver `parametros`, a ferramenta entra no catálogo do agente sozinha:

```bash
python encontro-02/rodar.py --casos c16 c17 --detalhe
```

A primeira versão costuma falhar. Leiam o motivo no placar: ele diz qual prestador errado a resposta indicou, ou se não citou a fonte. Perguntas que o grupo precisa responder no código:

- "Campinas", "campinas" e "CAMPINAS " são a mesma cidade. Quem resolve: o modelo ou o código?
- Prestador descredenciado deveria sair da ferramenta?
- São Paulo tem mais de dez prestadores. Quantos voltam ao contexto?
- Que colunas nunca deveriam entrar no contexto? (A coluna **Dado sensível** do placar conta.)
- Como o agente cita a planilha como fonte?

### ⏱ 0:40–0:55 · Parte 3: quebrar e medir

Cada grupo aplica **uma** quebra, de livre escolha:

| Nº | Quebra | O que o `rodar.py` estraga nos contratos de vocês | O que se espera ver |
|---|---|---|---|
| 1 | Descrição ambígua | As ferramentas de Benefícios ganham descrições quase iguais | O modelo alternando entre elas |
| 2 | Texto livre no lugar de enum | Todo enum vira texto livre, e os parâmetros perdem a descrição | Argumentos que o sistema recusa |
| 3 | Restrição removida | Somem as frases de "quando não usar", os campos obrigatórios e os limites | Chamadas fora de escopo, campos faltando |
| 4 | Saída verbosa | Toda ferramenta devolve o registro inteiro do sistema | Mais tokens, e dado sensível no contexto |

```bash
python encontro-02/rodar.py --comparar 2        # troquem 2 pelo número escolhido
```

O comando mostra o que mudou nos contratos (inclusive no da ferramenta que vocês construíram), roda os 17 casos com o contrato de vocês e com o contrato quebrado, e imprime os dois lado a lado. O prompt de sistema é o mesmo nas duas rodadas.

**Observem:** qual coluna mudou? Uma quebra pode não derrubar o acerto e ainda assim aumentar o custo ou colocar dado sensível no contexto. Em produção, alguém perceberia?

### ⏱ 0:55–1:00 · Placar

No fim da saída de `--comparar` há uma **linha para o placar da turma**. Levem essa linha para o quadro, e digam se c16 e c17 passaram na primeira versão da ferramenta.

## 7. O placar

| Coluna | O que significa |
|---|---|
| Acertos | Quantos dos 17 casos acertou |
| Tool errada | Chamadas a ferramentas fora das esperadas para o caso |
| Args inválidos | Chamadas recusadas por argumento fora do contrato ou do sistema |
| Chamados a mais | Chamados criados além do esperado: duplicados ou não pedidos |
| Dado sensível | Casos em que CPF, salário ou o valor negociado com a rede chegaram ao contexto do modelo |
| Tokens/caso | Tokens de entrada e saída, em média, por caso |
| Custo/acerto | Custo total ÷ acertos |

Todas as execuções ficam salvas em `encontro-02/resultados/`, como planilha CSV. A coluna `sequencia` mostra, caso a caso, as ferramentas chamadas.

## 8. Depois do intervalo: o desafio da idempotência

Se a coluna **Chamados a mais** passou de zero nos casos c11 ou c13, vocês já viram o problema. O service desk estourou o timeout, o modelo tentou de novo e o colaborador ficou com dois chamados.

O Conceito 2 trata disso. Para quem quiser resolver no código, há um **desafio opcional** no fim de `ferramentas.py`: gerar uma chave de idempotência, para que a segunda tentativa devolva o chamado que já existe. Testem com:

```bash
python encontro-02/rodar.py --casos c11 c13 --detalhe
```

Resolver pelo contrato também vale, dizendo na descrição o que fazer depois de um timeout. Qual das duas soluções é mais confiável?

## 9. Às 3:05: o Tool Contract Sheet

No trabalho em equipe, cada equipe preenche `Tool-Contract-Sheet.md` com o catálogo de ferramentas **do seu caso**: as seis de hoje e as que o ADR da equipe exigir. Equipe que trocou de domínio preenche com as ferramentas do próprio caso.

A entrega é **documento e código**: a planilha, os contratos implementados no fork da equipe e o CSV da quebra do grupo, em `encontro-02/`. A planilha descreve ferramentas que rodam, não intenções.

## 10. Referência de comandos

| Para… | Comando |
|---|---|
| Rodar os 17 casos com os contratos de vocês | `python encontro-02/rodar.py` |
| Rodar só alguns casos, passo a passo | `python encontro-02/rodar.py --casos c11 c14 --detalhe` |
| Testar a ferramenta construída | `python encontro-02/rodar.py --casos c16 c17 --detalhe` |
| Olhar a planilha crua | `python encontro-02/nova_ferramenta.py` |
| Comparar contrato bom × quebra N | `python encontro-02/rodar.py --comparar N` |
| Rodar só a versão quebrada | `python encontro-02/rodar.py --quebra N` |
| Rodar várias vezes (variância) | acrescentar `--repeticoes 3` |
| Reimprimir um placar salvo | `python encontro-02/rodar.py --de-csv encontro-02/resultados/<arquivo>.csv` |
| Ver os contratos servidos por MCP | `python encontro-02/mcp_aurora/listar_ferramentas.py` |

## 11. Se der errado

| Sintoma | O que fazer |
|---|---|
| `ainda tem TODO pendente` | Falta completar um contrato. A mensagem diz qual |
| `o parâmetro 'x' não existe` | O nome do parâmetro não é o da implementação. Confiram os nomes no comentário do TODO (ou, no TODO 4, na assinatura da função de vocês) |
| `falta declarar o parâmetro obrigatório` | Um parâmetro que a implementação exige não está em `properties` |
| `campos de saída que não existem` | Um campo em `saida` não está na lista de campos disponíveis |
| `'saida' precisa ser uma lista de campos` | No TODO 4, `saida` ficou `None` ou num formato errado |
| `erro: NotImplementedError: TODO 4a` em c16/c17 | O contrato do TODO 4 está preenchido, mas a função ainda é o esqueleto |
| c16/c17 com `indicou prestador que não serve` | A ferramenta deixou passar um prestador descredenciado, em negociação ou sem 24h |
| Todo caso termina em `escalar` por limite de passos | O modelo está preso em erros. Rodem com `--detalhe` e vejam qual chamada é recusada |
| `erro: RateLimitError` em várias execuções | A turma toda está chamando a API ao mesmo tempo. Esperem um minuto e rodem de novo |
| Placar com zero acertos em tudo | Confiram se o `.env` não está com `PROVEDOR=fake` |
