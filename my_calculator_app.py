#!/usr/bin/env python
# coding: utf-8

# In[1]:


import streamlit as st
import numpy as np

# --------------------------------------------------------------------------
#  这里是我们之前已经完成的、高效的“工程师版本”计算函数
#  我们直接把它复制到这里，作为一个核心的计算引擎。
# --------------------------------------------------------------------------
def solve_product_distribution(
    total_products: int,
    total_quantity: int,
    total_price_with_tax: float,
    tax_rate: float,
    known_prices: list[float],
    x_price_range: list[float],
    quantity_tolerance: int = 2,
    max_iterations: int = 200
) -> dict:
    """在满足总价和总数约束下，均衡分配商品件数并估算未知单价。"""
    base_quantity = total_quantity // total_products
    remainder = total_quantity % total_products
    quantities = [base_quantity + 1] * remainder + [base_quantity] * (total_products - remainder)
    
    priced_items = sorted([(price, i) for i, price in enumerate(known_prices)], key=lambda item: item[0])
    target_pre_tax_price = total_price_with_tax / (1 + tax_rate)

    for i in range(max_iterations):
        known_items_price = sum(quantities[j] * known_prices[j] for j in range(total_products - 1))
        
        if quantities[-1] == 0:
            return {"status": "错误", "message": "第8种商品数量为0，无法求解 x"}
            
        calculated_x = (target_pre_tax_price - known_items_price) / quantities[-1]

        if x_price_range[0] <= calculated_x <= x_price_range[1]:
            return {
                "status": "成功",
                "message": "找到最优解。",
                "counts": quantities,
                "estimated_price_x": round(calculated_x, 4)
            }

        if calculated_x > x_price_range[1]:
            for _, low_idx in priced_items:
                if quantities[low_idx] > base_quantity - quantity_tolerance:
                    for _, high_idx in reversed(priced_items):
                        if low_idx != high_idx:
                            quantities[low_idx] -= 1
                            quantities[high_idx] += 1
                            break
                    break
        elif calculated_x < x_price_range[0]:
            for _, high_idx in reversed(priced_items):
                if quantities[high_idx] > base_quantity - quantity_tolerance:
                    for _, low_idx in priced_items:
                        if low_idx != high_idx:
                            quantities[high_idx] -= 1
                            quantities[low_idx] += 1
                            break
                    break
    
    # 如果循环结束还没找到解
    known_items_price = sum(quantities[j] * known_prices[j] for j in range(total_products - 1))
    final_x = (target_pre_tax_price - known_items_price) / quantities[-1]
    return {
        "status": "警告",
        "message": f"达到最大迭代次数，未找到完美解。当前解的 x 值为 {final_x:.4f}，已超出范围 {x_price_range}。",
        "counts": quantities,
        "estimated_price_x": round(final_x, 4)
    }

# --------------------------------------------------------------------------
#  这就是我们网站的全部界面代码，非常简洁！
# --------------------------------------------------------------------------

# 设置网页标题
st.set_page_config(page_title="商品件数均衡分配计算器", layout="wide")
st.title("📦 商品件数均衡分配计算器")

# 使用列布局让界面更美观
col1, col2 = st.columns(2)

with col1:
    st.subheader("基本信息")
    # 创建输入框，并填入默认值方便测试
    total_quantity_input = st.number_input("1. 商品总件数 (N)", value=92)
    total_price_input = st.number_input("2. 含税总价 (P_total)", value=31595.16)
    tax_rate_input = st.number_input("3. 税率 (R)", value=0.13, format="%.2f")

with col2:
    st.subheader("商品价格")
    # 用文本区域输入多个价格，并提供说明
    prices_str = st.text_area(
        "4. 已知商品单价列表 (英文逗号隔开)", 
        "218, 268, 258, 308, 228, 480, 318"
    )
    # st.slider可以创建一个滑动条输入
    x_range_input = st.slider(
        "5. 最后一行商品的价格范围",
        min_value=0.0, max_value=1000000.0, value=(200.0, 400.0)
    )

# 创建一个居中的计算按钮
st.divider() # 分割线
if st.button("🚀 开始计算", use_container_width=True):
    try:
        # --- 1. 数据预处理 ---
        # 从文本框中解析价格列表
        known_prices_list = [float(p.strip()) for p in prices_str.split(',')]
        total_products_count = len(known_prices_list) + 1

        # --- 2. 调用核心函数 ---
        result = solve_product_distribution(
            total_products=total_products_count,
            total_quantity=int(total_quantity_input),
            total_price_with_tax=float(total_price_input),
            tax_rate=float(tax_rate_input),
            known_prices=known_prices_list,
            x_price_range=list(x_range_input)
        )

        # --- 3. 显示结果 ---
        st.subheader("计算结果")
        if result['status'] == '成功':
            st.success(f"**状态: {result['status']}** - {result['message']}")
            st.write(f"**每种商品件数:** `{result['counts']}`")
            st.write(f"**第八种商品单价 (x):** `{result['estimated_price_x']}`")
            
            # 使用更美观的指标卡显示关键数据
            c1, c2 = st.columns(2)
            c1.metric("最终商品件数分布", str(result['counts']))
            c2.metric("计算出的未知单价 x", f"{result['estimated_price_x']:.2f} 元")

        else:
            st.warning(f"**状态: {result['status']}** - {result['message']}")
            st.write(f"**当前商品件数:** `{result['counts']}`")
            st.write(f"**计算出的未知单价 (x):** `{result['estimated_price_x']}`")

    except Exception as e:
        st.error(f"输入数据有误或计算出错，请检查！\n错误信息: {e}")


# In[ ]:




