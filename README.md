# TEMU 营销数据看板（重构版）

这是一个基于 **Streamlit + Pandas + Plotly** 的 TEMU 营销数据分析看板。项目已从单文件/混合职责结构重构为分层包结构，数据文件也已独立放入 `data/` 目录，便于提前下载真实数据或直接使用内置 demo 数据演示。

## 本次重构完成内容

### 1. 项目架构重新设计

原项目中 `app.py` 过长，承担了页面渲染、文件读取、数据清洗、指标计算、API 调用、图表生成等职责。重构后按职责拆分为：

- `marketing_dashboard/data/`：数据读取、文件分类、清洗、前端订单处理、基础数据集构建
- `marketing_dashboard/analytics/`：指标计算、Goods ID/SKU 匹配、售后退货、高级诊断
- `marketing_dashboard/viz/`：Plotly 图表
- `marketing_dashboard/ui/`：页面组件、样式、Streamlit 主页面
- `marketing_dashboard/integrations/`：TEMU API 客户端与接口结果转换
- `marketing_dashboard/core/`：配置常量、缓存工具
- `scripts/`：演示数据生成、TEMU 数据提前下载脚本
- `data/`：所有数据文件集中目录

根目录 `app.py` 现在只保留 Streamlit 入口，启动方式仍然兼容：

```bash
streamlit run app.py
```

### 2. 数据文件独立目录

所有演示、下载、处理和导出数据统一放到 `data/`：

```text
data/
├── demo/       # 内置演示数据，可直接运行本地演示
├── raw/        # 提前从 TEMU API 下载的真实原始数据
├── processed/  # 后续可放清洗后的中间数据
└── exports/    # 后续可放导出文件
```

当前已内置一套 demo CSV，可直接选择侧边栏的 **本地演示数据** 运行：

```text
data/demo/
├── DemoStore-sales_demo.csv
├── DemoStore-traffic_demo.csv
├── DemoStore-mapping_demo.csv
├── DemoStore-frontend_orders_demo.csv
└── DemoStore-returns_demo.csv
```

### 3. 支持提前下载真实数据后离线演示

新增脚本：

```bash
python scripts/download_temu_data.py \
  --start-date 2026-06-01 \
  --end-date 2026-06-14
```

脚本会把 TEMU API 拉取结果保存到 `data/raw/`。演示时在侧边栏选择 **本地演示数据**，将目录从 `data/demo` 改为 `data/raw` 即可使用提前下载好的真实数据，无需现场等待 API。

### 4. README 已同步详细更新

本文档覆盖：项目结构、安装、运行、演示数据、提前下载数据、TEMU API 配置、输入字段要求、核心模块说明、开发规范和常见问题。

---

## 快速开始

### 1. 创建环境并安装依赖

建议使用 Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate       # Windows PowerShell

pip install -r requirements.txt
```

### 2. 直接运行内置 demo

```bash
streamlit run app.py
```

打开页面后，在左侧侧边栏中：

1. `选择取数方式` 选择 **本地演示数据**
2. `数据目录` 保持默认 `data/demo`
3. 页面会自动读取内置 demo 数据并展示看板

### 3. 重新生成 demo 数据（可选）

如果需要刷新 demo CSV，可执行：

```bash
python scripts/make_demo_data.py
```

生成位置：

```text
data/demo/
```

---

## 项目结构

```text
marketing_dashboard_refactored/
├── app.py
├── README.md
├── requirements.txt
├── .streamlit/
│   └── secrets.example.toml
├── data/
│   ├── demo/
│   │   ├── DemoStore-sales_demo.csv
│   │   ├── DemoStore-traffic_demo.csv
│   │   ├── DemoStore-mapping_demo.csv
│   │   ├── DemoStore-frontend_orders_demo.csv
│   │   └── DemoStore-returns_demo.csv
│   ├── raw/
│   ├── processed/
│   └── exports/
├── scripts/
│   ├── make_demo_data.py
│   └── download_temu_data.py
└── marketing_dashboard/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── cache.py
    │   └── config.py
    ├── data/
    │   ├── __init__.py
    │   ├── cleaners.py
    │   ├── frontend_orders.py
    │   ├── local_files.py
    │   └── pipeline.py
    ├── analytics/
    │   ├── __init__.py
    │   ├── advanced_analytics.py
    │   ├── matching.py
    │   ├── metrics.py
    │   └── returns.py
    ├── integrations/
    │   ├── __init__.py
    │   └── temu_api.py
    ├── ui/
    │   ├── __init__.py
    │   ├── app.py
    │   ├── components.py
    │   └── helpers.py
    └── viz/
        ├── __init__.py
        └── charts.py
