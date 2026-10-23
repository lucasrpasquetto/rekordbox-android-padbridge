r"""
PadBridge - ponte entre o tablet e o Rekordbox.

Faz tudo em um programa so:
  - serve a tela do tablet (http://localhost:8765);
  - converte os toques em MIDI para uma porta virtual do loopMIDI (que o Rekordbox ve como um controlador);
  - devolve ao tablet o estado que o Rekordbox manda (stems);
  - roda 'adb reverse' sozinho quando o tablet e plugado por USB;
  - fica na bandeja do Windows (verde = tablet conectado, amarelo = esperando o tablet, vermelho = problema).

Uso:
    python -m padbridge                    (bandeja, sem janela)
    python -m padbridge --console          (sem bandeja: roda no terminal)
    python -m padbridge --console --debug  (mostra todo MIDI enviado e recebido)
    opcoes: --porta TRECHO  --http 8765  --wifi  --adb CAMINHO

Arquivos ao lado do programa (opcionais):
  index.html          se existir, e esta tela que e servida (da para atualizar a tela sem gerar o .exe de novo)
  padbridge_config.json   opcoes (criado na primeira vez)
  padbridge.log           registro do que aconteceu
"""
import asyncio
import collections
import ctypes
import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser

CREATE_NO_WINDOW = 0x08000000
NOME_APP = "PadBridge"
CONFIG_PADRAO = {
    "porta_midi": "PadBridge",  # trecho do nome da porta do loopMIDI
    "http": 8765,
    "wifi": False,            # True = aceita conexoes da rede (alem do USB)
    "adb": "",                # caminho do adb.exe (vazio = procurar sozinho)
    "feedback": True,         # False = nao abre a entrada MIDI (sem estado dos stems vindo do Rekordbox)
    "usar_adb": True,         # roda 'adb reverse' automaticamente
}


# ----------------------------------------------------------------------------- pastas / config / log
def pasta_programa():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def caminho_html():
    """index.html ao lado do programa tem prioridade; senao usa o que veio junto (padbridge/web/index.html ou embutido no .exe)."""
    ao_lado = os.path.join(pasta_programa(), "index.html")
    if os.path.isfile(ao_lado):
        return ao_lado
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    embutido = os.path.join(base, "web", "index.html")
    if os.path.isfile(embutido):
        return embutido
    alt = os.path.join(base, "padbridge", "web", "index.html")
    return alt if os.path.isfile(alt) else None


def carregar_config(pasta):
    caminho = os.path.join(pasta, "padbridge_config.json")
    cfg = dict(CONFIG_PADRAO)
    try:
        with open(caminho, encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in CONFIG_PADRAO})
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        logging.exception("padbridge_config.json invalido: usando os valores padrao")
    if not os.path.exists(caminho):  # cria so na primeira vez (nunca sobrescreve o que voce editou)
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except OSError:
            pass
    return cfg


