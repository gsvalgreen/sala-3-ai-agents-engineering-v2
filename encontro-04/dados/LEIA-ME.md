# dados/

Gerado pelos scripts de `preparo/`, na máquina do professor. Não edite à mão.

| Arquivo | Gerado por | O que é |
|---|---|---|
| `indice-aurora.json` | `preparar_indice.py` | os trechos da wiki, cortados por estrutura, com os metadados |
| `vetores-aurora.npz` | `preparar_indice.py` | o vetor de cada trecho |
| `consultas-aurora.npz` | `preparar_indice.py` e `gravar_replay.py` | o vetor de cada consulta já feita |
| `replay.jsonl` | `gravar_replay.py` | as respostas gravadas do modelo, que a turma reproduz sem chave |
| `replay-professor.jsonl` | notebook 03 | as respostas da demonstração de LangGraph |
