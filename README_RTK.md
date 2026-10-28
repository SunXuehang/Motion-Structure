# 已选定的 V6 RTK 天线支架

2026-10-28 用户确认采用 V6。用于在 MID-360 顶部安装 HARXON HX-CUX623A。
本次将已选定结构及其复现、验证材料从审阅导出区纳入现有仓库目录；结构仍待实物试装和强度验证。

![V6 三维扫描遮挡](renders/rtk_scan_occlusion_3d_v6_20261028.png)

## 先看这些文件

| 文件 | 用途 |
| --- | --- |
| [独立支架 STEP](step/rtk_antenna_mount_v6.step) | 已选定的一体打印件；保留雷达装配坐标，切片前需调整摆放 |
| [站立手柄整机 STEP](step/standing_device_with_rtk_v6.step) | 5 个原结构打印件、V6 支架、官方雷达 CAD 和圆柱天线包络；不含相机、PCB、线缆及紧固件实体 |
| [交互三维遮挡 HTML](renders/rtk_scan_occlusion_3d_v6_20261028.html) | 下载后用浏览器打开，可离线旋转、缩放及隐藏图层 |
| [参数快照](reports/rtk_mount_v6_parameters.json) | 完整尺寸；参数修改入口为 `scripts/build_rtk_mount.py` 中的 `PARAMS` |
| [几何报告](reports/rtk_mount_review_v6_20261028.json) | 实体、孔位、基线差异及干涉检查 |
| [遮挡报告](reports/rtk_scan_occlusion_v6_20261028.json) | 三档独立网格、精确 52° 边界、立体角加权及方法限制 |
| [三维图数据报告](reports/rtk_shadow_3d_v6_20261028.json) | 模型指纹、显示网格与分析数据一致性 |
| [选版记录](reports/rtk_mount_v6_selection.json) | 用户选版、关键文件及原审阅件来源指纹 |

## 已确认的尺寸和验证范围

| 项目 | V6 |
| --- | --- |
| 抱箍 | 候选金属带 Ø51；抱箍内 Ø51.2、径向壁厚 3.5、接触高 4、开口 0.8 |
| 抱箍紧固 | 1 颗 M3；通孔 Ø3.4；右耳热熔螺母底孔 Ø4 × 深 3，直接沿用 A 件参数 |
| 立柱 | 3 根内收圆弧，主体 Ø3.1；底部锚点半径 28.3，顶部半径 11，固定底端竖直切线 |
| 顶托盘 | Ø48、厚 4、中央开口 Ø14 |
| 天线三孔 | 用户提供的边长 23 等边三角形；托盘 Ø3 通孔；天线官方螺纹 #3-48 UNC |
| 托盘外缘扫描边界余量 | **0.90 mm（竖向）**，不是托盘到玻璃罩的距离 |
| 天线安装面高于玻璃罩顶点 | 22.5215 mm，比 V5 降低 2.4785 mm |
| 16.5 mm 弯头与玻璃顶点的名义竖向余量 | 6.0215 mm；弯头实体及线缆弯曲尚未建模 |
| 托盘外缘最低投影仰角 | 52.7998°，高于名义 52° 上边界 |
| 新增件几何遮挡立体角占比 | 6.0191%，三个柱影仍存在；托盘及天线包络无命中 |

坐标以雷达底安装面为 Z=0，连接器朝 −Y。整机恢复到开发板坐标时，雷达平移 Y=−5、Z=73.1522。
支架为一个有效实体；名义 CAD 与雷达无体积交叠，安装轴向高度抽样以及 0° / 20° / 40° 俯仰检查通过。

遮挡从手册 O 点 `[0, 0, 47]` 作中心投影，视场为 360°、−7°～52°，用 0.5° / 0.25° / 0.125° 独立网格，并按立体角加权；另测精确 52° 上边界。
**6.02% 是几何估算，不是实测丢点率。** O 点不是已验证的真实光学出射孔径；折射、光束发散、扫描驻留、线缆、弯头和紧固件未计入。
托盘无命中不代表整个上部视场完全无遮挡，三根立柱仍遮挡窄扇区。
0.9 mm 名义余量、弹性开口、夹持力、蠕变和强度均需实物验证。Livox 手册不允许雷达承载额外载荷，这个夹持面不是厂家认可的承载接口。

