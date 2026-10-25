"""
Gerador do PadBridge: produz, a partir de UMA tabela propria (abaixo),
  - mapping/PadBridge.midi.csv     (arquivo de mapeamento para importar no Rekordbox)
  - padbridge/web/index.html       (a tela do tablet; usa tools/template.html)

Uso:   python tools/gerar.py
Opcional (so para desenvolvedores): --registro comandos.txt
    confere se cada nome de funcao existe na tabela de comandos do Rekordbox (arquivo
    de duas ou mais colunas separadas por TAB, primeira coluna = nome). Esse arquivo NAO faz parte do repositorio.

Convencao de canais MIDI (a mesma que os controladores Pioneer DJ usam):
  pads .......... deck 1 = canal 7, deck 2 = canal 9   (SHIFT = canal 8 / 10, mesma nota)
  botoes ........ deck 1 = canal 0, deck 2 = canal 1
  retorno (RB->tablet) de stems: canais 12 / 13  (canais que nenhuma funcao usa como entrada, para o eco nao disparar nada)
Em MIDI, "canal N" aqui e o numero de 0 a 15 (canal 7 = "canal 8" nos programas que contam a partir de 1).
"""
import argparse
import csv
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME = "PadBridge"
CSV_SAIDA = os.path.join(RAIZ, "mapping", f"{NOME}.midi.csv")
HTML_SAIDA = os.path.join(RAIZ, "padbridge", "web", "index.html")
TEMPLATE = os.path.join(RAIZ, "tools", "template.html")

PAD = ("7", "9")          # canais dos pads (deck 1, deck 2)
PAD_SHIFT = ("8", "10")   # mesmo pad com SHIFT
DECK = ("0", "1")         # canais dos botoes
FB_STEMS = ("12", "13")   # retorno de estado dos stems
FB_PADS = FB_STEMS        # retorno dos pads (hot cue gravado, loop ativo, slot carregado); notas diferentes das dos stems, e nenhuma entrada usa esses canais


def linha(nome, funcao, tipo, entrada, decks, comentario, saida=("", "", ""), opcao="Fast"):
    """Uma linha do CSV de mapeamento do Rekordbox (15 colunas)."""
    return [nome, funcao, tipo, entrada, decks[0], decks[1], "", "", saida[0], saida[1], saida[2], "", "", opcao, comentario]


def secao(titulo):
    return ["# " + titulo] + [""] * 14


