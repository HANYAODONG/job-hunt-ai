import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from elasticsearch import Elasticsearch, helpers


class ChineseBM25Service:
    """Index and retrieve canonical Chinese job records with weighted BM25."""

    DEFAULT_INDEX_NAME = "bigcompany_jobs_v1"
    SEARCH_FIELDS = [
        "standard_job^7",
        "title^6",
        "job_family^6",
        "skills^5",
        "new_skills^4.5",
        "requirements^3",
        "responsibilities^2.5",
        "domain_context^1.5",
        "description",
        "all_text^0.5",
    ]

    def __init__(
        self,
        client: Elasticsearch,
        index_name: str = DEFAULT_INDEX_NAME,
    ) -> None:
        self.client = client
        self.index_name = index_name

    @staticmethod
    def index_definition() -> Dict[str, Any]:
        text_field = {
            "type": "text",
            "analyzer": "zh_mixed",
            "similarity": "job_bm25",
        }
        text_keyword_field = {
            **text_field,
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        }
        return {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "zh_mixed": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": ["lowercase"],
                        }
                    }
                },
                "similarity": {
                    "job_bm25": {
                        "type": "BM25",
                        "k1": 1.2,
                        "b": 0.75,
                    }
                },
            },
            "mappings": {
                "dynamic": False,
                "properties": {
                    "job_id": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "source_type": {"type": "keyword"},
                    "title": text_keyword_field,
                    "standard_job": text_keyword_field,
                    "standard_category": text_keyword_field,
                    "job_family": text_keyword_field,
                    "skills": text_keyword_field,
                    "traditional_skills": text_keyword_field,
                    "new_skills": text_keyword_field,
                    "domain_context": text_keyword_field,
                    "responsibilities": text_field,
                    "requirements": text_field,
                    "description": text_field,
                    "detailed": text_field,
                    "company": text_keyword_field,
                    "location": text_keyword_field,
                    "publish_time": {"type": "date", "ignore_malformed": True},
                    "publish_time_raw": {"type": "keyword", "index": False},
                    "content_hash": {"type": "keyword"},
                    "all_text": text_field,
                },
            },
        }

    def create_index(self, recreate: bool = False) -> None:
        if self.client.indices.exists(index=self.index_name):
            if not recreate:
                return
            self.client.indices.delete(index=self.index_name)
        self.client.indices.create(index=self.index_name, **self.index_definition())

    @staticmethod
    def normalize_terms(value: Any) -> List[str]:
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            raw_items = value.split(";")
        else:
            raw_items = []

        terms: List[str] = []
        seen: set[str] = set()
        for value in raw_items:
            item = str(value).strip()
            key = item.casefold()
            if item and key not in seen:
                terms.append(item)
                seen.add(key)
        return terms

    @staticmethod
    def first_text(row: Dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @classmethod
    def prepare_document(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        title = cls.first_text(row, "title", "job_title")
        standard_job = cls.first_text(row, "standard_job", "keyword")
        responsibilities = cls.first_text(row, "responsibilities", "job_responsibility")
        requirements = cls.first_text(row, "requirements", "job_requirement")
        detailed = cls.first_text(row, "detailed")
        description = cls.first_text(row, "description", "job_description")
        if not description:
            description = "\n".join(
                part for part in [responsibilities, requirements, detailed] if part
            )

        skills = cls.normalize_terms(row.get("skills") or row.get("tags"))
        traditional_skills = cls.normalize_terms(row.get("traditional_skills"))
        new_skills = cls.normalize_terms(row.get("new_skills"))
        domain_context = cls.normalize_terms(row.get("domain_context"))
        company = cls.first_text(row, "company", "company_name")
        location = cls.first_text(row, "location", "location_text", "city")

        document = {
            "job_id": cls.first_text(row, "job_id", "id"),
            "source": cls.first_text(row, "source"),
            "source_type": cls.first_text(row, "source_type"),
            "title": title,
            "standard_job": standard_job,
            "standard_category": cls.first_text(row, "standard_category"),
            "job_family": cls.first_text(row, "job_family") or standard_job,
            "skills": skills,
            "traditional_skills": traditional_skills,
            "new_skills": new_skills,
            "domain_context": domain_context,
            "responsibilities": responsibilities,
            "requirements": requirements,
            "description": description,
            "detailed": detailed,
            "company": company,
            "location": location,
            "publish_time": row.get("publish_time") or None,
            "publish_time_raw": cls.first_text(row, "publish_time_raw"),
            "content_hash": cls.first_text(row, "content_hash"),
        }
        document["all_text"] = " ".join(
            value
            for value in [
                title,
                standard_job,
                document["job_family"],
                " ".join(skills),
                " ".join(domain_context),
                responsibilities,
                requirements,
                description,
            ]
            if value
        )
        return document

    def iter_actions(self, input_path: Path) -> Iterable[Dict[str, Any]]:
        with input_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc
                document = self.prepare_document(row)
                if not document["job_id"]:
                    raise ValueError(f"Missing job_id at line {line_number}")
                yield {
                    "_op_type": "index",
                    "_index": self.index_name,
                    "_id": document["job_id"],
                    "_source": document,
                }

    def bulk_index(self, input_path: Path, batch_size: int = 500) -> Dict[str, Any]:
        self.client.indices.put_settings(
            index=self.index_name,
            settings={"index": {"refresh_interval": "-1"}},
        )
        succeeded = 0
        failed = 0
        errors: List[Dict[str, Any]] = []
        try:
            for success, result in helpers.streaming_bulk(
                self.client,
                self.iter_actions(input_path),
                chunk_size=batch_size,
                max_retries=3,
                initial_backoff=1,
                max_backoff=8,
                request_timeout=120,
                raise_on_error=False,
                raise_on_exception=False,
            ):
                if success:
                    succeeded += 1
                else:
                    failed += 1
                    if len(errors) < 20:
                        errors.append(result)
        finally:
            self.client.indices.put_settings(
                index=self.index_name,
                settings={"index": {"refresh_interval": "1s"}},
            )
            self.client.indices.refresh(index=self.index_name)
        return {
            "index_name": self.index_name,
            "input_path": str(input_path),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors,
            "document_count": self.client.count(index=self.index_name)["count"],
        }

    def search(
        self,
        query_text: str,
        size: int = 20,
        source_type: Optional[str] = None,
        location: Optional[str] = None,
        exclude_duplicates: bool = True,
    ) -> Dict[str, Any]:
        del exclude_duplicates  # Canonical Workflow 1 data is unique by job_id.
        filters: List[Dict[str, Any]] = []
        if source_type:
            filters.append({"term": {"source_type": source_type}})
        if location:
            filters.append({"match": {"location": {"query": location}}})

        bool_query: Dict[str, Any] = {
            "must": [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": self.SEARCH_FIELDS,
                        "type": "best_fields",
                        "operator": "or",
                        "minimum_should_match": "20%",
                        "tie_breaker": 0.2,
                    }
                }
            ],
            "should": [
                {"match_phrase": {"standard_job": {"query": query_text, "boost": 3.0}}},
                {"match_phrase": {"title": {"query": query_text, "boost": 2.0}}},
                {"match_phrase": {"job_family": {"query": query_text, "boost": 2.0}}},
                {"match_phrase": {"skills": {"query": query_text, "boost": 1.5}}},
            ],
            "filter": filters,
        }

        response = self.client.search(
            index=self.index_name,
            size=max(1, min(size, 200)),
            track_total_hits=True,
            query={"bool": bool_query},
            _source_excludes=["all_text"],
        )
        hits = []
        for rank, hit in enumerate(response["hits"]["hits"], start=1):
            hits.append({"rank": rank, "score": hit["_score"], **hit["_source"]})
        return {
            "index_name": self.index_name,
            "query": query_text,
            "took_ms": response["took"],
            "total": response["hits"]["total"]["value"],
            "hits": hits,
        }

    def stats(self) -> Dict[str, Any]:
        return {
            "index_name": self.index_name,
            "document_count": self.client.count(index=self.index_name)["count"],
            "search_fields": self.SEARCH_FIELDS,
        }
