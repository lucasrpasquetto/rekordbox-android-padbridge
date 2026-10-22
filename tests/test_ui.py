"""Teste da tela (Playwright + Chromium): confere cada botao, cada codigo MIDI e o CSV de mapeamento.
Rode:  python tests/test_ui.py   (precisa de: pip install playwright && playwright install chromium)"""
import csv, os, tempfile
from playwright.sync_api import sync_playwright
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do repositorio
falhas = []
def ok(c, m):
    if not c: falhas.append(m); print("FALHA:", m)
cs = set()   # (input, canal)
for r in csv.reader(open(os.path.join(AQUI, "mapping/PadBridge.midi.csv"))):
    if len(r) == 15 and r[3] and not r[0].startswith("#"):
        if r[4] == "" and r[5] == "": cs.add((r[3], int(r[3][1], 16)))   # canal dentro do input (funcao global)
        for col in (4, 5):
            if r[col] != "": cs.add((r[3], int(r[col])))
LOOP = ["1/4", "1/2", "1", "2", "4", "8", "16", "32"]
KEYB = ["+4", "+5", "+6", "+7", "0", "+1", "+2", "+3"]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1340, "height": 800}, has_touch=True)
    erros = []; pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.add_init_script("window.__wl=0;Object.defineProperty(navigator,'wakeLock',{configurable:true,value:{request:async()=>{window.__wl++;return {addEventListener(){},release(){}}}}});window.__env=[];window.WebSocket=class{constructor(){window.__ws=this;this.readyState=1;setTimeout(()=>this.onopen&&this.onopen(),5)}send(m){window.__env.push(m)}close(){}}")
    pg.goto("file://" + os.path.join(AQUI, "padbridge/web/index.html")); pg.wait_for_timeout(200)
    env = lambda: pg.evaluate("window.__env")
    clr = lambda: pg.evaluate("window.__env.length=0")
    def tocar(sel, pid=1):
        pg.locator(sel).dispatch_event("pointerdown", {"pointerId": pid, "pointerType": "touch"})
        pg.locator(sel).dispatch_event("pointerup", {"pointerId": pid, "pointerType": "touch"})
    def visiveis(d): return [pg.locator(f"#d{d} .pad").nth(i).is_visible() for i in range(12)]
    for d in (0, 1):
        chp = (7, 9)[d]
        # --- HOT CUE (modo inicial)
        ok(sum(visiveis(d)) == 12, f"d{d+1}: hot cue deve mostrar 12 pads")
        for shift in (False, True):
            for i in range(12):
                clr()
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerdown", {"pointerId": 50})
                tocar(f"#d{d} .pad >> nth={i}")
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerup", {"pointerId": 50})
                ch = chp + (1 if shift else 0)
                ok(env() == [f"on,{ch},{i},127", f"rel,{ch},{i},0"], f"hotcue d{d+1} shift={shift} pad{i+1}: {env()}")
                ok(("90%02X" % i, ch) in cs, f"CSV sem 90{i:02X} canal {ch}")
        # --- troca para BEAT LOOP
        clr(); tocar(f"#d{d} .modos .btn:text-is('BEAT LOOP')")
        ok(env() == [f"on,{d},109,127", f"rel,{d},109,0"], f"modo beat loop d{d+1}: {env()}")
        ok(("906D", d) in cs, "CSV sem modo BEAT LOOP")
        v = visiveis(d); ok(sum(v) == 8 and all(v[:8]), f"d{d+1}: beat loop deve mostrar 8 pads: {v}")
        rot = [pg.locator(f"#d{d} .pad").nth(i).inner_text() for i in range(8)]
        ok(rot == LOOP, f"rotulos beat loop: {rot}")
        for shift in (False, True):
            for i in range(8):
                clr()
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerdown", {"pointerId": 50})
                tocar(f"#d{d} .pad >> nth={i}")
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerup", {"pointerId": 50})
                nota = 0x60 + i
                ok(env() == [f"on,{chp},{nota},127", f"rel,{chp},{nota},0"], f"loop d{d+1} shift={shift} {LOOP[i]}: {env()}")
                ok(("90%02X" % nota, chp) in cs, f"CSV sem 90{nota:02X}")
        ok("shift" not in (pg.locator(f"#d{d}").get_attribute("class") or "").split(), "shift ficou preso no beat loop")
        # --- SAMPLER
        clr(); tocar(f"#d{d} .modos .btn:text-is('SAMPLER')")
        ok(env() == [f"on,{d},34,127", f"rel,{d},34,0"], f"modo sampler d{d+1}: {env()}")
        ok(("9022", d) in cs, "CSV sem modo SAMPLER")
        v = visiveis(d); ok(sum(v) == 8 and all(v[:8]), f"d{d+1}: sampler deve mostrar 8 pads: {v}")
        ok(pg.locator(f"#d{d} .bank .barra").nth(0).is_visible() and not pg.locator(f"#d{d} .bank .barra").nth(1).is_visible(), "so a barra de bancos deveria aparecer no sampler")
        for shift in (False, True):
            for i in range(8):
                clr()
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerdown", {"pointerId": 50})
                tocar(f"#d{d} .pad >> nth={i}")
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerup", {"pointerId": 50})
                nota = 0x30 + i; ch = chp + (1 if shift else 0)
                ok(env() == [f"on,{ch},{nota},127", f"rel,{ch},{nota},0"], f"sampler d{d+1} shift={shift} slot{i+1}: {env()}")
                ok(("90%02X" % nota, ch) in cs, f"CSV sem 90{nota:02X} canal {ch}")
        # bancos: + / - mandam o codigo oficial e o rotulo anda de 1 a 4
        lbl = lambda: pg.locator(f"#d{d} .bank .barra").nth(0).locator(".lbl").inner_text()
        ok(lbl() == "BANCO 1 / 4", f"rotulo inicial: {lbl()}")
        for esperado in ("BANCO 2 / 4", "BANCO 3 / 4", "BANCO 4 / 4", "BANCO 4 / 4"):
            clr(); tocar(f"#d{d} .bank .btn:text-is('BANCO +')")
            ok(env() == [f"on,{d},47,127", f"rel,{d},47,0"], f"banco + d{d+1}: {env()}")
            ok(lbl() == esperado, f"rotulo {lbl()} != {esperado}")
        clr(); tocar(f"#d{d} .bank .btn:text-is('BANCO -')")
        ok(env() == [f"on,{d},39,127", f"rel,{d},39,0"], f"banco - d{d+1}: {env()}")
        ok(("902F", d) in cs and ("9027", d) in cs, "CSV sem os codigos de banco")
        pg.locator(f"#d{d} .bank .barra").nth(0).locator(".lbl").dispatch_event("pointerdown", {"pointerId": 3}); ok(lbl() == "BANCO 1 / 4", "rotulo nao voltou ao 1")
        # --- KEYBOARD
        clr(); tocar(f"#d{d} .modos .btn:text-is('KEYBOARD')")
        ok(env() == [f"on,{d},105,127", f"rel,{d},105,0"], f"modo keyboard d{d+1}: {env()}")
        ok(("9069", d) in cs, "CSV sem modo KEYBOARD")
        v = visiveis(d); ok(sum(v) == 8 and all(v[:8]), f"d{d+1}: keyboard deve mostrar 8 pads: {v}")
        rot = [pg.locator(f"#d{d} .pad").nth(i).inner_text() for i in range(8)]
        ok(rot == KEYB, f"rotulos keyboard: {rot}")
        for shift in (False, True):
            for i in range(8):
                clr()
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerdown", {"pointerId": 50})
                tocar(f"#d{d} .pad >> nth={i}")
                if shift: pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerup", {"pointerId": 50})
                nota = 0x40 + i
                ok(env() == [f"on,{chp},{nota},127", f"rel,{chp},{nota},0"], f"keyboard d{d+1} shift={shift} {KEYB[i]}: {env()}")
                ok(("90%02X" % nota, chp) in cs, f"CSV sem 90{nota:02X}")
        ok(len([r for r in cs if r[0] in ("9046", "9047") and r[1] in (8, 10)]) == 0, "CSV nao deve ter seletor de hot cue")
        ok(not pg.locator(f"#d{d} .bank").is_visible(), "keyboard nao deve mostrar barra extra")
        # --- volta ao HOT CUE
        clr(); tocar(f"#d{d} .modos .btn:text-is('HOT CUE')")
        ok(env() == [f"on,{d},27,127", f"rel,{d},27,0"], f"modo hot cue d{d+1}: {env()}")
        ok(sum(visiveis(d)) == 12 and not pg.locator(f"#d{d} .bank").is_visible(), "hot cue deve voltar a 12 pads sem barra de bancos")
        # SHIFT sozinho nao envia nada
        clr(); pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerdown", {"pointerId": 9}); pg.locator(f"#d{d} .shiftbtn").dispatch_event("pointerup", {"pointerId": 9})
        ok(env() == [], f"SHIFT enviou MIDI: {env()}")
    # --- STEMS (painel fixo; um codigo por parte; toque alterna so a tela)
    for d in (0, 1):
        chp = (7, 9)[d]
        for k, nome in enumerate(["VOCAL", "INST", "BASS", "DRUMS"]):
            sel = f"#d{d} .stems .btn:text-is('{nome}')"
            ok("ativo" in pg.locator(sel).get_attribute("class"), f"{nome} d{d+1} deveria comecar ativo")
            for vez, ativo in ((1, False), (2, True)):
                clr(); tocar(sel)
                ok(env() == [f"on,{chp},{0x10 + k},127", f"rel,{chp},{0x10 + k},0"], f"stem {nome} d{d+1} vez {vez}: {env()}")
                ok(("90%02X" % (0x10 + k), chp) in cs, f"CSV sem stem {nome}")
                ok(("ativo" in pg.locator(sel).get_attribute("class")) == ativo, f"estado visual {nome} d{d+1} vez {vez}")
    # SHIFT sozinho nao afeta stems
    clr(); pg.locator("#d0 .shiftbtn").dispatch_event("pointerdown", {"pointerId": 8}); tocar("#d0 .stems .btn:text-is('BASS')"); pg.locator("#d0 .shiftbtn").dispatch_event("pointerup", {"pointerId": 8})
    ok(env() == ["on,7,18,127", "rel,7,18,0"], f"SHIFT nao deve mudar stems: {env()}")
    # --- LOOP e KEY por deck (canal do deck)
    for d in (0, 1):
        for fila, rot, nota in ((".ctl", "KEY -", 0x0A), (".ctl", "KEY +", 0x79), (".ctl", "KEY SYNC", 0x65), (".ctl", "KEY RESET", 0x64)):
            clr(); tocar(f"#d{d} {fila} .btn:text-is('{rot}')")
            ok(env() == [f"on,{d},{nota},127", f"rel,{d},{nota},0"], f"{rot} d{d+1}: {env()}")
            ok(("90%02X" % nota, d) in cs, f"CSV sem {rot}")
    cls = lambda sel: pg.locator(sel).get_attribute("class")
    msg = lambda m: pg.evaluate("m=>window.__ws.onmessage({data:m})", m)
    # --- PERFORMANCE: 2a pagina da fila de baixo (NUDGE -/+, SLIP, MASTER); botao PERF/KEY alterna, sem MIDI
    vis = lambda sel: pg.locator(sel).is_visible()
    for d in (0, 1):
        ok(vis(f"#d{d} .ctl .btn:text-is('KEY -')") and not vis(f"#d{d} .ctl .btn:text-is('NUDGE -')"), f"d{d+1}: a fila abre na pagina KEY")
        clr(); tocar(f"#d{d} .ctl .btn.tog"); ok(env() == [], f"d{d+1}: PERF nao envia MIDI: {env()}")
        ok(vis(f"#d{d} .ctl .btn:text-is('NUDGE -')") and not vis(f"#d{d} .ctl .btn:text-is('KEY -')"), f"d{d+1}: PERF mostra a pagina de performance")
        ok(vis(f"#d{d} .ctl .shiftbtn"), f"d{d+1}: SHIFT continua visivel na pagina PERF")
        for rot, nota in (("NUDGE -", 0x50), ("NUDGE +", 0x51), ("SLIP", 0x52)):
            clr(); tocar(f"#d{d} .ctl .btn:text-is('{rot}')")
            ok(env() == [f"on,{d},{nota},127", f"rel,{d},{nota},0"], f"{rot} d{d+1}: {env()}")
            ok(("90%02X" % nota, d) in cs, f"CSV sem {rot}")
        for rot, nota in (("SLIP", 0x52),):   # estado vindo do Rekordbox
            sel = f"#d{d} .ctl .btn:text-is('{rot}')"
            msg(f"st,{12 + d},{nota},127"); ok("sel" in cls(sel), f"{rot} d{d+1}: feedback deve acender")
            msg(f"st,{12 + d},{nota},0"); ok("sel" not in cls(sel), f"{rot} d{d+1}: feedback deve apagar")
        msg(f"st,{12 + d},{0x50},127"); ok("sel" not in cls(f"#d{d} .ctl .btn:text-is('NUDGE -')"), "NUDGE nao segue estado")
        ok(not vis(f"#d{d} .ctl .btn:text-is('MASTER')") and pg.locator(f"#d{d} .ctl .btn:text-is('MASTER')").count() == 0, f"d{d+1}: MASTER saiu da fila de baixo")
        tocar(f"#d{d} .ctl .btn.tog")
        ok(vis(f"#d{d} .ctl .btn:text-is('KEY -')"), f"d{d+1}: KEY volta")
    # --- INSTANT DOUBLES (por deck) e CFX ON (global: sempre canal 0, estado volta uma vez em 12 e acende os dois decks)
    for d in (0, 1):
        tocar(f"#d{d} .ctl .btn.tog")
        clr(); tocar(f"#d{d} .dbl")
        ok(env() == [f"on,{d},84,127", f"rel,{d},84,0"], f"DOUBLES d{d+1}: {env()}")
        ok(pg.locator(f"#d{d} .dbl").get_attribute("aria-label") == "Instant Doubles", "DOUBLES com nome acessivel")
        clr(); tocar(f"#d{d} .ctl .btn:text-is('CFX ON')")
        ok(env() == ["on,0,85,127", "rel,0,85,0"], f"CFX ON d{d+1} deve usar sempre o canal 0: {env()}")
        tocar(f"#d{d} .ctl .btn.tog")
    for d in (0, 1):
        tocar(f"#d{d} .ctl .btn.tog")
    msg("st,12,85,127")
    ok(all("sel" in cls(f"#d{d} .ctl .btn:text-is('CFX ON')") for d in (0, 1)), "CFX ON: estado global acende os dois decks")
    msg("st,12,85,0")
    ok(all("sel" not in cls(f"#d{d} .ctl .btn:text-is('CFX ON')") for d in (0, 1)), "CFX ON: estado global apaga os dois decks")
    for d in (0, 1):
        tocar(f"#d{d} .ctl .btn.tog")
    rb2 = [r for r in csv.reader(open(os.path.join(AQUI, "mapping/PadBridge.midi.csv"), encoding="utf-8")) if len(r) > 10]
    ok(any(r[0] == "InstDoubles" and r[3] == "9054" and r[4:6] == ["0", "1"] and r[8] == "" for r in rb2), "CSV: InstDoubles por deck, sem saida")
    ok(any(r[0] == "CFXOn" and r[3] == "9055" and r[4:6] == ["", ""] and r[8] == "9C55" for r in rb2), "CSV: CFXOn global com saida 9C55")
    # MASTER no cabecalho do deck: sempre visivel (nas duas paginas da fila de baixo), envia MIDI e segue o Rekordbox
    for d in (0, 1):
        sel = f"#d{d} .topo .master"
        ok(vis(sel), f"d{d+1}: MASTER visivel no cabecalho")
        clr(); tocar(sel); ok(env() == [], f"MASTER d{d+1} e so um rotulo, nao envia MIDI: {env()}")
        msg(f"st,{12 + d},83,127"); ok("sel" in cls(sel), f"MASTER d{d+1}: deve acender")
        msg(f"st,{12 + d},83,0"); ok("sel" not in cls(sel), f"MASTER d{d+1}: deve apagar")
        tocar(f"#d{d} .ctl .btn.tog"); ok(vis(sel), f"d{d+1}: MASTER continua visivel na pagina PERF"); tocar(f"#d{d} .ctl .btn.tog")
    for nome, saida in (("Slip", ["9052", "12", "13"]), ("Master", ["9053", "12", "13"]), ("PitchBendUp", ["", "", ""])):
        ok(any(r[0] == nome and r[8:11] == saida for r in csv.reader(open(os.path.join(AQUI, "mapping/PadBridge.midi.csv"), encoding="utf-8")) if len(r) > 10), f"CSV: saida de {nome} deve ser {saida}")
    # --- FEEDBACK do Rekordbox (canais 12/13 = stems dos decks 1/2, 14/15 = modo SOLO/MUTE)
    cls = lambda sel: pg.locator(sel).get_attribute("class")
    msg = lambda m: pg.evaluate("m=>window.__ws.onmessage({data:m})", m)
    for d in (0, 1):
        for k, nome in enumerate(("VOCAL", "INST", "BASS", "DRUMS")):
            sel = f"#d{d} .stems .btn:text-is('{nome}')"
            msg(f"st,{12 + d},{16 + k},0"); ok("ativo" not in cls(sel), f"feedback: {nome} d{d+1} deve apagar")
            clr(); tocar(sel); ok("ativo" not in cls(sel), f"{nome} d{d+1}: com feedback o toque nao deve alternar a cor")
            ok(env() == [f"on,{7 + 2 * d},{16 + k},127", f"rel,{7 + 2 * d},{16 + k},0"], f"{nome} d{d+1} deve continuar enviando MIDI: {env()}")
            msg(f"st,{12 + d},{16 + k},127"); ok("ativo" in cls(sel), f"feedback: {nome} d{d+1} deve acender")
    rb = [r for r in csv.reader(open(os.path.join(AQUI, "mapping/PadBridge.midi.csv"), encoding="utf-8"))]
    ok(any(r[0] == "ActivePartVocal" and r[8:11] == ["9010", "12", "13"] for r in rb if len(r) > 10), "CSV: saida do stem VOCAL em 12/13")
    # --- FEEDBACK dos PADS (hot cue gravado, loop ativo...): canais 12/13, notas = as do proprio pad
    padc = lambda d, i: pg.locator(f"#d{d} .pads .pad").nth(i).get_attribute("class")
    for d in (0, 1):
        tocar(f"#d{d} .modos .btn:text-is('HOT CUE')")
        ok("aceso" not in padc(d, 0) and "apagado" not in padc(d, 0), f"d{d+1}: antes de qualquer retorno os pads ficam como estao")
        msg(f"st,{12 + d},0,127"); msg(f"st,{12 + d},1,0")
        ok("aceso" in padc(d, 0), f"d{d+1}: hot cue A gravado deve acender")
        ok("apagado" in padc(d, 1), f"d{d+1}: hot cue B vazio deve apagar")
        ok("apagado" in padc(d, 5), f"d{d+1}: pad sem retorno, mas modo informado, deve apagar")
        msg(f"st,{12 + d},1,127"); ok("aceso" in padc(d, 1) and "apagado" not in padc(d, 1), f"d{d+1}: hot cue B passou a existir")
        o = 1 - d
        ok("aceso" not in padc(o, 0) or d == 1, "retorno de um deck nao pode vazar para o outro") if d == 0 else None
        tocar(f"#d{d} .modos .btn:text-is('BEAT LOOP')")
        ok("aceso" not in padc(d, 0) and "apagado" not in padc(d, 0), f"d{d+1}: BEAT LOOP sem retorno nao pode herdar o estado do hot cue")
        msg(f"st,{12 + d},96,127"); ok("aceso" in padc(d, 0) and "apagado" in padc(d, 3), f"d{d+1}: loop 1/4 ativo acende")
        tocar(f"#d{d} .modos .btn:text-is('HOT CUE')")
        ok("aceso" in padc(d, 0), f"d{d+1}: voltar ao HOT CUE reaplica o estado")
    ok("aceso" not in padc(0, 11) , "d1: hot cue L nunca informado fica sem classe aceso")
    for nome, saida in (("PAD1_HotCue", ["9000", "12", "13"]), ("PAD12_HotCue", ["900B", "12", "13"]), ("PAD5_BeatLoop", ["9060", "12", "13"]),
                        ("PAD1_Sampler", ["9030", "12", "13"]), ("PAD1_Keyboard", ["9040", "12", "13"]), ("PAD1_HotCue+Shift", ["9000", "12", "13"]), ("PAD1_Sampler+Shift", ["9030", "12", "13"])):
        ok(any(r[0] == nome and r[8:11] == saida for r in rb if len(r) > 10), f"CSV: saida de {nome} deve ser {saida}")
    entradas = {(r[3], r[4]) for r in rb if len(r) > 10 and r[3]}
    ok(all(r[9] not in ("7", "8", "9", "10", "0", "1") and r[10] not in ("7", "8", "9", "10", "0", "1") for r in rb if len(r) > 10 and r[8]), "CSV: nenhuma saida pode cair em canal usado como entrada (laco no loopMIDI)")
    # --- AJUSTES DE UI (auditoria): contraste, estados, tamanho de toque, depuracao escondida, wake lock, papeis
    def rgb_de(sel_js, prop):
        return pg.evaluate("""([s,prop])=>{const e=document.querySelector(s);const c=document.createElement('canvas').getContext('2d',{willReadFrequently:true});
          c.fillStyle='#000';c.fillRect(0,0,1,1);c.fillStyle=getComputedStyle(e)[prop];c.fillRect(0,0,1,1);return [...c.getImageData(0,0,1,1).data].slice(0,3)}""", [sel_js, prop])
    def lum(c):
        f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255 + 0.055) / 1.055) ** 2.4)
        return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])
    def cr(a, b):
        la, lb = lum(a), lum(b); return (max(la, lb) + .05) / (min(la, lb) + .05)
    tocar("#d0 .modos .btn:text-is('HOT CUE')")
    for i in range(12):   # texto dos pads: >= 3:1 (texto grande) no repouso e aceso
        sel = f"#d0 .pads .pad:nth-child({i + 1})"
        pg.evaluate("s=>document.querySelector(s).classList.remove('aceso','on','sel','apagado')", sel)
        txt = rgb_de(sel, "color"); rep = rgb_de(sel, "backgroundColor")
        pg.evaluate("s=>document.querySelector(s).classList.add('aceso')", sel)
        ace = rgb_de(sel, "backgroundColor"); txa = rgb_de(sel, "color")
        ok(list(txt) == [255, 255, 255] and list(txa) == [14, 15, 19], f"pad {chr(65 + i)}: letra branca no repouso e preta quando acesa ({txt} {txa})")
        pg.evaluate("s=>document.querySelector(s).classList.remove('aceso')", sel)
        ok(cr(txt, rep) >= 3 and cr(txa, ace) >= 3, f"pad {chr(65 + i)}: contraste do texto repouso {cr(txt, rep):.2f} aceso {cr(txt, ace):.2f} (minimo 3)")
    for d in (0, 1):
        ativo = rgb_de(f"#d{d} .stems .btn:nth-child(2)", "backgroundColor")
        normal = rgb_de(f"#d{d} .modos .btn:nth-child(2)", "backgroundColor")   # fundo neutro dos botoes
        for k, nome in enumerate(("VOCAL", "INST", "BASS", "DRUMS")):
            sel = f"#d{d} .stems .btn:nth-child({k + 1})"
            msg(f"st,{12 + d},{16 + k},127"); a = rgb_de(sel, "backgroundColor"); t = rgb_de(sel, "color")
            msg(f"st,{12 + d},{16 + k},0"); n = rgb_de(sel, "backgroundColor")
            ok(cr(a, n) >= 3, f"stem {nome} d{d+1}: ativo vs apagado {cr(a, n):.2f} (minimo 3)")
            ok(cr(t, a) >= 4.5, f"stem {nome} d{d+1}: texto ativo {cr(t, a):.2f} (minimo 4,5)")
            ok(pg.locator(sel).get_attribute("aria-pressed") == "false", f"stem {nome}: aria-pressed false quando apagado")
            msg(f"st,{12 + d},{16 + k},127"); ok(pg.locator(sel).get_attribute("aria-pressed") == "true", f"stem {nome}: aria-pressed true quando ativo")
        for j, nome in enumerate(("HOT CUE", "BEAT LOOP", "SAMPLER", "KEYBOARD")):
            sel = f"#d{d} .modos .btn:nth-child({j + 1})"
            tocar(sel); s_bg = rgb_de(sel, "backgroundColor"); s_tx = rgb_de(sel, "color")
            outro = f"#d{d} .modos .btn:nth-child({2 if j == 0 else 1})"
            n_bg = rgb_de(outro, "backgroundColor")
            ok(cr(s_bg, n_bg) >= 3, f"modo {nome} d{d+1}: selecionado vs nao {cr(s_bg, n_bg):.2f} (minimo 3)")
            ok(cr(s_tx, s_bg) >= 4.5, f"modo {nome} d{d+1}: texto selecionado {cr(s_tx, s_bg):.2f}")
        tocar(f"#d{d} .modos .btn:text-is('HOT CUE')")
        for sel in (f"#d{d} .zoom", f"#d{d} .full"):
            ok(pg.locator(sel).bounding_box()["height"] >= 44, f"{sel}: altura de toque >= 44px")
        ok(pg.locator(f"#d{d} .zoom").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)") >= 12, "AMPLIAR com fonte >= 12px")
    ok(not pg.locator("#ult").is_visible(), "linha de depuracao escondida sem ?dbg=1")
    ok(pg.evaluate("window.__wl") >= 1, f"wake lock pedido ao abrir/tocar: {pg.evaluate('window.__wl')}")
    sem_papel = pg.evaluate("[...document.querySelectorAll('.btn,.pad,.shiftbtn,.mini')].filter(e=>e.getAttribute('role')!=='button').length")
    ok(sem_papel == 0, f"controles sem role=button: {sem_papel}")
    ok(pg.locator("#d0 .pads .pad").first.get_attribute("aria-label") == "Deck 1 HOT CUE A", pg.locator("#d0 .pads .pad").first.get_attribute("aria-label"))
    pg2 = b.new_page(viewport={"width": 1340, "height": 800}, has_touch=True)
    pg2.add_init_script("window.WebSocket=class{constructor(){this.readyState=1}send(){}close(){}}")
    pg2.goto("file://" + os.path.join(AQUI, "padbridge/web/index.html") + "?dbg=1"); pg2.wait_for_timeout(150)
    ok(pg2.locator("#ult").is_visible() is not None and pg2.evaluate("document.body.classList.contains('dbg')"), "?dbg=1 liga a linha de depuracao")
    pg2.close()
    # decks independentes
    tocar("#d0 .modos .btn:text-is('BEAT LOOP')")
    ok(sum(visiveis(0)) == 8 and sum(visiveis(1)) == 12, "decks devem ter modos independentes")
    pg.screenshot(path=os.path.join(tempfile.gettempdir(), "padbridge_tela.png"))
    ok(erros == [], f"erros de pagina: {erros}")
    b.close()
print("FALHAS:", len(falhas))
