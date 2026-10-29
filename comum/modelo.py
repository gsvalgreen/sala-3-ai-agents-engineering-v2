"""Único ponto de contato com o provedor do modelo.

Todo o resto do projeto chama só estas funções:

    chamar(mensagens, sistema, ferramentas)  -> Resposta
    mensagem_do_usuario(texto)
    mensagem_do_assistente(resposta)
    mensagem_de_resultados([(chamada, texto_do_resultado), ...])

Trocar de provedor significa reescrever apenas este arquivo.

Provedores disponíveis (variável PROVEDOR no .env):
    anthropic      chamadas reais à Anthropic (precisa de ANTHROPIC_API_KEY)
    openai_compat  qualquer API compatível com a da OpenAI: OpenRouter, Gemini, OpenAI.
                   Precisa de BASE_URL e API_KEY. No OpenRouter, o mesmo endpoint serve
                   Claude, GPT, Qwen, DeepSeek...: troca-se só a variável MODELO.
    fake           respostas simuladas, sem custo. Serve só para testar a instalação.

O histórico da conversa fica sempre no formato da Anthropic (blocos tool_use e
tool_result). O adaptador openai_compat traduz na ida e na volta, então o resto do
projeto não sabe qual provedor está por trás.

Replay (a partir do Encontro 4)
    replay(arquivo, "gravar")  cada resposta nova do modelo é guardada no arquivo
    replay(arquivo, "usar")    a mesma pergunta, com o mesmo histórico e as mesmas
                               ferramentas, devolve a resposta guardada, sem chamar a
                               API e sem custo. O placar mostra os tokens e o custo que
                               a chamada teve quando foi gravada.
    replay(None)               desliga

Assim a turma roda o hands-on sem chave: o professor grava uma vez, todos reproduzem.

Amostras (a partir do Encontro 5)
    amostra(n)   a mesma chamada, repetida, dá respostas diferentes: o modelo não é
                 determinístico. Para gravar a variação, cada repetição recebe um número
                 de amostra, que entra na impressão digital da chamada. amostra(0), o
                 padrão, deixa a impressão digital igual à dos Encontros 1 a 4.
"""
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from comum import medidor

PROVEDOR = os.getenv("PROVEDOR", "anthropic").strip().lower()
MODELO = os.getenv("MODELO", "claude-haiku-4-5-20251001").strip()


@dataclass
class Chamada:
    """Um pedido do modelo para usar uma ferramenta."""
    id: str
    nome: str
    args: dict


@dataclass
class Resposta:
    texto: str        # o que o modelo escreveu
    chamadas: list    # ferramentas que o modelo pediu para usar (lista de Chamada)
    conteudo: list    # a resposta no formato do provedor, para voltar ao histórico


class RespostaNaoGravada(RuntimeError):
    """No modo replay "usar", a chamada não está na gravação e não há chave para chamar a API."""


# ---------------------------------------------------------------- interface

def chamar(mensagens: list, sistema: str = "", ferramentas: list | None = None,
           max_tokens: int = 1024, exigir_ferramenta: bool | str = False) -> Resposta:
    """Envia a conversa ao modelo e devolve a resposta.

    ferramentas: lista de dicts no formato neutro do projeto:
        {"nome": ..., "descricao": ..., "parametros": <JSON Schema>}
    exigir_ferramenta: False (o modelo escolhe entre texto e ferramenta), True (precisa
        chamar alguma ferramenta) ou o nome de uma ferramenta (precisa chamar essa).
        É o tool_choice da API: a garantia vem do provedor, não de uma frase no prompt.
    """
    if exigir_ferramenta and not ferramentas:
        raise ValueError("exigir_ferramenta precisa de ferramentas")

    chave = None
    if _replay["modo"]:
        chave = _chave(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta)
        gravada = _replay["respostas"].get(chave)
        if gravada is not None:
            _replay["reproduzidas"] += 1
            uso = gravada["uso"]
            medidor.registrar(uso["entrada"], uso["saida"], uso["segundos"])
            return _resposta_de_dict(gravada["resposta"])
        _replay["faltando"] += 1
        if _replay["modo"] == "usar" and not tem_credencial():
            raise RespostaNaoGravada(
                "Esta chamada não está na gravação, e não há chave de API configurada para fazê-la ao vivo.\n"
                "Isso acontece quando você muda algo que o modelo lê (um prompt, a descrição de um "
                "especialista, uma pergunta nova) ou escolhe uma opção fora do menu do notebook.\n"
                "Volte a configuração para uma das opções do menu, ou configure a chave (README do encontro).")

    antes = (medidor.atual().tokens_entrada, medidor.atual().tokens_saida, medidor.atual().segundos_no_modelo)
    resposta = _chamar_provedor(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta)

    if _replay["modo"] == "gravar":
        depois = medidor.atual()
        uso = {"entrada": depois.tokens_entrada - antes[0], "saida": depois.tokens_saida - antes[1],
               "segundos": round(depois.segundos_no_modelo - antes[2], 3)}
        registro = {"chave": chave, "resposta": _resposta_para_dict(resposta), "uso": uso}
        _replay["respostas"][chave] = registro
        with open(_replay["arquivo"], "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        _replay["gravadas"] += 1
    return resposta


def mensagem_do_usuario(texto: str) -> dict:
    return {"role": "user", "content": texto}


def mensagem_do_assistente(resposta: Resposta) -> dict:
    return {"role": "assistant", "content": resposta.conteudo}


def mensagem_de_resultados(pares: list) -> dict:
    """Devolve ao modelo o resultado de cada ferramenta que ele pediu."""
    return {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": chamada.id, "content": texto}
            for chamada, texto in pares
        ],
    }