```

---

## 数据来源模式

看板侧边栏提供 4 种数据来源：

### 1. 本地演示数据

从本地目录读取 CSV / Excel 文件。

默认目录：

```text
data/demo
```

可以改成：

```text
data/raw
```

适合演示场景：先把数据下载到 `data/raw/`，现场打开页面即可展示。

### 2. 上传文件

通过页面上传销售表、流量表、商品信息表、前端价订单表、售后退货报表。

### 3. TEMU API

在页面中填写 API type 并点击按钮实时拉取。

### 4. 上传 + TEMU API

上传文件和接口数据会合并后进入同一套清洗、匹配、指标计算流程。

---

## 本地数据文件命名规则

本地模式会按文件名自动识别类型。建议命名时包含店铺名前缀，格式类似：

```text
店铺名-sales-日期.csv
店铺名-traffic-日期.csv
店铺名-mapping.csv
店铺名-frontend-orders.csv
店铺名-returns.csv
```

识别关键词：

| 类型 | 文件名关键词 |
|---|---|
| 销售表 | `sales`、`order`、`销售`、`订单` |
| 流量表 | `traffic`、`impression`、`click`、`流量`、`曝光`、`点击` |
| 商品映射表 | `mapping`、`sku`、`product`、`goods`、`商品`、`映射` |
| 前端价订单表 | `frontend`、`front_price`、`front-price`、`前端价` |
| 售后退货表 | `return`、`refund`、`returns`、`售后`、`退款`、`退货` |

店铺名仍沿用清洗逻辑：会优先从文件名前缀推断，例如 `DemoStore-sales_demo.csv` 会识别为 `DemoStore`。

---

## 提前下载 TEMU 数据

### 1. 配置密钥

复制示例配置：

```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

然后填写：

```toml
[TEMU]
APP_KEY = ""
APP_SECRET = ""
ACCESS_TOKEN = ""
BASE_URL = ""
SALES_API_TYPE = ""
TRAFFIC_API_TYPE = ""
MAPPING_API_TYPE = ""
EXTRA_API_TYPES = ""
PAGE_SIZE = 100
MAX_PAGES = 50
```

也可以使用环境变量：

```bash
export TEMU_APP_KEY="..."
export TEMU_APP_SECRET="..."
export TEMU_ACCESS_TOKEN="..."
export TEMU_BASE_URL="..."
export TEMU_SALES_API_TYPE="..."
export TEMU_TRAFFIC_API_TYPE="..."
export TEMU_MAPPING_API_TYPE="..."
```

### 2. 下载数据到 `data/raw/`

```bash
python scripts/download_temu_data.py \
  --start-date 2026-06-01 \
  --end-date 2026-06-14
```

也可以在命令行覆盖 API type：

```bash
python scripts/download_temu_data.py \
  --start-date 2026-06-01 \
  --end-date 2026-06-14 \
  --sales-api-type "你的销售接口type" \
  --traffic-api-type "你的流量接口type" \
  --mapping-api-type "你的商品接口type"
```

下载后会生成类似：

```text
data/raw/sales_temu_2026-06-01_to_2026-06-14.csv
data/raw/traffic_temu_2026-06-01_to_2026-06-14.csv
data/raw/mapping_temu_2026-06-01_to_2026-06-14.csv
```

### 3. 页面中使用提前下载数据

1. 启动看板：`streamlit run app.py`
2. 左侧 `选择取数方式` 选择 **本地演示数据**
3. 将 `数据目录` 改为 `data/raw`
4. 看板会读取已下载文件，无需再次调用 API

---

## 输入文件字段要求

### 销售表

必需字段：

- `Date`
- `Goods ID`

常见可识别字段：

- `Goods Name`
- `Base price sales`
- `Buyers`
- `Total order items`
- `Units ordered`
- `Order status`

支持中文/英文常见字段名，清洗逻辑见 `marketing_dashboard/data/cleaners.py`。

### 流量表

必需字段：

- `Date`
- `Goods ID`

常见可识别字段：

- `Goods Name`
- `Product impressions`
- `Product clicks`
- `CTR`

### 商品信息表 / SKU 映射表

必需字段：

- `Goods ID`

建议字段：

- `SKU`
- `Product name`
- `Quantity`
- `Date created`
- `Store`

### 前端价订单表

支持格式：`csv`、`xlsx`、`xls`

必需字段：

- `purchase date`
- `Retail price (tax excl.)`
- `quantity purchased`

建议字段：

- `contribution sku`
- `product name`
- `order status`

用途：生成前端价格与销量走势图。

### 售后退货表

必需字段：

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

---

## 核心模块说明

### 模块 1：筛选与核心指标区

支持按店铺、日期、Goods ID、SKU、标签和文本粘贴 Goods ID 筛选。

核心指标包括：

