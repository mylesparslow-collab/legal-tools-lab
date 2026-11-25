"""Write the synthetic sample data. Every agency, supplier, price and part here is made up."""
import csv
import json
from pathlib import Path

OUT = Path(__file__).parent / "sample_data"
FIELDS = ["project_id", "line_id", "parent_id", "tier", "category", "description", "supplier",
          "cost_usd", "mfg_country", "all_processes_us", "material_type", "tariff_exempt_reexport",
          "raw_material", "waiver_ref", "frame_or_shell", "us_steel_iron_cost", "cert_on_file",
          "gwp", "epd_on_file"]

rows: list[dict] = []


def add(project, line_id, parent, tier, desc, supplier="", cost="", country="", **kw):
    row = dict.fromkeys(FIELDS, "")
    row.update(project_id=project, line_id=line_id, parent_id=parent, tier=tier, description=desc,
               supplier=supplier, cost_usd=cost, mfg_country=country, cert_on_file="Y")
    row.update(kw)
    rows.append(row)


def comp(project, cid, parent, desc, supplier, cost, country, subs=(), **kw):
    add(project, cid, parent, "component", desc, supplier, cost, country, **kw)
    for i, (sdesc, scost, scountry, *extra) in enumerate(subs, 1):
        add(project, f"{cid}-S{i}", cid, "subcomponent", sdesc, "", scost, scountry,
            **(extra[0] if extra else {}))


# ---- Project 1: battery electric buses (per-vehicle bill of materials) ----
P = "TB-BEB-40"
add(P, "BEB", "", "end_product", "40-foot battery electric bus (per vehicle)", "Corvane Coach Works", category="rolling_stock")
comp(P, "C01", "BEB", "Body structure and frame", "Corvane Coach Works", 148000, "US",
     [("Steel tubing", 52000, "US"), ("Aluminum extrusions", 21000, "US"), ("Composite panels", 18000, "MX")])
comp(P, "C02", "BEB", "Battery energy storage system", "Halvorsen Cell Systems", 310000, "US",
     [("Lithium-ion cells", 150000, "KR"), ("Module housings", 31000, "US"), ("Battery management system", 27000, "US"),
      ("Thermal plates", 14000, "US"), ("Busbars and contactors", 18000, "US")])
comp(P, "C03", "BEB", "Traction motor and inverter", "Brennholt Antriebe", 62000, "DE",
     [("Power semiconductors", 9000, "US", {"tariff_exempt_reexport": "Y"}), ("Motor windings", 20000, "DE"),
      ("Aluminum casting stock", 4000, "US", {"raw_material": "Y"})])
comp(P, "C04", "BEB", "Rear axle assembly", "Pell River Driveline", 38000, "US",
     [("Gear set", 14000, "US"), ("Axle housing", 9000, "US"), ("Bearings", 5000, "JP")])
comp(P, "C05", "BEB", "Front axle and suspension", "Pell River Driveline", 29000, "US")
comp(P, "C06", "BEB", "HVAC unit", "Northgate Climate", 34000, "US",
     [("Compressor", 12000, "CN"), ("Coils", 6000, "US"), ("Controls", 4000, "US")])
comp(P, "C07", "BEB", "Entrance and exit door systems", "Tamsin Door Co.", 21000, "US",
     [("Actuators", 8000, "US"), ("Door panels", 6000, "US"), ("Door glass", 2000, "US")])
comp(P, "C08", "BEB", "Passenger seats", "Ardley Seating", 26000, "US",
     [("Seat frames", 11000, "US"), ("Fabric", 5000, "US"), ("Foam", 2000, "CA")])
comp(P, "C09", "BEB", "Window assemblies", "Tamsin Door Co.", 17000, "US",
     [("Glass", 9000, "US"), ("Frames", 4000, "US")])
comp(P, "C10", "BEB", "Low-voltage wiring harness", "Quillon Electric", 23000, "US",
     [("Wire", 12000, "US"), ("Connectors", 3000, "US"), ("Terminals", 4000, "CN")])
comp(P, "C11", "BEB", "Destination signs and onboard ITS", "Lumenroute Displays", 19000, "US",
     [("LED modules", 7000, "TW"), ("Controller", 6000, "US"), ("Enclosure", 2000, "US")])
