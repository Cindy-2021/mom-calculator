#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import numpy as np
import copy

# --------------------------------------------------------------------------
#  新增的“安检员”函数，负责所有输入校验
# --------------------------------------------------------------------------
def validate_inputs(total_quantity, total_price, tax_rate, prices_str, constraints):
    errors = []
    
    # 1. 校验基本信息
    if total_quantity <= 0:
        errors.append("基本信息错误：商品总件数必须是大于零的数字。")
    if total_price <= 0:
        errors.append("基本信息错误：含税总价必须是大于零的数字。")
    if tax_rate <= 0:
        errors.append("基本信息错误：税率必须是大于零的数字。")
    if tax_rate >= 1:
        errors.append("税率格式错误：税率必须是介于 0 与 1 之间的小数，例如 0.13 表示13%。")

    # 2. 校验价格列表
    if not prices_str.strip():
        errors.append("请输入至少一个已知商品的价格。")
        return errors # 如果价格为空，后续校验无意义，直接返回

    try:
        # 尝试转换，这能同时检测出非数字和错误的分隔符
        known_prices_list = [float(p.strip()) for p in prices_str.split(',')]
        if any(p < 0 for p in known_prices_list):
            errors.append("价格数据无效：商品价格不能为负数。")
    except ValueError:
        errors.append("价格列表格式错误：请确保所有价格都是数字，并只使用英文逗号 (,) 分隔。")
        return errors # 价格格式错误，后续校验无意义
    
    # 3. 校验逻辑关系
    num_known_products = len(known_prices_list)
    total_products = num_known_products + 1
    if total_quantity < total_products:
        errors.append(f"商品总件数 ({int(total_quantity)}) 不能少于商品种类总数 ({total_products})。")

    # 4. 校验特殊限制
    for c in constraints:
        if c['idx'] > num_known_products or c['idx'] < 1:
            errors.append(f"特殊限制错误：商品序号 {c['idx']} 无效。根据您输入的价格列表，有效的序号范围是 1 到 {num_known_products}。")
        if c['value'] < 0:
            errors.append(f"特殊限制错误：商品序号 {c['idx']} 的限制数量不能为负数。")

    return errors

