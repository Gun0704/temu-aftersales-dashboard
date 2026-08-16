# 产品售后监控看板

这是从原 TEMU 营销数据看板中独立出来的「模块 7：产品售后监控 - SKU 退货退款统计」项目。

## 运行

在仓库根目录执行：

```bash
streamlit run aftersales_app.py
```

## Streamlit Community Cloud 部署

推荐部署设置：

- Repository：包含本项目代码的 GitHub 仓库
- Branch：`main`
- Main file path：`aftersales_app.py`
- Python dependencies：根目录 `requirements.txt`

注意：真实业务 Excel 不建议提交到公开 GitHub 仓库。云端部署后，可以让使用者在页面选择「上传文件」并上传 TEMU 退货报表和 TEMU 全部订单报表。如果需要云端预置真实数据，请使用私有 GitHub 仓库，并在 Streamlit Cloud 的 Sharing 设置中只邀请指定用户。

也可以进入本目录后执行：

```bash
streamlit run app.py
```

## 数据

售后退货表必需字段：

- `Order ID`
- `SKU ID`

常见可识别字段：

- `Return ID`
- `Return status`
- `Reason for request`
- `Return quantity`
- `Amount request to refund`
- `Amount refund to buyer`
- `Order date`
- `Requested date`
- `Types of after-sales service`

销售表和 SKU 映射表是可选项。上传后可计算订单维度退货率和产品件数退货率；不上传时，看板仍会展示退款金额、退货退款订单数、退货退款件数、原因分布和明细导出。

### TEMU 实际数据适配

本项目已适配 TEMU 后台导出的：

- `退货Temu*.xlsx`：售后退货报表
- `Temu全部订单*.xlsx` / `Order report`：全部订单报表，用作退货率分母

本地扫描会自动跳过文件名以 `TK-` 开头的数据文件。TEMU 全部订单报表顶部常带有平台提示行，看板会自动定位包含 `订单号`、`SKU编号`、`购买数量` 的真实表头。

默认日期范围会取「售后申请日期」和「订单分母日期」的交集，避免退货文件覆盖时间早于订单文件时造成退货率口径错配。订单维度退货率分母按订单号去重，产品件数退货率分母按购买数量汇总。

## 功能

- 本地演示数据或上传文件两种取数方式
- 店铺、申请日期、SKU ID、售后状态、售后类型、申请理由、一级原因和关键词筛选
- 退款金额、退货退款订单数、退货退款件数、订单维度退货率、产品件数退货率
- SKU 风险排行、一级原因分布、每日售后趋势、售后状态分布
- SKU 汇总表、售后明细表和 Excel 导出