def tem_credencial() -> bool:
    """Há como chamar a API de verdade com a configuração atual?"""
    if PROVEDOR == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY", "").strip().startswith("sk-")
    if PROVEDOR == "openai_compat":
        return bool(os.getenv("BASE_URL", "").strip() and os.getenv("API_KEY", "").strip())
    return PROVEDOR == "fake"


def _chamar_provedor(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta) -> Resposta:
    if PROVEDOR == "anthropic":
        return _chamar_anthropic(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta)
    if PROVEDOR == "openai_compat":
        return _chamar_openai_compat(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta)
    if PROVEDOR == "fake":
        return _chamar_fake(mensagens, sistema, ferramentas, exigir_ferramenta)
    raise ValueError(f"PROVEDOR desconhecido no .env: '{PROVEDOR}'. Use 'anthropic', 'openai_compat' ou 'fake'.")


# ---------------------------------------------------------------- replay

_replay = {"modo": None, "arquivo": None, "respostas": {}, "cabecalho": {},
           "reproduzidas": 0, "faltando": 0, "gravadas": 0, "amostra": 0}
_lidos: dict = {}      # gravações já lidas no modo "usar": trocar de gravação não relê o arquivo


def amostra(n: int = 0) -> None:
    """Escolhe a repetição: amostra(3) grava ou reproduz a 4ª resposta para a mesma chamada."""
    _replay["amostra"] = int(n)


def replay(arquivo: str | Path | None, modo: str = "usar") -> dict:
    """Liga o replay. modo "usar" reproduz; "gravar" reproduz o que já existe e grava o que falta.

    No modo "usar", o preço por token do placar passa a ser o da gravação, para que o custo
    mostrado seja o que a chamada custou de verdade, com o modelo que a respondeu.
    Devolve o cabeçalho da gravação (provedor, modelo, preços, data).
    """
    _replay.update(modo=None, arquivo=None, respostas={}, cabecalho={}, reproduzidas=0, faltando=0, gravadas=0)
    if arquivo is None:
        return {}
    if modo not in ("usar", "gravar"):
        raise ValueError('modo deve ser "usar" ou "gravar"')
    arquivo = Path(arquivo)
    cabecalho = {}
    marca = (str(arquivo.resolve()), arquivo.stat().st_mtime_ns, arquivo.stat().st_size) if arquivo.exists() else None
    if modo == "usar" and marca and marca in _lidos:
        cabecalho, respostas = _lidos[marca]
        _replay["respostas"] = dict(respostas)
    elif arquivo.exists():
        with open(arquivo, encoding="utf-8") as f:
            for linha in f:
                if not linha.strip():
                    continue
                dado = json.loads(linha)
                if "_cabecalho" in dado:
                    cabecalho = dado["_cabecalho"]
                else:
                    _replay["respostas"][dado["chave"]] = dado
        if modo == "usar":
            _lidos[marca] = (cabecalho, dict(_replay["respostas"]))
    if modo == "usar":
        if not arquivo.exists():
            raise FileNotFoundError(f"Gravação não encontrada: {arquivo}. O professor precisa rodar o gravar_replay.py.")
        if cabecalho:
            medidor.PRECO_ENTRADA = cabecalho.get("preco_entrada", medidor.PRECO_ENTRADA)
            medidor.PRECO_SAIDA = cabecalho.get("preco_saida", medidor.PRECO_SAIDA)
    else:
        if cabecalho and (cabecalho.get("modelo"), cabecalho.get("provedor")) != (MODELO, PROVEDOR):
            raise ValueError(f"{arquivo.name} foi gravado com {cabecalho.get('modelo')} ({cabecalho.get('provedor')}) "
                             f"e o .env está com {MODELO} ({PROVEDOR}). Não misture modelos numa gravação: "
                             "use outro arquivo ou apague este.")
        if not cabecalho:
            cabecalho = {"provedor": PROVEDOR, "modelo": MODELO, "preco_entrada": medidor.PRECO_ENTRADA,
                         "preco_saida": medidor.PRECO_SAIDA, "temperatura": os.getenv("TEMPERATURA", ""),
                         "criado_em": time.strftime("%Y-%m-%d %H:%M")}
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(json.dumps({"_cabecalho": cabecalho}, ensure_ascii=False) + "\n")
    _replay.update(modo=modo, arquivo=arquivo, cabecalho=cabecalho)
    return cabecalho