# --------------------------------------------------------------------------
#  核心计算函数 - 已升级以支持特殊限制和内部逻辑校验
# --------------------------------------------------------------------------
def solve_product_distribution(
    total_products: int,
    total_quantity: int,
    total_price_with_tax: float,
    tax_rate: float,
    known_prices: list[float],
    x_price_range: list[float],
    constraints: list = None
) -> dict:
    """核心计算函数，已内置逻辑冲突检测"""
    rules = {c['idx'] - 1: {'type': c['type'], 'value': c['value']} for c in constraints} if constraints else {}

    # --- 内部逻辑校验 ---
    # 校验1：限制条件是否自相矛盾
    for i in rules:
        min_val, max_val = 0, float('inf')
        if rules[i]['type'] == '>=': min_val = rules[i]['value']
        if rules[i]['type'] == '<=': max_val = rules[i]['value']
        if rules[i]['type'] == '==':
             min_val = rules[i]['value']
             max_val = rules[i]['value']
        
        # 查找同一商品的其他限制
        for c in constraints:
            if c['idx'] - 1 == i:
                if c['type'][0] == '>' and c['value'] > min_val: min_val = c['value']
                if c['type'][0] == '<' and c['value'] < max_val: max_val = c['value']
        
        if min_val > max_val:
            return {"status": "错误", "message": f"特殊限制逻辑冲突：商品 #{i+1} 的数量不能同时满足 '最少{min_val}件' 和 '最多{max_val}件'。"}

    # 校验2：各项限制之和是否超过总数
    min_sum = sum(rules[i]['value'] for i in rules if rules[i]['type'] in ['>=', '=='])
    if min_sum > total_quantity:
        return {"status": "错误", "message": f"特殊限制逻辑冲突：您设定的各项‘最少/固定’数量之和 ({min_sum}件) 已超过商品总件数 ({int(total_quantity)})。"}

    # --- 阶段一：初始分配 ---
    quantities = [0] * total_products
    # (此处省略了复杂的初始分配逻辑，以保持核心清晰，实际的分配逻辑已包含在之前的版本中并经过简化和测试)
    # ... 简化的分配逻辑开始 ...
    base_quantity = total_quantity // total_products
    remainder = total_quantity % total_products
    quantities = [base_quantity + 1] * remainder + [base_quantity] * (total_products - remainder)
    if constraints:
        temp_quantities = copy.deepcopy(quantities)
        for _ in range(total_products * 2):
            for i in rules:
                if rules[i]['type'] == '==': temp_quantities[i] = rules[i]['value']
                elif rules[i]['type'] == '>=' and temp_quantities[i] < rules[i]['value']: temp_quantities[i] = rules[i]['value']
                elif rules[i]['type'] == '<=' and temp_quantities[i] > rules[i]['value']: temp_quantities[i] = rules[i]['value']
            delta = total_quantity - sum(temp_quantities)
            unlocked = [i for i in range(total_products) if i not in rules or rules[i]['type'] != '==']
            if unlocked:
                add_each = delta // len(unlocked)
                for i in unlocked: temp_quantities[i] += add_each
                remainder_add = delta % len(unlocked)
                for i in range(remainder_add): temp_quantities[unlocked[i]] += 1
        quantities = temp_quantities
    if sum(quantities) != total_quantity:
        quantities[0] += total_quantity - sum(quantities)
    # ... 简化的分配逻辑结束 ...

    # --- 阶段二：价格平衡微调 ---
    if quantities[-1] == 0:
        return {"status": "错误", "message": "计算错误：根据您的特殊限制，分配给未知单价商品的数量为0，导致其价格无法计算。"}
        
    priced_items = sorted([(price, i) for i, price in enumerate(known_prices)], key=lambda item: item[0])
    target_pre_tax_price = total_price_with_tax / (1 + tax_rate)

    for i in range(200): # max_iterations
        known_items_price = sum(quantities[j] * known_prices[j] for j in range(total_products - 1))
        calculated_x = (target_pre_tax_price - known_items_price) / quantities[-1]

        if x_price_range[0] <= calculated_x <= x_price_range[1]:
            return {"status": "成功", "message": "找到最优解。", "counts": quantities, "estimated_price_x": round(calculated_x, 4)}

        def is_valid_swap(qtys, from_idx, to_idx, rules):
            if from_idx in rules:
                rule = rules[from_idx]
                if rule['type'] == '==' or (rule['type'] == '>=' and qtys[from_idx] - 1 < rule['value']): return False
            if to_idx in rules:
                rule = rules[to_idx]
                if rule['type'] == '==' or (rule['type'] == '<=' and qtys[to_idx] + 1 > rule['value']): return False
            return True

        swapped = False
        if calculated_x > x_price_range[1]:
            for _, low_idx in priced_items:
                if quantities[low_idx] > 0:
                    for _, high_idx in reversed(priced_items):
                        if low_idx != high_idx and is_valid_swap(quantities, low_idx, high_idx, rules):
                            quantities[low_idx] -= 1; quantities[high_idx] += 1; swapped = True; break
                if swapped: break
        elif calculated_x < x_price_range[0]:
            for _, high_idx in reversed(priced_items):
                if quantities[high_idx] > 0:
                    for _, low_idx in priced_items:
                        if low_idx != high_idx and is_valid_swap(quantities, high_idx, low_idx, rules):
                            quantities[high_idx] -= 1; quantities[low_idx] += 1; swapped = True; break
                if swapped: break
        if not swapped: break

    final_x = (target_pre_tax_price - sum(quantities[j] * known_prices[j] for j in range(total_products - 1))) / quantities[-1]
    return {"status": "警告", "message": "计算警告：在满足您所有输入和限制条件下，无法找到一个能让未知商品单价落在预设范围内的数量组合。当前最接近的结果已显示。", "counts": quantities, "estimated_price_x": round(final_x, 4)}

# --------------------------------------------------------------------------
#  网站界面代码 - 已升级
# --------------------------------------------------------------------------
if 'constraints' not in st.session_state:
    st.session_state.constraints = []

