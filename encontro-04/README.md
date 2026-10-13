# Encontro 4 · Padrões de arquitetura e multi-agentes

**Pergunta do dia:** quando dividir em vários agentes melhora, e quando só encarece?

## Antes da aula

**Nada a instalar.** Os notebooks deste encontro rodam no Google Colab, a partir do botão no topo de cada um. Basta uma conta Google.

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-04/01-dentro-do-multiagente.ipynb) `01-dentro-do-multiagente.ipynb`, acompanhado ao vivo

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/se-ai-agents-engineering/ai-agents-engineering-v2/blob/main/encontro-04/02-hands-on-multiagente.ipynb) `02-hands-on-multiagente.ipynb`, o hands-on do grupo

Abra o notebook 01 antes da aula e rode só a primeira célula. Se aparecer "Tudo certo, pode seguir", você está pronto.

**Também não precisa de chave de API.** As respostas do modelo foram gravadas pelo professor (*replay*): cada célula reproduz exatamente o que o modelo respondeu, e o placar mostra os tokens e o custo que cada chamada teve de verdade. Tudo o que o menu do hands-on oferece está gravado.

> **Prefere rodar na sua máquina?** Funciona igual, a partir da raiz do repositório depois do Sync fork: `pip install -r requirements.txt` e `jupyter notebook encontro-04/`. Este encontro só precisa de `numpy` e `python-dotenv`. A busca já vem indexada, então não há modelo de embeddings para baixar.

## O que tem nesta pasta

| Arquivo | Para que serve |
|---|---|
| `01-dentro-do-multiagente.ipynb` | Acompanhado ao vivo com o professor. Não tem entrega. |
| `02-hands-on-multiagente.ipynb` | O hands-on do grupo. Gera o placar que vai na nota. |
| `NOTA-ARQUITETURA.md` | **O entregável.** Modelo de uma página para preencher. |
| `03-langgraph-checkpoint.ipynb` | Demonstração do professor: checkpoint e aprovação humana em LangGraph. |
| `04-crewai.ipynb` | Demonstração do professor: o mesmo atendimento em CrewAI. |
| `multiagente.py` | As arquiteturas (agente único, roteador + especialistas, supervisor), o trace e o placar. |
| `busca.py` | A busca do Encontro 3, já indexada, rodando só com numpy. |
| `casos.json` | Os 16 casos da demonstração do Encontro 3 e mais 3 que testam a divisão (R1 a R3). |
| `dados/` | O índice da busca e a gravação das respostas do modelo. Não mexa. |
| `preparo/` | Scripts do professor para gerar o índice e gravar o replay. A turma não usa. |

## O que muda em relação ao Encontro 3

Nada do que vocês construíram foi trocado. O agente único deste encontro é o agente que decide buscar da demonstração do Encontro 3: a mesma busca, atrás do mesmo contrato e da mesma camada do Encontro 2, com as mesmas regras de resposta do Encontro 1. A única coisa nova é a **coordenação** entre agentes.

Cada especialista tem a sua própria ferramenta de busca, presa aos espaços da wiki da área dele. O metadado `espaco` do Encontro 3 vira **controle de acesso por fonte**.

## O entregável

`encontro-04/NOTA-ARQUITETURA.md` no fork da equipe: o padrão escolhido, o diagrama, o placar gerado no notebook 02 e a decisão "a divisão se paga?", defendida com um caso. Os detalhes estão no topo do notebook 02.

## Para ir além, com chave (opcional)

Mudar o que o modelo lê (a descrição de um especialista, um prompt, uma pergunta nova) gera chamadas que não estão na gravação. Com uma chave liberada pelo professor, a última célula do notebook 02 mostra como fazer isso no Colab. O que já está gravado continua vindo da gravação, sem custo. Para desfazer uma mudança, use **Ambiente de execução → Reiniciar sessão**.

---

## Para o professor: preparar o encontro

Uma vez por turma, na sua máquina, a partir da raiz do repositório, com o ambiente do Encontro 3 instalado:

```bash
# 1. índice da busca (sem custo de API)
python encontro-04/preparo/preparar_indice.py

# 2. escolher o modelo pelo placar (centavos, com modelos baratos)
python encontro-04/preparo/comparar_modelos.py \
    google/gemini-2.5-flash-lite:0.10:0.40 deepseek/deepseek-v4-flash:0.09:0.18

# 3. pôr no .env o MODELO escolhido e os dois preços; gravar
python encontro-04/preparo/gravar_replay.py

# 4. conferir que tudo roda sem chave
python encontro-04/preparo/gravar_replay.py --conferir
```

Depois, faça commit da pasta `encontro-04/dados/` no repositório da disciplina. Sem ela, os notebooks não rodam no Colab. Se editar os notebooks 01 ou 02, rode o passo 3 de novo: ele só chama a API para o que ainda não estiver gravado.

As demonstrações 03 e 04 precisam de `pip install -r encontro-04/requirements-demo.txt`. A 03 grava as próprias respostas em `dados/replay-professor.jsonl`: só o ensaio tem custo.
