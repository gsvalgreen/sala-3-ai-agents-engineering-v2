# Encontro 1 · Do workflow ao agente

**Hands-on 1: um problema, três arquiteturas**
Em grupos

---

## Sumário

1. [A pergunta do dia](#1-a-pergunta-do-dia)
2. [O que vocês vão fazer](#2-o-que-vocês-vão-fazer)
3. [O material da pasta](#3-o-material-da-pasta)
4. [Como uma resposta é corrigida](#4-como-uma-resposta-é-corrigida)
5. [Roteiro, passo a passo](#5-roteiro-passo-a-passo)
6. [O placar](#6-o-placar)
7. [Depois do hands-on: o ADR](#7-depois-do-hands-on-o-adr)
8. [Referência de comandos](#8-referência-de-comandos)
9. [Se der errado](#9-se-der-errado)

---

## 1. A pergunta do dia

A Aurora Tecnologia quer um assistente para responder dúvidas de colaboradores. Antes de discutir *como* construir, a pergunta é:

> **Este problema precisa de um agente?**

A resposta vai sair de números, e não de opinião. Vocês vão resolver o mesmo problema de três jeitos e medir acerto, custo e tempo de cada um.

## 2. O que vocês vão fazer

Responder às **mesmas 10 perguntas de colaboradores** com três arquiteturas, que vão do mais simples ao mais autônomo:

| | Arquitetura | Quem decide o próximo passo | Como funciona | O que vocês fazem |
|---|---|---|---|---|
| **A** | Prompt único | Ninguém: é uma chamada só | Manda todos os documentos e a pergunta numa única chamada ao modelo | Nada. Já vem pronta: rodem e observem |
| **B** | Workflow determinístico | **O código** | Classifica o tema, busca os documentos daquele tema e responde | Completar os **TODOs 1 e 2** |
| **C** | Agente em loop | **O modelo** | O modelo decide sozinho quando buscar, onde, quantas vezes e quando parar | Completar os **TODOs 3 e 4** |

Ao final, cada dupla leva para o placar da turma os números das três.

## 3. O material da pasta

| Arquivo | O que é | Pode mexer? |
|---|---|---|
| `corpus/` | 12 documentos de política da Aurora (5 de RH, 4 de TI, 3 de Benefícios) | ❌ Não |
| `casos.json` | As 10 perguntas e o desfecho esperado de cada uma | ❌ Não |
| `ferramentas.py` | `buscar(tema, consulta)`: acha documentos por palavras-chave | ❌ Não |
| `politica_de_resposta.py` | As regras de resposta, iguais para as três arquiteturas | ❌ Não |
| `rodar.py` | Roda as arquiteturas, corrige, mede e mostra o placar | ❌ Não |
| `arquitetura_a.py` | Prompt único, pronta | 👀 Ler e experimentar |
| `arquitetura_b.py` | Workflow, com lacunas | ✏️ **TODOs 1 e 2** |
| `arquitetura_c.py` | Agente, com lacunas | ✏️ **TODOs 3 e 4** |
| `ADR-template.md` | Modelo do documento da equipe | ✏️ Na atividade seguinte |

### As 10 perguntas

Cada pergunta foi escolhida para testar uma situação diferente:

| Casos | Tipo | O que testa |
|---|---|---|
| c01–c04 | Diretas | O básico: achar o documento certo e responder |
| c05, c06 | Ambíguas | A pergunta parece ser de uma área, mas a resposta está em outra |
| c07 | Conflito | Dois documentos dizem coisas diferentes |
| c08 | Fora do corpus | A informação não existe em nenhum documento |
| c09 | Elegibilidade | A pessoa pergunta se *ela* tem direito a um benefício |
| c10 | Multi-passo | A resposta precisa de dois documentos, de áreas diferentes |

## 4. Como uma resposta é corrigida

### O formato obrigatório

Toda arquitetura devolve a resposta no mesmo formato:

```json
{"desfecho": "responder", "fontes": ["ti-equipamentos"], "resposta": "Sim, o seguro cobre..."}
```

O **desfecho** só pode ser um destes três:

| Desfecho | Quando usar |
|---|---|
| `responder` | Os documentos sustentam a resposta |
| `escalar` | A pessoa pergunta se *ela* tem direito a um benefício. Quem analisa é o RH |
| `nao_sei` | A informação não existe, ou os documentos se contradizem |

### A nota

Uma resposta conta como **acerto** quando:

1. o **desfecho** é o esperado, **e**
2. todas as **fontes obrigatórias** foram citadas.

Citar uma fonte a mais não tira ponto. O **texto da resposta não entra na nota**: assim a correção é automática e igual para todas as duplas.

Se o modelo devolver algo fora do formato, a resposta conta como erro ("saída fora do contrato"). Respeitar o contrato faz parte do resultado.

## 5. Roteiro, passo a passo

Os comandos abaixo são rodados **a partir da raiz do repositório**.

### ⏱ 0:00–0:05 · Preparação

```bash
python setup/verificar_ambiente.py
```

Tudo `[ok]`? Sigam em frente.

### ⏱ 0:05–0:15 · Arquitetura A, prompt único

**Rodem:**

```bash
python encontro-01/rodar.py --arq a
```

**Leiam** `arquitetura_a.py`. A lógica toda cabe em 5 linhas.

**Observem:**

- Quantas perguntas ela acertou? Em quais errou, e por quê?
  - 9, errou 1 onde o resultado devia ser "não sei" e o modelo respondeu um valor.
- Quantos tokens de entrada cada pergunta gasta? Estão na coluna `tokens_entrada` da planilha salva em `encontro-01/resultados/`.
  - Em média 3230 tokens de entrada por pergunta.
- O que aconteceria com essa arquitetura se a Aurora tivesse 5.000 documentos?
  - Supondo que cada arquivo tivesse 250 tokens, 5k arquivos seria 1.250.000 tokens.
  - Essa arquitetura perderia eficiencia, gastaria mais por interação e poderia demorar mais para responder.
  - Gastaria a toa e geraria insatisfação do usuário.

### ⏱ 0:15–0:30 · Arquitetura B, workflow

Abram `arquitetura_b.py`. O fluxo já está desenhado no topo do arquivo:

```
pergunta ──► classificar ──► tema?
                               ├── "elegibilidade" ──► escalar (sem chamar o modelo)
                               └── "rh" | "ti" | "beneficios"
                                      ──► buscar(tema, pergunta) ──► modelo responde
```

**TODO 1 · O classificador.** Escrevam o prompt que faz o modelo responder com uma das categorias (`rh`, `ti`, `beneficios`, `elegibilidade`), e decidam o que fazer quando o modelo responder outra coisa.

**TODO 2 · O roteamento.** Elegibilidade vai direto para o RH. Qualquer outra categoria busca os documentos do tema e pede ao modelo a resposta.

**Testem aos poucos, depois rodem tudo:**

```bash
python encontro-01/rodar.py --arq b --casos c01 c05 --detalhe
python encontro-01/rodar.py --arq b
```

**Observem:** em quais casos o classificador escolheu o tema errado? O que acontece com o c07 e o c10?

### ⏱ 0:30–0:45 · Arquitetura C, agente em loop

Abram `arquitetura_c.py`. As ferramentas já estão definidas. Falta o motor:

**TODO 3 · O critério de parada.** Quantos passos o agente pode dar por pergunta, no máximo? Implementem `deve_parar`. **Anotem o número escolhido e o porquê**: ele vai para o ADR.

**TODO 4 · O corpo do loop.** A cada passo, o modelo pede uma ou mais ferramentas. Tratem cada pedido:

| O modelo pediu | O que o código faz |
|---|---|
| `responder` | Encerra e devolve a resposta |
| `escalar_para_rh` | Encerra, com desfecho `escalar` |
| `buscar` | Executa a busca e devolve o resultado ao modelo, que segue para o próximo passo |

**Testem com o caso mais difícil, depois rodem tudo:**

```bash
python encontro-01/rodar.py --arq c --casos c10 --detalhe
python encontro-01/rodar.py --arq c
```

**Observem:** quantas buscas o agente fez em cada caso? Ele buscou onde vocês esperavam?

### ⏱ 0:45–0:50 · Placar

Rodem as três arquiteturas, com o agente três vezes:

```bash
python encontro-01/rodar.py --arq a b
python encontro-01/rodar.py --arq c --repeticoes 3
```

Levem os números para o placar da turma (próxima seção).

## 6. O placar

O `rodar.py` imprime duas tabelas.

**Caso a caso:** mostra em quais perguntas cada arquitetura acertou (`ok`) ou errou (`x`, com o motivo).

**Placar:** o resumo que vai para o quadro:

| Coluna | O que significa |
|---|---|
| Acertos | Quantas das 10 perguntas acertou |
| Custo total | Quanto custaram as 10 perguntas, em dólares |
| p50 | Tempo típico de uma pergunta: metade foi mais rápida que isso |
| p95 | Tempo das perguntas mais lentas: só 5% demoraram mais |
| Custo/acerto | Custo total ÷ acertos. **É o número que mais importa** |
| Casos que variaram | Só com `--repeticoes`: em quantas perguntas a resposta mudou de uma rodada para outra |

**Levem para o placar da turma**, de cada arquitetura: acertos, custo total, p50, p95 e custo por acerto. Do agente, também quantos casos variaram.

Todas as execuções ficam salvas em `encontro-01/resultados/`, como planilha CSV. Vocês vão precisar delas no ADR.

## 7. Depois do hands-on: o ADR

Às 3:00, as equipes usam esses números para escrever o **Agent Decision Record**: a decisão, registrada, sobre qual arquitetura o caso da Aurora deveria usar, e por quê.

O modelo está em `ADR-template.md`. A tabela do placar entra na seção 2 ("Alternativas consideradas").

> Uma equipe que conclua, com fundamento, que o caso pede workflow e não agente entrega um ADR igualmente válido.

**Material de apoio:** `referencia/langchain-basico.ipynb` mostra os mesmos conceitos deste exercício (chamada, ferramentas, loop) escritos em LangChain. Não é necessário para o hands-on; é para consulta.

## 8. Referência de comandos

| Para… | Comando |
|---|---|
| Rodar uma arquitetura | `python encontro-01/rodar.py --arq a` |
| Rodar várias | `python encontro-01/rodar.py --arq a b c` |
| Rodar só alguns casos | `python encontro-01/rodar.py --arq b --casos c05 c06` |
| Ver o detalhe de cada execução | acrescentar `--detalhe` |
| Rodar várias vezes (variância) | acrescentar `--repeticoes 3` |
| Reimprimir um placar salvo | `python encontro-01/rodar.py --de-csv encontro-01/resultados/<arquivo>.csv` |

## 9. Se der errado

| Sintoma | O que fazer |
|---|---|
| `ainda tem TODO pendente` | Falta completar um TODO daquela arquitetura. A mensagem diz qual |
| `saída fora do contrato` | O modelo não devolveu o JSON esperado. Conta como erro, e faz parte do resultado |
| `erro: RateLimitError` em várias execuções | A turma toda está chamando a API ao mesmo tempo. Esperem um minuto e rodem de novo |
| `erro: AuthenticationError` | Problema na chave. Confiram o `.env` na raiz do repositório |
| O agente sempre termina escalando por limite de passos | O critério de parada está baixo demais, ou o TODO 4 não está devolvendo os resultados das buscas ao modelo |
| Placar com zero acertos em tudo | Confiram se o `.env` não está com `PROVEDOR=fake` |