def estado_replay() -> dict:
    """Quantas chamadas vieram da gravação, quantas faltaram e quantas foram gravadas agora."""
    return {k: _replay[k] for k in ("modo", "reproduzidas", "faltando", "gravadas")} | \
           {"respostas_no_arquivo": len(_replay["respostas"]), "modelo": _replay["cabecalho"].get("modelo")}


def _chave(mensagens, sistema, ferramentas, max_tokens, exigir) -> str:
    """Impressão digital da chamada: tudo o que o modelo lê, menos o nome do modelo."""
    pedido = {"m": mensagens, "s": sistema, "f": ferramentas or [], "t": max_tokens, "e": exigir}
    if _replay["amostra"]:
        pedido["a"] = _replay["amostra"]
    bruto = json.dumps(pedido, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(bruto.encode()).hexdigest()[:32]


def _resposta_para_dict(r: Resposta) -> dict:
    return {"texto": r.texto, "chamadas": [{"id": c.id, "nome": c.nome, "args": c.args} for c in r.chamadas],
            "conteudo": r.conteudo}


def _resposta_de_dict(d: dict) -> Resposta:
    return Resposta(d["texto"], [Chamada(c["id"], c["nome"], c["args"]) for c in d["chamadas"]], d["conteudo"])


# ---------------------------------------------------------------- anthropic

_cliente = None


def _chamar_anthropic(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta=False) -> Resposta:
    global _cliente
    import anthropic

    if _cliente is None:
        _cliente = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente

    pedido = {"model": MODELO, "max_tokens": max_tokens, "messages": mensagens}
    if sistema:
        pedido["system"] = sistema
    if ferramentas:
        pedido["tools"] = [
            {"name": f["nome"], "description": f["descricao"], "input_schema": f["parametros"]}
            for f in ferramentas
        ]
        if exigir_ferramenta is True:
            pedido["tool_choice"] = {"type": "any"}
        elif exigir_ferramenta:
            pedido["tool_choice"] = {"type": "tool", "name": exigir_ferramenta}
    if os.getenv("TEMPERATURA"):
        pedido["temperature"] = float(os.environ["TEMPERATURA"])

    inicio = time.perf_counter()
    r = _cliente.messages.create(**pedido)
    medidor.registrar(r.usage.input_tokens, r.usage.output_tokens, time.perf_counter() - inicio)

    texto, chamadas, conteudo = [], [], []
    for bloco in r.content:
        if bloco.type == "text":
            texto.append(bloco.text)
            conteudo.append({"type": "text", "text": bloco.text})
        elif bloco.type == "tool_use":
            chamadas.append(Chamada(bloco.id, bloco.name, dict(bloco.input)))
            conteudo.append({"type": "tool_use", "id": bloco.id, "name": bloco.name,
                             "input": dict(bloco.input)})
    return Resposta("".join(texto), chamadas, conteudo)


# ---------------------------------------------------------------- openai_compat

def _para_openai(mensagens: list, sistema: str) -> list:
    """Histórico no formato da Anthropic -> formato de chat da OpenAI."""
    saida = [{"role": "system", "content": sistema}] if sistema else []
    for m in mensagens:
        if isinstance(m["content"], str):
            saida.append({"role": m["role"], "content": m["content"]})
            continue
        if m["role"] == "assistant":
            texto = "".join(b["text"] for b in m["content"] if b.get("type") == "text")
            chamadas = [{"id": b["id"], "type": "function",
                         "function": {"name": b["name"], "arguments": json.dumps(b["input"], ensure_ascii=False)}}
                        for b in m["content"] if b.get("type") == "tool_use"]
            msg = {"role": "assistant", "content": texto or None}
            if chamadas:
                msg["tool_calls"] = chamadas
            saida.append(msg)
        else:  # resultados de ferramenta: uma mensagem "tool" para cada um
            for b in m["content"]:
                if b.get("type") == "tool_result":
                    saida.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": str(b["content"])})
                elif b.get("type") == "text":
                    saida.append({"role": "user", "content": b["text"]})
    return saida


# Parâmetros extras do pedido, por modelo (ex.: {"reasoning_effort": "low"} para modelos de raciocínio).
EXTRA: dict = {}
# Modelos de raciocínio (GPT-5 em diante, série o) recusam max_tokens e pedem max_completion_tokens, que conta
# também os tokens de raciocínio. Descoberto na primeira recusa e lembrado por modelo.
_LIMITE_NOVO: set = set()
RESERVA_RACIOCINIO = int(os.getenv("RESERVA_RACIOCINIO", "4000"))


def _pedido_openai(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta=False) -> dict:
    pedido = {"model": MODELO, "messages": _para_openai(mensagens, sistema)}
    if MODELO in _LIMITE_NOVO:
        pedido["max_completion_tokens"] = max_tokens + RESERVA_RACIOCINIO
    else:
        pedido["max_tokens"] = max_tokens
    if ferramentas:
        pedido["tools"] = [{"type": "function", "function": {"name": f["nome"], "description": f["descricao"],
                                                             "parameters": f["parametros"]}}
                           for f in ferramentas]
        if exigir_ferramenta is True:
            pedido["tool_choice"] = "required"
        elif exigir_ferramenta:
            pedido["tool_choice"] = {"type": "function", "function": {"name": exigir_ferramenta}}
    if os.getenv("TEMPERATURA"):
        pedido["temperature"] = float(os.environ["TEMPERATURA"])
    if "openrouter.ai" in os.getenv("BASE_URL", ""):
        # Só provedores que não guardam nem usam o conteúdo. Mude no .env por sua conta e risco.
        preferencias = {"data_collection": os.getenv("OPENROUTER_DATA_COLLECTION", "deny")}
        # O mesmo modelo é servido por vários provedores, com preços muito diferentes.
        # "price" escolhe o mais barato; deixe OPENROUTER_ORDENAR vazio para o roteamento padrão.
        ordenar = os.getenv("OPENROUTER_ORDENAR", "price").strip()
        if ordenar:
            preferencias["sort"] = ordenar
        if ferramentas:
            # Só provedores que aceitam tools e tool_choice: sem isso, um provedor barato pode
            # ignorar a ferramenta exigida e o agente quebra o contrato de saída.
            preferencias["require_parameters"] = True
        pedido["provider"] = preferencias
    pedido.update(EXTRA)
    return pedido


def _de_openai(dados: dict) -> Resposta:
    """Resposta no formato da OpenAI -> Resposta neutra, com 'conteudo' no formato da Anthropic."""
    msg = dados["choices"][0]["message"]
    texto = msg.get("content") or ""
    chamadas, conteudo = [], []
    if texto:
        conteudo.append({"type": "text", "text": texto})
    for c in msg.get("tool_calls") or []:
        try:
            args = json.loads(c["function"].get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {"_argumentos_invalidos": c["function"].get("arguments")}
        chamadas.append(Chamada(c["id"], c["function"]["name"], args))
        conteudo.append({"type": "tool_use", "id": c["id"], "name": c["function"]["name"], "input": args})
    return Resposta(texto, chamadas, conteudo)


def _chamar_openai_compat(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta=False) -> Resposta:
    import urllib.error
    import urllib.request

    base = os.getenv("BASE_URL", "").rstrip("/")
    chave = os.getenv("API_KEY", "").strip()
    if not base or not chave:
        raise RuntimeError("PROVEDOR=openai_compat precisa de BASE_URL e API_KEY no .env")
    corpo = json.dumps(_pedido_openai(mensagens, sistema, ferramentas, max_tokens, exigir_ferramenta)).encode()
    inicio = time.perf_counter()
    for tentativa in range(5):           # limite de taxa e instabilidade passageira: espera e tenta de novo
        pedido = urllib.request.Request(f"{base}/chat/completions", data=corpo, method="POST",
                                        headers={"Authorization": f"Bearer {chave}",
                                                 "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=120) as r:
                dados = json.loads(r.read().decode())
            if "choices" in dados:
                break
            erro = RuntimeError(f"{base} respondeu sem 'choices': {str(dados)[:500]}")
        except urllib.error.HTTPError as e:
            texto = e.read().decode()
            erro = RuntimeError(f"{base} respondeu {e.code}: {texto[:500]}")
            if e.code == 400 and "max_completion_tokens" in texto and MODELO not in _LIMITE_NOVO:
                _LIMITE_NOVO.add(MODELO)     # modelo de raciocínio: refaz o pedido com o parâmetro novo
                corpo = json.dumps(_pedido_openai(mensagens, sistema, ferramentas, max_tokens,
                                                  exigir_ferramenta)).encode()
                continue
            if e.code not in (429, 500, 502, 503, 504):
                raise erro from None
        except (urllib.error.URLError, TimeoutError) as e:
            erro = RuntimeError(f"sem resposta de {base}: {e}")
        time.sleep(2 * 2 ** tentativa)
    else:
        raise erro
    uso = dados.get("usage") or {}
    medidor.registrar(uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0), time.perf_counter() - inicio)
    return _de_openai(dados)


# ---------------------------------------------------------------- fake

def _texto_plano(sistema: str, mensagens: list) -> str:
    partes = [sistema]
    for m in mensagens:
        if isinstance(m["content"], str):
            partes.append(m["content"])
        else:
            for bloco in m["content"]:
                partes.append(str(bloco.get("text") or bloco.get("content") or bloco.get("input") or ""))
    return "\n".join(partes)


def _args_fake(ferramenta: dict, pergunta: str, ids: list) -> dict:
    """Preenche os parâmetros obrigatórios de uma ferramenta qualquer com valores plausíveis."""
    if ferramenta["nome"] == "responder":
        return {"desfecho": "responder", "fontes": ids[:1], "resposta": "(resposta simulada)"}
    schema = ferramenta.get("parametros") or {}
    args = {}
    for nome in schema.get("required", []):
        regra = schema.get("properties", {}).get(nome, {})
        if "enum" in regra:
            args[nome] = regra["enum"][0]
        elif regra.get("type") == "array":
            args[nome] = ids[:1]
        elif regra.get("type") in ("integer", "number"):
            args[nome] = regra.get("minimum", 1)
        else:
            args[nome] = pergunta[: regra.get("maxLength", 300)]
    return args


def _chamar_fake(mensagens, sistema, ferramentas, exigir_ferramenta=False) -> Resposta:
    """Simula o modelo sem chamar API nenhuma. Não mede nada real: só testa o encanamento."""
    texto_total = _texto_plano(sistema, mensagens)
    ids = re.findall(r'id="([a-z0-9-]+)"', texto_total) + re.findall(r'"id": "([a-z0-9-]+)"', texto_total)
    medidor.registrar(len(texto_total) // 4, 40, 0.01)

    if ferramentas:
        por_nome = {f["nome"]: f for f in ferramentas}
        ja_buscou = any(
            isinstance(m["content"], list) and any(b.get("type") == "tool_result" for b in m["content"])
            for m in mensagens
        )
        pergunta = mensagens[0]["content"] if isinstance(mensagens[0]["content"], str) else ""
        busca = next((n for n in por_nome if n.startswith(("buscar", "consultar"))), None)
        if isinstance(exigir_ferramenta, str):
            alvo = exigir_ferramenta
        elif busca and not ja_buscou:
            alvo = busca
        elif "responder" in por_nome:
            alvo = "responder"
        else:
            alvo = next(iter(por_nome))
        chamada = Chamada(f"fake-{len(mensagens)}", alvo, _args_fake(por_nome[alvo], pergunta, ids))
        conteudo = [{"type": "tool_use", "id": chamada.id, "name": chamada.nome, "input": chamada.args}]
        return Resposta("", [chamada], conteudo)

    if not ids:  # sem documentos no contexto: provavelmente é o classificador
        return Resposta("rh", [], [{"type": "text", "text": "rh"}])

    texto = '{"desfecho": "responder", "fontes": ["%s"], "resposta": "(resposta simulada)"}' % ids[0]
    return Resposta(texto, [], [{"type": "text", "text": texto}])