# Troca de domínio · guia para a equipe

Este guia é só para a equipe que decidiu trocar o caso Aurora pelo domínio da própria empresa. Se a sua equipe continua em Aurora, não precisa ler.

**Prazo:** a janela de troca fecha no fim do Encontro 2. Depois disso, a equipe segue no domínio em que estiver até o pitch.

---

## 1. O que muda e o que não muda

A disciplina tem dois trilhos, e a troca mexe só em um deles.

| | Hands-on de cada encontro | Protótipo da equipe (o que vale nota) |
|---|---|---|
| **Onde roda** | Sempre em Aurora, para a turma toda | No domínio de vocês |
| **Por quê** | Corpus, casos e gabarito calibrados: é o que permite comparar duplas e medir cada quebra | É onde a equipe aplica o conceito de cada encontro ao próprio problema |
| **Em que pasta** | `encontro-0N/` | `projeto/`, no fork da equipe |

Ou seja: no hands-on, a dupla continua fazendo exatamente o mesmo que as outras. O que muda é o bloco de equipe e a entrega.

## 2. O domínio precisa ter quatro propriedades

- [ ] **Três fontes ou sistemas**, no mínimo, para integrar. Exemplo: uma base de documentos, um sistema de chamados e um cadastro.
- [ ] **Uma base de conhecimento em texto**, real ou realista: políticas, manuais, contratos, FAQ.
- [ ] **Uma ação irreversível** definida: algo que, depois de feito, nenhum rollback desfaz.
- [ ] **Uma métrica de negócio** mensurável: tempo de atendimento, taxa de resolução sem humano, custo por caso.

Faltou uma? O domínio não serve para a disciplina. Fiquem em Aurora.

**Nunca use dado real** de cliente, colaborador ou da empresa. Os sistemas são simulados, como os da Aurora, e os documentos são realistas, escritos ou adaptados pela equipe. Também não integre com o sistema real da empresa: o objetivo é o desenho, não a credencial.

## 3. O tamanho certo

Pequeno, mas completo. A régua para o Encontro 2:

| Peça | Mínimo | Para quê |
|---|---|---|
| Documentos no corpus | 5 a 10 | A base que o agente consulta |
| Ferramentas | 3 a 5 | Pelo menos uma leitura, uma escrita e uma decisão sensível, como as três da Parte 1 |
| Casos com gabarito | 5 a 8 | Pelo menos um caso em que a ferramenta certa é *não* agir |
| Sistemas simulados | Em memória, como em `encontro-02/sistemas.py` | Comportamento controlado, sem conta de terceiros |

Mais do que isso não dá nota a mais. Gastem o tempo no contrato, não no volume.

## 4. Passo a passo no código

Tudo a partir da raiz do fork.

### 4.1 · Crie a pasta do projeto

Copie a pasta do Encontro 2 para `projeto/` e apague o que é só da Aurora:

```bash
# macOS / Linux
cp -r encontro-02 projeto
rm -rf projeto/resultados projeto/mcp_aurora projeto/nova_ferramenta.py projeto/README.md projeto/TROCA-DE-DOMINIO.md
```

```powershell
# Windows (PowerShell)
Copy-Item encontro-02 projeto -Recurse
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue projeto/resultados, projeto/mcp_aurora, projeto/nova_ferramenta.py, projeto/README.md, projeto/TROCA-DE-DOMINIO.md
```

Nunca edite `encontro-02/` para o domínio de vocês: o hands-on dos próximos encontros depende dela intacta.

### 4.2 · O que fica como está

Estes arquivos não dependem do domínio. Não mexam neles:

- `comum/`, na raiz: modelo, medição e correção;
- `projeto/camada.py`: validação, corte da saída e erros escritos para o modelo;
- `projeto/rodar.py`: o placar, os CSVs e as comparações;
- `projeto/quebras.py`, com um único ajuste opcional, no passo 4.7.

### 4.3 · `corpus/` e `sistemas.py`: o mundo do domínio

Crie `projeto/corpus/` com os documentos em Markdown, um arquivo por documento. O nome do arquivo, sem `.md`, é o id que o agente cita como fonte.

Reescreva `projeto/sistemas.py` com os sistemas simulados do domínio. Usem o da Aurora como molde. Cada sistema é uma classe com dados em memória. Se algum sistema escreve no mundo (abrir chamado, registrar pedido), guarde o que foi criado numa lista e dê a ele um método `reiniciar()`.

### 4.4 · `ferramentas.py`: as implementações

Mantenham do arquivo copiado a classe `ErroDeFerramenta` e a função `_exigir`. Troquem todo o resto pelas ferramentas de vocês. O `rodar.py` e a `camada.py` esperam encontrar seis nomes:

| Nome | O que é |
|---|---|
| `IMPLEMENTACOES` | `{"nome_da_ferramenta": funcao, ...}` |
| `CONTEXTO` | `{"nome_da_ferramenta": "bounded_context", ...}`, que vai para o log de auditoria |
| `CAMPOS_DISPONIVEIS` | Para cada ferramenta, os campos que o sistema *pode* devolver. O contrato escolhe quais devolve |
| `CAMPOS_SENSIVEIS` | Os campos que nunca deveriam chegar ao modelo. O placar conta quando chegam |
| `reiniciar_atendimento()` | Chamada antes de cada caso: chame o `reiniciar()` de cada sistema que escreve |
| `efeitos_criados()` | Devolve a lista do que o atendimento criou no mundo. O placar compara com o campo `chamados` do gabarito |

Cada ferramenta é uma função comum, que devolve um dicionário. Quando a entrada não serve, ela levanta `ErroDeFerramenta` com `aceitos` e `como_corrigir`, para o modelo conseguir se corrigir sozinho.

### 4.5 · `contratos.py`: o que o modelo lê

Apaguem o conteúdo e escrevam um contrato por ferramenta, no mesmo formato dos TODOs da Parte 1: `descricao` (com quando *não* usar), `parametros` (JSON Schema, com enums e limites) e `saida`. Este arquivo é o par em código do Tool Contract Sheet: cada linha da planilha corresponde a um contrato aqui.

### 4.6 · `casos.json` e `agente.py`

**Casos.** Troquem pelos casos do domínio, no mesmo formato:

```json
{
  "id": "d01",
  "tipo": "direta",
  "pergunta": "A pergunta, como o usuário a faria",
  "esperado": {"desfecho": "responder", "fontes_obrigatorias": ["id-do-documento"], "chamados": 0},
  "ferramentas_aceitas": ["nome_da_ferramenta"]
}
```

O `desfecho` pode ser `responder`, `escalar` ou `nao_sei`. Em `chamados`, coloquem quantos efeitos o caso deveria criar (0 quando o certo é não agir). Para conferir o texto da resposta, existem também `resposta_contem_algum` e `resposta_nao_contem` (veja os casos c16 e c17 do Encontro 2).

**Agente.** No `projeto/agente.py`, troquem só três coisas, e nada no loop:

1. O bloco que lê as regras do Encontro 1 e monta `SISTEMA`: substituam por um `SISTEMA` com as regras do domínio de vocês. Mantenham a instrução de citar os ids das fontes e de encerrar pela ferramenta `responder` ou pela de escalar.
2. O `NOME_ESCALAR` e o `"nome"` da segunda ferramenta de `ENCERRAMENTO`, por exemplo `escalar_para_atendente`.
3. A descrição dessa ferramenta: quando o atendimento deve passar para um humano. Normalmente é aí que mora a ação irreversível.

### 4.7 · Rodar e quebrar

```bash
python projeto/rodar.py --detalhe
python projeto/rodar.py --comparar 3
```

As quebras 2, 3 e 4 funcionam em qualquer domínio. A quebra 1 escolhe as ferramentas a confundir pelo nome. Para usá-la, troquem em `projeto/quebras.py` a lista de nomes pelas duas ou três ferramentas mais parecidas de vocês.

Para conferir sem gastar API: coloquem `PROVEDOR=fake` no `.env`. O placar sai zerado, mas mostra se tudo importa e roda.

## 5. A entrega do Encontro 2 no domínio de vocês

O mesmo que as outras equipes, só que sobre o caso de vocês:

- **`encontro-02/Tool-Contract-Sheet.md`**, preenchido com as ferramentas do domínio de vocês. O modelo é o mesmo.
- **O código em `projeto/`**, rodando: cada linha da planilha é um contrato em `projeto/contratos.py`. Uma ferramenta que ainda não existe vai marcada como *planejada* na planilha.
- **A linha da quebra** da dupla no placar, que vem do hands-on em Aurora, como para todo mundo.
- **A ação irreversível do ADR** localizada na planilha.

**Se trocaram hoje:** reescrevam o ADR no domínio novo, em `encontro-01/ADR.md`, durante o bloco de equipe. O código do experimento do Encontro 1 pode continuar sendo o de Aurora. A partir desta entrega, o código é o do domínio de vocês.

## 6. Dúvidas frequentes

**O hands-on do próximo encontro vai ser no nosso domínio?** Não. Ele continua em Aurora. No bloco de equipe, vocês levam o conceito do dia para `projeto/`.

**Podemos usar uma API real, como fizemos com a planilha na demo?** Só para uma fonte pública ou sem dado sensível, e com a chave fora do repositório. Na dúvida, simulem.

**Começamos com 3 ferramentas e o domínio precisa de 10. E agora?** Implementem as 3 que cobrem leitura, escrita e decisão sensível. As outras entram na planilha como *planejadas*, e cada encontro pode trazer mais uma.

**Quanto vamos gastar de API?** Uns poucos centavos por rodada com 5 a 8 casos. Usem `--casos` para rodar só o que estão mexendo.
