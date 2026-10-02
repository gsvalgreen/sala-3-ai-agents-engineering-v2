# Agent Decision Record — [nome da equipe]

**Caso:** Dúvidas Internas do Colaborador **Data:** 29/10/2026 · **Integrantes:** Gustavo Santos Valverde, Nádia
Oliveira Moretti, Leticia Perdun, Vinicius Ribeiro Neri, Guilherme Brun Moraes, Rodolfo de Lima Gaspar **Status:**
proposta

## 1. Contexto

[Qual é o problema, para quem, e com quais restrições. 3 a 5 linhas.]

**Ação irreversível do
caso:** [a ação que, depois de executada, não pode ser desfeita. Ex.: confirmar a um colaborador que ele é elegível a um benefício.]

## 2. Alternativas consideradas

Números do Hands-on 1 (mesmos 10 casos):

| Arquitetura        | Acertos | Custo total | p50    | p95    | Custo por acerto | Variou entre execuções? |
|--------------------|---------|-------------|--------|--------|------------------|-------------------------|
| A · Prompt único   | 09/10   | US$ 0.03941 | 1.94 s | 3.79 s | US$ 0.00438      | —                       |
| B · Workflow       | 08/10   | US$ 0.01486 | 1.75 s | 2.39 s | US$ 0.00186      | —                       |
| C · Agente em loop | 10/10   | US$ 0.06124 | 4.45 s | 6.44 s | US$ 0.00612      | 0 de 10 casos           |

**Onde cada uma errou, e por
quê:** [2 a 4 linhas. Ex.: "B errou c07 porque o documento conflitante está em outro tema."]

* A e B erraram c07 porque o documento conflitante está em outro tema.
* B errou c10 porque o prompt não foi suficiente para o modelo classificar a pergunta.

## 3. Decisão

Escolhemos a arquitetura B (Workflow) porque ela é mais barata por acerto e mais rápida que as outras arquiteturas enquanto mantém 80% de acerto.

**Escopo de autonomia:** Não responde sobre eligibilidade de benefícios, apenas sobre dúvidas internas do colaborador.

**Critério de parada** (se houver agente): N/A

## 4. Trade-offs assumidos

Capacidade de transitar entre diferentes temas de documentos vs custo reduzido e velocidade de resposta.
Ex. Para evitar a falha no cenário onde dois temas tem respostas conflitantes, 
    entendemos que refinar os arquivos de contexto e o prompt compensa mais do que usar um agente em loop.

## 5. Critério de reversão

[A condição mensurável que faria a equipe voltar atrás. Deve dizer o que medir, o limite e para onde voltar.]

Considerar agente em loop se o workflow não superar 80% de acertos nos casos de teste, ou se o custo por acerto ultrapassar US$ 0.00438.
