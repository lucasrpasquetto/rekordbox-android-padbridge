"""Teste da logica do servico (sem precisar de MIDI, rede ou bandeja). Rode:  python tests/test_servico.py"""
import os, sys, tempfile, asyncio, types, importlib.util, time
spec = importlib.util.spec_from_file_location("sv", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "padbridge", "app.py"))
sv = importlib.util.module_from_spec(spec); spec.loader.exec_module(sv)
falhas = []
def ok(c, m):
    if not c: falhas.append(m); print("FALHA:", m)
# adb devices
txt = "List of devices attached\nR58N123\tdevice\nABC\tunauthorized\nXYZ\toffline\n192.168.0.5:5555\tdevice\n\n"
ok(sv.interpretar_adb_devices(txt) == ["R58N123", "192.168.0.5:5555"], f"adb devices: {sv.interpretar_adb_devices(txt)}")
ok(sv.interpretar_adb_devices("* daemon not running; starting now\n* daemon started successfully\nList of devices attached\n") == [], "adb sem aparelhos")
# procurar adb
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "adb.exe"); open(f, "w").write("x")
    ok(sv.procurar_adb(f) == f, "adb configurado")
    sv.procurar_adb(os.path.join(d, "nao.exe"))  # adb inexistente nao pode quebrar
# config
with tempfile.TemporaryDirectory() as d:
    c = sv.carregar_config(d); ok(c == sv.CONFIG_PADRAO and os.path.isfile(os.path.join(d, "padbridge_config.json")), "config padrao criada")
    open(os.path.join(d, "padbridge_config.json"), "w").write('{"http": 9000, "lixo": 1}')
    c = sv.carregar_config(d); ok(c["http"] == 9000 and "lixo" not in c and c["porta_midi"] == "PadBridge", f"config mesclada: {c}")
    open(os.path.join(d, "padbridge_config.json"), "w").write('{quebrado')
    c = sv.carregar_config(d); ok(c == sv.CONFIG_PADRAO, "config invalida cai no padrao")
# html: ao lado tem prioridade
with tempfile.TemporaryDirectory() as d:
    sv.pasta_programa = lambda: d
    ok(sv.caminho_html() is None or sv.caminho_html().endswith("index.html"), "sem html ao lado: usa o do pacote (ou nenhum)")
    open(os.path.join(d, "index.html"), "w").write("<html>")
    ok(sv.caminho_html() == os.path.join(d, "index.html"), "html ao lado do programa")
# cor do icone
e = sv.Estado(); ok(e.cor() == "vermelho", "sem MIDI = vermelho")
e.midi_ok = True; ok(e.cor() == "amarelo", "MIDI ok sem tablet = amarelo")
e.clientes.add(object()); ok(e.cor() == "verde", "com tablet = verde")
e.http_erro = "x"; ok(e.cor() == "vermelho", "erro http = vermelho")
# eco x estado do Rekordbox
class M:
    def __init__(s, t, **k): s.type = t; s.__dict__.update(k)
    def bytes(s): return [0x90 | s.channel, s.note, s.velocity]
enviados = []
class Loop:
    def call_soon_threadsafe(s, fn): enviados.append(fn)
sv.estado = sv.Estado(); sv.estado.loop = Loop()
sv.estado.recentes.append((time.time(), [0x97, 16, 127]))
sv.ao_chegar_midi(M("note_on", channel=7, note=16, velocity=127)); ok(not enviados, "eco nosso deve ser ignorado")
sv.ao_chegar_midi(M("note_on", channel=12, note=16, velocity=0)); ok(len(enviados) == 1 and sv.estado.ultimo_rb == "12,16,0", "estado do RB deve ser repassado")
# o repasse manda o texto certo a cada tablet
async def teste():
    recebidos = []
    class C:
        async def send_str(s, t): recebidos.append(t)
    sv.estado.clientes.add(C()); enviados.clear()
    class L2:
        def call_soon_threadsafe(s, fn): fn()
    sv.estado.loop = L2()
    sv.avisar_tablets("st,12,16,0"); await asyncio.sleep(0.05)
    ok(recebidos == ["st,12,16,0"], f"broadcast: {recebidos}")
asyncio.run(teste())
# comando de inicio com o Windows
ok(sv.comando_inicio().startswith('"'), "comando de inicio entre aspas")
# argumentos de linha de comando
a = sv.ler_argumentos(["--console", "--debug", "--porta", "XP2", "--http", "9001", "--wifi", "--sem-adb"])
c = sv.aplicar_argumentos(dict(sv.CONFIG_PADRAO), a)
ok(c["porta_midi"] == "XP2" and c["http"] == 9001 and c["wifi"] and not c["usar_adb"] and a.console and a.debug, f"argumentos: {c}")
print("FALHAS:", len(falhas))
sys.exit(1 if falhas else 0)
