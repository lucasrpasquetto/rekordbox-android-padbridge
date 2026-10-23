# Changelog

## Nao lancado
- Botao **MODO** (mute/solo dos stems) na linha de stems de cada deck: funcao global `ActivePartMuteSolo` (nota 0x56, canal 0, retorno em 12); os dois decks mostram o mesmo estado. Requer reimportar o mapeamento.
- A tela aceita, quando embutida em outra pagina, o tempo dos hot cues dentro dos pads (`window.__padsCues`); no PadBridge puro nada muda.
- Estudo de dados em tempo real (`docs/TEMPO_REAL.md`) e sonda `tools/sonda_prolink.py` para testar o PRO DJ LINK (somente leitura).
- MASTER virou so um rotulo no cabecalho (nao e mais botao): o texto fica verde quando o deck e o master; DOUBLES usa o mesmo estilo de AMPLIAR e TELA CHEIA.
- Letra dos pads: branca quando apagados ou em repouso, preta quando acesos (cor do pad mais escura no repouso para manter o contraste).
- DOUBLES (Instant Doubles: carrega no deck a faixa do outro deck) fica no cabecalho de cada deck, ao lado do MASTER; a pagina PERF ganha CFX ON (liga/desliga o Color FX, global; acende nos dois decks se o Rekordbox devolver o estado). Requer reimportar o mapeamento.
- MASTER agora fica no cabecalho de cada deck (sempre visivel) e acende quando o deck e o master no Rekordbox.
- Ajustes da auditoria de UX/UI: texto dos pads escuro nas cores claras (contraste minimo 3:1), stems ativos e modo selecionado com preenchimento solido (3:1 contra o estado desligado), botoes do cabecalho com 44 px, Wake Lock para a tela do tablet nao apagar, linha de depuracao so com `?dbg=1`, `role="button"`, `aria-label` e `aria-pressed` nos controles.
- Fila de baixo com 2 paginas (botao PERF/KEY): NUDGE -/+ (pitch bend enquanto segura), SLIP e MASTER (os dois ultimos acompanham o estado do Rekordbox). Requer reimportar o mapeamento.
- Pads acendem conforme o Rekordbox (hot cue gravado, loop ativo, slot carregado): retorno nos canais 12/13. Requer reimportar o mapeamento. Validado no Rekordbox 7.2.19 (Hot Cue, Beat Loop, Sampler e Keyboard).
- A ponte registra no log o que o Rekordbox envia (so quando muda) e reenvia o estado atual ao tablet quando ele conecta.
- `?dbg=1` na URL mostra a velocidade recebida em cada pad.

## 0.1.0
- Tela para tablet (1340x800, paisagem) com 2 decks: stems, 4 modos de pad (Hot Cue 12, Beat Loop 8, Sampler 8 + 4 bancos, Keyboard 8), SHIFT e controles de KEY.
- Ampliar deck e tela cheia.
- Ponte MIDI (WebSocket -> loopMIDI) com feedback dos stems vindo do Rekordbox.
- Servico com icone na bandeja, adb reverse automatico (USB), inicio com o Windows.
- Gerador do mapeamento `PadBridge.midi.csv` para o Rekordbox.