def preparar_log(pasta):
    h = logging.handlers.RotatingFileHandler(os.path.join(pasta, "padbridge.log"), maxBytes=300_000, backupCount=1, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(h)


# ----------------------------------------------------------------------------- adb
def procurar_adb(configurado=""):
    candidatos = []
    if configurado:
        candidatos.append(configurado)
    achado = shutil.which("adb")
    if achado:
        candidatos.append(achado)
    local = os.environ.get("LOCALAPPDATA", "")
    home = os.path.expanduser("~")
    candidatos += [
        os.path.join(local, "Android", "Sdk", "platform-tools", "adb.exe"),
        os.path.join(home, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
        r"C:\platform-tools\adb.exe",
        r"C:\adb\adb.exe",
        r"C:\Program Files\platform-tools\adb.exe",
        r"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe",
        os.path.join(home, "platform-tools", "adb.exe"),
        os.path.join(home, "Downloads", "platform-tools", "adb.exe"),
        os.path.join(pasta_programa(), "platform-tools", "adb.exe"),
        os.path.join(pasta_programa(), "adb.exe"),
    ]
    for c in candidatos:
        if c and os.path.isfile(c):
            return c
    return None


def interpretar_adb_devices(texto):
    """Devolve os numeros de serie dos aparelhos prontos ('device'), ignorando 'unauthorized' e 'offline'."""
    prontos = []
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[1] == "device":
            prontos.append(partes[0])
    return prontos


def rodar_adb(adb, *args, tempo=8):
    r = subprocess.run([adb, *args], capture_output=True, text=True, timeout=tempo, creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ----------------------------------------------------------------------------- estado compartilhado
class Estado:
    def __init__(self):
        self.midi = "procurando o loopMIDI..."
        self.midi_ok = False
        self.http_erro = ""
        self.adb = "iniciando..."
        self.ultimo_rb = ""
        self.debug = False
        self.clientes = set()
        self.loop = None
        self.saida = None
        self.entrada = None
        self.recentes = collections.deque(maxlen=256)
        self.cache_rb = {}      # (canal, nota) -> ultima velocidade vinda do Rekordbox; reenviado ao tablet quando ele conecta
        self.parar = threading.Event()
        self.forcar_adb = threading.Event()
        self.trava = threading.Lock()

    def n_tablets(self):
        return len(self.clientes)

    def cor(self):
        if self.http_erro or not self.midi_ok:
            return "vermelho"
        return "verde" if self.n_tablets() else "amarelo"


estado = Estado()


# ----------------------------------------------------------------------------- MIDI
def _achar(nomes, trecho):
    for n in nomes:
        if trecho.lower() in n.lower():
            return n
    return None


def enviar_midi(tipo, ch, a, b):
    """tipo: on | rel | off | cc. 'rel' = note_on com velocidade 0 (padrao Pioneer)."""
    import mido
    with estado.trava:
        saida = estado.saida
        if saida is None:
            return False
        if tipo == "on":
            m = mido.Message("note_on", channel=ch, note=a, velocity=max(1, b))
        elif tipo == "rel":
            m = mido.Message("note_on", channel=ch, note=a, velocity=0)
        elif tipo == "off":
            m = mido.Message("note_off", channel=ch, note=a, velocity=0)
        elif tipo == "cc":
            m = mido.Message("control_change", channel=ch, control=a, value=b)
        else:
            return False
        saida.send(m)
        estado.recentes.append((time.time(), m.bytes()))
        if estado.debug:
            logging.info('[enviado ] %s', ' '.join(f'{x:02X}' for x in m.bytes()))
    return True


def avisar_tablets(texto):
    lp = estado.loop
    if lp is None:
        return
    def enviar():
        for c in list(estado.clientes):
            asyncio.ensure_future(c.send_str(texto))
    lp.call_soon_threadsafe(enviar)


def ao_chegar_midi(msg):
    """Chega do Rekordbox pela porta virtual. O que nao foi enviado por nos e estado do Rekordbox."""
    b = msg.bytes()
    agora = time.time()
    eco = any(b == x and agora - t < 1.0 for t, x in list(estado.recentes))
    if estado.debug:
        logging.info('[chegou  ] %s  %s', ' '.join(f'{x:02X}' for x in b), '(eco do que enviamos)' if eco else '<<< vem do Rekordbox >>>')
    if eco:
        return  # eco do que nos mesmos enviamos
    if msg.type in ("note_on", "note_off"):
        vel = msg.velocity if msg.type == "note_on" else 0
        estado.ultimo_rb = f"{msg.channel},{msg.note},{vel}"
        if estado.cache_rb.get((msg.channel, msg.note)) != vel:   # registra so quando muda
            logging.info('Rekordbox -> canal %d nota 0x%02X vel %d', msg.channel, msg.note, vel)
        estado.cache_rb[(msg.channel, msg.note)] = vel
        avisar_tablets(f"st,{msg.channel},{msg.note},{vel}")
    elif msg.type == "control_change":
        avisar_tablets(f"sc,{msg.channel},{msg.control},{msg.value}")


def fechar_portas():
    with estado.trava:
        for p in (estado.entrada, estado.saida):
            try:
                if p is not None:
                    p.close()
            except Exception:
                pass
        estado.entrada = estado.saida = None
        estado.midi_ok = False


def thread_midi(cfg):
    import mido
    try:
        mido.set_backend("mido.backends.rtmidi")
    except Exception:
        logging.exception("backend rtmidi indisponivel")
    trecho = cfg["porta_midi"]
    while not estado.parar.is_set():
        try:
            if estado.saida is None:
                n_out = _achar(mido.get_output_names(), trecho)
                if not n_out:
                    estado.midi_ok = False
                    estado.midi = f'abra o loopMIDI e crie a porta "{trecho}..."'
                else:
                    n_in = _achar(mido.get_input_names(), trecho) if cfg.get("feedback", True) else None
                    with estado.trava:
                        estado.saida = mido.open_output(n_out)
                        estado.entrada = mido.open_input(n_in, callback=ao_chegar_midi) if n_in else None
                    estado.midi_ok = True
                    estado.midi = f"ligado em {n_out}"
                    logging.info("MIDI aberto: saida=%s entrada=%s", n_out, n_in)
                    logging.info("portas de saida do Windows: %s", mido.get_output_names())
                    logging.info("portas de entrada do Windows: %s", mido.get_input_names())
            else:
                # a porta sumiu (loopMIDI fechado)? entao solta e volta a procurar
                if not _achar(mido.get_output_names(), trecho):
                    logging.warning("porta MIDI sumiu")
                    fechar_portas()
                    estado.midi = f'a porta "{trecho}" sumiu: abra o loopMIDI'
        except Exception as e:  # noqa: BLE001
            logging.exception("erro no MIDI")
            fechar_portas()
            estado.midi = f"erro: {e}"
        estado.parar.wait(2.0)
    fechar_portas()


# ----------------------------------------------------------------------------- servidor web (tela + websocket)
def thread_servidor(cfg):
    from aiohttp import WSMsgType, web

    async def pagina(request):
        caminho = caminho_html()
        if not caminho:
            return web.Response(status=404, text="index.html nao encontrado.")
        return web.FileResponse(caminho, headers={"Cache-Control": "no-store"})

    async def ws(request):
        w = web.WebSocketResponse(heartbeat=15)
        await w.prepare(request)
        estado.clientes.add(w)
        logging.info("tablet conectado (%d)", len(estado.clientes))
        for (c_, n_), v_ in list(estado.cache_rb.items()):   # estado atual do Rekordbox para quem acabou de conectar
            await w.send_str(f"st,{c_},{n_},{v_}")
        ativas = set()  # notas seguradas: soltas se a conexao cair
        try:
            async for msg in w:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    tipo, ch, a, b = msg.data.split(",")
                    ch, a, b = int(ch), int(a), int(b)
                except ValueError:
                    continue
                if tipo == "lib":
                    ativas.discard((ch, a))
                    continue
                try:
                    enviar_midi(tipo, ch, a, b)
                except Exception:  # noqa: BLE001
                    logging.exception("falha ao enviar MIDI")
                    continue
                if tipo == "on":
                    ativas.add((ch, a))
                elif tipo in ("rel", "off"):
                    ativas.discard((ch, a))
        finally:
            estado.clientes.discard(w)
            logging.info("tablet desconectado (%d)", len(estado.clientes))
            for ch, a in ativas:
                try:
                    enviar_midi("rel", ch, a, 0)
                except Exception:  # noqa: BLE001
                    pass
        return w

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    estado.loop = loop
    app = web.Application()
    app.router.add_get("/", pagina)
    app.router.add_get("/ws", ws)
    runner = web.AppRunner(app)
    try:
        loop.run_until_complete(runner.setup())
        host = "0.0.0.0" if cfg["wifi"] else "127.0.0.1"
        loop.run_until_complete(web.TCPSite(runner, host, int(cfg["http"])).start())
        logging.info("servidor em %s:%s", host, cfg["http"])
    except OSError as e:
        estado.http_erro = f"porta {cfg['http']} ocupada ({e.strerror or e})"
        logging.exception("servidor nao iniciou")
        return
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(runner.cleanup())


# ----------------------------------------------------------------------------- adb reverse automatico
PORTAS_EXTRA = []   # outras portas que tambem precisam do 'adb reverse' (o v2 acrescenta a dele)


def thread_adb(cfg):
    if not cfg["usar_adb"]:
        estado.adb = "desligado na configuracao"
        return
    ja = set()           # (aparelho, porta) com reverse feito
    servidor_adb = None  # caminho do adb para o qual ja rodamos 'start-server'
    ultimo_txt, falhas = None, 0
    while not estado.parar.is_set():
        try:
            portas = [f"tcp:{int(cfg['http'])}"] + [f"tcp:{int(p)}" for p in PORTAS_EXTRA]
            adb = procurar_adb(cfg["adb"])
            if not adb:
                estado.adb = 'adb.exe nao encontrado (indique o caminho em padbridge_config.json, campo "adb")'
            else:
                if servidor_adb != adb:
                    # o daemon do adb herda os pipes e travaria a leitura: sobe-o sem capturar a saida
                    subprocess.run([adb, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                                   creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
                    servidor_adb = adb
                _, saida = rodar_adb(adb, "devices", tempo=15)
                falhas = 0
                resumo = " | ".join(l.strip() for l in saida.splitlines()[1:] if l.strip())
                if resumo != ultimo_txt:                   # so registra quando algo muda
                    logging.info("adb devices: %s", resumo or "(nenhum)")
                    ultimo_txt = resumo
                aparelhos = interpretar_adb_devices(saida)
                ja = {(s_, p_) for (s_, p_) in ja if s_ in aparelhos}
                for s_ in aparelhos:
                    _, lista = rodar_adb(adb, "-s", s_, "reverse", "--list")
                    for porta in portas:
                        if porta in lista and (s_, porta) in ja:
                            continue
                        cod, txt = rodar_adb(adb, "-s", s_, "reverse", porta, porta)
                        if cod == 0:
                            logging.info("adb reverse ok: %s %s", s_, porta)
                            ja.add((s_, porta))
                        else:
                            logging.warning("adb reverse falhou (%s %s): %s", s_, porta, txt.strip())
                estado.adb = f"{len(aparelhos)} tablet(s) por USB" if aparelhos else "nenhum tablet por USB (ative a depuracao USB)"
        except Exception as e:  # noqa: BLE001
            falhas += 1
            logging.exception("erro no adb")
            estado.adb = f"erro no adb: {e}"
            if falhas >= 2 and servidor_adb:     # adb travado (acontece depois de desligar o cabo): reinicia o servidor dele
                try:
                    subprocess.run([servidor_adb, "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
                                   creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
                except Exception:  # noqa: BLE001
                    pass
                servidor_adb, ja, falhas = None, set(), 0
        estado.forcar_adb.wait(3.0)
        estado.forcar_adb.clear()


# ----------------------------------------------------------------------------- iniciar com o Windows
CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def comando_inicio():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw if os.path.isfile(pyw) else sys.executable}" "{os.path.abspath(__file__)}"'


def inicio_ativo():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN) as k:
            return winreg.QueryValueEx(k, "PadBridge")[0] == comando_inicio()
    except Exception:
        return False


def alternar_inicio():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN, 0, winreg.KEY_SET_VALUE) as k:
            if inicio_ativo():
                winreg.DeleteValue(k, "PadBridge")
            else:
                winreg.SetValueEx(k, "PadBridge", 0, winreg.REG_SZ, comando_inicio())
    except Exception:
        logging.exception("nao consegui mudar 'iniciar com o Windows'")


# ----------------------------------------------------------------------------- bandeja
CORES = {"verde": (46, 204, 113), "amarelo": (241, 196, 15), "vermelho": (231, 76, 60)}


def desenhar_icone(cor):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(28, 30, 38, 255))
    for i in range(3):
        for j in range(3):
            d.rounded_rectangle((10 + i * 15, 10 + j * 15, 20 + i * 15, 20 + j * 15), radius=2, fill=(70, 74, 92, 255))
    d.ellipse((38, 38, 60, 60), fill=CORES[cor] + (255,), outline=(255, 255, 255, 255), width=2)
    return img


def rodar_bandeja(cfg):
    import pystray
    url = f"http://localhost:{cfg['http']}"

    def status_midi(_): return f"MIDI: {estado.midi}"
    def status_tablet(_): return f"Tablet: {estado.n_tablets()} conectado(s)" if estado.n_tablets() else "Tablet: aguardando conexao"
    def status_usb(_): return f"USB: {estado.adb}"
    def status_http(_): return f"Servidor: {estado.http_erro}" if estado.http_erro else f"Servidor: {url}"
    def status_rb(_): return f"Ultimo estado do Rekordbox: {estado.ultimo_rb or '-'}"

    def sair(icone, _item=None):
        estado.parar.set()
        estado.forcar_adb.set()
        if estado.loop is not None:
            estado.loop.call_soon_threadsafe(estado.loop.stop)
        icone.stop()

    menu = pystray.Menu(
        pystray.MenuItem(status_midi, None, enabled=False),
        pystray.MenuItem(status_tablet, None, enabled=False),
        pystray.MenuItem(status_usb, None, enabled=False),
        pystray.MenuItem(status_http, None, enabled=False),
        pystray.MenuItem(status_rb, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Reconectar o tablet agora (USB)", lambda i, it: estado.forcar_adb.set()),
        pystray.MenuItem("Abrir a tela no navegador (teste)", lambda i, it: webbrowser.open(url)),
        pystray.MenuItem("Iniciar com o Windows", lambda i, it: alternar_inicio(), checked=lambda it: inicio_ativo()),
        pystray.MenuItem("Abrir a pasta do programa", lambda i, it: os.startfile(pasta_programa())),
        pystray.MenuItem("Ver o registro (log)", lambda i, it: os.startfile(os.path.join(pasta_programa(), "padbridge.log"))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", sair),
    )
    icone = pystray.Icon("PadBridge", desenhar_icone("amarelo"), NOME_APP, menu)

    def atualizar():
        ultima = None
        while not estado.parar.is_set():
            cor = estado.cor()
            if cor != ultima:
                icone.icon = desenhar_icone(cor)
                ultima = cor
            icone.title = f"{NOME_APP}: {estado.midi if not estado.midi_ok else ('tablet conectado' if estado.n_tablets() else 'aguardando o tablet')}"
            try:
                icone.update_menu()
            except Exception:
                pass
            estado.parar.wait(1.5)

    threading.Thread(target=atualizar, daemon=True).start()
    icone.run()


# ----------------------------------------------------------------------------- instancia unica
def ja_esta_rodando():
    if os.name != "nt":
        return False
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\PadBridge")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def aviso(texto):
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, texto, NOME_APP, 0x40)
    else:
        print(texto)


def ler_argumentos(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="padbridge", description="Tablet como gadget de pads para o Rekordbox.")
    ap.add_argument("--console", action="store_true", help="roda no terminal, sem icone na bandeja")
    ap.add_argument("--debug", action="store_true", help="mostra todo o MIDI enviado e recebido (use com --console)")
    ap.add_argument("--porta", help='trecho do nome da porta do loopMIDI (padrao: "PadBridge")')
    ap.add_argument("--http", type=int, help="porta do servidor (padrao: 8765)")
    ap.add_argument("--wifi", action="store_true", help="aceita conexoes da rede, alem do USB")
    ap.add_argument("--adb", help="caminho do adb.exe")
    ap.add_argument("--sem-feedback", action="store_true", help="nao escuta o MIDI vindo do Rekordbox (diagnostico)")
    ap.add_argument("--sem-adb", action="store_true", help="nao rodar o 'adb reverse' automaticamente")
    return ap.parse_args(argv)


def aplicar_argumentos(cfg, args):
    if args.porta:
        cfg["porta_midi"] = args.porta
    if args.http:
        cfg["http"] = args.http
    if args.wifi:
        cfg["wifi"] = True
    if args.adb:
        cfg["adb"] = args.adb
    if args.sem_adb:
        cfg["usar_adb"] = False
    if args.sem_feedback:
        cfg["feedback"] = False
    return cfg


def main(argv=None):
    args = ler_argumentos(argv)
    pasta = pasta_programa()
    preparar_log(pasta)
    if args.console:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(h)
    if ja_esta_rodando():
        aviso("O PadBridge ja esta rodando (procure o icone ao lado do relogio).")
        return
    cfg = aplicar_argumentos(carregar_config(pasta), args)
    estado.debug = args.debug
    logging.info("iniciando; pasta=%s tela=%s", pasta, caminho_html())
    if not caminho_html():
        aviso("Nao achei a tela (index.html). Rode  python tools/gerar.py  ou coloque o index.html ao lado do programa.")
    for alvo in (thread_midi, thread_servidor, thread_adb):
        threading.Thread(target=alvo, args=(cfg,), daemon=True).start()
    if args.console:
        print(f"PadBridge no terminal. Tela: http://localhost:{cfg['http']}  (Ctrl+C para sair)")
        try:
            while True:
                time.sleep(1)
                if estado.http_erro:
                    print("ERRO:", estado.http_erro)
                    break
        except KeyboardInterrupt:
            pass
        finally:
            estado.parar.set()
            estado.forcar_adb.set()
        return
    try:
        rodar_bandeja(cfg)
    except Exception:  # noqa: BLE001
        logging.exception("erro na bandeja")
        aviso("Erro ao criar o icone da bandeja. Veja padbridge.log.")
    estado.parar.set()


if __name__ == "__main__":
    main()
