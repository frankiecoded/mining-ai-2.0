import logging

logger = logging.getLogger("ai_os.database.seed_data")


def seed_database(conn, is_sqlite: bool = False):
    """
    Creates and seeds core analytical tables for the AI OS databases.
    Supports both SQLite (for local fallback) and PostgreSQL.
    """
    param_style = "?" if is_sqlite else "%s"

    table_creations = [
        """
        CREATE TABLE IF NOT EXISTS production_logs (
            id SERIAL PRIMARY KEY,
            date VARCHAR(50) NOT NULL,
            shaft VARCHAR(100) NOT NULL,
            tons_milled FLOAT NOT NULL,
            head_grade_cu VARCHAR(50) NOT NULL,
            recovery_rate VARCHAR(50) NOT NULL,
            concentrate_produced FLOAT NOT NULL
        )
        """ if not is_sqlite else
        """
        CREATE TABLE IF NOT EXISTS production_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            shaft TEXT NOT NULL,
            tons_milled REAL NOT NULL,
            head_grade_cu TEXT NOT NULL,
            recovery_rate TEXT NOT NULL,
            concentrate_produced REAL NOT NULL
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS department_budgets (
            department VARCHAR(100) PRIMARY KEY,
            allocated FLOAT NOT NULL,
            spent FLOAT NOT NULL,
            variance FLOAT NOT NULL,
            status VARCHAR(50) NOT NULL
        )
        """ if not is_sqlite else
        """
        CREATE TABLE IF NOT EXISTS department_budgets (
            department TEXT PRIMARY KEY,
            allocated REAL NOT NULL,
            spent REAL NOT NULL,
            variance REAL NOT NULL,
            status TEXT NOT NULL
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS equipment_status (
            equipment_id VARCHAR(100) PRIMARY KEY,
            type VARCHAR(100) NOT NULL,
            status VARCHAR(50) NOT NULL,
            operating_hours INTEGER NOT NULL,
            next_service VARCHAR(50) NOT NULL,
            engine_temp_c FLOAT NOT NULL,
            oil_pressure_psi FLOAT NOT NULL
        )
        """ if not is_sqlite else
        """
        CREATE TABLE IF NOT EXISTS equipment_status (
            equipment_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            operating_hours INTEGER NOT NULL,
            next_service TEXT NOT NULL,
            engine_temp_c REAL NOT NULL,
            oil_pressure_psi REAL NOT NULL
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS sops (
            topic VARCHAR(100) PRIMARY KEY,
            code VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL
        )
        """ if not is_sqlite else
        """
        CREATE TABLE IF NOT EXISTS sops (
            topic TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL
        )
        """
    ]

    try:
        cur = conn.cursor()

        for query in table_creations:
            cur.execute(query)

        # Check if tables are already populated. If empty, seed them.

        cur.execute("SELECT COUNT(*) FROM production_logs;")
        if cur.fetchone()[0] == 0:
            logger.info("Seeding production_logs table...")
            insert_production = f"INSERT INTO production_logs (date, shaft, tons_milled, head_grade_cu, recovery_rate, concentrate_produced) VALUES ({param_style}, {param_style}, {param_style}, {param_style}, {param_style}, {param_style});"
            if is_sqlite:
                insert_production = insert_production.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
            production_rows = [
                ("2026-04-01", "Pit 1 - Lake Victoria", 4200.0, "3.15 g/t", "94.2%", 480.5),
                ("2026-04-02", "Pit 1 - Lake Victoria", 4350.0, "3.28 g/t", "94.5%", 510.2),
                ("2026-04-03", "Pit 1 - Lake Victoria", 4100.0, "3.05 g/t", "93.8%", 455.8),
                ("2026-04-04", "Underground - Bulawayo", 2100.0, "5.75 g/t", "96.1%", 385.0),
                ("2026-04-05", "Underground - Bulawayo", 2250.0, "5.82 g/t", "96.3%", 412.5),
                ("2026-04-06", "Pit 1 - Lake Victoria", 4500.0, "3.42 g/t", "94.8%", 545.0),
                ("2026-04-07", "Pit 1 - Lake Victoria", 4400.0, "3.35 g/t", "94.6%", 528.0),
                ("2026-04-08", "Underground - Bulawayo", 2300.0, "5.90 g/t", "96.4%", 425.0),
                ("2026-04-09", "Pit 1 - Lake Victoria", 4150.0, "3.10 g/t", "94.0%", 468.0),
                ("2026-04-10", "Pit 1 - Lake Victoria", 4600.0, "3.50 g/t", "95.0%", 568.0),
                ("2026-04-11", "Underground - Bulawayo", 2400.0, "6.05 g/t", "96.5%", 450.0),
                ("2026-04-12", "Pit 1 - Lake Victoria", 4300.0, "3.22 g/t", "94.3%", 495.0),
                ("2026-04-13", "Pit 1 - Lake Victoria", 4250.0, "3.18 g/t", "94.1%", 482.0),
                ("2026-04-14", "Underground - Bulawayo", 2200.0, "5.70 g/t", "96.0%", 395.0),
                ("2026-04-15", "Pit 1 - Lake Victoria", 4450.0, "3.30 g/t", "94.5%", 518.0),
            ]
            for row in production_rows:
                cur.execute(insert_production, row)

        cur.execute("SELECT COUNT(*) FROM department_budgets;")
        if cur.fetchone()[0] == 0:
            logger.info("Seeding department_budgets table...")
            insert_budget = f"INSERT INTO department_budgets (department, allocated, spent, variance, status) VALUES ({param_style}, {param_style}, {param_style}, {param_style}, {param_style});"
            if is_sqlite:
                insert_budget = insert_budget.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
            budget_rows = [
                ("exploration", 12000000.0, 5400000.0, 6600000.0, "under_budget"),
                ("mining_operations", 38000000.0, 20100000.0, 17900000.0, "under_budget"),
                ("processing", 28000000.0, 14200000.0, 13800000.0, "under_budget"),
                ("gemstone_recovery", 8500000.0, 4800000.0, 3700000.0, "under_budget"),
                ("environmental", 4500000.0, 2100000.0, 2400000.0, "under_budget"),
                ("safety", 6500000.0, 2900000.0, 3600000.0, "under_budget"),
                ("corporate", 9000000.0, 4200000.0, 4800000.0, "under_budget"),
                ("market_intelligence", 2000000.0, 850000.0, 1150000.0, "under_budget"),
            ]
            for row in budget_rows:
                cur.execute(insert_budget, row)

        cur.execute("SELECT COUNT(*) FROM equipment_status;")
        if cur.fetchone()[0] == 0:
            logger.info("Seeding equipment_status table...")
            insert_equip = f"INSERT INTO equipment_status (equipment_id, type, status, operating_hours, next_service, engine_temp_c, oil_pressure_psi) VALUES ({param_style}, {param_style}, {param_style}, {param_style}, {param_style}, {param_style}, {param_style});"
            if is_sqlite:
                insert_equip = insert_equip.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
            equip_rows = [
                ("TRK-001", "CAT 797F Haul Truck", "operational", 14250, "2026-08-20", 88.5, 65.0),
                ("TRK-002", "CAT 797F Haul Truck", "operational", 12800, "2026-09-10", 86.2, 67.5),
                ("TRK-003", "Komatsu 980E Haul Truck", "maintenance", 18500, "2026-07-25", 0.0, 0.0),
                ("LDR-001", "Komatsu WA1200 Loader", "operational", 9200, "2026-08-01", 82.0, 58.5),
                ("LDR-002", "CAT 994K Loader", "operational", 7800, "2026-08-15", 79.5, 60.0),
                ("DRL-001", "Sandvik DD421iJ Drill Rig", "operational", 4500, "2026-08-10", 78.0, 62.0),
                ("DRL-002", "Sandvik Leopard Di650i RC Drill", "operational", 3200, "2026-09-01", 80.5, 59.0),
                ("DRL-003", "Boart Longyear LR90", "maintenance", 6800, "2026-07-22", 0.0, 0.0),
                ("CR-001", "Metso HP500 Cone Crusher", "operational", 18200, "2026-08-25", 84.0, 70.0),
                ("CR-002", "Sandvik CJ613 Jaw Crusher", "operational", 15600, "2026-09-15", 82.5, 68.0),
                ("MILL-001", "Metso DM5600 Ball Mill", "operational", 22000, "2026-08-15", 75.0, 0.0),
                ("CV-001", "Overland Conveyor 1200mm", "operational", 28000, "2026-07-30", 65.0, 0.0),
                ("CV-002", "Stacker Conveyor 900mm", "operational", 18000, "2026-08-10", 62.5, 0.0),
                ("PUMP-001", "Metso MP1250 CIL Pump", "operational", 10500, "2026-08-20", 55.0, 45.0),
                ("PUMP-002", "Sulzer Dewatering Pump", "operational", 8200, "2026-08-05", 52.0, 42.0),
            ]
            for row in equip_rows:
                cur.execute(insert_equip, row)

        cur.execute("SELECT COUNT(*) FROM sops;")
        if cur.fetchone()[0] == 0:
            logger.info("Seeding sops table...")
            insert_sop = f"INSERT INTO sops (topic, code, title, content) VALUES ({param_style}, {param_style}, {param_style}, {param_style});"
            if is_sqlite:
                insert_sop = insert_sop.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
            sop_rows = [
                ("gold_mining", "SOP-GOLD-001", "Gold Recovery CIL Circuit Operation",
                 "1. Maintain cyanide concentration at 150-300 ppm NaCN in leach tanks.\n2. Control pH at 10.0-10.5 using lime dosing.\n3. Monitor carbon loading every 4 hours; replace carbon when gold loading reaches 2000 g/t.\n4. Verify pulp density at 40-50% solids.\n5. Sample tails every 4 hours; target <0.02 g/t Au in tails.\n6. Maintain dissolved oxygen above 6 ppm in leach tanks."),
                ("gold_mining", "SOP-GOLD-002", "Gravity Gold Recovery Procedure",
                 "1. Feed ball mill discharge to Knelson concentrator at 40% solids.\n2. Adjust centrifuge speed to 100-150 G-force based on particle size.\n3. Discharge concentrate every 2 hours to shaker table.\n4. Clean gold from concentrate using panning and acid wash.\n5. Melt gold doré bar in induction furnace at 1064°C.\n6. Weigh, assay, and record doré production daily."),
                ("gemstone", "SOP-GEM-001", "Tanzanite Sorting and Grading",
                 "1. Sort rough tanzanite by size and color under controlled D65 lighting.\n2. Grade stones: AAA (vivid blue, >5ct), AA (blue-violet, 2-5ct), A (violet-blue, 1-3ct), Commercial (<1ct or included).\n3. Record carat weight, color grade, and clarity for each stone.\n4. Heat treatment: 500-600°C for 2-4 hours to enhance blue color.\n5. Package stones in anti-static containers for secure transport.\n6. Submit daily production report with carat totals and average price."),
                ("safety", "SOP-SAFE-001", "Underground Refuge Chamber Protocol",
                 "1. If alarm sounds, proceed to nearest refuge chamber immediately.\n2. Seal chamber door and activate oxygen scrubber system.\n3. Use VHF Radio Channel 1 to communicate with surface dispatch.\n4. Shift supervisor must account for all personnel.\n5. Do not exit until ALL CLEAR given by Mine Safety Officer.\n6. Test refuge chamber equipment monthly; document results."),
                ("environmental", "SOP-ENV-001", "Cyanide Management and Spill Response",
                 "1. Store cyanide in locked, ventilated facility with secondary containment.\n2. Measure cyanide concentration before each shift.\n3. Maintain pH >10.5 in cyanide solutions to prevent HCN generation.\n4. In case of spill: evacuate area upwind, notify Environmental Officer within 5 minutes.\n5. Contain spill with berms; apply sodium hypochlorite for neutralization.\n6. Report any cyanide-related incident to regulatory authorities within 24 hours."),
                ("exploration", "SOP-EXPL-001", "Soil Sampling for Gold Exploration",
                 "1. Establish sample grid (100m x 25m) based on geology and terrain.\n2. Collect B-horizon soil samples (20-40cm depth) using hand auger.\n3. Record GPS coordinates, elevation, and description for each station.\n4. Sample 1-2 kg material; sieve to -2mm fraction.\n5. Submit samples for fire assay (Au) and ICP-MS multi-element analysis.\n6. Flag anomalies: Au >20 ppb, As >50 ppm, Sb >5 ppm."),
            ]
            for row in sop_rows:
                cur.execute(insert_sop, row)

        conn.commit()
        cur.close()
        logger.info("Database seeding successfully completed.")
    except Exception as e:
        logger.error(f"Error seeding database: {e}", exc_info=True)
        try:
            conn.rollback()
        except:
            pass