- 总曝光量
- 总点击量
- 整体 CTR
- 总订单数
- 整体转化率
- 总销售额
- 总销量
- 每单销售额
- 每单销售量
- 日均销售额
- 日均销量
- 单品库销比

### 模块 2：每日趋势可视化区

包含：

- 曝光量 + CTR 趋势
- 点击量 + 转化率趋势
- 单品前端价格 + 销量趋势

前端价格计算口径：

```text
前端价(day) = 当日 Retail price (tax excl.) 总额 / 当日 quantity purchased 总量 × 1.16
销量(day) = 当日 quantity purchased 汇总
```

### 模块 3：每日数据明细区

支持：

- 默认排序字段和升降序
- 点击列头排序
- SKU 优先显示，缺失则回退 Goods ID
- 异常值红字标注
- 导出当前筛选结果 Excel

导出的 Excel 包含：

- `每日明细`
- `字段说明`

### 模块 4：SKU 流量销售联动分析区

包含：

- SKU 综合表现 TOP20
- 异常 SKU 榜
- 未联动 SKU 明细

### 模块 5：API 高级维度与自动诊断区

当 API 扩展数据包含加购、库存、退款、价格、成本等字段时，系统会自动合并并生成：

- 加购率
- 退款订单率
- 毛利率
- 可售天数
- 自动诊断动作建议

### 模块 6：异常提示与行动指引区

基于 CTR、曝光、销量、转化等变化识别异常，并输出建议动作。

### 模块 7：产品售后监控 - SKU 退货退款统计

支持售后退货报表的：

- 店铺筛选
- SKU ID 筛选
- 售后状态筛选
- 原因筛选
- 日期筛选
- 关键词搜索
- Excel 导出

---

## 开发说明

### 运行语法检查

```bash
python -m compileall app.py marketing_dashboard scripts
```

### 增加新清洗字段

修改：

```text
marketing_dashboard/data/cleaners.py
```

字段候选名集中定义在文件顶部，例如：

- `SALES_FIELD_MAP`
- `TRAFFIC_FIELD_MAP`
- `MAP_*_KEYS`

### 增加新指标

优先修改：

```text
marketing_dashboard/analytics/metrics.py
```

如果是 TEMU API 扩展指标，优先修改：

```text
marketing_dashboard/analytics/advanced_analytics.py
```

### 增加新图表

优先修改：

```text
marketing_dashboard/viz/charts.py
```

### 修改 UI 样式或指标卡

优先修改：

```text
marketing_dashboard/ui/components.py
marketing_dashboard/ui/helpers.py
```

### 修改主页面布局

主页面在：

```text
marketing_dashboard/ui/app.py
```

根目录 `app.py` 不建议加入业务逻辑，只作为入口。

---

## 常见问题

### 1. 本地模式显示没有数据怎么办？

检查：

1. 数据目录是否存在，例如 `data/demo` 或 `data/raw`
2. 文件扩展名是否为 `.csv`、`.xlsx`、`.xls`
3. 文件名是否包含可识别关键词，如 `sales`、`traffic`、`mapping`
4. 销售表和流量表是否包含 `Date` 与 `Goods ID`

### 2. 销售和流量没有匹配上怎么办？

优先检查：

- `Goods ID` 是否一致
- 文件名前缀推断出的店铺是否一致
- 日期是否在同一天粒度
- `Goods ID` 是否存在 `.0`、空格或特殊字符

清洗器会自动处理常见 `.0` 和空格问题，但如果源文件中 Goods ID 本身不一致，需要先修正源数据。

### 3. 前端价格走势图不显示怎么办？

该图只在选中单个 Goods ID 或单个 SKU 后展示。还需要前端价订单表包含：

- `purchase date`
- `Retail price (tax excl.)`
- `quantity purchased`

如果要和商品联动，建议额外提供：

- `contribution sku`
- `product name`

### 4. TEMU API 拉取失败怎么办？

检查：

- `.streamlit/secrets.toml` 是否已创建，而不是只存在 `secrets.example.toml`
- `APP_KEY`、`APP_SECRET`、`ACCESS_TOKEN`、`BASE_URL` 是否填写
- 销售接口 type 和流量接口 type 是否填写
- API 返回字段是否符合 `temu_api.py` 的宽松字段映射

### 5. 为什么 data/raw 不提交真实数据？

`data/raw/` 用于存放真实业务数据，通常不应该提交到代码仓库。本项目只保留 `.gitkeep` 占位，演示可使用 `data/demo/`。

---

## 当前版本验证

本次整理后已执行：

```bash
python -m compileall app.py marketing_dashboard scripts
```

并用 `data/demo/` 内置数据验证了本地数据收集、销售/流量/映射清洗、基础明细合并、前端订单清洗与映射流程。
