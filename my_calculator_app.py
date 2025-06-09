#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import numpy as np
import copy

# --------------------------------------------------------------------------
#  核心计算函数 - 已升级以支持特殊限制
# --------------------------------------------------------------------------
def solve_product_distribution(
    total_products: int,
    total_quantity: int,
    total_price_with_tax: float,
    tax_rate: float,
    known_prices: list[float],
    x_price_range: list[float],
    constraints: list = None, # 新增参数：用于接收限制规则
    quantity_tolerance: int = 2,
    max_iterations: int = 200
) -> dict:
    """
    在满足总价和总数约束下，均衡分配商品件数并估算未知单价。
    新版支持对特定商品添加数量限制。
    """
    # --- 阶段一：根据限制规则，进行带偏向的初始数量分配 ---
    
    # 1. 先进行一次理论上的“绝对平均”分配
    base_quantity = total_quantity // total_products
    remainder = total_quantity % total_products
    quantities = [base_quantity + 1] * remainder + [base_quantity] * (total_products - remainder)
    
    # 2. 应用限制规则 (这是一个简化的约束满足过程)
    if constraints:
        # 创建一个副本用于调整
        temp_quantities = copy.deepcopy(quantities)
        
        # 预处理：将限制转换为字典，方便查询
        # {product_index: {'type': '>=', 'value': 5}, ...}
        rules = {c['idx'] - 1: {'type': c['type'], 'value': c['value']} for c in constraints}
        
        # 多轮调整以尽量满足所有约束
        for _ in range(total_products * 2): 
            # 应用固定规则
            for i in range(total_products):
                if i in rules and rules[i]['type'] == '==':
                    temp_quantities[i] = rules[i]['value']

            # 计算当前总数与目标总数的差距
            current_total = sum(temp_quantities)
            delta = total_quantity - current_total
            
            # 将差距分配给未被固定的商品
            unlocked_indices = [i for i in range(total_products) if not (i in rules and rules[i]['type'] == '==')]
            if unlocked_indices:
                # 简单地平分差额
                add_each = delta // len(unlocked_indices)
                remainder_add = delta % len(unlocked_indices)
                for i in unlocked_indices:
                    temp_quantities[i] += add_each
                for i in range(remainder_add):
                    temp_quantities[unlocked_indices[i]] += 1
            
            # 应用最多/最少规则
            for i in range(total_products):
                if i in rules:
                    if rules[i]['type'] == '>=' and temp_quantities[i] < rules[i]['value']:
                        temp_quantities[i] = rules[i]['value']
                    elif rules[i]['type'] == '<=' and temp_quantities[i] > rules[i]['value']:
                        temp_quantities[i] = rules[i]['value']
        
        # 最后一轮平衡总数
        final_delta = total_quantity - sum(temp_quantities)
        if unlocked_indices:
            temp_quantities[unlocked_indices[0]] += final_delta

        quantities = temp_quantities

    # --- 阶段二：在满足限制的基础上，进行价格平衡微调 ---
    
    priced_items = sorted([(price, i) for i, price in enumerate(known_prices)], key=lambda item: item[0])
    target_pre_tax_price = total_price_with_tax / (1 + tax_rate)

    for i in range(max_iterations):
        known_items_price = sum(quantities[j] * known_prices[j] for j in range(total_products - 1))
        
        if quantities[-1] == 0:
            return {"status": "错误", "message": "未知单价商品数量为0，无法求解 x"}
            
        calculated_x = (target_pre_tax_price - known_items_price) / quantities[-1]

        if x_price_range[0] <= calculated_x <= x_price_range[1]:
            # 找到解，返回前最后检查总数
            if sum(quantities) != total_quantity:
                 return {"status": "错误", "message": f"最终件数总和 {sum(quantities)} 不等于目标总数 {total_quantity}，请检查限制条件是否冲突。"}
            return {"status": "成功", "message": "找到最优解。", "counts": quantities, "estimated_price_x": round(calculated_x, 4)}

        # 调整逻辑需要判断是否会违反约束
        def is_valid_swap(qtys, from_idx, to_idx, rules):
            # 减少一个是否违规
            if from_idx in rules:
                rule = rules[from_idx]
                if rule['type'] == '==' or (rule['type'] == '>=' and qtys[from_idx] - 1 < rule['value']):
                    return False
            # 增加一个是否违规
            if to_idx in rules:
                rule = rules[to_idx]
                if rule['type'] == '==' or (rule['type'] == '<=' and qtys[to_idx] + 1 > rule['value']):
                    return False
            return True

        # 价格平衡调整
        if calculated_x > x_price_range[1]: # 提升已知商品总价
            for _, low_idx in priced_items:
                if quantities[low_idx] > 0:
                    for _, high_idx in reversed(priced_items):
                        if low_idx != high_idx and is_valid_swap(quantities, low_idx, high_idx, rules if constraints else {}):
                            quantities[low_idx] -= 1
                            quantities[high_idx] += 1
                            break
                    break
        elif calculated_x < x_price_range[0]: # 降低已知商品总价
            for _, high_idx in reversed(priced_items):
                if quantities[high_idx] > 0:
                    for _, low_idx in priced_items:
                        if low_idx != high_idx and is_valid_swap(quantities, high_idx, low_idx, rules if constraints else {}):
                            quantities[high_idx] -= 1
                            quantities[low_idx] += 1
                            break
                    break
    
    # 如果循环结束还没找到解
    final_x = (target_pre_tax_price - sum(quantities[j] * known_prices[j] for j in range(total_products - 1))) / quantities[-1]
    return {"status": "警告", "message": f"达到最大迭代次数，未找到完美解。当前解的 x 值为 {final_x:.4f}。", "counts": quantities, "estimated_price_x": round(final_x, 4)}