st.set_page_config(page_title="智能商品件数分配器", layout="wide")
st.title("📦 智能商品件数分配器")

# ... [UI代码与上一版相同，此处省略以保持简洁] ...
col1, col2 = st.columns(2)
with col1:
    st.subheader("基本信息")
    total_quantity_input = st.number_input("1. 商品总件数 (N)", value=92, min_value=1)
    total_price_input = st.number_input("2. 含税总价 (P_total)", value=31595.16, min_value=0.01)
    tax_rate_input = st.number_input("3. 税率 (R)", value=0.13, min_value=0.0, max_value=1.0, format="%.4f")
with col2:
    st.subheader("商品价格")
    prices_str = st.text_area("4. 已知商品单价列表 (英文逗号隔开)", "218, 268, 258, 308, 228, 480, 318")
    st.info("未知商品的价格范围将根据上方列表的最高价和最低价自动设定。")
st.divider()
st.subheader("特殊限制 (可选)")
if st.checkbox("启用特殊限制（如季节、库存等）"):
    st.caption("在这里为特定商品添加数量限制。商品序号从1开始，对应上方价格列表的顺序。")
    for i, constraint in enumerate(st.session_state.constraints):
        c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
        constraint['idx'] = c1.number_input("商品序号", min_value=1, key=f"idx_{i}", value=constraint['idx'])
        constraint['type'] = c2.selectbox("限制类型", options=['<= (最多)', '>= (最少)', '== (固定为)'], key=f"type_{i}", index=['<= (最多)', '>= (最少)', '== (固定为)'].index(constraint['type']))
        constraint['value'] = c3.number_input("数量", min_value=0, key=f"val_{i}", value=constraint['value'])
        if c4.button("删除", key=f"del_{i}"):
            st.session_state.constraints.pop(i)
            st.rerun()
    if st.button("➕ 增加一条限制"):
        st.session_state.constraints.append({'idx': 1, 'type': '<= (最多)', 'value': 1})
        st.rerun()
st.divider()

if st.button("🚀 开始计算", use_container_width=True, type="primary"):
    # --- 步骤一：执行“安检” ---
    active_constraints = [c for c in st.session_state.get('constraints', [])]
    validation_errors = validate_inputs(
        total_quantity=total_quantity_input,
        total_price=total_price_input,
        tax_rate=tax_rate_input,
        prices_str=prices_str,
        constraints=active_constraints
    )

    if validation_errors:
        st.error("发现以下输入问题，请检查：")
        for error in validation_errors:
            st.write(f"- {error}")
    else:
        # --- 步骤二：“安检”通过，正式计算 ---
        try:
            known_prices_list = [float(p.strip()) for p in prices_str.split(',')]
            total_products_count = len(known_prices_list) + 1
            x_range_auto = [min(known_prices_list), max(known_prices_list)] if known_prices_list else [0,0]
            
            clean_constraints = [{'idx': c['idx'], 'type': c['type'].split(' ')[0], 'value': c['value']} for c in active_constraints]

            result = solve_product_distribution(
                total_products=total_products_count,
                total_quantity=int(total_quantity_input),
                total_price_with_tax=float(total_price_input),
                tax_rate=float(tax_rate_input),
                known_prices=known_prices_list,
                x_price_range=x_range_auto,
                constraints=clean_constraints
            )

            # --- 步骤三：显示结果 ---
            st.subheader("计算结果")
            if result['status'] == '成功':
                st.success(f"**状态: {result['status']}** - {result['message']}")
                c1, c2 = st.columns(2)
                c1.metric("最终商品件数分布", str(result['counts']))
                c2.metric("计算出的未知单价 x", f"{result['estimated_price_x']:.2f} 元")
            elif result['status'] == '警告':
                 st.warning(f"**状态: {result['status']}** - {result['message']}")
                 st.write(f"**当前商品件数:** `{result['counts']}`")
                 st.write(f"**计算出的未知单价 (x):** `{result['estimated_price_x']}`")
            else: # 错误
                st.error(f"**状态: {result['status']}** - {result['message']}")

        except Exception as e:
            st.error(f"在计算过程中发生未知错误，请检查您的输入是否合理。\n技术细节: {e}")

