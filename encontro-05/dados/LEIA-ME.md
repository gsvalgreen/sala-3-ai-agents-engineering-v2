# dados/

Gerado pelo `preparo/gravar_replay.py`, na máquina do professor. Não edite à mão.

| Arquivo | O que é |
|---|---|
| `replay-principal.jsonl` | as respostas do modelo principal: v1 e v2, cada caso gravado 5 vezes (amostras 0 a 4) |
| `replay-barato.jsonl` | as respostas do modelo mais barato: v3, 5 amostras por caso |
| `replay-juiz.jsonl` | os vereditos dos dois juízes |
| `consultas-aurora.npz` | o vetor de cada consulta de busca já feita (o índice dos trechos continua em `encontro-04/dados/`) |

Cada arquivo de gravação começa com uma linha de cabeçalho: o modelo, os preços por milhão de tokens e a data.
O custo que o placar mostra é calculado com esses preços.
