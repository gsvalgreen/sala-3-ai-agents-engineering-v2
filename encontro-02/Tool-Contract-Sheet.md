# Tool Contract Sheet · Equipe [nome da equipe]

**Encontro 2 · Entrega de 10%: esta planilha e o código** · Caso: [Aurora Tecnologia ou domínio próprio]

Uma linha por ferramenta do caso: as seis do hands-on e as que o ADR da equipe exigir. Equipe que trocou de domínio preenche com as ferramentas do próprio caso.

**A entrega é documento e código.** Cada linha descreve uma ferramenta que existe no fork da equipe, com contrato implementado. Linha sem código correspondente vai marcada como *planejada*.

---

## 1. Catálogo

**Antes de cada linha, respondam a coluna "Quem decide":** essa chamada precisa ser escolhida pelo modelo, ou pode ser um passo fixo do workflow? Toda linha com "Modelo" precisa justificar, na seção 2, por que o código não poderia decidir.

| Nome | Quem decide | Descrição | Entrada | Saída | Escopo | Criticidade | Reversível |
|---|---|---|---|---|---|---|---|
| `abrir_chamado_ti` *(exemplo)* | Modelo | Cria chamado quando a base de TI não resolve ou o colaborador pede | categoria (enum), descricao (15–500), urgencia (enum) | id, status, prazo | Colaborador autenticado; só TI | Média | Com custo |
| | | | | | | | |
| | | | | | | | |
| | | | | | | | |
| | | | | | | | |

**Como preencher cada coluna:**

- **Nome:** verbo + objeto, na linguagem do domínio.
- **Quem decide:** `Modelo` (o agente escolhe) ou `Código` (passo fixo do workflow).
- **Descrição:** resumida aqui. A versão completa vai na seção 3, com o **quando não usar**.
- **Entrada:** parâmetros, tipos e restrições (enum, obrigatório, limites).
- **Saída:** só os campos que voltam ao modelo.
- **Escopo:** quem pode chamar, em nome de quem, que dados alcança.
- **Criticidade:** Baixa, Média ou Alta. O que acontece se ela falhar ou for chamada errado?
- **Reversível:** `Sim` (nada muda no mundo), `Com custo` (desfaz, mas alguém já viu) ou `Não`.

## 2. Justificativas

Para cada ferramenta com **Quem decide = Modelo**: por que essa chamada depende do conteúdo da pergunta e não pode ser um passo fixo?

- [ferramenta]: [justificativa]

## 3. Contratos completos

Colem aqui, ou referenciem no repositório, a descrição completa e o schema de cada ferramenta. Para as seis do hands-on, basta apontar `encontro-02/contratos.py` e `encontro-02/nova_ferramenta.py`.

## 4. Evidência do hands-on

**A quebra da dupla** ([nº e nome da quebra]):

| Versão | Acertos | Tool errada | Args inválidos | Chamados a mais | Dado sensível | Tokens/caso |
|---|---|---|---|---|---|---|
| Contrato da dupla | | | | | | |
| Quebra [nº] | | | | | | |

CSV: `encontro-02/resultados/[arquivo].csv`

**A ferramenta construída** (`consultar_rede_credenciada`): c16 [passou/falhou] e c17 [passou/falhou] na primeira versão. O que precisou mudar até passar: [uma ou duas frases]

**O que isso mudou no nosso contrato:** [uma ou duas frases]

## 5. A ação irreversível do ADR

A ação irreversível definida no ADR do Encontro 1 é: [ação].

- Ela aparece na linha: [ferramenta], com Reversível = `Não`.
- Ou: ela **não** é executada por nenhuma ferramenta do sistema, porque [motivo].

> No Encontro 6, a coluna Reversível vira o eixo de impacto da matriz autonomia × impacto.