def gerar():
    rows = [[f"@file,1,{NOME}"],
            ["#name", "function", "type", "input", "deck1", "deck2", "deck3", "deck4", "output", "deck1", "deck2", "deck3", "deck4", "option", "comment"],
            [""] * 15,
            secao("Pad mode")]

    # ---- botoes de modo --------------------------------------------------------------------------------
    MODOS = []
    for id_, nome_ui, nome, funcao, entrada in (
            ("hotcue", "HOT CUE", "HotCue", "HotCueMode", "901B"),
            ("beatloop", "BEAT LOOP", "BeatLoop", "BeatJump+Shift", "906D"),
            ("sampler", "SAMPLER", "Sampler", "SamplerMode", "9022"),
            ("keyboard", "KEYBOARD", "Keyboard", "HotCue+Shift", "9069")):
        rows.append(linha(nome, funcao, "Button", entrada, DECK, f"Modo de pads: {nome_ui}"))
        MODOS.append(dict(id=id_, nome=nome_ui, nota_modo=int(entrada[2:], 16)))

    # ---- HOT CUE: 12 pads (A-L), notas 0x00-0x0B; SHIFT (canal +1) = apagar o hot cue --------------------
    rows.append(secao("HOT CUE (12 pads; SHIFT apaga)"))
    pads = []
    for n in range(1, 13):
        entrada = "90%02X" % (n - 1)
        rows.append(linha(f"PAD{n}_HotCue", f"PAD{n}.HotCue", "Pad", entrada, PAD, f"Hot cue {chr(64 + n)}", saida=(entrada, *FB_PADS)))
        rows.append(linha(f"PAD{n}_HotCue+Shift", f"PAD{n}.HotCue+Shift", "Pad", entrada, PAD_SHIFT, f"Apagar hot cue {chr(64 + n)}", saida=(entrada, *FB_PADS)))
        pads.append(dict(rot=chr(64 + n), nota=n - 1))
    MODOS[0].update(pads=pads, shift=True, colunas=4, linhas=3)

    # ---- BEAT LOOP: 8 pads 1/4 ... 32, notas 0x60-0x67 (as funcoes PAD5..PAD12_BeatLoop do Rekordbox) ----
    rows.append(secao("BEAT LOOP (1/4 a 32)"))
    valores = ["1/4", "1/2", "1", "2", "4", "8", "16", "32"]
    pads = []
    for i in range(8):
        rows.append(linha(f"PAD{5 + i}_BeatLoop", f"PAD{1 + i}_BeatLoop", "Pad", "90%02X" % (0x60 + i), PAD, f"Beat loop {valores[i]}", saida=("90%02X" % (0x60 + i), *FB_PADS)))
        pads.append(dict(rot=valores[i], nota=0x60 + i))
    MODOS[1].update(pads=pads, shift=False, colunas=4, linhas=2)

    # ---- SAMPLER: 8 slots, notas 0x30-0x37; SHIFT = parar o slot -------------------------------------------
    rows.append(secao("SAMPLER (8 slots por banco; SHIFT para o slot)"))
    pads = []
    for i in range(8):
        n = i + 1
        entrada = "90%02X" % (0x30 + i)
        f_play = "PAD1.Sampler" if n == 1 else f"PAD{n}_Sampler"
        rows.append(linha(f"PAD{n}_Sampler", f_play, "Pad", entrada, PAD, f"Tocar o slot {n}", saida=(entrada, *FB_PADS)))
        rows.append(linha(f"PAD{n}_Sampler+Shift", f_play + "+Shift", "Pad", entrada, PAD_SHIFT, f"Parar o slot {n}", saida=(entrada, *FB_PADS)))
        pads.append(dict(rot=f"SLOT {n}", nota=0x30 + i))
    MODOS[2].update(pads=pads, shift=True, colunas=4, linhas=2, shift_txt="SHIFT (parar slot)")
    rows.append(secao("SAMPLER - banco anterior / proximo (botoes no canal do deck)"))
    rows.append(linha("Parameter1Left_Sampler", "Parameter1Left.Sampler", "Button", "9027", DECK, "Banco do sampler anterior"))
    rows.append(linha("Parameter1Right_Sampler", "Parameter1Right.Sampler", "Button", "902F", DECK, "Banco do sampler seguinte"))
    MODOS[2]["barra"] = dict(menos="BANCO -", mais="BANCO +", rot="BANCO", contador=4, canal="deck", nota_menos=0x27, nota_mais=0x2F)

    # ---- KEYBOARD: 8 pads, notas 0x40-0x47 = +4 +5 +6 +7 / 0 +1 +2 +3 semitons --------------------------
    rows.append(secao("KEYBOARD (tom a partir do hot cue selecionado na controladora)"))
    valk = ["+4", "+5", "+6", "+7", "0", "+1", "+2", "+3"]
    pads = []
    for i in range(8):
        n = i + 1
        rows.append(linha(f"PAD{n}_Keyboard", "PAD1.Keyboard" if n == 1 else f"PAD{n}_Keyboard", "Pad", "90%02X" % (0x40 + i), PAD, f"Keyboard {valk[i]} semitons", saida=("90%02X" % (0x40 + i), *FB_PADS)))
        pads.append(dict(rot=valk[i], nota=0x40 + i))
    MODOS[3].update(pads=pads, shift=False, colunas=4, linhas=2)

    # ---- STEMS: um codigo por stem (o Rekordbox alterna sozinho); estado volta nos canais 12/13 -----------
    rows.append(secao("STEMS (mute on/off; o Rekordbox devolve o estado nos canais 12/13)"))
    partes = []
    for i, (nome, rot) in enumerate((("ActivePartVocal", "VOCAL"), ("ActivePartInst", "INST"), ("ActivePartBass", "BASS"), ("ActivePartDrums", "DRUMS"))):
        entrada = "90%02X" % (0x10 + i)
        rows.append(linha(nome, "", "Button", entrada, PAD, f"Stem {rot.lower()} on/off", saida=(entrada, FB_STEMS[0], FB_STEMS[1])))
        partes.append(dict(rot=rot, nota=0x10 + i))
    # modo dos stems (mute/solo): funcao global do Rekordbox, sem coluna de deck; canal 0 dentro do codigo, estado volta em 12 (nota 0x56)
    rows.append(linha("ActivePartMuteSolo", "", "Button", "9056", ("", ""), "Stems: alterna mute/solo (global)", saida=("9C56", "", "")))
    stems = dict(modo=dict(rot="MODO", nota=0x56), partes=partes, fb=dict(stems=[int(c) for c in FB_STEMS]))

    # ---- KEY: semitom -/+, sincronizar e resetar o tom (botoes no canal do deck) ---------------------------
    rows.append(secao("KEY (botoes no canal do deck)"))
    ctrl = []
    for nome, funcao, entrada, rot, desc in (("SemitoneDown", "SemitoneDown", "900A", "KEY -", "Tom -1 semitom"),
                                              ("SemitoneUp", "SemitoneUp", "9079", "KEY +", "Tom +1 semitom"),
                                              ("KeySync", "SemitoneDown+Shift", "9065", "KEY SYNC", "Sincronizar o tom"),
                                              ("KeyReset", "SemitoneUp+Shift", "9064", "KEY RESET", "Resetar o tom")):
        rows.append(linha(nome, funcao, "Button", entrada, DECK, desc))
        ctrl.append(dict(rot=rot, nota=int(entrada[2:], 16)))

    # ---- PERFORMANCE (2a pagina da fila de baixo): nudge, slip e master (botoes no canal do deck) -------------
    rows.append(secao("PERFORMANCE (nudge segura; slip e master devolvem o estado nos canais 12/13)"))
    perf = []
    for nome, entrada, rot, desc, estado in (("PitchBendDown", "9050", "NUDGE -", "Pitch bend para baixo (enquanto segura)", False),
                                              ("PitchBendUp", "9051", "NUDGE +", "Pitch bend para cima (enquanto segura)", False),
                                              ("Slip", "9052", "SLIP", "Slip mode liga/desliga", True),
                                              ("Master", "9053", "MASTER", "Deck master", True),
                                              ("InstDoubles", "9054", "DOUBLES", "Instant Doubles: copia a faixa do outro deck", False)):
        rows.append(linha(nome, "", "Button", entrada, DECK, desc, saida=(entrada, *FB_PADS) if estado else ("", "", "")))
        perf.append(dict(rot=rot, nota=int(entrada[2:], 16), estado=estado, topo=(nome in ("Master","InstDoubles")),   # MASTER fica no cabecalho do deck
                         aria="Instant Doubles" if nome == "InstDoubles" else None))
    # CFX ON e global (vale para os dois decks): sem coluna de deck, o canal vai dentro do codigo; o estado volta em 12 (nota 0x55)
    rows.append(linha("CFXOn", "", "Button", "9055", ("", ""), "Color FX liga/desliga (global)", saida=("9C55", "", "")))
    perf.append(dict(rot="CFX ON", nota=0x55, estado=True, topo=False, aria="Color FX ligado/desligado", **{"global": True}))

    # ---- SEEK: arrastar o dedo na waveform do PadBridge v2 move a musica (Needle Search, 14 bits: CC 3 = MSB, CC 35 = LSB) ----
    rows.append(secao("Seek (PadBridge v2): Needle Search"))
    rows.append(linha("NeedleSearch", "NeedleSearch+Touch", "Button", "9043", DECK, "Needle Search: toque (00/7f)", opcao=""))
    rows.append(linha("NeedleSearch", "NeedleSearch", "Value", "B003", DECK, "Needle Search: posicao (14 bits)", opcao="Max=16383"))

    return rows, MODOS, stems, ctrl, perf