## 复现

安装 [requirements_rtk.txt](requirements_rtk.txt)；这是独立 OCP 入口，不依赖本机临时目录，不要求 FreeCAD。
官方 CAD 不重复提交，放到已有约定路径 `vendor/livox/mid-360-asm.stp`。Linux 可用现有 `bash scripts/fetch_mid360.sh`。
Windows PowerShell 可在已有 `vendor/livox/` 目录下载：

```powershell
Invoke-WebRequest -Uri 'https://terra-1-g.djicdn.com/65c028cd298f4669a7f0e40e50ba1131/Mid360/mid-360-asm.stp' -OutFile 'vendor/livox/mid-360-asm.stp'
Get-FileHash 'vendor/livox/mid-360-asm.stp' -Algorithm SHA256
```

预期 SHA-256：`b93e9b51282ed319b6aa755e76a132c0eb03306da5f3b9676bcabf2e2ae25f02`，生成器会校验。
重新生成会覆盖下述 V6 STEP、参数、报告及 HTML：

```text
python -m pip install -r requirements_rtk.txt
python scripts/build_rtk_mount.py
python scripts/analyze_rtk_occlusion.py
python scripts/render_rtk_shadow_3d.py
```

生成器和分析器保留真实孔位、单实体、STEP 回读、无干涉、固定底部与收敛网格等断言。
分析将 V5 / V6 射线数据保存为 `reports/rtk_mount_v6_angular_shadow.npz`；绘图会重新计算显示数据对应的指标并核对当前 STEP 指纹，防止图与报告错配。
`tests/rtk_mount_baseline_v2.step`、`tests/rtk_mount_baseline_v5.step` 和 V5 参数仅用于底部不变及遮挡对照，不作为可选打印版本。
原始 `exports/` 中的历史文件不再是这些脚本的依赖。

如需重新导出 PNG，在已安装 Playwright 的 Node 环境中运行 `node scripts/verify_rtk_viewer.cjs`。
默认使用 Playwright Chromium；`PLAYWRIGHT_BROWSER_PATH` 可指定现有 Edge / Chrome。
该脚本检查两个三维画布、页面错误并旋转视角，将 PNG 和浏览器报告写回现有 `renders/`、`reports/`。
截图后的完整一致性检查：

```text
python -m pytest -p no:cacheprovider tests/test_rtk_mount_selection.py
```

这套独立入口尚未纳入原 FreeCAD 标准打印排版与完整相机 / 板卡干涉流程；使用独立 STEP 前需在切片软件确认姿态与支撑。

## exports 中保留了什么

| 内容 | 当前用途 |
| --- | --- |
| `current_structure_battery_review_20261028.step`、`current_structure_standing_review_20261028.step` | 添加 RTK 前的两种原机结构快照 |
| `rtk_mount_review_20261028/`、`rtk_mount_review_v2_20261028/` … `rtk_mount_review_v6_20261028/` | 六版迭代；各含独立支架、雷达局部 / 站立整机装配、脚本和参数，后期含遮挡数据 |
| 六个同名 ZIP | 每版的审阅副本，包含图、报告和模型，和展开目录存在重复 |

已纳入仓库的是 V6 最终独立件、站立整机、复现代码、参数与验证材料、一个交互 HTML 和预览 PNG；两份较小的历史支架只作为回归基线。
旧版大装配、ZIP、调研截图与可下载官方 CAD 留在本地，不随本次提交重复保存。

来源：[Livox 规格](https://www.livoxtech.com/mid-360/specs)、[Livox 手册](https://terra-1-g.djicdn.com/851d20f7b9f64838a34cd02351370894/Livox/Livox_Mid-360_User_Manual_EN.pdf)、[Harxon 官方天线](https://www.harxon.com/product/detail/2)。天线三孔间距和弯头高度来自用户输入，尚未获得对应厂家机械图复核。
