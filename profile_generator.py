"""
OrcaSlicer filamenttiprofiiin luonti Creality K1C:lle (0.4 mm suutin).
Filamenttipresetit Orca-tyylisessä JSON-muodossa, heuristiikan tai LLM:n tekeminä.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any
import re
import urllib.request


@dataclass
class MaterialPreset:
    name: str
    nozzle_temp: int
    bed_temp: int
    fan_speed: int
    fan_speed_min: int
    fan_speed_max: int
    flow_ratio: float
    density: float
    cost: float
    retraction_length: float
    retraction_speed: int
    default_pressure_advance: float


MATERIALS: Dict[str, MaterialPreset] = {
    "pla": MaterialPreset(
        name="PLA K1C",
        nozzle_temp=210,
        bed_temp=60,
        fan_speed=95,
        fan_speed_min=80,
        fan_speed_max=100,
        flow_ratio=1.0,
        density=1.24,
        cost=20,
        retraction_length=0.8,
        retraction_speed=35,
        default_pressure_advance=0.0,
    ),
    "petg": MaterialPreset(
        name="PETG K1C",
        nozzle_temp=240,
        bed_temp=80,
        fan_speed=45,
        fan_speed_min=30,
        fan_speed_max=60,
        flow_ratio=1.0,
        density=1.27,
        cost=25,
        retraction_length=1.0,
        retraction_speed=40,
        default_pressure_advance=0.02,
    ),
}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def slugify(text: str) -> str:
    """Create a filesystem-friendly slug for filenames."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "profile"


def parse_temp_hint(raw: str, fallback: int) -> int:
    """Parse a temp hint like '190-230' or '205'. Uses midpoint for ranges."""
    if not raw:
        return fallback
    try:
        if "-" in raw:
            parts = [p for p in re.split(r"[-–]", raw) if p.strip()]
            nums = [int(p.strip()) for p in parts]
            if len(nums) >= 2:
                return int(sum(nums[:2]) / 2)
        return int(raw)
    except ValueError:
        return fallback


def call_ollama(prompt: str, model: str = "llama2", endpoint: str = "http://localhost:11434/api/chat", timeout: float = 60.0) -> str:
    """Call Ollama LLM (local, free). Returns generated JSON content."""
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a 3D printing profile generator that replies with compact JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        response_text = resp.read().decode("utf-8")
    
    # Ollama streaming response parsing
    full_content = ""
    for line in response_text.strip().split("\n"):
        if line.strip():
            try:
                data = json.loads(line)
                if "message" in data and "content" in data["message"]:
                    full_content += data["message"]["content"]
            except json.JSONDecodeError:
                pass
    return full_content if full_content else response_text


def ai_generate_material_preset(name: str, nozzle_hint: int, bed_hint: int, fan_pref: str) -> MaterialPreset:
    """Generate a fresh material preset using heuristics from user hints."""
    nozzle_temp = int(clamp(nozzle_hint, 160, 290))
    bed_temp = int(clamp(bed_hint, 30, 120))

    fan_pref = fan_pref.lower()
    if fan_pref == "high":
        fan_speed, fan_min, fan_max = 90, 70, 100
        retraction_len = 0.8
    elif fan_pref == "low":
        fan_speed, fan_min, fan_max = 40, 25, 60
        retraction_len = 1.0
    else:
        fan_speed, fan_min, fan_max = 60, 40, 80
        retraction_len = 0.9

    # Suuntaa-antava tiheys
    density = 1.24
    if "cf" in name.lower() or "carbon" in name.lower():
        density = 1.3
    if "pa" in name.lower() or "nylon" in name.lower():
        density = max(density, 1.14)

    cost = 25

    return MaterialPreset(
        name=name,
        nozzle_temp=nozzle_temp,
        bed_temp=bed_temp,
        fan_speed=fan_speed,
        fan_speed_min=fan_min,
        fan_speed_max=fan_max,
        flow_ratio=1.0,
        density=density,
        cost=cost,
        retraction_length=retraction_len,
        retraction_speed=38,
        default_pressure_advance=0.02 if fan_pref in {"medium", "low"} else 0.0,
    )


