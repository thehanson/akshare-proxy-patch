# -*- coding: utf-8 -*-

import time
import multiprocessing
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


def install_proxy_patch():
    """
    在子进程内注入代理补丁，确保 akshare 请求走指定代理。
    """
    import akshare_proxy_patch

    akshare_proxy_patch.install_patch(
        "101.201.173.125",
        auth_token="你的TOKEN",
        retry=30,
        hook_domains=[
            "fund.eastmoney.com",
            "push2.eastmoney.com",
            "push2his.eastmoney.com",
            "emweb.securities.eastmoney.com",
        ],
    )


def worker(worker_id, chunk_codes, beg_date, klt, fqt):
    install_proxy_patch()
    import efinance as ef

    if not chunk_codes:
        print(f"⚠ [Worker {worker_id}] 任务列表为空，退出")
        return None

    print(
        f" 🚀 [Worker {worker_id}] 启动成功！读取到 {len(chunk_codes)} 只股票。指定日期: {beg_date}"
    )

    try:
        df = ef.stock.get_quote_history(
            stock_codes=chunk_codes,
            beg=beg_date,
            end=beg_date,
            klt=int(klt),
            fqt=int(fqt),
            return_df=True,
        )

        if df is not None and not df.empty:
            print(
                f" 📜 [Worker {worker_id}] 成功获取 {len(df)} 行数据，准备返回主进程。"
            )
            return df

        print(f" ⚠ [Worker {worker_id}] 接口未返回数据（可能是停牌或无交易）。")
        return None
    except Exception as e:
        print(f"❌ [Worker {worker_id}] 运行期间发生异常: {e}")
        return None


def main():
    stock_code_s = get_codes()
    print(f"📊 总共加载了 {len(stock_code_s)} 只股票")

    target_date = "20260528"
    klt = "5"
    fqt = "1"

    if not stock_code_s:
        print("❌ 未读取到任何股票代码，程序退出。")
        return

    process_num = min(PROCESS_NUM, len(stock_code_s))
    chunk_size = (len(stock_code_s) + process_num - 1) // process_num
    chunks = chunk(stock_code_s, chunk_size)

    total_start = time.time()
    print(f"⚙ 指挥官：正在派发 {len(chunks)} 个子进程任务...")

    args = [
        (str(idx + 1), chunk_codes, target_date, klt, fqt)
        for idx, chunk_codes in enumerate(chunks)
    ]

    with multiprocessing.Pool(process_num) as pool:
        results = pool.starmap(worker, args)

    print("\n--- 🏁 所有独立子进程已全部结束，开始合并数据 ---")

    all_dfs = [df for df in results if df is not None and not df.empty]

    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        output_name = f"stock_5m_{target_date}.csv"
        final_df.to_csv(output_name, index=False, encoding="utf-8-sig")
        print(f"🎉 【跨进程执行】数据完美合并！总行数: {len(final_df)}")
        print(f"💾 最终文件已保存至: {output_name}")
    else:
        print("❌ 灾难：未能收集到任何有效数据。请检查子进程运行日志。")

    total_end = time.time()
    print(f"🚀 运行总耗时：{total_end - total_start:.2f}秒")


if __name__ == "__main__":
    main()