comp(P, "C12", "BEB", "Air compressor and pneumatic system", "Northgate Climate", 15000, "US",
     [("Compressor head", 9000, "US"), ("Dryer and valves", 3000, "US")])
comp(P, "C13", "BEB", "Steering system", "Pell River Driveline", 12000, "US",
     [("Steering gear", 7000, "US"), ("Pump", 2000, "IT")])
comp(P, "C14", "BEB", "Wheelchair ramp", "Ardley Seating", 11000, "US", [("Ramp assembly parts", 8000, "US")])
comp(P, "C15", "BEB", "Wheels and tires", "Marrow Creek Tire", 9000, "US",
     [("Wheels", 4000, "US"), ("Tires", 4500, "US")])
comp(P, "C16", "BEB", "Flooring and interior trim", "Ardley Seating", 14000, "US",
     [("Plywood subfloor", 6000, "US"), ("Floor covering", 5000, "US")])

# ---- Project 2: light rail vehicles (per-vehicle bill of materials) ----
P = "TB-LRV"
add(P, "LRV", "", "end_product", "Low-floor light rail vehicle (per vehicle)", "Sorrelbahn Rail Systems", category="rolling_stock")
comp(P, "L01", "LRV", "Car shell", "Sorrelbahn Rail Systems", 620000, "ES", frame_or_shell="Y", us_steel_iron_cost=140000)
comp(P, "L02", "LRV", "Trucks", "Kestrel Truck Works", 540000, "US",
     [("Truck frames", 190000, "US"), ("Wheelsets", 120000, "US"), ("Gearboxes", 110000, "DE")])
comp(P, "L03", "LRV", "Propulsion system", "Sorrelbahn Rail Systems", 480000, "US",
     [("Traction motors", 210000, "AT"), ("Inverters", 120000, "US"), ("Propulsion controls", 40000, "US")])
comp(P, "L04", "LRV", "Brake system", "Dunmore Brake", 210000, "US",
     [("Calipers and discs", 120000, "US"), ("Brake control unit", 40000, "DE")])
comp(P, "L05", "LRV", "Air conditioning equipment", "Northgate Climate", 150000, "US",
     [("Rooftop unit", 80000, "US"), ("Ducting", 30000, "US"), ("Compressor", 20000, "CN")])
comp(P, "L06", "LRV", "Doors and door controls", "Tamsin Door Co.", 170000, "US",
     [("Door leaves", 90000, "US"), ("Door operators", 50000, "AT")])
comp(P, "L07", "LRV", "Couplers and draft gear", "Brennholt Antriebe", 95000, "DE")
comp(P, "L08", "LRV", "Pantograph", "Brennholt Antriebe", 60000, "AT")
comp(P, "L09", "LRV", "Onboard train control", "Wexcombe Signal", 230000, "US",
     [("ATP equipment", 150000, "US"), ("Speed sensors", 30000, "FR")])
comp(P, "L10", "LRV", "Seating and interior linings", "Ardley Seating", 260000, "US",
     [("Seats", 180000, "US"), ("Lining panels", 30000, "CA")])
comp(P, "L11", "LRV", "Low-voltage auxiliary power supply", "Quillon Electric", 140000, "US",
     [("Converter modules", 70000, "US"), ("Battery set", 45000, "JP")])
comp(P, "L12", "LRV", "Communication equipment", "Lumenroute Displays", 85000, "US",
     [("Passenger information displays", 50000, "US"), ("Radio", 15000, "US")])
comp(P, "L13", "LRV", "Articulation assembly", "Brennholt Antriebe", 110000, "DE")

# ---- Project 3: bus depot charging and facility work ----
P = "TB-DEPOT"
def item(lid, cat, desc, supplier, cost, country, **kw):
    add(P, lid, "", "end_product", desc, supplier, cost, country, category=cat, **kw)

item("D01", "iron_steel", "Structural steel for charging canopy", "Hollin Steel Fabricators", 1240000, "US",
     all_processes_us="Y", material_type="structural_steel")
item("D02", "iron_steel", "Epoxy-coated rebar (coating applied in Mexico)", "Hollin Steel Fabricators", 186000, "US",
     all_processes_us="N", material_type="carbon_steel_rebar")
