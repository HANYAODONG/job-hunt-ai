"""
Node2Vec 图嵌入模块 - 用于计算岗位与候选人之间的图谱关联度
"""
import logging
import pickle
from pathlib import Path
from typing import List, Tuple
import numpy as np
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity
from app.services.knowledge_graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)
kg_service = KnowledgeGraphService()

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "node2vec_model.pkl"
NODE_MAP_PATH = MODEL_DIR / "node_id_map.pkl"


def export_edges_from_neo4j() -> List[Tuple[str, str]]:
    """从Neo4j导出所有(HAS_SKILL, REQUIRES_SKILL)关系作为边列表"""
    edges = []
    try:
        with kg_service.neo4j.get_session() as session:
            query1 = """
            MATCH (c:Candidate)-[:HAS_SKILL]->(s:Skill)
            RETURN c.id AS source, s.name AS target
            """
            result1 = session.run(query1)
            for record in result1:
                edges.append((record["source"], record["target"]))

            query2 = """
            MATCH (j:Job)-[:REQUIRES_SKILL]->(s:Skill)
            RETURN j.id AS source, s.name AS target
            """
            result2 = session.run(query2)
            for record in result2:
                edges.append((record["source"], record["target"]))

        logger.info(f"从Neo4j导出 {len(edges)} 条边")
        return edges
    except Exception as e:
        logger.error(f"导出边失败: {e}")
        return []


def train_node2vec_model(edges: List[Tuple[str, str]], dimensions: int = 128, walk_length: int = 30, num_walks: int = 200, workers: int = 4):
    """训练Node2Vec模型"""
    if not edges:
        logger.error("边列表为空，无法训练")
        return None

    try:
        from node2vec import Node2Vec
    except ImportError:
        logger.error("node2vec is not installed. Install it before training graph embeddings.")
        return None

    logger.info(f"开始训练Node2Vec模型，边数: {len(edges)}")
    
    G = nx.Graph()
    for source, target in edges:
        G.add_edge(source, target)
    
    logger.info(f"图构建完成，节点数: {G.number_of_nodes()}")
    
    node2vec = Node2Vec(
        G,
        dimensions=dimensions,
        walk_length=walk_length,
        num_walks=num_walks,
        workers=workers
    )
    
    model = node2vec.fit(window=10, min_count=1, batch_words=4)
    logger.info("Node2Vec模型训练完成")
    return model


def train_and_save_model():
    """完整训练流程"""
    edges = export_edges_from_neo4j()
    if not edges:
        logger.error("没有边数据，训练终止")
        return False

    model = train_node2vec_model(edges)
    if model is None:
        return False

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)

    all_nodes = list(set([e[0] for e in edges] + [e[1] for e in edges]))
    node_map = {node: idx for idx, node in enumerate(all_nodes)}
    with open(NODE_MAP_PATH, 'wb') as f:
        pickle.dump(node_map, f)

    logger.info(f"模型保存成功: {MODEL_PATH}")
    logger.info(f"节点映射保存成功: {NODE_MAP_PATH}")
    logger.info(f"总节点数: {len(all_nodes)}")
    return True


def load_model():
    """加载已训练的模型"""
    try:
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
        with open(NODE_MAP_PATH, 'rb') as f:
            node_map = pickle.load(f)
        logger.info("模型加载成功")
        return model, node_map
    except FileNotFoundError:
        logger.warning("模型文件不存在，请先运行 train_and_save_model()")
        return None, None


def get_graph_relatedness(candidate_id: str, job_id: str) -> float:
    """计算候选人与岗位的图谱关联度"""
    model, _ = load_model()
    if model is None:
        return 0.5

    try:
        vec1 = model.wv.get_vector(candidate_id)
        vec2 = model.wv.get_vector(job_id)
        similarity = cosine_similarity([vec1], [vec2])[0][0]
        return round((similarity + 1) / 2, 4)
    except KeyError:
        return 0.0
