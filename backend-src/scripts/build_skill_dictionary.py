import csv

# 读取原始技能
with open('skills_temp.txt', 'r', encoding='utf-8') as f:
    skills = [line.strip() for line in f if line.strip()]

# 按中文/英文粗略分类（你可以手动调整）
# 这里先全部放在"通用技能"下，后面你可以按需调整
with open('standard_skill_dictionary.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['skill_id', 'canonical_name', 'aliases', 'skill_category', 'parent_skill', 'match_pattern', 'source', 'version'])
    for idx, skill in enumerate(skills, 1):
        # 如果有别名可以加在 aliases 里，这里先留空
        writer.writerow([
            f'SK{idx:03d}',
            skill,
            '',  # aliases，后面可补充
            '通用技能',  # skill_category
            '',  # parent_skill
            '',  # match_pattern
            'data_collection',
            'v1'
        ])

print(f'已生成 standard_skill_dictionary.csv，共 {len(skills)} 条')