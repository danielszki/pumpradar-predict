# PumpRadar Predict

[![Release](https://img.shields.io/github/v/release/danielszki/pumpradar-predict)](https://github.com/danielszki/pumpradar-predict/releases)
[![CI: Build .deb](https://img.shields.io/github/actions/workflow/status/danielszki/pumpradar-predict/release.yml?label=CI%20build)](https://github.com/danielszki/pumpradar-predict/actions)

Radar que varre **todos os perpétuos USDT da MEXC** em 5 timeframes
(5m / 15m / 1h / 4h / 1d) e acha as moedas no **setup que costuma ANTECEDER o
pump** — o oposto do PumpRadar (que caça quem já subiu e vai cair).

Aqui o filtro é de **pré-pump**: só sobe no ranking o que ainda está
*montando* o movimento, não o que já disparou.

## Corretora

| Fonte | Perpétuos USDT |
|---|---|
| **MEXC** | ~410 ativos |

O auto-refresh de 5 min mantém a varredura sempre atualizada.

## O que ele te diz

| Coluna | Significado |
|---|---|
| Moeda / Idade | ativo + há quanto tempo foi listado (novo = oportunidade de pump de listagem) |
| Console (%) | apertamento da consolidação nos últimos `K` candles (quanto menor, mais "mola") |
| Rompimento (%) | quanto a moeda já saiu acima do teto da consolidação (acima de ~+15% = entrada tardia, R:R ruim) |
| Volume ×̄ | vela atual vs média da consolidação (≥2× = rompimento com força) |
| RS vs BTC | força relativa da janela de varredura (acima de +1,2% = dinheiro indo pra ela, não pro mercado todo) |
| Hoje | variação do dia (grande demais = já era, o pump já aconteceu) |
| Score | probabilidade do setup completar o pump **agora** (rompimento+volume+RS+ativos jovens) |
| Sinais | chips: Rompimento · Volume · RS vs BTC · Nova |
| Status | AÇÃO (setup pronto) / OBSERVAR (quase) / VIGIA (marginal) |

O **score** combina rompimento de acumulação com volume, volume súbito,
força relativa vs BTC, consolidação apertada e ativos recém-listados
(reduz a nota se a moeda **já subiu demais** — sinal de entrada tardia).

Regra prática: **compre antes do primeiro rompimento, nunca depois do pump.**
Quem entra no topo vira o tombo. Use as abas 5m/15m/1h/4h/1d conforme seu estilo
(scalp → 5m/15m, swing → 4h/1d); setups "frescos" (listados há ≤45 dias) têm mais
chance de romper feito o clássico pump de listagem.

## Instalação (.deb)

```bash
sudo apt install -f -y
sudo dpkg -i pumpradar-predict_1.0.0_all.deb
pumpradar-predict        # ou pela busca de aplicativos: "PumpRadar Predict"
```

## Rodar direto da fonte

```bash
cd src
python3 server.py --port 8766   # abre no navegador
python3 app.py                  # abre janela nativa (WebKitGTK)
```

## Gerar o .deb

```bash
./build_deb.sh          # cria build/pumpradar-predict_1.0.0_all.deb
```

## Estrutura

```
src/server.py      backend + varredura multi-thread dos 5 timeframes (stdlib)
src/app.py         janela nativa WebKitGTK (fallback p/ navegador)
src/web/           frontend (index.html, style.css, app.js)
make_icon.py       gera o ícone PNG sem PIL
build_deb.sh       empacota o .deb
```

## Observações

- Ideia **informativa** baseada em dados públicos da MEXC. "Setup pré-pump"
  é leitura estatística de acumulação, volume e força relativa — **nunca
  garante pump**. Pode haver pump vindo e também pode simplesmente não vir.
  Regra prática: espere o rompimento confirmado com volume; nunca entre "na
  euforia" de um pump já esticado.
- Funding rate, volume, onboard (idade) e classes são da API pública; nada de
  chave, sem cadastro.
- Servidor local em `127.0.0.1:porta aleatória`, sem exposição à rede.

## Licença

MIT — veja [LICENSE](LICENSE).