def ollama_generate_material(name: str, nozzle_hint: int, bed_hint: int, fan_pref: str) -> MaterialPreset:
    """Use Ollama (local LLM) to propose a material preset, then clamp to safe bounds."""
    prompt = (
        "Create 3D printing filament profile JSON with keys: "
        "nozzle_temp, bed_temp, fan_speed, fan_speed_min, fan_speed_max, flow_ratio, "
        "retraction_length, retraction_speed, pressure_advance. "
        f"Filament name: {name}. Suggested nozzle temp: {nozzle_hint}. Bed temp: {bed_hint}. "
        f"Cooling level: {fan_pref} (low/medium/high). "
        "Return ONLY JSON, no prose. Keep values realistic for FDM."
    )

    raw = call_ollama(prompt)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"LLM did not return valid JSON: {raw}")

    def get(key, default):
        return data.get(key, default)

    nozzle_temp = int(clamp(get("nozzle_temp", nozzle_hint), 160, 290))
    bed_temp = int(clamp(get("bed_temp", bed_hint), 30, 120))

    fan_speed = clamp(get("fan_speed", 60), 0, 100)
    fan_min = clamp(get("fan_speed_min", max(0, fan_speed - 20)), 0, 100)
    fan_max = clamp(get("fan_speed_max", max(fan_speed, 60)), 0, 100)

    flow_ratio = clamp(get("flow_ratio", 1.0), 0.9, 1.1)
    retraction_length = clamp(get("retraction_length", 0.9), 0.4, 1.8)
    retraction_speed = clamp(get("retraction_speed", 38), 15, 55)
    pressure_advance = clamp(get("pressure_advance", 0.02), 0.0, 0.2)

    density = 1.24
    if "cf" in name.lower() or "carbon" in name.lower():
        density = 1.3

    cost = 25

    return MaterialPreset(
        name=name,
        nozzle_temp=int(nozzle_temp),
        bed_temp=int(bed_temp),
        fan_speed=int(fan_speed),
        fan_speed_min=int(fan_min),
        fan_speed_max=int(fan_max),
        flow_ratio=float(flow_ratio),
        density=density,
        cost=cost,
        retraction_length=float(retraction_length),
        retraction_speed=int(retraction_speed),
        default_pressure_advance=float(pressure_advance),
    )


def ai_tune_filament(material: MaterialPreset, suggested_temp: int) -> Dict[str, Any]:
    """Heuristic tuner that adjusts temps, fan, and flow based on the hint."""
    base = material

    # Lämpötila rajattu turvalliselle alueelle perusasetuksen perusteella.
    nozzle_temp = int(clamp(suggested_temp, base.nozzle_temp - 10, base.nozzle_temp + 15))

    # Bed temp hieman nostettu, jos ajetaan kuumempana kuin perusasetukset.
    bed_temp = base.bed_temp
    if nozzle_temp > base.nozzle_temp + 5:
        bed_temp = min(base.bed_temp + 5, base.bed_temp + 10)

    # Tuulettimien asetukset voivat vaihdella materiaalin mukaan.
    if "PLA" in base.name:
        fan_speed = clamp(base.fan_speed - (nozzle_temp - base.nozzle_temp) * 2, 80, 100)
        fan_min = clamp(base.fan_speed_min - (nozzle_temp - base.nozzle_temp), 70, 100)
        fan_max = 100
    else:  # PETG polku
        fan_speed = clamp(base.fan_speed - (nozzle_temp - base.nozzle_temp), 25, 65)
        fan_min = clamp(base.fan_speed_min - (nozzle_temp - base.nozzle_temp) * 0.5, 20, 60)
        fan_max = clamp(base.fan_speed_max - (nozzle_temp - base.nozzle_temp) * 0.5, 40, 80)

    # Flow ratio tweak: hieman pienempi flow ratio kuumemmalla, hieman suurempi viileämmällä.
    delta = nozzle_temp - base.nozzle_temp
    flow_ratio = clamp(base.flow_ratio - delta * 0.002, 0.96, 1.04)

    # Pressure advance jätetty ennalleen, ellei käyttäjä ohita CLI:n kautta.
    return {
        "nozzle_temp": nozzle_temp,
        "bed_temp": bed_temp,
        "fan_speed": int(fan_speed),
        "fan_speed_min": int(fan_min),
        "fan_speed_max": int(fan_max),
        "flow_ratio": round(flow_ratio, 3),
        "pressure_advance": base.default_pressure_advance,
    }


def default_volumetric_speed(material_name: str) -> float:
    name = material_name.lower()
    if "petg" in name:
        return 18.0
    return 20.0


