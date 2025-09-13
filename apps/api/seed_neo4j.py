import os, csv
from pathlib import Path
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASS = os.getenv("NEO4J_PASS")

if not all([URI, USER, PASS]):
    raise SystemExit("Set NEO4J_URI, NEO4J_USER, NEO4J_PASS env vars first.")

default_csv = Path(__file__).resolve().parents[2] / "data" / "seeds" / "tickers.csv"
CSV_PATH = Path(os.getenv("SEED_CSV") or default_csv)
if not CSV_PATH.exists():
    raise SystemExit(f"Seed CSV not found: {CSV_PATH}")

rows = []
with CSV_PATH.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append({"ticker": r["ticker"].strip().upper(),
                     "name": r["name"].strip(),
                     "sector": r["sector"].strip()})

driver = GraphDatabase.driver(URI, auth=(USER, PASS))

with driver.session() as s:
    s.run("CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE")
    s.run("CREATE CONSTRAINT asset_ticker IF NOT EXISTS FOR (a:Asset) REQUIRE a.ticker IS UNIQUE")

    s.run("""
    UNWIND $rows AS row
    MERGE (sec:Sector {name: row.sector})
    MERGE (a:Asset {ticker: row.ticker})
      ON CREATE SET a.name = row.name
      ON MATCH SET a.name = coalesce(a.name, row.name)
    MERGE (a)-[:IN_SECTOR]->(sec)
    """, rows=rows)

    counts = s.run("""
    MATCH (a:Asset)-[r:IN_SECTOR]->(s:Sector)
    RETURN count(a) AS assets, count(DISTINCT s) AS sectors, count(r) AS rels
    """).single()

print(f"Seeded: assets={counts['assets']} sectors={counts['sectors']} rels={counts['rels']}")
driver.close()
