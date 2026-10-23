# Dados em tempo real do Rekordbox (estudo)

Resultado da analise estatica (strings, listagem de arquivos) do Rekordbox 7.2.19 e dos instaladores de drivers que vem nele. Nada foi quebrado, descompilado ou extraido alem de nomes de classes/portas; os arquivos da Pioneer nao entram neste repositorio.

## O que e cada coisa
| Item | Conclusao | Como foi visto |
|---|---|---|
| `rekordbox\...\drivers\*.exe` (XDJ-XZ, DDJ-*, DJM-*...) | Instaladores de **audio** (driver `.sys` + ASIO `.dll`). Nao levam metadados, waveform nem nome de faixa. | XDJ-XZ: `XDJ-XZAudio.sys/.inf/.cat`, `XDJ-XZ_ASIO.dll`; CDJ/XDJ 1.801: NSIS, "AlphaTheta CDJXDJ ASIO" |
| Controle (pads, jog, fader) | MIDI/HID de classe, lido direto pelo Rekordbox (`HidD_*`, `JuceMidiDeviceDetector`, `MidiSysEx*`). | strings de `rekordbox.exe` |
| Mapeamento MIDI | So carrega LEDs e valores (ex.: `TempoSlider`, `MasterLevel`). **Nao existe funcao de nome de faixa nem de waveform.** | registro de funcoes (707 linhas) |
| PRO DJ LINK | Rede UDP/TCP: `PSvLinkUDP/TCPServer/TCPClient`, `PSvLinkSysMgr`, `PSvLinkTimeBeatCounter`, `PSvLinkDeviceConnect2`, `PSvNFSd`; checagem de portas **2049, 50000, 50001, 50002, 50004, 50111**; `PSvLinkSysMgrINI.xml` (Device Id=17, Type=4). | strings + arquivo XML |
| Banco de dados | `RemoteDBServer`, `PSvDBMain/Comm/Connection` (servidor de banco para players ligados). `master.db` local (SQLCipher) legivel pelo `rekordbox-mcp`. | strings + MCP |
| Analise de faixa (ANLZ) | `share\PIONEER\USBANLZ\xxx\<uuid>\ANLZ0000.DAT/.EXT/.2EX` com tags `PQTZ` (beat grid), `PWAV`/`PWV2` (miniatura), `PWV3` (detalhe), `PWV4`/`PWV5` (colorido), `PWV6`/`PWV7`/`PWVC` (3 bandas), `PCOB`/`PCO2` (cues). | parser de 20 linhas em arquivo real |
| `rbHttpServer.exe` | Servidor Go (HTTP/TLS) do app; nao e uma API de dados de decks (a investigar so se necessario). | strings |

## Estrategia para waveform e nome da musica
1. **Waveform e grade de batidas**: ler do ANLZ (offline, estatico) e desenhar no tablet.
2. **Qual faixa esta em cada deck e a posicao**: precisa de fonte ao vivo. Candidatas, da mais promissora:
   - PRO DJ LINK (UDP 50001/50002) emitido pelo Rekordbox como "rekordbox" (device 17). **A testar** com `tools/sonda_prolink.py`.
   - Historico no `master.db` (via rekordbox-mcp): serve para "ultima faixa tocada", com atraso.
   - Sem fonte ao vivo, a posicao pode ser estimada pelo relogio a partir de play/pause + BPM + grade (precisa de ID da faixa).
3. Protocolo PRO DJ LINK e os formatos ANLZ sao documentados publicamente por terceiros (Deep Symmetry: *dysentery*, *beat-link*, *crate-digger*); usar essas fontes, nao inventar.

## Para testar no PC
```
python tools/sonda_prolink.py --seg 60 --hex
```
Com o Rekordbox aberto, PRO DJ LINK ligado, um deck tocando. Resultado "nada recebido" tambem e informacao.