def build_filament_profile(
    tuned: Dict[str, Any],
    pressure_advance: float,
    profile_name: str,
) -> Dict[str, Any]:
    """Build OrcaSlicer filament profile JSON (simplified)."""
    nozzle_temp = tuned["nozzle_temp"]
    bed_temp = tuned["bed_temp"]

    def as_arr(val: Any) -> list:
        return [str(val)]

    return {
        "name": profile_name,
        "filament_settings_id": profile_name,
        "inherits": "Creality Generic PLA",
        "nozzle_temperature": as_arr(nozzle_temp),
        "hot_plate_temp": as_arr(bed_temp),
        "additional_cooling_fan_speed": as_arr(int(tuned["fan_speed_max"])),
        "pressure_advance": as_arr(pressure_advance),
        "enable_pressure_advance": as_arr("1" if pressure_advance > 0 else "0"),
        "version": "1.9.0.2",
    }


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OrcaSlicer filamentprofiilien luontityökalu (Creality K1C)")
    parser.add_argument("--name", type=str, help="Profiilin nimi")
    parser.add_argument("--material", choices=MATERIALS.keys(), default="pla", help="Materiaalin esiasetukset")
    parser.add_argument("--pressure-advance", type=float, default=None, help="Paineen ennakko (0.0-0.2)")
    parser.add_argument("--ai-new", action="store_true", help="Luo uusi materiaaliprofiili heuristiikalla")
    parser.add_argument("--use-ollama", action="store_true", help="Käytä Ollamaa (paikallinen LLM, ilmainen)")
    parser.add_argument("--output", type=Path, default=Path("out_profiles"), help="Tulostuskansio")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    pressure_advance = args.pressure_advance
    if pressure_advance is not None:
        pressure_advance = clamp(pressure_advance, 0.0, 0.2)

    profile_name = args.name.strip() if args.name else input("Profiilin nimi: ").strip()
    while not profile_name:
        profile_name = input("Profiilin nimi (pakollinen): ").strip()

    if args.ai_new:
        custom_material_name = input("Materiaali (esim. PLA-CF, ABS+): ").strip() or "Custom"
        temp_hint_raw = input("Suositeltu suutinlämpötila (esim. 190-230): ").strip()
        bed_hint_raw = input("Suositeltu levyn lämpötila (esim. 50-80, tyhjä=auto): ").strip()
        fan_pref = input("Jäähdytys (low/medium/high, oletus medium): ").strip().lower() or "medium"

        temp_hint = parse_temp_hint(temp_hint_raw, 210)
        bed_hint = parse_temp_hint(bed_hint_raw, 60) if bed_hint_raw else 60
        fan_pref = fan_pref if fan_pref in {"low", "medium", "high"} else "medium"

        if args.use_ollama:
            print("Käytössä: Ollama (llama2) - odotetaan vastausta (~30-60s)...")
            material = ollama_generate_material(
                custom_material_name,
                nozzle_hint=temp_hint,
                bed_hint=bed_hint,
                fan_pref=fan_pref,
            )
        else:
            material = ai_generate_material_preset(custom_material_name, temp_hint, bed_hint, fan_pref)

        tuned_temp = temp_hint
        material_key = slugify(custom_material_name)
    else:
        material_key = args.material
        if args.material is None:
            material_key = input(f"Valitse materiaali ({'/'.join(MATERIALS.keys())}): ").strip().lower()
        while material_key not in MATERIALS:
            material_key = input(f"Valitse: {', '.join(MATERIALS.keys())}: ").strip().lower()

        material = MATERIALS[material_key]
        tuned_temp = material.nozzle_temp
        entered = input(f"Suositeltu suutinlämpötila materiaalille {material_key} (esim. 190-230): ").strip()
        if entered:
            tuned_temp = parse_temp_hint(entered, material.nozzle_temp)

    slug = slugify(profile_name)
    tuned = ai_tune_filament(material, int(tuned_temp))
    pressure_eff = pressure_advance if pressure_advance is not None else tuned["pressure_advance"]

    filament = build_filament_profile(
        tuned=tuned,
        pressure_advance=pressure_eff,
        profile_name=profile_name,
    )

    out_path = args.output / f"{slug}.json"
    write_json(out_path, filament)

    print(f"Profiili tallennettu: {out_path.resolve()}")
    print("Tuo OrcaSlicer-ohjelmaan: File → Import → Import Configs, valitse JSON-tiedosto.")


if __name__ == "__main__":
    main()
