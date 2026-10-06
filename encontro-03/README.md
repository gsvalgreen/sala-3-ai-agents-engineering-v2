# Encontro 3 · Recuperação como ferramenta

**Pergunta do dia:** o que muda quando o agente decide *se* e *quando* buscar?

## Antes da aula (obrigatório, 10 minutos)

Na raiz do repositório, depois do **Sync fork**:

```bash
pip install -r requirements.txt
jupyter notebook encontro-03/01-dentro-do-rag.ipynb
```

> **Linux:** instale antes a versão do PyTorch só para CPU, que é muito menor: `pip install torch --index-url https://download.pytorch.org/whl/cpu`. No macOS e no Windows, o `pip install` normal já baixa a versão para CPU.

Rode só a **Etapa 0** do notebook. Ela baixa o modelo de embeddings (cerca de 470 MB) e confirma que o ambiente está pronto. Se você chegar à aula sem isso, vai passar o hands-on esperando o download.

Nada nos notebooks chama a API da Anthropic: a busca roda toda na sua máquina, sem custo.

## O que tem nesta pasta

| Arquivo | Para que serve |
|---|---|
| `01-dentro-do-rag.ipynb` | Acompanhado ao vivo com o professor. Não tem entrega. |
| `02-hands-on-chunking.ipynb` | O hands-on da equipe. Gera a tabela que vai na nota. |
| `NOTA-CHUNKING.md` | **O entregável.** Modelo de uma página para preencher. |
| `03-agente-sem-framework.ipynb` | Demonstração do professor: o agente que decide buscar, com o loop do Encontro 2. Chama a API. |
| `04-agente-com-langchain.ipynb` | Demonstração do professor: o mesmo agente em LangChain, para comparar. Chama a API e precisa do `requirements-demo.txt`. |
| `agente_busca.py`, `casos-agente.json` | As peças e os casos das duas demonstrações. |
| `corpus/` | A wiki da Aurora: as 12 páginas do Encontro 1, agora com seções, e mais 13. Metadados no cabeçalho. |
| `casos.json` | O gabarito: perguntas e o trecho que a busca precisa trazer. |
| `rag_aurora.py` | As peças do RAG, pequenas e comentadas. Abra quando quiser ver como algo funciona. |
| `meu-corpus-exemplo/`, `meus-casos-exemplo.json` | Modelos para a equipe que trocou de domínio usar no `projeto/`, no bloco de equipe. |

## O entregável

`encontro-03/NOTA-CHUNKING.md` no fork da equipe: a estratégia adotada, por quê (com a tabela do placar), o que ela não resolve e quais metadados a ingestão precisa garantir. Os detalhes estão no topo do notebook 02.
