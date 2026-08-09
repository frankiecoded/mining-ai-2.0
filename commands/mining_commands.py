import math
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("ai_os.commands.mining")


def calculate_grade(args: str) -> str:
    """Calculate cut-off grade, gold value, or recovery from parameters.

    Usage:
        /grade value <grams_per_tonne> <tonnes> <recovery_pct>
        /grade cog <mining_cost> <processing_cost> <ga_cost> <gold_price_usd> <recovery_pct>
        /grade conversion <grams_per_tonne>
        /grade dilution <bankruptcy_grade> <dilution_pct>
        /grade reconciliation <planned_grade> <actual_grade> <planned_tonnes> <actual_tonnes>
    """
    parts = args.strip().split()
    if not parts:
        return _grade_help()

    sub = parts[0].lower()

    if sub == "value":
        return _grade_value(parts[1:])
    elif sub == "cog":
        return _grade_cog(parts[1:])
    elif sub == "conversion":
        return _grade_conversion(parts[1:])
    elif sub == "dilution":
        return _grade_dilution(parts[1:])
    elif sub == "reconciliation":
        return _grade_reconciliation(parts[1:])
    else:
        return _grade_help()


def _grade_help() -> str:
    return """*Grade Calculator Usage:*

`/grade value <g/t> <tonnes> <recovery%>`
  Calculate contained gold value
  Example: /grade value 5.2 10000 93

`/grade cog <mining> <processing> <ga> <gold_price> <recovery%>`
  Calculate cut-off grade
  Example: /grade cog 8 25 5 3250 95

`/grade conversion <g/t>`
  Convert g/t to oz/tonne
  Example: /grade conversion 5.2

`/grade dilution <bankruptcy_grade> <dilution%>`
  Apply mining dilution factor
  Example: /grade dilution 2.5 15

`/grade reconciliation <planned_g/t> <actual_g/t> <planned_t> <actual_t>`
  Reconcile planned vs actual
  Example: /grade reconciliation 1.5 1.3 50000 48000"""


def _grade_value(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /grade value <g/t> <tonnes> <recovery%>\nExample: /grade value 5.2 10000 93"
    try:
        g_t = float(parts[0])
        tonnes = float(parts[1])
        recovery = float(parts[2]) / 100.0
        gold_oz = g_t * tonnes * recovery / 31.1035
        gold_usd = gold_oz * 3250
        gold_kg = g_t * tonnes * recovery / 1000.0

        return f"""*Grade Value Calculation*

*Inputs:*
  Grade: {g_t} g/t
  Tonnage: {tonnes:,.0f} t
  Recovery: {recovery*100:.1f}%

*Results:*
  Contained metal: {gold_kg:.2f} kg ({gold_oz:,.1f} oz)
  Gross value: ${gold_usd:,.0f}
  Value per tonne: ${gold_usd/tonnes:,.2f}/t

*Formula:* grade × tonnes × recovery / 31.1035 = oz
*Assumed gold price:* $3,250/oz"""
    except ValueError:
        return "Invalid numbers. Use: /grade value 5.2 10000 93"


def _grade_cog(parts: List[str]) -> str:
    if len(parts) < 5:
        return "Usage: /grade cog <mining_cost> <processing_cost> <ga_cost> <gold_price> <recovery%>\nExample: /grade cog 8 25 5 3250 95"
    try:
        mining = float(parts[0])
        processing = float(parts[1])
        ga = float(parts[2])
        gold_price = float(parts[3])
        recovery = float(parts[4]) / 100.0

        total_cost = mining + processing + ga
        cog_oz_t = total_cost / (gold_price * recovery)
        cog_g_t = cog_oz_t * 31.1035

        return f"""*Cut-Off Grade Calculation*

*Inputs:*
  Mining cost: ${mining}/t
  Processing cost: ${processing}/t
  G&A cost: ${ga}/t
  Gold price: ${gold_price:,.0f}/oz
  Recovery: {recovery*100:.1f}%

*Results:*
  Total cost: ${total_cost}/t
  COG: {cog_oz_t:.4f} oz/t = {cog_g_t:.3f} g/t

*Interpretation:*
  Grades below {cog_g_t:.3f} g/t are sub-economic at these costs.
  For max NPV use marginal cost only: ${mining}/t → COG = {mining/(gold_price*recovery)*31.1035:.3f} g/t

*Formula:* COG (oz/t) = Total Cost / (Recovery × Price)"""
    except ValueError:
        return "Invalid numbers. Use: /grade cog 8 25 5 3250 95"


def _grade_conversion(parts: List[str]) -> str:
    if not parts:
        return "Usage: /grade conversion <grams_per_tonne>\nExample: /grade conversion 5.2"
    try:
        g_t = float(parts[0])
        oz_t = g_t / 31.1035
        pct = g_t / 10.0
        lb_t = g_t * 0.00220462

        return f"""*Grade Conversion*

{g_t} g/t = {oz_t:.4f} oz/t
         = {pct:.4f}%
         = {lb_t:.6f} lb/t

*Reference:*
  1 troy oz = 31.1035 g
  1 g/t = 0.032151 oz/t
  1 g/t = 0.1%"""
    except ValueError:
        return "Invalid number. Use: /grade conversion 5.2"


def _grade_dilution(parts: List[str]) -> str:
    if len(parts) < 2:
        return "Usage: /grade dilution <bankruptcy_grade> <dilution%>\nExample: /grade dilution 2.5 15"
    try:
        grade = float(parts[0])
        dilution = float(parts[1]) / 100.0
        diluted_grade = grade * (1.0 - dilution)
        waste_ratio = dilution / (1.0 - dilution)

        return f"""*Dilution Adjustment*

*Inputs:*
  Bankruptcy grade: {grade} g/t
  Dilution: {dilution*100:.0f}%

*Results:*
  Diluted grade: {diluted_grade:.3f} g/t
  Waste-to-ore ratio: {waste_ratio:.2f}:1

*Formula:* Diluted grade = Grade × (1 - Dilution)
*Loss:* {(grade - diluted_grade):.3f} g/t ({dilution*100:.0f}%)"""
    except ValueError:
        return "Invalid numbers. Use: /grade dilution 2.5 15"


def _grade_reconciliation(parts: List[str]) -> str:
    if len(parts) < 4:
        return "Usage: /grade reconciliation <planned_g/t> <actual_g/t> <planned_tonnes> <actual_tonnes>\nExample: /grade reconciliation 1.5 1.3 50000 48000"
    try:
        planned_g = float(parts[0])
        actual_g = float(parts[1])
        planned_t = float(parts[2])
        actual_t = float(parts[3])

        grade_var = ((actual_g - planned_g) / planned_g) * 100
        tonnage_var = ((actual_t - planned_t) / planned_t) * 100
        planned_metal = planned_g * planned_t / 31.1035
        actual_metal = actual_g * actual_t / 31.1035
        metal_var = ((actual_metal - planned_metal) / planned_metal) * 100
        status = "ON TRACK" if abs(metal_var) <= 10 else "VARIANCE ALERT"

        return f"""*Grade Reconciliation*

              Planned       Actual       Variance
Grade:       {planned_g:.3f} g/t    {actual_g:.3f} g/t    {grade_var:+.1f}%
Tonnage:     {planned_t:,.0f} t      {actual_t:,.0f} t      {tonnage_var:+.1f}%
Metal (oz):  {planned_metal:,.1f}     {actual_metal:,.1f}     {metal_var:+.1f}%

Status: *{status}*
{'Grade control model is accurate.' if abs(grade_var) <= 5 else 'Investigate grade model - significant grade variance.'}
{'Tonnage within acceptable range.' if abs(tonnage_var) <= 10 else 'Check blasting/mucking factors.'}"""
    except ValueError:
        return "Invalid numbers."


def calculate_blast(args: str) -> str:
    """Blast design calculator.

    Usage:
        /blast hole <burden> <spacing> <depth> <hole_diameter>
        /blast powder <burden> <spacing> <depth> <powder_factor>
        /blast timing <holes> <delay_ms>
        /blast vibration <distance> <max_ppv>
    """
    parts = args.strip().split()
    if not parts:
        return _blast_help()

    sub = parts[0].lower()

    if sub == "hole":
        return _blast_hole(parts[1:])
    elif sub == "powder":
        return _blast_powder(parts[1:])
    elif sub == "timing":
        return _blast_timing(parts[1:])
    elif sub == "vibration":
        return _blast_vibration(parts[1:])
    else:
        return _blast_help()


def _blast_help() -> str:
    return """*Blast Design Calculator Usage:*

`/blast hole <burden_m> <spacing_m> <depth_m> <hole_dia_mm>`
  Calculate hole volume and explosive charge
  Example: /blast hole 3 3.5 10 89

`/blast powder <burden_m> <spacing_m> <depth_m> <powder_factor_kg/t>`
  Calculate total explosive requirement
  Example: /blast powder 3 3.5 10 0.4

`/blast timing <num_holes> <delay_ms>`
  Calculate blast timing pattern
  Example: /blast timing 50 25

`/blast vibration <distance_m> <max_ppv_mm_s>`
  Calculate scaled distance for vibration limit
  Example: /blast vibration 200 25"""


def _blast_hole(parts: List[str]) -> str:
    if len(parts) < 4:
        return "Usage: /blast hole <burden> <spacing> <depth> <hole_diameter_mm>\nExample: /blast hole 3 3.5 10 89"
    try:
        burden = float(parts[0])
        spacing = float(parts[1])
        depth = float(parts[2])
        dia = float(parts[3])

        radius = (dia / 1000.0) / 2.0
        hole_vol = math.pi * radius**2 * depth
        rock_vol = burden * spacing * depth
        rock_mass = rock_vol * 2.7
        charge_kg = hole_vol * 1.1 * 1.0
        pf = charge_kg / rock_mass if rock_mass > 0 else 0

        return f"""*Blast Hole Design*

*Inputs:*
  Burden: {burden} m | Spacing: {spacing} m
  Depth: {depth} m | Hole diameter: {dia} mm

*Results:*
  Hole volume: {hole_vol:.3f} m³
  Rock volume per hole: {rock_vol:.1f} m³
  Rock mass per hole: {rock_mass:.1f} t (SG=2.7)
  Estimated charge: {charge_kg:.1f} kg
  Powder factor: {pf:.3f} kg/t

*Check:*
  Burden/Dia ratio: {burden/(dia/1000):.1f} (optimal: 20-35)
  Spacing/Burden ratio: {spacing/burden:.2f} (optimal: 1.1-1.5)
  Hole length/Diameter: {depth*1000/dia:.0f} (optimal: 30-60)"""
    except ValueError:
        return "Invalid numbers."


def _blast_powder(parts: List[str]) -> str:
    if len(parts) < 4:
        return "Usage: /blast powder <burden> <spacing> <depth> <powder_factor>\nExample: /blast powder 3 3.5 10 0.4"
    try:
        burden = float(parts[0])
        spacing = float(parts[1])
        depth = float(parts[2])
        pf = float(parts[3])

        rock_mass = burden * spacing * depth * 2.7
        total_explosive = rock_mass * pf

        return f"""*Explosive Requirement*

*Inputs:*
  Pattern: {burden} × {spacing} m, Depth: {depth} m
  Powder factor: {pf} kg/t

*Results:*
  Rock mass per hole: {rock_mass:.1f} t
  Explosive per hole: {rock_mass*pf:.1f} kg
  Total explosive: {total_explosive:.1f} kg

*Emulsion specs:*
  Bulk density: 1,100-1,200 kg/m³
  Velocity of detonation: 4,500-5,500 m/s
  Water resistance: Excellent"""
    except ValueError:
        return "Invalid numbers."


def _blast_timing(parts: List[str]) -> str:
    if len(parts) < 2:
        return "Usage: /blast timing <num_holes> <delay_ms>\nExample: /blast timing 50 25"
    try:
        holes = int(parts[0])
        delay = int(parts[1])
        total_time = holes * delay
        holes_per_row = min(holes, 10)
        rows = math.ceil(holes / holes_per_row)

        return f"""*Blast Timing*

*Inputs:*
  Total holes: {holes}
  Inter-hole delay: {delay} ms
  Rows: {rows} × {holes_per_row} holes

*Timing:*
  Total blast duration: {total_time/1000:.1f} s
  Row delay: {delay*3} ms (3× inter-hole)
  Vibration control: Good (staggered initiation)

*Recommendations:*
  - Use 25ms inter-hole, 65ms row delay for hard rock
  - Use 17ms inter-hole, 42ms row delay for soft ground
  - Maximum 8-10 holes per delay for PPV control"""
    except ValueError:
        return "Invalid numbers."


def _blast_vibration(parts: List[str]) -> str:
    if len(parts) < 2:
        return "Usage: /blast vibration <distance_m> <max_ppv>\nExample: /blast vibration 200 25"
    try:
        distance = float(parts[0])
        max_ppv = float(parts[1])
        k = 500
        alpha = 1.5
        max_charge = (max_ppv / k) ** (1 / alpha) * distance

        return f"""*Vibration Analysis*

*Inputs:*
  Distance: {distance} m
  Max PPV: {max_ppv} mm/s

*Results:*
  Max charge per delay: {max_charge:.1f} kg
  Scaled distance: {distance / max_charge**0.33:.1f} m/kg^0.33

*PPV Thresholds:*
  < 5 mm/s: Safe for all structures
  5-12 mm/s: Residential buildings
  12-25 mm/s: Industrial structures
  25-50 mm/s: Reinforced concrete
  > 50 mm/s: Damage risk - reduce charge

*Control measures:*
  - Reduce charge per delay
  - Use electronic detonators
  - Monitor with seismograph"""
    except ValueError:
        return "Invalid numbers."


def calculate_cost(args: str) -> str:
    """Mining cost calculator.

    Usage:
        /cost aisc <direct_cost> <indirect_cost> <sustaining_capex> <milled_tonnes> <_gold_oz>
        /cost per_oz <total_cost_usd> <gold_oz>
        /cost per_tonne <total_cost_usd> <tonnes>
        /cost comparison <cost_a> <tonnes_a> <cost_b> <tonnes_b>
    """
    parts = args.strip().split()
    if not parts:
        return _cost_help()

    sub = parts[0].lower()

    if sub == "aisc":
        return _cost_aisc(parts[1:])
    elif sub == "per_oz":
        return _cost_per_oz(parts[1:])
    elif sub == "per_tonne":
        return _cost_per_tonne(parts[1:])
    elif sub == "comparison":
        return _cost_comparison(parts[1:])
    else:
        return _cost_help()


def _cost_help() -> str:
    return """*Cost Calculator Usage:*

`/cost aisc <direct> <indirect> <sustaining_capex> <tonnes> <gold_oz>`
  Calculate All-In Sustaining Cost
  Example: /cost aisc 18000000 5000000 3000000 500000 120000

`/cost per_oz <total_cost_usd> <gold_oz>`
  Cost per ounce produced
  Example: /cost per_oz 26000000 120000

`/cost per_tonne <total_cost_usd> <tonnes_milled>`
  Cost per tonne processed
  Example: /cost per_tonne 26000000 500000

`/cost comparison <cost_a> <tonnes_a> <cost_b> <tonnes_b>`
  Compare two mining operations
  Example: /cost comparison 25 500000 30 800000"""


def _cost_aisc(parts: List[str]) -> str:
    if len(parts) < 5:
        return "Usage: /cost aisc <direct> <indirect> <sustaining_capex> <tonnes> <gold_oz>\nExample: /cost aisc 18000000 5000000 3000000 500000 120000"
    try:
        direct = float(parts[0])
        indirect = float(parts[1])
        sustaining = float(parts[2])
        tonnes = float(parts[3])
        gold_oz = float(parts[4])

        total = direct + indirect + sustaining
        aisc_per_oz = total / gold_oz if gold_oz > 0 else 0
        cost_per_t = total / tonnes if tonnes > 0 else 0
        opex_per_t = (direct + indirect) / tonnes if tonnes > 0 else 0
        margin_per_oz = 3250 - aisc_per_oz
        margin_pct = (margin_per_oz / 3250 * 100) if aisc_per_oz > 0 else 0

        return f"""*All-In Sustaining Cost (AISC)*

*Cost Breakdown:*
  Mining cost:        ${direct:>15,.0f}
  Processing + G&A:   ${indirect:>15,.0f}
  Sustaining capex:   ${sustaining:>15,.0f}
  ─────────────────────────────
  Total AISC:         ${total:>15,.0f}

*Per-Unit Metrics:*
  AISC/oz:            ${aisc_per_oz:>10,.2f}
  Total cost/t:       ${cost_per_t:>10,.2f}
  Opex/t:             ${opex_per_t:>10,.2f}

*Margin Analysis (Gold @ $3,250/oz):*
  Margin/oz:          ${margin_per_oz:>10,.2f}
  Margin %:           {margin_pct:>9.1f}%
  Annual gold revenue: ${gold_oz*3250:>14,.0f}

*Classification:*
  {'Elite (<$800/oz)' if aisc_per_oz < 800 else 'Low-cost ($800-1000/oz)' if aisc_per_oz < 1000 else 'Mid-tier ($1000-1200/oz)' if aisc_per_oz < 1200 else 'High-cost (>$1200/oz)'}"""
    except ValueError:
        return "Invalid numbers."


def _cost_per_oz(parts: List[str]) -> str:
    if len(parts) < 2:
        return "Usage: /cost per_oz <total_cost_usd> <gold_oz>\nExample: /cost per_oz 26000000 120000"
    try:
        total = float(parts[0])
        gold_oz = float(parts[1])
        per_oz = total / gold_oz if gold_oz > 0 else 0
        margin = 3250 - per_oz

        return f"""*Cost Per Ounce*

  Total cost: ${total:,.0f}
  Gold produced: {gold_oz:,.0f} oz
  Cost per oz: ${per_oz:,.2f}
  Margin/oz: ${margin:,.2f}
  Margin: {margin/3250*100:.1f}%"""
    except ValueError:
        return "Invalid numbers."


def _cost_per_tonne(parts: List[str]) -> str:
    if len(parts) < 2:
        return "Usage: /cost per_tonne <total_cost_usd> <tonnes>\nExample: /cost per_tonne 26000000 500000"
    try:
        total = float(parts[0])
        tonnes = float(parts[1])
        per_t = total / tonnes if tonnes > 0 else 0

        return f"""*Cost Per Tonne*

  Total cost: ${total:,.0f}
  Tonnes processed: {tonnes:,.0f} t
  Cost per tonne: ${per_t:,.2f}

*Benchmarks (open pit gold):*
  Mining: $2-8/t | Processing: $15-25/t | G&A: $3-8/t
  Total: $20-40/t (excluding sustaining capex)"""
    except ValueError:
        return "Invalid numbers."


def _cost_comparison(parts: List[str]) -> str:
    if len(parts) < 4:
        return "Usage: /cost comparison <cost_a> <tonnes_a> <cost_b> <tonnes_b>\nExample: /cost comparison 25 500000 30 800000"
    try:
        cost_a = float(parts[0])
        tonnes_a = float(parts[1])
        cost_b = float(parts[2])
        tonnes_b = float(parts[3])

        total_a = cost_a * tonnes_a
        total_b = cost_b * tonnes_b
        diff_pct = ((cost_b - cost_a) / cost_a) * 100

        return f"""*Operation Comparison*

           Operation A    Operation B
Cost/t:    ${cost_a:>10,.2f}     ${cost_b:>10,.2f}
Tonnes:    {tonne_a:>10,.0f}     {tonnes_b:>10,.0f}
Total:     ${total_a:>12,.0f}    ${total_b:>12,.0f}

Difference: {diff_pct:+.1f}%
{'A is more cost-efficient' if cost_a < cost_b else 'B is more cost-efficient'}"""
    except ValueError:
        return "Invalid numbers."


def calculate_geology(args: str) -> str:
    """Geology helper - mineral properties, rock types, exploration guidance.

    Usage:
        /geology mineral <name>
        /geology rock <type>
        /geology exploration <region>
    """
    parts = args.strip().split()
    if not parts:
        return _geology_help()

    sub = parts[0].lower()

    if sub == "mineral":
        return _geology_mineral(parts[1:])
    elif sub == "rock":
        return _geology_rock(parts[1:])
    elif sub == "exploration":
        return _geology_exploration(parts[1:])
    else:
        return _geology_help()


def _geology_help() -> str:
    return """*Geology Helper Usage:*

`/geology mineral <name>`
  Properties of a mineral
  Example: /geology mineral gold

`/geology rock <type>`
  Rock type information
  Example: /geology rock granite

`/geology exploration <region>`
  Exploration guidance for region
  Example: /geology exploration tanzania"""


MINERALS_DB = {
    "gold": {
        "formula": "Au", "system": "Cubic", "hardness": "2.5-3",
        "density": "19.3 g/cm³", "color": "Golden yellow",
        "luster": "Metallic", "streak": "Golden yellow",
        "cleavage": "None", "fracture": "Hackly",
        "occurrences": "Hydrothermal veins, placers, epithermal, orogenic",
        "associates": "Quartz, pyrite, arsenopyrite, chalcopyrite, galena",
        "specific_gravity": "19.3",
        "mp": "1064°C",
        "tests": "Color, streak, specific gravity, fire assay, ICP-MS"
    },
    "tanzanite": {
        "formula": "Ca₂Al₃(SiO₄)₃(OH)", "system": "Orthorhombic", "hardness": "6.5-7",
        "density": "3.35 g/cm³", "color": "Blue-violet",
        "luster": "Vitreous", "streak": "White",
        "cleavage": "Perfect", "fracture": "Conchoidal to uneven",
        "occurrences": "Metamorphic rocks, Merelani Hills Tanzania only",
        "associates": "Graphite, calcite, diopside, wollastonite",
        "tests": "Refractive index, dichroism, absorption spectrum"
    },
    "diamond": {
        "formula": "C", "system": "Cubic", "hardness": "10",
        "density": "3.52 g/cm³", "color": "Colorless to yellow/brown",
        "luster": "Adamantine", "streak": "None",
        "cleavage": "Perfect octahedral", "fracture": "Conchoidal",
        "occurrences": "Kimberlite pipes, lamproites, alluvial deposits",
        "associates": "Garnet, olivine, ilmenite, chromite, pyroxene",
        "tests": "Thermal conductivity, UV fluorescence, specific gravity"
    },
    "ruby": {
        "formula": "Al₂O₃ (Cr-bearing)", "system": "Trigonal", "hardness": "9",
        "density": "4.0 g/cm³", "color": "Red",
        "luster": "Vitreous to adamantine", "streak": "White",
        "cleavage": "None", "fracture": "Conchoidal to uneven",
        "occurrences": "Metamorphic marbles, schists, pegmatites",
        "associates": "Spinel, garnet, kyanite, calcite, mica",
        "tests": "Fluorescence, absorption spectrum, inclusion analysis"
    },
    "emerald": {
        "formula": "Be₃Al₂(SiO₃)₆", "system": "Hexagonal", "hardness": "7.5-8",
        "density": "2.7 g/cm³", "color": "Green",
        "luster": "Vitreous", "streak": "None",
        "cleavage": "Imperfect", "fracture": "Conchoidal",
        "occurrences": "Pegmatites, hydrothermal veins, schists",
        "associates": "Beryl, feldspar, quartz, mica, tourmaline",
        "tests": "Refractive index, spectroscopy, inclusion study"
    },
    "sapphire": {
        "formula": "Al₂O₃ (Fe/Ti-bearing)", "system": "Trigonal", "hardness": "9",
        "density": "4.0 g/cm³", "color": "Blue (also pink, yellow, orange, green)",
        "luster": "Vitreous to adamantine", "streak": "White",
        "cleavage": "None", "fracture": "Conchoidal to uneven",
        "occurrences": "Metamorphic corundum deposits, alluvial placers",
        "associates": "Spinel, garnet, zircon, ilmenite",
        "tests": "Fluorescence, absorption lines, dichroism"
    },
    "spinel": {
        "formula": "MgAl₂O₄", "system": "Cubic", "hardness": "8",
        "density": "3.6 g/cm³", "color": "Red, blue, green, black, pink",
        "luster": "Vitreous", "streak": "White",
        "cleavage": "None", "fracture": "Conchoidal",
        "occurrences": "Metamorphic rocks, placer deposits, limestone",
        "associates": "Corundum, garnet, chrysoberyl, tourmaline",
        "tests": "Spectroscopy, inclusion analysis, specific gravity"
    },
    "columbite_tantalite": {
        "formula": "(Fe,Mn)(Nb,Ta)₂O₆", "system": "Orthorhombic", "hardness": "6",
        "density": "5.2-8.0 g/cm³", "color": "Black to brown",
        "luster": "Submetallic", "streak": "Dark reddish-brown",
        "cleavage": "Distinct", "fracture": "Subconchoidal",
        "occurrences": "Granite pegmatites, alluvial deposits",
        "associates": "Tourmaline, lepidolite, feldspar, quartz",
        "tests": "XRF, specific gravity, acid tests, electron microprobe"
    },
    "chrysoberyl": {
        "formula": "BeAl₂O₄", "system": "Orthorhombic", "hardness": "8.5",
        "density": "3.75 g/cm³", "color": "Yellow-green to brown",
        "luster": "Vitreous", "streak": "None",
        "cleavage": "Distinct", "fracture": "Conchoidal",
        "occurrences": "Pegmatites, metamorphic rocks",
        "associates": "Beryl, corundum, spinel, tourmaline",
        "tests": "Cat's eye effect, alexandrite color change, refraction"
    },
    "ilmenite": {
        "formula": "FeTiO₃", "system": "Trigonal", "hardness": "5-6",
        "density": "4.7 g/cm³", "color": "Black",
        "luster": "Metallic to submetallic", "streak": "Black to brownish-red",
        "cleavage": "None", "fracture": "Conchoidal to subconchoidal",
        "occurrences": "Igneous rocks, heavy mineral sands, placer deposits",
        "associates": "Magnetite, rutile, zircon, garnet, monazite",
        "tests": "Magnetic, acid test (HCl), titanium content"
    },
    "monazite": {
        "formula": "(Ce,La,Th)PO₄", "system": "Monoclinic", "hardness": "5-5.5",
        "density": "4.6-5.4 g/cm³", "color": "Yellow, brown, reddish",
        "luster": "Resinous to waxy", "streak": "White",
        "cleavage": "Distinct", "fracture": "Conchoidal",
        "occurrences": "Granite pegmatites, placer deposits, beach sands",
        "associates": "Xenotime, zircon, ilmenite, rutile, garnet",
        "tests": "Radioactive (thorium), XRF, acid test"
    },
    "xenotime": {
        "formula": "YPO₄", "system": "Tetragonal", "hardness": "4-5",
        "density": "4.4-5.1 g/cm³", "color": "Yellow-brown, reddish-brown",
        "luster": "Resinous to waxy", "streak": "White",
        "cleavage": "Perfect", "fracture": "Uneven",
        "occurrences": "Granite pegmatites, placer deposits",
        "associates": "Monazite, zircon, ilmenite, feldspar",
        "tests": "XRF, radioactive, electron microprobe"
    },
    "cassiterite": {
        "formula": "SnO₂", "system": "Tetragonal", "hardness": "6-7",
        "density": "6.98 g/cm³", "color": "Brown, black, yellow, red",
        "luster": "Adamantine to vitreous", "streak": "White to brown",
        "cleavage": "Indistinct", "fracture": "Subconchoidal to uneven",
        "occurrences": "Granite pegmatites, hydrothermal veins, placer deposits",
        "associates": "Wolframite, scheelite, fluorite, mica, feldspar",
        "tests": "High specific gravity, XRF, acid test"
    },
    "wolframite": {
        "formula": "(Fe,Mn)WO₄", "system": "Monoclinic", "hardness": "4.5-5.5",
        "density": "7.1-7.5 g/cm³", "color": "Black to brownish-black",
        "luster": "Submetallic", "streak": "Reddish-brown to brown",
        "cleavage": "Perfect", "fracture": "Uneven",
        "occurrences": "Granite pegmatites, quartz veins, skarn deposits",
        "associates": "Cassiterite, scheelite, fluorite, molybdenite",
        "tests": "Magnetic, high specific gravity, XRF"
    },
    "garnet": {
        "formula": "X₃Y₂(SiO₄)₃", "system": "Cubic", "hardness": "6.5-7.5",
        "density": "3.5-4.3 g/cm³", "color": "Red, brown, green, orange, yellow",
        "luster": "Vitreous to resinous", "streak": "White",
        "cleavage": "None", "fracture": "Conchoidal to uneven",
        "occurrences": "Metamorphic rocks, igneous rocks, placers",
        "associates": "Epidote, staurolite, kyanite, sillimanite",
        "tests": "Specific gravity, refractive index, spectroscopy"
    },
    "zircon": {
        "formula": "ZrSiO₄", "system": "Tetragonal", "hardness": "7.5",
        "density": "4.6-4.7 g/cm³", "color": "Brown, red, yellow, green, blue, colorless",
        "luster": "Adamantine to vitreous", "streak": "White",
        "cleavage": "Imperfect", "fracture": "Conchoidal",
        "occurrences": "Igneous rocks, metamorphic rocks, placer deposits",
        "associates": "Titanite, monazite, rutile, ilmenite, garnet",
        "tests": "Refractive index, birefringence, U-Pb dating"
    },
    "fluorite": {
        "formula": "CaF₂", "system": "Cubic", "hardness": "4",
        "density": "3.1 g/cm³", "color": "Purple, green, blue, yellow, clear",
        "luster": "Vitreous", "streak": "White",
        "cleavage": "Perfect octahedral", "fracture": "Conchoidal",
        "occurrences": "Hydrothermal veins, sedimentary rocks, pegmatites",
        "associates": "Galena, sphalerite, barite, quartz, calcite",
        "tests": "Fluorescence under UV, cleavage, acid test"
    },
    "barite": {
        "formula": "BaSO₄", "system": "Orthorhombic", "hardness": "3-3.5",
        "density": "4.5 g/cm³", "color": "White, gray, yellow, brown",
        "luster": "Vitreous to pearly", "streak": "White",
        "cleavage": "Perfect", "fracture": "Uneven",
        "occurrences": "Hydrothermal veins, sedimentary beds, evaporites",
        "associates": "Galena, sphalerite, fluorite, calcite, pyrite",
        "tests": "High specific gravity, acid test, flame test"
    }
}


def _geology_mineral(parts: List[str]) -> str:
    if not parts:
        return "Usage: /geology mineral <name>\nExample: /geology mineral gold"
    name = " ".join(parts).lower().replace(" ", "_")
    if name in MINERALS_DB:
        m = MINERALS_DB[name]
        return f"""*{name.replace('_', ' ').title()}*

Chemical: {m['formula']}
Crystal: {m['system']} | Hardness: {m['hardness']}
Density: {m['density']} | SG: {m.get('specific_gravity', 'N/A')}
Color: {m['color']}
Luster: {m['luster']} | Streak: {m['streak']}
Cleavage: {m['cleavage']} | Fracture: {m['fracture']}
Melting Point: {m.get('mp', 'N/A')}

*Occurrence:* {m['occurrences']}
*Associates:* {m['associates']}
*Identification:* {m['tests']}"""
    return f"Mineral '{parts[0]}' not found. Available: {', '.join(k.replace('_',' ').title() for k in sorted(MINERALS_DB.keys()))}"


ROCKS_DB = {
    "granite": {"type": "Igneous (intrusive)", "composition": "Feldspar, quartz, mica, amphibole", "texture": "Phaneritic, equigranular", "color": "Light to dark", "hardness": "6-7", "density": "2.63-2.75 g/cm³", "uses": "Construction, dimension stone, host for pegmatite deposits", "gold_occurrence": "Stockwork veins, porphyry systems, placer sources"},
    "basalt": {"type": "Igneous (extrusive)", "composition": "Plagioclase, pyroxene, olivine", "texture": "Aphanitic, vesicular", "color": "Dark gray to black", "hardness": "6-7", "density": "2.8-3.0 g/cm³", "uses": "Construction, aggregate, railway ballast", "gold_occurrence": "Rare, but hosted in volcanic-associated massive sulfides"},
    "limestone": {"type": "Sedimentary", "composition": "Calcite, aragonite (CaCO₃)", "texture": "Fossiliferous, crystalline, oolitic", "color": "White, gray, beige", "hardness": "3-4", "density": "2.3-2.7 g/cm³", "uses": "Cement, lime, steel flux, agriculture", "gold_occurrence": "Carlin-type disseminated gold deposits"},
    "quartzite": {"type": "Metamorphic", "composition": "Quartz (SiO₂)", "texture": "Granoblastic, sugary", "color": "White, gray, pink", "hardness": "7", "density": "2.6-2.7 g/cm³", "uses": "Railroad ballast, roofing, decorative stone", "gold_occurrence": "Host for orogenic gold veins"},
    "schist": {"type": "Metamorphic", "composition": "Mica, chlorite, talc, garnet", "texture": "Schistose, foliated", "color": "Silver, green, gray", "hardness": "3-6", "density": "2.7-3.0 g/cm³", "uses": "Slate, roofing, decorative", "gold_occurrence": "Greenstone belt gold deposits"},
    "gneiss": {"type": "Metamorphic", "composition": "Feldspar, quartz, mica, amphibole", "texture": "Gneissic banding, foliated", "color": "Banded light and dark", "hardness": "6-7", "density": "2.6-2.9 g/cm³", "uses": "Dimension stone, aggregate", "gold_occurrence": "Shear zone gold deposits"},
    "diorite": {"type": "Igneous (intrusive)", "composition": "Plagioclase, hornblende, biotite", "texture": "Phaneritic, porphyritic", "color": "Salt and pepper", "hardness": "6-7", "density": "2.8-2.9 g/cm³", "uses": "Construction, dimension stone", "gold_occurrence": "Host for porphyry copper-gold deposits"},
    "rhyolite": {"type": "Igneous (extrusive)", "composition": "Quartz, alkali feldspar, biotite", "texture": "Aphanitic, flow banded", "color": "Light gray, pink, tan", "hardness": "6-7", "density": "2.4-2.6 g/cm³", "uses": "Construction aggregate", "gold_occurrence": "Host for epithermal gold deposits"},
    "shale": {"type": "Sedimentary", "composition": "Clay minerals, quartz, feldspar", "texture": " fissile, laminated", "color": "Gray, black, red, brown", "hardness": "2-3", "density": "2.0-2.4 g/cm³", "uses": "Bricks, ceramics, oil/gas source rock", "gold_occurrence": "Rare; some paleoplacer deposits"},
    "sandstone": {"type": "Sedimentary", "composition": "Quartz, feldspar, lithic fragments", "texture": "Clastic, cemented", "color": "White, red, yellow, gray", "hardness": "6-7", "density": "2.2-2.8 g/cm³", "uses": "Building stone, abrasive, oil reservoir", "gold_occurrence": "Witwatersrand-type conglomerate gold deposits"},
}


def _geology_rock(parts: List[str]) -> str:
    if not parts:
        return "Usage: /geology rock <type>\nExample: /geology rock granite"
    name = " ".join(parts).lower()
    if name in ROCKS_DB:
        r = ROCKS_DB[name]
        return f"""*{name.title()}*

Type: {r['type']}
Composition: {r['composition']}
Texture: {r['texture']}
Color: {r['color']}
Hardness: {r['hardness']}
Density: {r['density']}

Uses: {r['uses']}
Gold occurrence: {r['gold_occurrence']}"""
    return f"Rock type '{parts[0]}' not found. Available: {', '.join(k.title() for k in sorted(ROCKS_DB.keys()))}"


EXPLORATION_REGIONS = {
    "tanzania": {"belt": "Lake Victoria Greenstone Belt", "minerals": ["gold", "tanzanite", "diamond"], "mines": ["Geita", "North Mara", "Bulyanhulu", "Buzwagi", "Merelani (tanzanite)"], "geology": "Archean greenstone belts, Proterozoic mobile belts", "exploration_methods": ["Airborne magnetics", "Soil sampling", "RC/Diamond drilling", "Channel sampling"]},
    "kenya": {"belt": "Nyanzian Greenstone Belt", "minerals": ["gold", "soda ash", "titanium"], "mines": ["Kakamega (exploration)", "Kwale (mineral sands)"], "geology": "Archean-Proterozoic greenstone belts, rift valley sediments", "exploration_methods": ["Soil sampling", "Geophysics", "Stream sediment sampling"]},
    "uganda": {"belt": "Kasai-Kibalian Belt", "minerals": ["gold", "cobalt", "coltan"], "mines": ["Karamoja (exploration)", "Busia (placer gold)"], "geology": "Proterozoic metamorphic belts, Archean basement", "exploration_methods": ["Artisanal mining mapping", "Pitting", "RAB drilling"]},
    "drc": {"belt": "Kibaran Belt / Congo Craton", "minerals": ["gold", "diamond", "coltan", "copper", "cobalt"], "mines": ["Kibali", "Kilo-Moto (artisanal)"], "geology": "Archean-Proterozoic greenstone belts, Kibaran orogen", "exploration_methods": ["Geophysics", "Heavy mineral sampling", "Diamond drilling"]},
    "ethiopia": {"belt": "Adola Belt / Omo-Gibe", "minerals": ["gold", "sapphire", "tantalite"], "mines": ["Lega Dembi", "Tulu Kapi (exploration)"], "geology": "Proterozoic metamorphic belt, Neoproterozoic ophiolites", "exploration_methods": ["Stream sediment sampling", "Soil geochemistry", "RC drilling"]},
    "ghana": {"belt": "Ashanti Belt", "minerals": ["gold", "diamond", "bauxite"], "mines": ["Obuasi", "Tarkwa", "Prestea", "Ahafo"], "geology": "Birimian-Tarkwaian greenstone belts", "exploration_methods": ["Airborne geophysics", "Soil/geochemical sampling", "Drilling"]},
    "mali": {"belt": "Birimian Greenstone Belts", "minerals": ["gold"], "mines": ["Loulo-Gounkoto", "Fekola", "Morila", "Sadiola"], "geology": "Paleoproterozoic Birimian supracrustal and intrusive rocks", "exploration_methods": ["Airborne magnetics/Radiometrics", "Geochemical sampling", "Diamond drilling"]},
    "zambia": {"belt": "Copperbelt", "minerals": ["copper", "cobalt", "emerald", "diamond"], "mines": ["Konkola", "Nchanga", "Kagem (emerald)"], "geology": "Lufilian Arc, Katangan sediments", "exploration_methods": ["IP/Resistivity geophysics", "Soil sampling", "Diamond drilling"]},
}


def _geology_exploration(parts: List[str]) -> str:
    if not parts:
        return "Usage: /geology exploration <region>\nExample: /geology exploration tanzania"
    region = " ".join(parts).lower()
    if region in EXPLORATION_REGIONS:
        r = EXPLORATION_REGIONS[region]
        return f"""*Exploration Guide: {region.title()}*

*Geological Belt:* {r['belt']}
*Geology:* {r['geology']}

*Target Minerals:* {', '.join(r['minerals'])}

*Known Deposits/Mines:*
  {chr(10).join('• ' + m for m in r['mines'])}

*Recommended Methods:*
  {chr(10).join('• ' + m for m in r['exploration_methods'])}

*Permit Requirements:*
  - Prospecting license (1-4 years)
  - Mining license (up to 25 years)
  - Environmental impact assessment (EIA)
  - Community benefit agreement"""
    return f"Region '{region}' not found. Available: {', '.join(k.title() for k in sorted(EXPLORATION_REGIONS.keys()))}"


def calculate_fleet(args: str) -> str:
    """Fleet and equipment calculator.

    Usage:
        /fleet productivity <bucket_m3> <cycle_min> <availability_pct>
        /fleet trucks <mine_tonnes> <truck_capacity> <distance_km> <speed_kmh>
        /fleet diesel <engine_hp> <hours> <consumption_rate>
    """
    parts = args.strip().split()
    if not parts:
        return _fleet_help()

    sub = parts[0].lower()

    if sub == "productivity":
        return _fleet_productivity(parts[1:])
    elif sub == "trucks":
        return _fleet_trucks(parts[1:])
    elif sub == "diesel":
        return _fleet_diesel(parts[1:])
    else:
        return _fleet_help()


def _fleet_help() -> str:
    return """*Fleet Calculator Usage:*

`/fleet productivity <bucket_m3> <cycle_min> <availability%>`
  Loader productivity
  Example: /fleet productivity 8 3.5 85

`/fleet trucks <mine_tonnes> <capacity_t> <distance_km> <speed_kmh>`
  Truck fleet requirement
  Example: /fleet trucks 50000 220 3 15

`/fleet diesel <engine_hp> <hours> <litres_per_hp_hr>`
  Fuel consumption
  Example: /fleet diesel 2500 12 0.2"""


def _fleet_productivity(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /fleet productivity <bucket_m3> <cycle_min> <availability%>\nExample: /fleet productivity 8 3.5 85"
    try:
        bucket = float(parts[0])
        cycle = float(parts[1])
        avail = float(parts[2]) / 100.0
        passes = math.ceil(1.0 / bucket) if bucket > 0 else 1
        cycles_per_hour = 60.0 / cycle
        tph = bucket * cycles_per_hour * 1.6 * avail
        daily = tph * 12

        return f"""*Loader Productivity*

*Inputs:*
  Bucket: {bucket} m³ | Cycle: {cycle} min | Avail: {avail*100:.0f}%

*Results:*
  Cycles/hour: {cycles_per_hour:.1f}
  Passes to fill truck: {passes}
  Hourly productivity: {tph:.0f} t/hr
  Daily (12hr shift): {daily:,.0f} t/day

*Equipment Match:*
  Cat 992K: 10.3 m³ bucket, ~600 t/hr
  Cat 988F: 6.4 m³ bucket, ~400 t/hr
  Komatsu WA1200: 7.1 m³ bucket, ~450 t/hr"""
    except ValueError:
        return "Invalid numbers."


def _fleet_trucks(parts: List[str]) -> str:
    if len(parts) < 4:
        return "Usage: /fleet trucks <mine_tonnes> <capacity> <distance> <speed>\nExample: /fleet trucks 50000 220 3 15"
    try:
        tonnage = float(parts[0])
        capacity = float(parts[1])
        distance = float(parts[2])
        speed = float(parts[3])
        cycle_time = (distance * 2 / speed) * 60 + 15
        trips_per_truck = (12 * 60) / cycle_time
        tonnes_per_truck = trips_per_truck * capacity * 0.9
        trucks_needed = math.ceil(tonnage / tonnes_per_truck)

        return f"""*Truck Fleet Requirement*

*Inputs:*
  Mine tonnage: {tonnage:,.0f} t/day
  Truck capacity: {capacity} t
  Haul distance: {distance} km (one way)
  Haul speed: {speed} km/h

*Results:*
  Cycle time: {cycle_time:.1f} min
  Trips/truck/day: {trips_per_truck:.1f}
  Tonnes/truck/day: {tonnes_per_truck:,.0f}
  Trucks needed: {trucks_needed}

*Fleet Match:*
  Cat 793F: 227 t capacity
  Cat 797F: 363 t capacity
  Komatsu PC800: 254 t capacity"""
    except ValueError:
        return "Invalid numbers."


def _fleet_diesel(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /fleet diesel <engine_hp> <hours> <consumption_rate>\nExample: /fleet diesel 2500 12 0.2"
    try:
        hp = float(parts[0])
        hours = float(parts[1])
        rate = float(parts[2])
        daily = hp * hours * rate
        monthly = daily * 26
        cost = monthly * 1.2

        return f"""*Fuel Consumption*

*Inputs:*
  Engine: {hp:,.0f} HP
  Operating: {hours:.0f} hrs/day
  Consumption: {rate} L/HP-hr

*Results:*
  Daily: {daily:,.0f} litres
  Monthly (26 days): {monthly:,.0f} litres
  Monthly cost (@$1.20/L): ${cost:,.0f}

*Benchmarks:*
  Cat 793F (2,650 HP): 450-550 L/hr
  Cat 797F (3,500 HP): 600-750 L/hr
  Cat 390 Excavator (523 HP): 80-120 L/hr"""
    except ValueError:
        return "Invalid numbers."


def calculate_carbon(args: str) -> str:
    """Carbon footprint calculator for mining operations.

    Usage:
        /carbon emission <fuel_litres> <grid_kwh> <travel_km>
        /carbon offset <total_tonnes_co2> <trees_or_credits>
        /carbon efficiency <fuel_litres> <tonnes_mined>
    """
    parts = args.strip().split()
    if not parts:
        return _carbon_help()

    sub = parts[0].lower()

    if sub == "emission":
        return _carbon_emission(parts[1:])
    elif sub == "offset":
        return _carbon_offset(parts[1:])
    elif sub == "efficiency":
        return _carbon_efficiency(parts[1:])
    else:
        return _carbon_help()


def _carbon_help() -> str:
    return """*Carbon Calculator Usage:*

`/carbon emission <diesel_L> <grid_kWh> <travel_km>`
  Calculate CO₂ emissions
  Example: /carbon emission 50000 200000 100000

`/carbon offset <total_tonnes_CO2> <offset_type: trees|credits|renewable>`
  Offset recommendations
  Example: /carbon offset 15000 trees

`/carbon efficiency <fuel_litres> <tonnes_mined>`
  Fuel efficiency per tonne
  Example: /carbon efficiency 500000 5000000"""


def _carbon_emission(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /carbon emission <diesel_L> <grid_kWh> <travel_km>\nExample: /carbon emission 50000 200000 100000"
    try:
        diesel = float(parts[0])
        grid = float(parts[1])
        travel = float(parts[2])
        diesel_co2 = diesel * 2.68 / 1000
        grid_co2 = grid * 0.5 / 1000
        travel_co2 = travel * 0.21 / 1000
        total = diesel_co2 + grid_co2 + travel_co2

        return f"""*CO₂ Emission Estimate*

*Sources:*
  Diesel:     {diesel:>12,.0f} L  → {diesel_co2:>8,.1f} tCO₂
  Grid power: {grid:>12,.0f} kWh → {grid_co2:>8,.1f} tCO₂
  Transport:  {travel:>12,.0f} km  → {travel_co2:>8,.1f} tCO₂
  ─────────────────────────────────────────
  Total:      {total:>28,.1f} tCO₂

*Emission Factors (Africa avg):*
  Diesel: 2.68 kgCO₂/L
  Grid: 0.50 kgCO₂/kWh
  Road transport: 0.21 kgCO₂/km

*Reduction Opportunities:*
  Solar power: -80% grid emissions
  Electric fleet: -60% diesel emissions
  Local sourcing: -30% transport emissions"""
    except ValueError:
        return "Invalid numbers."


def _carbon_offset(parts: List[str]) -> str:
    if len(parts) < 2:
        return "Usage: /carbon offset <total_tonnes_CO2> <trees|credits|renewable>\nExample: /carbon offset 15000 trees"
    try:
        total = float(parts[0])
        method = parts[1].lower()
        trees = math.ceil(total * 40 / 1000) * 1000
        credits = total * 15
        solar = total * 1000 * 0.8 / 0.5

        if method == "trees":
            return f"""*Carbon Offset: Reforestation*

  CO₂ to offset: {total:,.1f} tCO₂/year
  Trees needed: {trees:,.0f} (at 25 kgCO₂/tree/year)
  Land required: {trees*10/10000:.0f} hectares
  Annual cost: ${total*12:,.0f} (@ $12/tCO₂)
  Time to maturity: 5-10 years

*East African Species:*
  - Grevillea robusta: Fast growth, 30 kgCO₂/tree/yr
  - Calliandra calothyrsus: Nitrogen fixing, 25 kgCO₂/tree/yr
  - Cordia africana: Native hardwood, 20 kgCO₂/tree/yr"""
        elif method == "credits":
            return f"""*Carbon Offset: Carbon Credits*

  CO₂ to offset: {total:,.1f} tCO₂/year
  Credits needed: {total:,.0f} tCO₂e
  Cost: ${credits:,.0f} (@ $15/tCO₂)
  Standard: Verra VCS or Gold Standard

*Recommended Projects:*
  - East Africa Cookstoves: $8-12/tCO₂
  - Kenya Wind Power: $10-15/tCO₂
  - Tanzania Reforestation: $12-18/tCO₂"""
        else:
            return f"""*Carbon Offset: Renewable Energy*

  CO₂ to offset: {total:,.1f} tCO₂/year
  Solar capacity needed: {solar:,.0f} kW
  Investment: ${solar*800:,.0f} (@ $800/kW)
  Payback: 3-5 years
  Annual savings: ${total*1000*0.1:,.0f}

*Solar for Mining:*
  - 5 MW solar = 8,000 tCO₂/yr offset
  - ROI: 25-35% over 25 years
  - Battery storage: $200-400/kWh"""
    except ValueError:
        return "Invalid numbers."


def _carbon_efficiency(parts: List[str]) -> str:
    if len(parts) < 2:
        return "Usage: /carbon efficiency <fuel_litres> <tonnes_mined>\nExample: /carbon efficiency 500000 5000000"
    try:
        fuel = float(parts[0])
        tonnes = float(parts[1])
        litres_per_tonne = fuel / tonnes
        co2_per_tonne = litres_per_tonne * 2.68 / 1000
        benchmark = 0.05
        status = "EXCELLENT" if co2_per_tonne < benchmark * 0.7 else "GOOD" if co2_per_tonne < benchmark else "NEEDS IMPROVEMENT"

        return f"""*Fuel Efficiency*

*Inputs:*
  Total diesel: {fuel:,.0f} litres
  Total tonnage: {tonnes:,.0f} t

*Results:*
  Litres/t: {litres_per_tonne:.3f}
  CO₂/t: {co2_per_tonne:.4f} tCO₂/t

*Benchmark:*
  Target: < 0.05 tCO₂/t
  Status: *{status}*

*Reduction Strategies:*
  - Autonomous haul trucks: -15% fuel
  - Mine planning optimization: -10% fuel
  - Electric/hybrid fleet: -40% fuel
  - Renewable energy: -60% grid emissions"""
    except ValueError:
        return "Invalid numbers."


def calculate_water(args: str) -> str:
    """Water balance calculator for mining operations.

    Usage:
        /water balance <makeup> <recirculation> <evaporation> <seepage>
        /water treatment <flow_m3hr> <contaminant_level> <target_level>
    """
    parts = args.strip().split()
    if not parts:
        return _water_help()

    sub = parts[0].lower()

    if sub == "balance":
        return _water_balance(parts[1:])
    elif sub == "treatment":
        return _water_treatment(parts[1:])
    else:
        return _water_help()


def _water_help() -> str:
    return """*Water Calculator Usage:*

`/water balance <makeup_m3> <recirculated_m3> <evaporation_m3> <seepage_m3>`
  Water balance for pit/heap
  Example: /water balance 5000 20000 8000 1000

`/water treatment <flow_m3hr> <current_level> <target_level>`
  Water treatment sizing
  Example: /water treatment 100 500 10"""


def _water_balance(parts: List[str]) -> str:
    if len(parts) < 4:
        return "Usage: /water balance <makeup> <recirculated> <evaporation> <seepage>\nExample: /water balance 5000 20000 8000 1000"
    try:
        makeup = float(parts[0])
        recirc = float(parts[1])
        evap = float(parts[2])
        seepage = float(parts[3])
        total_in = makeup + recirc
        total_out = evap + seepage
        surplus = total_in - total_out
        recycle_ratio = recirc / evap * 100 if evap > 0 else 0

        return f"""*Water Balance*

*Inputs:*
  Makeup water: {makeup:,.0f} m³/month
  Recirculated: {recirc:,.0f} m³/month
  Evaporation: {evap:,.0f} m³/month
  Seepage: {seepage:,.0f} m³/month

*Balance:*
  Total inflow:  {total_in:,.0f} m³/month
  Total outflow: {total_out:,.0f} m³/month
  Surplus/deficit: {surplus:+,.0f} m³/month

*Metrics:*
  Recycle ratio: {recycle_ratio:.0f}%
  Water intensity: {makeup/50000:.2f} m³/t ore

*Targets:*
  Recycle ratio: > 70% (good), > 85% (excellent)
  Water intensity: < 0.5 m³/t ore"""
    except ValueError:
        return "Invalid numbers."


def _water_treatment(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /water treatment <flow_m3hr> <current_level> <target_level>\nExample: /water treatment 100 500 10"
    try:
        flow = float(parts[0])
        current = float(parts[1])
        target = float(parts[2])
        removal = current - target
        removal_pct = (removal / current) * 100
        daily = flow * 24
        tank_size = flow * 4

        return f"""*Water Treatment Sizing*

*Inputs:*
  Flow rate: {flow:,.0f} m³/hr
  Current level: {current} mg/L
  Target level: {target} mg/L

*Results:*
  Removal needed: {removal:,.0f} mg/L ({removal_pct:.1f}%)
  Daily throughput: {daily:,.0f} m³/day
  Treatment tank: {tank_size:,.0f} m³ (4hr retention)

*Treatment Options:*
  - Neutralization (lime): pH adjustment, $0.1-0.5/m³
  - Clarification: TSS removal, $0.2-0.8/m³
  - Reverse osmosis: Heavy metals, $0.5-2.0/m³
  - Constructed wetlands: Passive, $0.05-0.2/m³"""
    except ValueError:
        return "Invalid numbers."


def calculate_geotech(args: str) -> str:
    """Geotechnical calculator.

    Usage:
        /geotech rmr <ucs> <rqd> <spacing> <condition> <water>
        /geotech slope <bench_height> <bench_angle> <overall_angle>
        /geotech pillar <width> <height> <depth> <ucs>
    """
    parts = args.strip().split()
    if not parts:
        return _geotech_help()

    sub = parts[0].lower()

    if sub == "rmr":
        return _geotech_rmr(parts[1:])
    elif sub == "slope":
        return _geotech_slope(parts[1:])
    elif sub == "pillar":
        return _geotech_pillar(parts[1:])
    else:
        return _geotech_help()


def _geotech_help() -> str:
    return """*Geotech Calculator Usage:*

`/geotech rmr <ucs> <rqd> <spacing> <condition> <water>`
  Rock Mass Rating (Bieniawski)
  Example: /geotech rmr 120 75 1.5 20 15

`/geotech slope <bench_height> <bench_angle> <overall_angle>`
  Slope stability assessment
  Example: /geotech slope 12 65 42

`/geotech pillar <width> <height> <depth> <ucs>`
  Pillar strength estimation
  Example: /geotech pillar 10 5 50 120"""


def _geotech_rmr(parts: List[str]) -> str:
    if len(parts) < 5:
        return "Usage: /geotech rmr <ucs> <rqd> <spacing> <condition> <water>\nExample: /geotech rmr 120 75 1.5 20 15"
    try:
        ucs = float(parts[0])
        rqd = float(parts[1])
        spacing = float(parts[2])
        condition = float(parts[3])
        water = float(parts[4])

        ucs_r = min(15, ucs / 10) if ucs < 100 else min(15, ucs / 40 + 10)
        rqd_r = rqd / 5
        space_r = min(20, spacing * 10)
        total = ucs_r + rqd_r + space_r + condition + water

        if total >= 81:
            rock_class = "I - Very Good"
            support = "Spot bolting, minimal shotcrete"
        elif total >= 61:
            rock_class = "II - Good"
            support = "Systematic bolting, thin shotcrete"
        elif total >= 41:
            rock_class = "III - Fair"
            support = "Bolting + mesh + shotcrete"
        elif total >= 21:
            rock_class = "IV - Poor"
            support = "Heavy support: bolts + mesh + thick shotcrete + cables"
        else:
            rock_class = "V - Very Poor"
            support = "Full support system, consider TBM or NATM"

        return f"""*Rock Mass Rating (Bieniawski 1989)*

*Input Ratings:*
  UCS ({ucs} MPa):     {ucs_r:.0f}/15
  RQD ({rqd}%):        {rqd_r:.0f}/20
  Spacing ({spacing}m): {space_r:.0f}/20
  Condition:           {condition}/30
  Groundwater:         {water}/15
  ────────────────────────
  Total RMR:           {total:.0f}/100

*Classification:* {rock_class}
*Support Class:* {support}
*Stand-up time:* {'Indefinite' if total > 80 else '> 10 years' if total > 61 else '1 year' if total > 41 else '10 hours' if total > 21 else '< 30 minutes'}"""
    except ValueError:
        return "Invalid numbers."


def _geotech_slope(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /geotech slope <bench_height> <bench_angle> <overall_angle>\nExample: /geotech slope 12 65 42"
    try:
        bench_h = float(parts[0])
        bench_a = float(parts[1])
        overall_a = float(parts[2])

        if overall_a > bench_a:
            return "Error: Overall slope angle cannot exceed bench face angle."
        catch_bench = bench_h / math.tan(math.radians(bench_a)) + 2
        berm_width = catch_bench * 1.5
        risk = "LOW" if overall_a < 35 else "MODERATE" if overall_a < 45 else "HIGH" if overall_a < 55 else "VERY HIGH"

        return f"""*Slope Stability Assessment*

*Inputs:*
  Bench height: {bench_h} m
  Bench face angle: {bench_a}°
  Overall slope angle: {overall_a}°

*Design:*
  Catch bench width: {catch_bench:.1f} m
  Berm width: {berm_width:.1f} m
  Number of benches: {math.ceil(berm_width * 3 / bench_h)}

*Risk Assessment:*
  Risk level: *{risk}*
  Safety factor: {'> 1.5 (safe)' if overall_a < 40 else '1.2-1.5 (marginal)' if overall_a < 50 else '< 1.2 (unstable)'}
  
*Monitoring Required:*
  - Slope stability radar (SSR)
  - Extensometers
  - Inclinometers
  - Regular inspections"""
    except ValueError:
        return "Invalid numbers."


def _geotech_pillar(parts: List[str]) -> str:
    if len(parts) < 4:
        return "Usage: /geotech pillar <width> <height> <depth> <ucs>\nExample: /geotech pillar 10 5 50 120"
    try:
        width = float(parts[0])
        height = float(parts[1])
        depth = float(parts[2])
        ucs = float(parts[3])

        area = width * height
        volume = area * depth
        stress = 0.278 * ucs * (height / width) ** 0.36
        extraction_ratio = 1 - (area / ((width + 10) * (height + 10)))
        safety_factor = stress / (depth * 0.027)

        return f"""*Pillar Design*

*Inputs:*
  Pillar: {width} × {height} × {depth} m
  Rock UCS: {ucs} MPa

*Results:*
  Pillar area: {area:,.0f} m²
  Pillar volume: {volume:,.0f} m³
  Pillar stress: {stress:.1f} MPa
  Extraction ratio: {extraction_ratio*100:.1f}%
  Safety factor: {safety_factor:.2f}

*Assessment:*
  {'SAFE (SF > 1.5)' if safety_factor > 1.5 else 'MARGINAL (SF 1.2-1.5)' if safety_factor > 1.2 else 'UNSAFE (SF < 1.2) - Reduce extraction'}

*Formulas:* Obert-Duvall strength = 0.278 × UCS × (H/W)^0.36"""
    except ValueError:
        return "Invalid numbers."


def calculate_reserves(args: str) -> str:
    """Resource/reserve calculator.

    Usage:
        /reserves classification <tonnes> <grade> <recovery>
        /reservesJORC <measured> <indicated> <inferred>
    """
    parts = args.strip().split()
    if not parts:
        return _reserves_help()

    sub = parts[0].lower()

    if sub == "classification":
        return _reserves_classification(parts[1:])
    elif sub == "jorc":
        return _reserves_jorc(parts[1:])
    else:
        return _reserves_help()


def _reserves_help() -> str:
    return """*Reserves Calculator Usage:*

`/reserves classification <tonnes> <grade_g/t> <recovery%>`
  Calculate contained metal and classify
  Example: /reserves classification 5000000 1.5 95

`/reserves jorc <measured_t> <indicated_t> <inferred_t>`
  JORC resource classification
  Example: /reserves jorc 1000000 3000000 500000"""


def _reserves_classification(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /reserves classification <tonnes> <grade_g/t> <recovery%>\nExample: /reserves classification 5000000 1.5 95"
    try:
        tonnes = float(parts[0])
        grade = float(parts[1])
        recovery = float(parts[2]) / 100.0
        metal_kg = grade * tonnes * recovery / 1000
        metal_oz = metal_kg * 31.1035
        if metal_oz >= 1000000:
            size = "Tier 1 (1M+ oz)"
        elif metal_oz >= 500000:
            size = "Tier 2 (500K-1M oz)"
        elif metal_oz >= 100000:
            size = "Tier 3 (100K-500K oz)"
        else:
            size = "Small deposit (<100K oz)"
        revenue = metal_oz * 3250
        value_per_share = revenue / tonnes

        return f"""*Resource/Reserve Classification*

*Inputs:*
  Tonnes: {tonnes:,.0f} t
  Grade: {grade} g/t Au
  Recovery: {recovery*100:.0f}%

*Contained Metal:*
  Kilograms: {metal_kg:,.1f} kg
  Ounces: {metal_oz:,.1f} oz
  Classification: *{size}*

*Economic Value:*
  Gross revenue: ${revenue:,.0f}
  Value per tonne: ${value_per_share:,.2f}/t

*JORC Categories:*
  Measured: High confidence (drill spacing <50m)
  Indicated: Moderate confidence (50-100m spacing)
  Inferred: Low confidence (100-200m+ spacing)
  
*Note:* Reserve = Measured + Indicated × economic cut-off"""
    except ValueError:
        return "Invalid numbers."


def _reserves_jorc(parts: List[str]) -> str:
    if len(parts) < 3:
        return "Usage: /reserves jorc <measured> <indicated> <inferred>\nExample: /reserves jorc 1000000 3000000 500000"
    try:
        measured = float(parts[0])
        indicated = float(parts[1])
        inferred = float(parts[2])
        total = measured + indicated + inferred
        measured_pct = (measured / total) * 100 if total > 0 else 0
        indicated_pct = (indicated / total) * 100 if total > 0 else 0
        inferred_pct = (inferred / total) * 100 if total > 0 else 0

        if measured_pct > 40:
            confidence = "HIGH"
        elif measured_pct > 20:
            confidence = "MODERATE"
        else:
            confidence = "LOW"

        return f"""*JORC Resource Classification*

*Resource Breakdown:*
  Measured:   {measured:>12,.0f} t  ({measured_pct:.1f}%)
  Indicated:  {indicated:>12,.0f} t  ({indicated_pct:.1f}%)
  Inferred:   {inferred:>12,.0f} t  ({inferred_pct:.1f}%)
  ───────────────────────────────────────
  Total:      {total:>12,.0f} t

*Confidence Level:* *{confidence}*

*JORC 2012 Requirements:*
  - Competent Person (CP) sign-off
  - Public disclosure in Table 1 format
  - Annual reporting for listed companies
  - Due diligence for all resource estimates"""
    except ValueError:
        return "Invalid numbers."
