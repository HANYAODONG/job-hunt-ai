"""Import the canonical role-pool v2 package into isolated Neo4j labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from neo4j import GraphDatabase


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def batches(rows: Iterable[dict], size: int) -> Iterable[list[dict]]:
    batch: list[dict] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def run_batches(session, query: str, path: Path, batch_size: int) -> int:
    count = 0
    for batch in batches(read_jsonl(path), batch_size):
        session.run(query, rows=batch).consume()
        count += len(batch)
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import isolated canonical role-pool v2 graph data")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--clear-v2", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    required = {
        "jobs": args.input_dir / "jobs.jsonl",
        "roles": args.input_dir / "canonical_roles.jsonl",
        "skills": args.input_dir / "skills.jsonl",
        "relationships": args.input_dir / "relationships.jsonl",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing graph package files: {missing}")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        driver.verify_connectivity()
        with driver.session(database=args.database) as session:
            if args.clear_v2:
                session.run("MATCH (n:V2Job) DETACH DELETE n").consume()
                session.run("MATCH (n:V2CanonicalRole) DETACH DELETE n").consume()
                session.run("MATCH (n:V2Skill) DETACH DELETE n").consume()

            session.run(
                "CREATE CONSTRAINT v2_job_id IF NOT EXISTS "
                "FOR (n:V2Job) REQUIRE n.job_id IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT v2_role_id IF NOT EXISTS "
                "FOR (n:V2CanonicalRole) REQUIRE n.canonical_role_id IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT v2_skill_id IF NOT EXISTS "
                "FOR (n:V2Skill) REQUIRE n.skill_id IS UNIQUE"
            ).consume()

            counts = {
                "jobs": run_batches(
                    session,
                    "UNWIND $rows AS row MERGE (n:V2Job {job_id: row.job_id}) "
                    "SET n += row, n.role_pool_version = 'v2'",
                    required["jobs"],
                    args.batch_size,
                ),
                "roles": run_batches(
                    session,
                    "UNWIND $rows AS row "
                    "MERGE (n:V2CanonicalRole {canonical_role_id: row.canonical_role_id}) "
                    "SET n += row, n.role_pool_version = 'v2'",
                    required["roles"],
                    args.batch_size,
                ),
                "skills": run_batches(
                    session,
                    "UNWIND $rows AS row MERGE (n:V2Skill {skill_id: row.skill_id}) "
                    "SET n += row, n.role_pool_version = 'v2'",
                    required["skills"],
                    args.batch_size,
                ),
            }

            relationship_rows = list(read_jsonl(required["relationships"]))
            instance_rows = [row for row in relationship_rows if row["relationship"] == "INSTANCE_OF"]
            skill_rows = [row for row in relationship_rows if row["relationship"] == "REQUIRES_SKILL"]
            counts["instance_of"] = 0
            for batch in batches(instance_rows, args.batch_size):
                session.run(
                    "UNWIND $rows AS row "
                    "MATCH (j:V2Job {job_id: row.from_id}) "
                    "MATCH (r:V2CanonicalRole {canonical_role_id: row.to_id}) "
                    "MERGE (j)-[e:INSTANCE_OF]->(r) SET e.role_pool_version = 'v2'",
                    rows=batch,
                ).consume()
                counts["instance_of"] += len(batch)

            counts["requires_skill"] = 0
            for batch in batches(skill_rows, args.batch_size):
                session.run(
                    "UNWIND $rows AS row "
                    "MATCH (j:V2Job {job_id: row.from_id}) "
                    "MATCH (s:V2Skill {skill_id: row.to_id}) "
                    "MERGE (j)-[e:REQUIRES_SKILL]->(s) SET e.role_pool_version = 'v2'",
                    rows=batch,
                ).consume()
                counts["requires_skill"] += len(batch)

            verified = session.run(
                "MATCH (j:V2Job) WITH count(j) AS jobs "
                "MATCH (r:V2CanonicalRole) WITH jobs, count(r) AS roles "
                "MATCH (s:V2Skill) WITH jobs, roles, count(s) AS skills "
                "MATCH (:V2Job)-[i:INSTANCE_OF]->(:V2CanonicalRole) "
                "WITH jobs, roles, skills, count(i) AS instance_of "
                "MATCH (:V2Job)-[q:REQUIRES_SKILL]->(:V2Skill) "
                "RETURN jobs, roles, skills, instance_of, count(q) AS requires_skill"
            ).single().data()

        print(json.dumps({"submitted": counts, "verified": verified}, ensure_ascii=False, indent=2))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