# --------------------------------------------------------------------------
#  网站界面代码 - 已升级
# --------------------------------------------------------------------------

# 初始化会话状态，用于存储动态添加的限制规则
if 'constraints' not in st.session_state:
    st.session_state.constraints = []

st.set_page_config(page_title="商品件数均衡分配计算器", layout="wide")
st.title("📦 智能商品件数分配器")

# --- 主要输入区域 ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("基本信息")
    total_quantity_input = st.number_input("1. 商品总件数 (N)", value=92)
    total_price_input = st.number_input("2. 含税总价 (P_total)", value=31595.16)
    tax_rate_input = st.number_input("3. 税率 (R)", value=0.13, format="%.2f")

with col2:
    st.subheader("商品价格")
    prices_str = st.text_area("4. 已知商品单价列表 (英文逗号隔开)", "218, 268, 258, 308, 228, 480, 318")
    st.info("未知商品的价格范围将根据上方列表的最高价和最低价自动设定。")

st.divider()

# --- 可选的特殊限制模块 ---
st.subheader("特殊限制 (可选)")
if st.checkbox("启用特殊限制（如季节、库存等）"):
    st.caption("在这里为特定商品添加数量限制。商品序号从1开始，对应上方价格列表的顺序。")

    # 显示已添加的限制规则
    for i, constraint in enumerate(st.session_state.constraints):
        c1, c2, c3, c4 = st.columns([2, 3, 2, 1])
        constraint['idx'] = c1.number_input("商品序号", min_value=1, key=f"idx_{i}", value=constraint['idx'])
        constraint['type'] = c2.selectbox("限制类型", options=['<= (最多)', '>= (最少)', '== (固定为)'], key=f"type_{i}", index=['<= (最多)', '>= (最少)', '== (固定为)'].index(constraint['type']))
        constraint['value'] = c3.number_input("数量", min_value=0, key=f"val_{i}", value=constraint['value'])
        if c4.button("删除", key=f"del_{i}"):
            st.session_state.constraints.pop(i)
            st.rerun() # 重新运行刷新界面

    if st.button("➕ 增加一条限制"):
        st.session_state.constraints.append({'idx': 1, 'type': '<= (最多)', 'value': 1})
        st.rerun()

st.divider()

# --- 计算按钮和结果显示 ---
if st.button("🚀 开始计算", use_container_width=True, type="primary"):
    try:
        known_prices_list = [float(p.strip()) for p in prices_str.split(',')]
        total_products_count = len(known_prices_list) + 1

        if not known_prices_list:
             st.error("请输入至少一个已知商品的价格！")
        else:
            x_range_auto = [min(known_prices_list), max(known_prices_list)]
            
            # 清理和传递限制规则
            active_constraints = []
            if 'constraints' in st.session_state:
                for c in st.session_state.constraints:
                    # 转换 '>= (最少)' 为 '>='
                    clean_type = c['type'].split(' ')[0]
                    active_constraints.append({'idx': c['idx'], 'type': clean_type, 'value': c['value']})
            
            result = solve_product_distribution(
                total_products=total_products_count,
                total_quantity=int(total_quantity_input),
                total_price_with_tax=float(total_price_input),
                tax_rate=float(tax_rate_input),
                known_prices=known_prices_list,
                x_price_range=x_range_auto,
                constraints=active_constraints # 传递限制规则
            )

            st.subheader("计算结果")
            st.write(f"**自动设定的价格范围:** `{x_range_auto}`")

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
        st.error(f"输入数据有误或计算出错，请检查！\n错误信息: {e}")

