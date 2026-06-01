# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import time
import pandas as pd

# 设定并发进程数
PROCESS_NUM = 8


def chunk(lst, size):
    """
    将列表分割成指定大小 size 的子列表
    """
    if size <= 0:
        return []
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def get_codes():
    """
    获取所有股票代码，可以替换成你自己的股票列表来源
    """
    try:
        with open("./stock_lists.csv", "r", encoding="utf-8") as f:
            lines = f.read().splitlines()[1:]
        return [line.split(",")[2] for line in lines]
    except Exception:
        # 兜底测试数据
        return ["600519", "000858", "002594", "300750", "601318"]


if __name__ == "__main__":
    stock_code_s = get_codes()
    print(f"📊 总共加载了 {len(stock_code_s)} 只股票")

    target_date = "20260528"
    klt = "5"
    fqt = "1"

    CHUNK_SIZE = (len(stock_code_s) + PROCESS_NUM - 1) // PROCESS_NUM
    chunks = chunk(stock_code_s, CHUNK_SIZE)

    total_start = time.time()
    process_list = []
    task_files = []

    # 获取当前无视系统、无视环境的 Python 绝对路径
    current_python = sys.executable
    print(f"🎯 探测到当前客户端 Python 环境路径: {current_python}")
    print(f"⚙ 指挥官：正在生成并派发任务文件...")

    for idx, chunk_codes in enumerate(chunks):
        worker_id = str(idx + 1)

        task_file = f"./temp_task_{worker_id}.txt"
        with open(task_file, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk_codes))
        task_files.append(task_file)

        cmd = [
            current_python,
            "worker.py",
            worker_id,
            task_file,
            target_date,
            klt,
            fqt,
        ]

        # 异步启动子进程
        p = subprocess.Popen(cmd)
        process_list.append((worker_id, p))

    print(f"⏳ 指挥官：所有子进程已全部派发，正在等待它们各自运行结束...")

    # 等待所有后台进程结束
    for worker_id, p in process_list:
        p.wait()

    print("\n--- 🏁 所有独立子进程已全部结束，开始回收并合并数据 ---")

    # 读取临时文件并合并
    all_dfs = []
    for idx in range(len(chunks)):
        worker_id = idx + 1
        temp_filename = f"./temp_raw_data_{worker_id}.csv"
        try:
            df_part = pd.read_csv(temp_filename, encoding="utf-8-sig")
            all_dfs.append(df_part)
            os.remove(temp_filename)  # 回收成功后清理临时 CSV
        except FileNotFoundError:
            print(f"⚠ 未找到 Worker {worker_id} 的临时数据文件，该批次可能执行失败。")

    # 清理临时的任务 txt 文件
    for tf in task_files:
        if os.path.exists(tf):
            os.remove(tf)

    # 最终汇总
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        output_name = f"stock_5m_{target_date}.csv"
        final_df.to_csv(output_name, index=False, encoding="utf-8-sig")
        print(f"🎉 【跨平台多进程】数据完美合并！总行数: {len(final_df)}")
        print(f"💾 最终文件已保存至: {output_name}")
    else:
        print("❌ 灾难：未能收集到任何有效数据。请检查 worker.py 是否在当前目录下。")

    # 1. 自动删除临时数据 CSV 文件
    try:
        df_part = pd.read_csv(temp_filename, encoding="utf-8-sig")
        all_dfs.append(df_part)
        os.remove(
            temp_filename
        )  # 👈 读完并加入大部队后，这里会自动把 temp_raw_data_*.csv 删掉
    except FileNotFoundError:
        pass

    total_end = time.time()
    print(f"🚀 运行总耗时：{total_end - total_start:.2f}秒")