item("D03", "manufactured_product", "150 kW DC fast chargers (24 units)", "Voltmere Charging", 2880000, "US")
for cid, d, c, k in [("D03-1", "Power modules", 1150000, "US"), ("D03-2", "Cabinet and enclosure", 420000, "US"),
                     ("D03-3", "Dispenser cable and connector", 310000, "US"), ("D03-4", "Control board", 365000, "TW"),
                     ("D03-5", "Liquid cooling unit", 230000, "US"), ("D03-6", "Touchscreen display", 95000, "KR")]:
    add(P, cid, "D03", "component", d, "", c, k)
item("D04", "manufactured_product", "Medium-voltage switchgear", "Quillon Electric", 960000, "US")
for cid, d, c in [("D04-1", "Circuit breakers", 410000), ("D04-2", "Bus assembly", 180000),
                  ("D04-3", "Enclosure", 140000), ("D04-4", "Protective relays", 90000)]:
    add(P, cid, "D04", "component", d, "", c, "US")
item("D05", "manufactured_product", "Pad-mount transformers (assembled in Mexico)", "Quillon Electric", 540000, "MX")
for cid, d, c, k in [("D05-1", "Core steel", 210000, "US"), ("D05-2", "Windings", 150000, "US"), ("D05-3", "Tank", 70000, "MX")]:
    add(P, cid, "D05", "component", d, "", c, k)
item("D06", "manufactured_product", "Charge management servers", "Lumenroute Displays", 120000, "TW",
     waiver_ref="49 CFR 661.7 App. A(b), data processing equipment")
item("D07", "construction_material", "PVC conduit", "Marrow Creek Supply", 210000, "US",
     all_processes_us="Y", material_type="plastic_polymer")
item("D08", "construction_material", "Fiber optic cable (optical fiber drawn in Japan)", "Marrow Creek Supply", 74000, "US",
     all_processes_us="N", material_type="fiber_optic_cable")
item("D09", "construction_material", "Copper grounding conductor", "Marrow Creek Supply", 58000, "US",
     material_type="non_ferrous_metals", cert_on_file="N")
item("D10", "section_70917c", "Ready-mix concrete", "Tule Bay Aggregates", 390000, "US")
item("D11", "unclassified", "Solar canopy photovoltaic assembly", "Voltmere Charging", 610000, "US")

case = {
    "synthetic": True,
    "agency": "Tule Bay Transit District (fictional)",
    "projects": [
        {"project_id": "TB-BEB-40", "name": "30 battery electric buses", "funding": "FTA",
         "vehicle_type": "bus", "vehicle_count": 30, "average_vehicle_cost": 1150000,
         "scheduled_delivery_date": "2027-03-15", "final_assembly_country": "US",
         "service_area": "urbanized_over_200k", "revenue_service": True, "stage": "contract_signed",
         "documents": {"bidder_buy_america_certificate": True, "pre_award_buy_america_certification": True,
                       "pre_award_purchaser_requirements_certification": True, "fmvss_pre_award": True}},
        {"project_id": "TB-LRV", "name": "12 light rail vehicles", "funding": "FTA",
         "vehicle_type": "railcar", "vehicle_count": 12, "average_vehicle_cost": 4600000,
         "scheduled_delivery_date": "2026-08-20", "final_assembly_country": "US",
         "service_area": "urbanized_over_200k", "revenue_service": True, "stage": "delivered",
         "documents": {"bidder_buy_america_certificate": True, "pre_award_buy_america_certification": True,
                       "pre_award_purchaser_requirements_certification": True, "resident_inspector_report": True}},
        {"project_id": "TB-DEPOT", "name": "Bus depot charging and facility upgrade", "funding": "FTA",
         "awarding_authority_type": "local_agency", "stage": "contract_signed",
         "total_applicable_cost": 18400000, "federal_assistance": 14720000,
         "documents": {"bidder_buy_america_certificate": True}},
    ],
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    with open(OUT / "bom.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        w.writeheader()
        w.writerows(rows)
    (OUT / "case.json").write_text(json.dumps(case, indent=2) + "\n")
    print(f"Wrote {len(rows)} BOM lines and {len(case['projects'])} projects to {OUT}")
