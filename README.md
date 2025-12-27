# OrcaSlicer Filamentti-Profiilien Luontityökalu

AI:lla vahvistettu työkalu OrcaSlicer-filamenttiprofiilin luomiseen Creality K1C -tulostimelle.

## Ominaisuudet

- Heuristinen luominen – Nopea, ilmainen, ei API:a
- Ollama integraatio – Paikallinen LLM (llama2)
- OrcaSlicer-yhteensopiva - Tekee JSON-tiedostoja
- Valmis OrcaSlicer-ohjelmaan - OrcaSlicer --> File --> Import --> Import Configs

## Asennus

### Vaatimukset
- Python 3.9+
- (Valinnainen) Ollama + llama2 paikalliselle LLM:lle

### Ollaman asennus (paikallinen)
```bash
# Lataa Ollama: https://ollama.ai
ollama pull llama2
ollama serve
```

Ollama käynnistyy portilla `localhost:11434`.

## Käyttö

### 1. Perusesiasetusten käyttö
```bash
python profile_generator.py --name "Oma PLA" --material pla
```

Ohjelma kysyy suositeltua suutinlämpötilaa, jonka jälkeen se tuottaa profiilin.

### 2. Uusi materiaali (Heuristiikka)
```bash
python profile_generator.py --ai-new
```

Kysytään:
- Materiaali (esim. "ABS-CF")
- Suutimen lämpötila (esim. 250)
- Levyn lämpötila (esim. 60-100)
- Jäähdytystaso (low/medium/high)

**Nopea**, ei vaadi API:a.

### 3. Uusi materiaali (Ollama LLM)
```bash
python profile_generator.py --ai-new --use-ollama
```

Käyttää paikallista **llama2**-mallia:
- Ilmainen (paikallinen)
- Hitaampi (~30–60s ensimmäisellä kerralla)
- Yksityinen (ei pilveen menevää dataa)

## CLI-argumentit

| Argumentti | Kuvaus |
|-----------|--------|
| `--name` | Profiilin nimi |
| `--material` | Esiasetuksen materiaali (`pla`, `petg`) |
| `--ai-new` | Luo uusi materiaaliprofiili |
| `--use-ollama` | Käytä Ollamaa (paikallinen LLM) |
| `--pressure-advance` | Paineenhallinta (0.0–0.2) |
| `--output` | Tulostuskansio (oletus: `out_profiles`) |

## Esimerkit

### PLA-profiili 215°C:lla
```bash
python profile_generator.py --name "Mylar 215" --material pla
```

### ABS-CF (heuristiikka – nopea)
```bash
python profile_generator.py --ai-new
```

### ABS-CF (Ollama LLM – hitaampi, parempi)
```bash
python profile_generator.py --ai-new --use-ollama
```

### Mukautettu pressure advance
```bash
python profile_generator.py --ai-new --use-ollama --pressure-advance 0.05
```

## Tulosteen tuonti OrcaSlicer-ohjelmaan

1. Luo profiili (`out_profiles/` kansioon)
2. Avaa **OrcaSlicer**
3. **File** → **Import** → **Import Configs**
4. Valitse `.json` -tiedosto

## Materiaaliesiasetukset

| Materiaali | Suutin | Levy | Tuuletin | PA |
|-----------|--------|------|---------|-----|
| PLA | 210°C | 60°C | 95% | 0.0 |
| PETG | 240°C | 80°C | 45% | 0.02 |

## Vianmääritys

### "Connection refused" (Ollama)
- Tarkista: `ollama serve` käynnissä
- Testaa: `curl http://localhost:11434/api/tags`

### Timeout (Ollama)
- llama2 hidas ensimmäisellä suorituksella (~30–60s)
- Seuraavat kutsut nopeampia

## Rakennus

```
profile_generator.py      # Pääohjelma
README.md                 # Tämä dokumentaatio
out_profiles/             # Tulostetut JSON-profiilit
```