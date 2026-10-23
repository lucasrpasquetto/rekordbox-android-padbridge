# Protocolo MIDI do PadBridge

## Tablet -> ponte (WebSocket, texto)
`on|rel|lib|off|cc,canal,a,b`

- `on`  : nota ligada (velocity 127)
- `rel` : nota solta (note on, velocity 0 - convencao do mapeamento)
- `cc`  : control change (canal, controlador, valor)

## Canais (0 = canal 1)
| Uso | Deck 1 | Deck 2 |
|---|---|---|
| Pads | 7 | 9 |
| Pads com SHIFT | 8 | 10 |
| Botoes (KEY etc.) | 0 | 1 |
| Feedback de stems (saida) | 12 | 13 |

O SHIFT do tablet nao envia MIDI: apenas muda o canal do proximo pad.

## Notas
- Hot Cue: 0x00-0x0B (A-L)
- Beat Loop: 0x60-0x67
- Sampler: 0x30-0x37 (bancos: 0x27 e 0x2F)
- Keyboard: 0x40-0x47
- Stems (Vocal/Inst/Bass/Drums): 0x10-0x13
- MODO dos stems (mute/solo) 0x56 (`ActivePartMuteSolo`, global: entrada sempre no canal 0, retorno de estado em 12 com a nota 0x56, saida `9C56`)
- Performance (canal do deck 0/1): NUDGE - 0x50 (`PitchBendDown`), NUDGE + 0x51 (`PitchBendUp`), SLIP 0x52 (`Slip`), MASTER 0x53 (`Master`, botao fixo no cabecalho do deck); SLIP e MASTER devolvem o estado em 12/13 com a mesma nota
- Instant Doubles 0x54 (`InstDoubles`, por deck, sem retorno, botao no cabecalho) e CFX ON 0x55 (`CFXOn`, global: entrada sempre no canal 0, retorno de estado em 12 com a nota 0x55, saida `9C55`; o retorno ainda nao foi confirmado no Rekordbox)

## Feedback (Rekordbox -> tablet)
A ponte escuta a porta virtual, ignora o eco do que ela mesma enviou (1 s) e repassa o resto ao tablet como `st,canal,nota,vel` (notas) ou `sc,canal,cc,valor`.

## Estado dos pads (Rekordbox -> tablet)
Cada pad tem uma saida no mapeamento, nos canais 12 (deck 1) e 13 (deck 2), com a **mesma nota** do pad. O Rekordbox envia velocity 127 quando o pad esta ativo (hot cue gravado, loop ativo, slot carregado) e 0 quando nao esta. Nao ha codigo de cor.

Detalhes aprendidos na pratica (Rekordbox 7.2.19):
- O Rekordbox guarda **uma saida por pad**, compartilhada entre a linha normal e a linha `+Shift`. A linha `+Shift` deve repetir a mesma saida, senao ela apaga a saida do par.
- As saidas **nao podem** cair em canais usados como entrada (7-10 e 0-1): o loopMIDI devolveria o estado ao Rekordbox como se fosse um toque.
- O tablet so escurece os pads de um modo depois que o Rekordbox informa algo daquele modo; modos sem retorno ficam como estao.
- A ponte guarda o ultimo estado de cada nota e reenvia ao tablet quando ele conecta.

## Regenerar
`python tools/gerar.py` recria `mapping/PadBridge.midi.csv` e `padbridge/web/index.html`.
