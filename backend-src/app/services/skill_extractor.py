"""
技能抽取与标准化模块
输入文本，输出标准技能列表
"""
import csv
import re
from pathlib import Path
from typing import List, Dict, Optional
import jieba


class SkillExtractor:
    def __init__(self, dictionary_path: Optional[str] = None):
        """
        初始化技能抽取器
        :param dictionary_path: 技能词典路径，默认指向项目根目录的 standard_skill_dictionary.csv
        """
        if dictionary_path is None:
            # 默认路径：项目根目录
            base_dir = Path(__file__).resolve().parent.parent.parent
            dictionary_path = base_dir / "standard_skill_dictionary.csv"
        self.dictionary_path = Path(dictionary_path)
        self.skills: List[Dict[str, str]] = []  # 存储所有技能条目
        self.alias_map: Dict[str, str] = {}     # 别名 -> 标准技能名
        self.name_to_skill: Dict[str, Dict] = {} # 标准技能名 -> 完整条目
        self._load_dictionary()
        # 把所有别名加入 jieba 词典，避免被切分
        for alias in self.alias_map.keys():
            jieba.add_word(alias)
        # 把所有技能名加入 jieba 词典
        for skill in self.skills:
            jieba.add_word(skill['canonical_name'])

    def _load_dictionary(self):
        """加载技能词典"""
        if not self.dictionary_path.exists():
            raise FileNotFoundError(f"技能词典不存在: {self.dictionary_path}")
        
        with open(self.dictionary_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                canonical = row.get('canonical_name', '').strip()
                if not canonical:
                    continue
                
                # 存储完整条目
                self.skills.append({
                    'skill_id': row.get('skill_id', ''),
                    'canonical_name': canonical,
                    'skill_category': row.get('skill_category', ''),
                    'parent_skill': row.get('parent_skill', ''),
                    'match_pattern': row.get('match_pattern', ''),
                })
                self.name_to_skill[canonical] = self.skills[-1]
                
                # 处理别名
                aliases = row.get('aliases', '').strip()
                if aliases:
                    for alias in aliases.split(';'):
                        alias = alias.strip()
                        if alias and alias.lower() not in self.alias_map:
                            self.alias_map[alias.lower()] = canonical
                
                # 标准技能名本身也作为别名（便于匹配）
                if canonical.lower() not in self.alias_map:
                    self.alias_map[canonical.lower()] = canonical
        
        print(f"[SkillExtractor] 加载完成，共 {len(self.skills)} 个技能，{len(self.alias_map)} 个别名映射")

    def extract(self, text: str) -> List[str]:
        """
        从文本中抽取技能，返回标准技能名列表
        使用 jieba 分词 + 别名匹配，提高召回率
        :param text: 输入文本
        :return: 标准技能名列表（去重）
        """
        if not text or not text.strip():
            return []
        
        text_lower = text.lower()
        found = []
        matched_canonical = set()
        
        # 1. 先用 jieba 分词，对每个词进行匹配
        words = jieba.lcut(text)
        for word in words:
            # 跳过单字符词（如 "R"），避免误抽
            if len(word) < 2:
                continue
            word_lower = word.lower().strip()
            if word_lower in self.alias_map:
                canonical = self.alias_map[word_lower]
                if canonical not in matched_canonical:
                    matched_canonical.add(canonical)
                    found.append(canonical)
        
        # 2. 再用长别名匹配（覆盖多词技能，如 "Machine Learning"）
        sorted_aliases = sorted(
            [(alias, canonical) for alias, canonical in self.alias_map.items() if len(alias.split()) > 1],
            key=lambda x: len(x[0]), 
            reverse=True
        )
        for alias, canonical in sorted_aliases:
            if alias in text_lower and canonical not in matched_canonical:
                matched_canonical.add(canonical)
                found.append(canonical)
        
        return found

    def extract_with_details(self, text: str) -> List[Dict]:
        """
        从文本中抽取技能，返回详细信息
        :param text: 输入文本
        :return: 包含技能名、类别、上位技能的列表
        """
        skills = self.extract(text)
        results = []
        for skill in skills:
            if skill in self.name_to_skill:
                info = self.name_to_skill[skill]
                results.append({
                    'skill': skill,
                    'skill_id': info['skill_id'],
                    'category': info['skill_category'],
                    'parent': info['parent_skill'],
                })
        return results


# 便捷函数：供外部直接调用
_extractor: Optional[SkillExtractor] = None

def get_extractor(dictionary_path: Optional[str] = None) -> SkillExtractor:
    """获取单例抽取器"""
    global _extractor
    if _extractor is None or dictionary_path is not None:
        _extractor = SkillExtractor(dictionary_path)
    return _extractor

def extract_skills(text: str) -> List[str]:
    """快速抽取技能"""
    return get_extractor().extract(text)