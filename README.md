# AI Agents Engineering

**MBA Engenharia de Software Moderna: Arquitetura, Plataformas & IA · FIAP**
Módulo 7 · AI Native Engineering

Repositório prático da disciplina. Aqui ficam o código de apoio, os exercícios de cada encontro e o projeto que a sua equipe vai construir ao longo das seis aulas.

---

## Sumário

1. [A disciplina em uma página](#1-a-disciplina-em-uma-página)
2. [O caso: Aurora Tecnologia](#2-o-caso-aurora-tecnologia)
3. [Como o repositório funciona](#3-como-o-repositório-funciona)
4. [Preparação do ambiente](#4-preparação-do-ambiente)
5. [Estrutura de pastas](#5-estrutura-de-pastas)
6. [Regras do jogo](#6-regras-do-jogo)
7. [Problemas comuns](#7-problemas-comuns)

---

## 1. A disciplina em uma página

A pergunta que atravessa a disciplina: **quando um problema precisa de um agente, e como construir um que se possa colocar em produção?**

Duas ideias guiam as seis aulas:

- **Um agente é um sistema distribuído não-determinístico.** Tudo que vocês sabem de engenharia continua valendo. O que muda é que o plano de execução é gerado em tempo real por um modelo.
- **A maioria dos problemas não precisa de agente, precisa de workflow.** Saber a diferença, com números, é a competência que a disciplina quer formar.

| Encontro | Tema | Pergunta do dia | Entrega da equipe | Pasta |
|---|---|---|---|---|
| 1 | Do workflow ao agente | Este problema precisa de um agente? | Agent Decision Record | `encontro-01/` ✅ |
| 2 | Contexto e ferramentas | Que contrato o agente precisa? | Tool Contract Sheet | `encontro-02/` ✅ |
| 3 | Recuperação como ferramenta | O que muda quando o agente decide se e quando buscar? | Nota de chunking (a busca entra no agente no Encontro 4) | `encontro-03/` ✅ |
| 4 | Padrões e multi-agentes | Quando dividir melhora, e quando só encarece? | Diagrama de arquitetura + medição | em breve |
| 5 | Evals, observabilidade e custo | Como ganhar confiança para dar deploy? | Suíte de avaliação + painel | em breve |
| 6 | Segurança, governança e produção | O que precisa ser verdade para ir à produção? | Análise de riscos + pitch | em breve |

## 2. O caso: Aurora Tecnologia

Todas as aulas usam o mesmo caso. A **Aurora Tecnologia** é uma empresa fictícia de médio porte. Todos os dias, colaboradores mandam dúvidas sobre RH, TI e benefícios por canais diferentes, e as respostas demoram e às vezes vêm desatualizadas.

A diretoria quer um assistente que:

- responda com precisão, **citando a fonte**;
- saiba dizer **"não sei"** quando a informação não existe ou é contraditória;
- saiba **encaminhar ao RH** o que não pode decidir sozinho.

Por trás do caso há três problemas de arquitetura, que vão reaparecer ao longo da disciplina:

1. **Controle de acesso por fonte:** nem todo especialista pode ver todo dado.
2. **Fontes que se contradizem:** dois documentos válidos dizendo coisas diferentes.
3. **Auditabilidade:** quando o assistente erra, é preciso saber por quê.

## 3. Como o repositório funciona

O repositório **cresce uma aula por vez**. Antes de cada encontro, uma pasta nova é publicada com o material daquele dia.

**No Encontro 1:** cada equipe faz um **fork** deste repositório no GitHub. O fork é o repositório da equipe, onde vocês trabalham até o pitch final.

**A cada aula nova:** no fork da equipe, clique em **Sync fork** no GitHub para receber a pasta do encontro. O que vocês já fizeram continua lá.

```
repositório da disciplina ──fork──► repositório da equipe
        │                                  ▲
        └─ nova pasta a cada aula ──Sync fork──┘
```

## 4. Preparação do ambiente

Faça isto **antes da primeira aula**. Leva uns 10 minutos.

### O que você precisa

- **Python 3.10 ou mais novo.** Confira com `python --version`.
- **Git** e uma conta no GitHub.
- **Uma chave de API** do provedor do modelo. O professor informa como obter a da turma.

### Passo a passo

```bash
# 1. clonar o fork da sua equipe
git clone https://github.com/<sua-equipe>/ai-agents-engineering.git
cd ai-agents-engineering

# 2. (recomendado) criar um ambiente virtual
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. instalar as dependências
pip install -r requirements.txt

# 4. criar o arquivo de configuração
cp .env.example .env               # Windows: copy .env.example .env
```

Abra o `.env` e cole a chave de API em `ANTHROPIC_API_KEY`.

```bash
# 5. conferir se está tudo certo
python setup/verificar_ambiente.py
```

Todas as linhas com `[ok]`? Ambiente pronto.

> **Sem chave ainda?** Troque `PROVEDOR=anthropic` por `PROVEDOR=fake` no `.env`. O código roda com respostas simuladas. Serve para conferir a instalação, não para medir nada.

## 5. Estrutura de pastas

```
ai-agents-engineering/
├── README.md                   este arquivo
├── requirements.txt            dependências Python
├── .env.example                modelo do arquivo de configuração
│
├── setup/
│   └── verificar_ambiente.py   confere se está tudo pronto
│
├── comum/                      peças usadas em todas as aulas
│   ├── modelo.py               a única parte do código que fala com o provedor do modelo
│   ├── medidor.py              conta chamadas, tokens e custo
│   ├── resultado.py            o formato de resposta que toda solução devolve
│   └── avaliar.py              compara a resposta com o gabarito
│
├── encontro-01/                exercícios do Encontro 1 (tem README próprio)
├── encontro-02/                exercícios do Encontro 2
├── encontro-03/                notebooks do Encontro 3: busca, chunking e a wiki ampliada
│
└── referencia/
    └── langchain-basico.ipynb  apoio: os conceitos do Encontro 1 escritos em LangChain
```

### Sobre o provedor do modelo

Todo o código chama o modelo através de `comum/modelo.py`. Nenhum outro arquivo fala direto com o provedor. Isso é de propósito: trocar de provedor significa reescrever um arquivo só.

## 6. Regras do jogo

- **Nunca faça commit do `.env`.** Ele guarda a chave de API. O `.gitignore` já o protege, mas confira antes de cada `git push`.
- **Não altere `comum/`** nem os arquivos marcados como "não mexa" no README de cada aula. Eles são a régua comum da turma: se cada equipe mudar a régua, os números deixam de ser comparáveis.
- **Cada aula tem um README próprio.** É ali que está o roteiro do exercício.
- **O gasto com API é limitado por equipe.** Rode o que precisa, não em loop infinito. Estourar o orçamento também é uma lição, mas é melhor aprendê-la com o custo dos outros.

## 7. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `ModuleNotFoundError` | Dependências não instaladas, ou ambiente virtual desativado | Ative o `.venv` e rode `pip install -r requirements.txt` |
| `[FALHA] arquivo .env` | O `.env` não foi criado | `cp .env.example .env` |
| `[FALHA] ANTHROPIC_API_KEY` | A chave não foi colada, ou foi colada com espaços | Abra o `.env` e confira a linha da chave |
| `AuthenticationError` | Chave inválida ou revogada | Peça uma chave nova ao professor |
| `RateLimitError` | Muita gente chamando a API ao mesmo tempo | Espere um minuto e rode de novo |
| Comando não encontra os arquivos | Rodando de dentro de outra pasta | Rode os comandos a partir da raiz do repositório |
