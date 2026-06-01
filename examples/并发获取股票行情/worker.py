# -*- coding: utf-8 -*-

import os
import sys

# 1. 绝对优先注入代理补丁
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

import efinance as ef


def main():
    # 参数：[脚本名, worker_id, 任务文件名, 开始日期, K线类型, 复权类型]
    if len(sys.argv) < 6:
        print("❌ [Worker] 参数不足，无法运行")
        return

    worker_id = sys.argv[1]
    task_file = sys.argv[2]
    beg_date = sys.argv[3]
    klt = int(sys.argv[4])
    fqt = int(sys.argv[5])

    # 从任务文件中读取属于自己的股票代码
    if not os.path.exists(task_file):
        print(f"❌ [Worker {worker_id}] 未找到任务文件: {task_file}")
        return

    with open(task_file, "r", encoding="utf-8") as f:
        chunk_codes = f.read().splitlines()

    if not chunk_codes:
        print(f"⚠ [Worker {worker_id}] 任务文件为空，退出")
        return

    print(
        f" 🚀 [Worker {worker_id}] 启动成功！读取到 {len(chunk_codes)} 只股票。指定日期: {beg_date}"
    )

    try:
        df = ef.stock.get_quote_history(
            stock_codes=chunk_codes,
            beg=beg_date,
            end=beg_date,
            klt=klt,
            fqt=fqt,
            return_df=True,
        )

        if df is not None and not df.empty:
            temp_filename = f"./temp_raw_data_{worker_id}.csv"
            df.to_csv(temp_filename, index=False, encoding="utf-8-sig")
            print(
                f" 📜 [Worker {worker_id}] 成功保存 {len(df)} 行数据至 {temp_filename}"
            )
        else:
            print(f" ⚠ [Worker {worker_id}] 接口未返回数据（可能是停牌或无交易）。")
    except Exception as e:
        print(f"❌ [Worker {worker_id}] 运行期间发生异常: {e}")


if __name__ == "__main__":
    main()