def conferir(rows, registro_arquivo):
    registro = {l.split("\t")[0] for l in open(registro_arquivo, encoding="utf-8") if l.strip() and not l.startswith("##")}
    faltando = sorted({r[0] for r in rows if len(r) == 15 and r[3] and not r[0].startswith("#") and r[0] not in registro})
    assert not faltando, f"nomes que nao existem na tabela de comandos: {faltando}"
    print("registro conferido:", len({r[0] for r in rows if len(r) == 15 and r[3]}), "funcoes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registro", help="arquivo com a tabela de comandos do Rekordbox (opcional, so para conferir os nomes)")
    args = ap.parse_args()
    rows, modos, stems, ctrl, perf = gerar()
    if args.registro:
        conferir(rows, args.registro)
    os.makedirs(os.path.dirname(CSV_SAIDA), exist_ok=True)
    with open(CSV_SAIDA, "w", encoding="utf-8", newline="") as f:
        for r in rows:
            if len(r) == 1:
                f.write(r[0] + "\r\n")
            else:
                csv.writer(f, lineterminator="\r\n").writerow(r)
    print("mapeamento:", CSV_SAIDA, f"({len([r for r in rows if len(r) == 15 and r[3]])} linhas de mapeamento)")
    tpl = open(TEMPLATE, encoding="utf-8").read()
    for chave in ("__MODOS__", "__STEMS__", "__CTRL__", "__PERF__"):
        assert tpl.count(chave) == 1, chave
    html = tpl.replace("__MODOS__", json.dumps(modos)).replace("__STEMS__", json.dumps(stems)).replace("__CTRL__", json.dumps(ctrl)).replace("__PERF__", json.dumps(perf))
    os.makedirs(os.path.dirname(HTML_SAIDA), exist_ok=True)
    open(HTML_SAIDA, "w", encoding="utf-8").write(html)
    print("tela:", HTML_SAIDA)


if __name__ == "__main__":
    main()
