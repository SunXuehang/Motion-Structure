
# 手持式 MID-360 扫描装置 · 参数化结构件

<video src="renders/handheld_stack_exploded.mp4" controls width="100%"></video>

Livox MID-360 激光雷达 + RealSense D435i + UAV V3 开发板的手持扫描装置结构件。
全部几何由 Python + FreeCAD 代码生成，源代码是唯一真值——不手工建模，
FCStd / STEP 全部可一键重建并自动校验干涉。

结构爆炸动画：`renders/handheld_stack_exploded.mp4`（由代码生成，未入库；
跑 `scripts/build_exploded_view.py` 重建）。

## 六个 PLA 打印件

| 件 | STEP | 关键尺寸 |
|---|---|---|
| 结构 A · 雷达托板 | [`step/part_a_radar_plate.step`](step/part_a_radar_plate.step) | 69 × 85 × 6 |
| 结构 B · 倾斜底座 | [`step/part_b_tilt_base.step`](step/part_b_tilt_base.step) | 128 × 78 × 4，R45，0–40° |
| 开发板上盖板 | [`step/board_cover_upper.step`](step/board_cover_upper.step) | 128 × 78 × 3，隔柱 10 |
| 开发板下盖板 | [`step/board_cover_lower.step`](step/board_cover_lower.step) | 128 × 78 × 3，隔柱 13 |
| 电池手柄本体 | [`step/battery_grip_body.step`](step/battery_grip_body.step) | Ø41.6 圆筒，16 × M3 上吊 |
| 手柄底盖 | [`step/battery_grip_bottom_cap.step`](step/battery_grip_bottom_cap.step) | Ø41.6 × 4，3 × M3 |

每个 STEP 都是**单个实体、按打印姿态坐在 Z = 0、居中于原点**，可直接拖进切片软件。
另有 [`step/board_and_bracket_all_parts.step`](step/board_and_bracket_all_parts.step)：
除手柄外的四件排在一张 256 × 256 mm 打印床上；手柄两件另有
`exports/battery_grip_256x256_print_plate.step`。

## 快速开始

```sh
git clone <this repo> && cd mid360-tilt-bracket
./scripts/fetch_mid360.sh                              # 取官方 MID-360 CAD（SHA-256 锁定）
python -m pytest tests --ignore=tests/freecad           # 纯 Python 参数/运动学
./scripts/run_freecad.sh scripts/build_step_package.py  # 重建 step/ 下全部 STEP
```

需要 FreeCAD 1.1.3（默认从 `~/Applications/` 的 AppImage 启动，可用
`$FREECAD_APPIMAGE` 覆盖）。装配干涉校验还需要
`renders/UAV_V3_compute_carrier_reference_clean.stl`——67 MB 的整机算料参考网格，
体积过大未入库，须从原始整机 CAD 另行导出。缺它时件与件之间的校验照样跑，
只有"件 × 开发板本体"这一类检查和整机 FCStd/STEP 导出会失败。

## 想用 AI 接着改这个项目？

1. 先读 **[第 0 节 装配逻辑](#0-装配逻辑改尺寸前先读这一节)**——它讲清楚全局
   只有一个 Z 基准、每个面怎么推导出来的、以及哪些约束会在改错时直接报错。
2. 再读 **[第 3 节 术语对照](#3-术语对照)**——"上/下盖板"指开发板的上下，不是
   雷达 A/B 的上下，这一点最容易搞混。
3. 改几何前先改参数（`parameters.py` / `board_covers.py` / `battery_grip.py`），
   再跑对应的窄范围测试，最后重新生成 STEP。测试里写死的绝对坐标是技术债，
   遇到就改成从参数推导。
4. 每个模块顶部的 docstring 说明它负责哪一个件、坐标系原点在哪。

---

以下是设计细节与后续编辑约定。尺寸单位均为 **mm**，除非特别说明，
打印材料为 **PLA**，紧固件为金属螺钉/螺柱。

## 0. 装配逻辑（改尺寸前先读这一节）

**一句话：所有件的位置都是算出来的，不是填出来的。** 全局只有一个 Z 轴基准
——开发板（UAV V3）的 PCB 安装面，`BoardCoverParameters.board_mounting_z_min = 10.5`
与 `board_mounting_z_max = 23.1522`。其余每一个面都从它推导，所以改一个参数，
它上下游的件会自动跟着走。

### Z 链（自上而下，全部为推导值）

```
雷达 MID-360        底面坐在 A 板顶面
  结构 A 托板       绕 B 的转轴旋转 0..40°，转轴 y=38 z=-3（A 局部坐标）
  结构 B 倾斜底座    底面 = 上盖板顶面 + BRACKET_STANDOFF_HEIGHT_MM(20)
    └ D435i 托板     = B 底面 + b_base_thickness(4)，相机坐在这个面上
  开发板上盖板       板底 = board_mounting_z_max + top_standoff_height(10)
                    围挡从板底往下伸 top_rim_height(4)
━━ 开发板 PCB ━━━━  board_mounting_z_max .. board_mounting_z_min
  开发板下盖板       板顶 = board_mounting_z_min - bottom_standoff_height(13)
                    围挡从板顶往上伸 bottom_rim_height(5.5)
                    板底 = 板顶 - plate_thickness(3) = -5.5  ← 手柄基准
  电池手柄法兰       顶面 = cover_underside_z(-5.5)，厚 flange_thickness(6)
    空心锥根         高 root_height(14)，外 Ø41.6→Ø55，内 Ø35.6→Ø49
    圆筒握把         长 tube_height(72)，内孔 Ø35.6 / 壁厚 3 / 外径 Ø41.6
    手柄底盖         厚 cap_thickness(4)，最低点 -101.5
```

### 三条硬约束（写进了 `__post_init__`，违反直接报错）

1. **围挡不得碰 PCB**：`rim_height < standoff_height`。当前上余 6、下余 7.5。
2. **B 底板风扇孔不得越过扇形耳板**：孔半宽 + 中心偏移 ≤ `b_inner_width/2`，
   且四周至少留 3 mm 板料。当前朝耳板一侧最窄 4.75 mm。
3. **手柄内孔必须装得下三角电池组**：`pack_circumdiameter < bore_diameter`。
   当前电池组外接圆 Ø31.59，内孔 Ø35.6，单边余量 2.0。

### 螺钉接口（谁攻丝、谁过孔）

| 连接 | 数量 | 通孔侧 | 攻丝侧 |
|---|---:|---|---|
| 结构 A ↔ 结构 B（转轴 + 锁紧） | 4 × M3 | B 耳板 Ø3.4 / 弧槽 3.4 宽 | A 侧面 Ø2.9，啮合 6~6.6 |
| 结构 B ↔ 上盖板 | 16 × M3 | B 底板 Ø3.4 | 上盖板侧翼 |
| 上/下盖板 ↔ 开发板 | 4 × M3 | 盖板四角 Ø3.4 | 开发板自带铜柱 |
| 手柄 ↔ 下盖板 | **16 × M3** | 下盖板侧翼 Ø3.4 | 手柄法兰 Ø2.9，攻穿 6 |
| 手柄底盖 ↔ 手柄 | 3 × M3×6 | 底盖 Ø3.4 + Ø6.2 沉孔 | 内孔壁立柱 Ø6.5 高 5 |

孔位共享同一套坐标：盖板两侧各 8 个侧翼孔在 `x = ±59, y = ±5/±15/±25/±35`，
由 `board_covers.extension_hole_centers()` 统一生成，结构 B 和手柄法兰都调它，
所以**永远不可能对不上**。

### 干涉校验怎么跑

`build_board_bracket_assembly()` 把 10 个件建在同一个坐标系里，然后逐对算
`shape.common(other).Volume`，任何一对不为 0 就抛异常。校验矩阵和数值落在
`reports/UAV_V3_board_mid360_assembly.json`。

### 想改设计时该动哪里

| 想改 | 动这里 | 会自动跟随的件 |
|---|---|---|
| 雷达倾角范围 | `BracketParameters.working_angle_deg` | 弧槽、扇形轮廓、A 的行程 |
| 盖板与开发板的间隙 | `top/bottom_standoff_height` | 盖板、结构 B、A、雷达、D435i 全部上下移动 |
| 握把粗细 | `BatteryGripParameters.wall_thickness` | 外径、握持周长、底盖、立柱位置 |
| 电池数量/尺寸 | `cell_count` / `cell_diameter` | 三角形外接圆、内孔下限校验 |
| 手柄长度 | `tube_height` | 窗口高度、总高、底盖位置 |

**不要**手工改几何函数里的绝对坐标。所有位置都应该是参数的函数；如果你发现
必须写死一个数字，那说明缺一个参数。

## 1. 结构名称与装配关系

### 结构 A：雷达活动托板

- 承载 Livox MID-360 雷达。
- 是可绕前端转轴旋转的活动件。
- A 托板上的两个耳板位于水平托板左右外缘、托板上方。
- 雷达航插头位于抬升侧（后方圆弧端），航插方向相对原始方向旋转 180°。
- A 与 B 的转轴端通过侧面螺钉连接；A 上四个 MID-360 安装孔属于例外孔位，不随通用 M3 化修改。

### 结构 B：雷达固定底座/倾斜底座

- 固定在开发板上盖板上，是 A 的支撑与倾角调节件。
- B 有水平底板、左右两块扇形耳板和前端 D435i 相机托板。
- 扇形耳板在外侧，夹持 A 的耳板。
- 扇形耳板圆心位于前方/转轴区域，后方圆弧端用于抬升和锁紧。
- 当前工作倾角为 **0～40°**；前端向上旋转，不是向下旋转。
- B 扇形耳板不挖孔；滑轨/锁紧结构按现有模型保留。

### 开发板上盖板与下盖板

- 上盖板：覆盖开发板上方，板厚 3；上侧风扇开矩形孔。
- 下盖板：覆盖开发板下方，板厚 3；底部风扇和 IMU 各开矩形孔。
- 两块盖板分别通过四角隔柱与开发板连接。
- 当前下盖板内侧围挡高度为 **8**（最近一次由 6 增加 2）；上盖板围挡高度为 **2**。
- 围挡当前恢复为与盖板平面的直角连接；不要擅自重新加入圆角或减料式 R1。
- 围挡壁厚 1.5，外侧包到四角隔柱最外缘；盖板外形基准为 108×78，围挡外包络约 106×76（以源代码实际几何为准）。

### D435i 托板

- 属于 B 的前端附属打印结构，不是雷达 A/B 的一部分。
- 当前尺寸约 92×20，外侧连接处为 R4 圆角。
- 托板中部预留 D435i 底部安装孔，安装后不得与雷达倾斜结构干涉；若修改 B，应重新检查相机空间。

### 电池手柄（手持握把）

- 用 **16 颗 M3** 吊装在**下盖板底面**（Z = -5.5）下方，螺钉用满下盖板两侧各 8 个 Ø3.4 侧翼通孔（x = ±59，y = ±5/±15/±25/±35）。
- 顶部法兰与下盖板同外形：128×78，R4 圆角，**厚度均一 6 mm，两侧不加厚**；16 个 Ø2.9 底孔攻穿整个 6 mm（螺纹啮合 6 mm）。
- **手柄本身没有顶盖**：内孔直接贯穿法兰，下盖板底面就是电池腔顶。开发板底部风扇因此直接向下吹进内孔、吹到电池组上。
- 因为上面这一点，法兰上**不再开风扇孔和 IMU 让位孔**，手柄也就不必为散热让位、居中放在盖板正下方。
- 握把是**圆筒**：内孔 Ø35.6、壁厚 3、外径 Ø41.6（握持周长 130.7 mm），圆筒段长 72。
- 上端 14 mm 是**空心锥形过渡**：外 Ø41.6→Ø55，内 Ø35.6→Ø49，壁厚恒定 3。这个喇叭口同时是风扇的导流罩——下盖板风扇孔有 **98.5%** 的面积直接通进内孔。
- 内孔竖放三节五号（AA / 14500）锂电池，**底面为等边三角形**（边长 14.8，外接圆 Ø31.59，内孔单边余量 2.0）；串联约 11.1 V 标称，对应 DC 12 V 输出。
- 电池从圆筒**底面开口**装入；底盖用 3 颗 **M3×6** 拧进内孔壁上的三根 Ø6.5 × 高 5 立柱，立柱正好落在三角形电池组之间的三个空档（30°/150°/270°），并整根攻穿——所以 5 mm 就是螺纹啮合长度。
- 圆筒背面（-Y）开一个 14×10 小窗口引出两条 DC 12 V 线（供电 + 充电）。
- 法兰在四角板卡安装螺钉位（±50, ±35）留 Ø6.5 让位孔，装上手柄后仍能操作那四颗螺钉。
- 下盖板的 IMU 孔（14×18 @ X=33.7）被 6 mm 法兰完全盖住。**用户已确认该孔下方无元件伸出，不需要补让位坑**；报告里的 `imu_opening_open_fraction = 0` 是预期值，不是缺陷。





## 2. 当前有效主要参数

### 雷达倾斜结构

| 项目 | 当前值 |
|---|---:|
| A 托板宽 × 深 × 厚 | 69 × 85 × 6 |
| MID-360 安装孔距 | 36 × 48 |
| A-B 侧面攻丝深度 | 6 |
| B 底板宽 × 深 × 厚 | 128 × 78 × 4 |
| B 内侧宽度 | 69.8 |
| B 扇形锁紧半径 | R45 |
| B 扇形外轮廓半径 | R53 |
| 工作角度 | 40° |
| 滑轨宽度 | 3.4 |
| 滑轨两端余量 | 1.5 |
| 扇形耳板减薄 | 外侧减薄 1；内侧材料不减薄 |
| B 底板安装孔 | Ø3.4 通孔（M3 间隙孔） |
| D435i 托板 | 92 × 20，R4 |

### 开发板盖板

| 项目 | 当前值 |
|---|---:|
| 盖板长度 × 宽度 | 108 × 78 |
| 盖板厚度 | 3 |
| 四角隔柱外径 | Ø6 |
| 上隔柱高度 | 8 |
| 下隔柱高度 | 13 |
| 通用 M3 通孔 | Ø3.4 |
| M3 攻丝底孔 | Ø2.9（仅在需要攻丝的实体中使用） |
| 上盖风扇孔 | 60 × 41，R2 |
| 下盖风扇孔 | 24 × 24，R3 |
| 下盖 IMU 孔 | 14 × 18，R1 |
| 上盖围挡 | 高 2，厚 1.5，直角根部 |
| 下盖围挡 | 高 8，厚 1.5，直角根部 |

说明：所有 PLA 打印件的孔位已按 M3 方案处理，**A 与 MID-360 连接的四个安装孔除外**。不要把航插、雷达、开发板、D435i 参考模型或螺钉误当成 PLA 打印件。

### 电池手柄

| 项目 | 当前值 |
|---|---:|
| 顶部法兰 长 × 宽 × 厚 | 128 × 78 × 6，R4，**厚度均一** |
| 与下盖板连接螺钉 | **16 × M3**，x=±59，y=±5/±15/±25/±35 |
| 手柄侧攻丝底孔 | Ø2.9，攻穿 6（啮合 6 mm） |
| 板卡螺钉让位孔 | Ø6.5 @ (±50, ±35) |
| 空心锥形过渡 | 高 14；外 Ø41.6→Ø55，内 Ø35.6→Ø49 |
| 风扇孔通气率 | 98.5%（559.7 / 568.3 mm²） |
| 圆筒 内孔 / 壁厚 / 外径 | Ø35.6 / 3 / **Ø41.6**（周长 130.7） |
| 圆筒段长度 | 72（+ 锥根 14，法兰下总长 86） |
| 电池 | 3 × 五号 Ø14.5 × 50.5，等边三角形边长 14.8 |
| 电池组外接圆 | Ø31.59（内孔单边余量 **2.005**） |
| 电池腔 | Ø35.6 × 92，上端由下盖板封口，下端开口装电池 |
| 电池上方风扇腔 | 41.5 |
| 底盖螺柱 | 3 × Ø6.5，轴线半径 15.3，30°/150°/270°，**高 5（攻穿，啮合 5）** |
| 背部 DC 线窗口 | 14 × 10，R2，中心 Z = -36.25 |
| 底盖 厚 | 4，Ø6.2 × 2.2 沉孔，螺钉 M3×6 |
| 手柄总高（含底盖） | 96（Z = -5.5 → -101.5） |
| 估重（PLA 1.24） | 本体 98.2 g + 底盖 6.4 g |
| 打印姿态 | 本体法兰朝下（高 92）；底盖外表面朝下（高 4） |


### 整机装配与爆炸图

- `models/UAV_V3_board_mid360_assembly.FCStd` 包含 **10 个产品**：开发板参考 CAD、
  上盖板、下盖板、结构 B、结构 A、官方 MID-360、官方 D435i 参考、
  **电池手柄本体、手柄底盖、三节电池参考**。
- 同内容的 `exports/UAV_V3_board_mid360_assembly.step` 因为内嵌 25 万面的开发板参考壳
  会有 **305 MB**，**默认不留在磁盘上**；需要跟外部交接时再跑
  `build_board_bracket_assembly.py` 重新导出（约 12 分钟）。日常看图用 FCStd。
- 校验报告 `reports/UAV_V3_board_mid360_assembly.json` 增加了 `battery_grip_included: true`
  以及手柄对下盖板/上盖板/A/B/雷达/D435i/底盖的干涉体积（全为 0）和
  `grip_carrier_reference_z_gap_mm`（手柄顶面到开发板 CAD 底面还有 5.5 mm）。
- 网页用爆炸动画：`renders/handheld_stack_exploded.mp4`（H.264，约 0.1 MB，
  装配↔爆炸无缝循环）。按用户要求**只出 MP4**，不再生成 PNG/SVG/GIF。
- 视角固定在 elev 16° / **azim 118°**：D435i 装在结构 B 的 +Y 前端托板上，
  相机必须放在 +Y 一侧，否则结构 B 会把它整个挡住。
- 爆炸位移不是手填的：`_explosion_offsets` 用各零件真实包围盒，从开发板往两侧
  逐个让出 `EXPLODE_GAP_MM`（24 mm），所以某个零件变大时不会悄悄叠到邻件上。

## 3. 术语对照

- **抬升端/后方圆弧端**：雷达后侧向上抬起的一端，航插头所在侧。
- **转轴端/圆心端**：B 扇形耳板前方的旋转中心区域，A 托板前边连接此处。
- **锁紧端**：后方圆弧和滑轨末端，用螺钉锁紧角度。
- **扇形耳板**：B 两侧的弧形侧板；当前只 B 保持扇形，A 为短耳板/平板耳板。
- **夹持 A**：B 扇形耳板位于外侧，A 耳板夹在两侧之间。
- **上盖板/下盖板**：相对于开发板的上方/下方盖板，不是雷达 A/B 的上下件。
- **围挡**：盖板内侧四周的连续薄壁，用于限制开发板位置；隔柱位于围挡四角。
- **隔柱**：盖板内侧四角的圆柱支撑，不等同于螺钉头凸台。
- **通孔**：螺钉自由穿过的孔，M3 当前采用 Ø3.4。
- **攻丝底孔**：打印后用于攻 M3 螺纹的预留孔，当前采用 Ø2.9。
- **薄壳/局部凸台**：曾经的设计思路；当前盖板为平板加围挡、B 为现有实心结构，不要自行恢复旧凸台。
- **R1/R4/R45/R53**：分别表示 1、4、45、53 mm 半径。R1 围挡根部圆角已被用户否决并恢复为直角。

## 4. 当前文件与生成方式

主要源文件：

- `src/bracket/board_covers.py`：开发板上、下盖板参数和几何。
- `src/bracket/freecad_geometry.py`：雷达 A/B 几何。
- `src/bracket/parameters.py`：雷达倾斜结构参数。
- `src/bracket/print_plate.py`：四个 PLA 件的打印床排布与 STEP 导出。
- `src/bracket/step_package.py`：每件一个 STEP + 除手柄外四件的合并 STEP。
- `src/bracket/battery_grip.py`：电池手柄参数、几何、与下盖板的装配和校验。
- `src/bracket/exploded_view.py`：整机结构爆炸动画（MP4）。
- `scripts/build_print_plate.py`：调用 FreeCAD 生成打印 STEP。
- `scripts/build_battery_grip.py`：生成手柄本体 / 底盖 / 手柄+下盖板装配 / **打印床 STEP**（只出 STEP 与 FCStd，不出 STL）。
- `scripts/build_exploded_view.py`：生成结构爆炸动画 MP4。
- `scripts/build_step_package.py`：生成 `step/` 下的全部交付 STEP。

手柄打印文件：`exports/battery_grip_256x256_print_plate.step`——两个打印件已摆成打印姿态、坐在 Z=0 上，直接拖进切片软件即可。本体**法兰朝下**（首层 128×78，锥根向上收窄自支撑，内孔开口朝上）；底盖**外表面朝下**（沉孔朝上，零悬空）。零件最小间隔 8.2，整体在 256×256 床内。

### 目录职责与可再生性

| 目录 | 内容 | 是否可由本仓库代码再生 |
|---|---|---|
| `src/bracket/` | 参数与 CSG 几何，唯一真值 | — 源代码 |
| `scripts/` | FreeCAD 构建/渲染入口 | — 源代码 |
| `tests/`、`tests/freecad/` | 纯 Python 与 FreeCAD 几何回归 | — 源代码 |
| `models/`、`exports/`、`reports/` | FCStd / STEP / STL / 校验 JSON | 可，全部由 `scripts/build_*.py` 生成；未入库 |
| `step/` | **交付 STEP：每件一个 + 除手柄外的合并件** | 可，由 `build_step_package.py` 生成；**已入库** |
| `renders/*.png` | 评审图 | 可，由 `render_model.py`、`build_board_covers.py` 生成 |
| `renders/handheld_stack_exploded.mp4` | 网页用结构爆炸动画 | 可，由 `build_exploded_view.py` 生成 |
| `renders/UAV_V3_compute_carrier_reference_clean.stl` | 整机算料参考网格，4 个模块读取它 | **不可**，只能从原始整机 CAD 重新导出 |
| `vendor/livox/mid-360-asm.stp` | 官方雷达 CAD，SHA-256 锁定 | 可，`scripts/fetch_mid360.sh` |
| `vendor/realsense/` | 官方 D435 参考网格 | 已跟踪 |
| `手持结构/` | 早期手持方案的输入 STEP，**当前代码已不读取**，仅作原始 CAD 留存 | 不可再生（已跟踪） |
| `docs/superpowers/` | 历史 spec/plan，**已被本文件取代** | — 历史记录 |

`renders/UAV_V3_compute_carrier_reference_clean.stl`（67 MB）因体积过大不入 git，但它是装配干涉校验的必需输入，请另行备份。

当前一次性打印文件：

`exports/all_PLA_parts_256x256_print_plate.step`

该文件只包含四个实体：B 底座、上盖板、下盖板、A 雷达托板；采用左右两列排布，零件最小间隔不小于 8。最近一次 FreeCAD 检查结果为 4 个有效实体，整体包围盒约 242×221.5×54.1，完整位于 256×256 mm 打印范围内。

### 构建与测试命令

```bash
python -m pytest tests --ignore=tests/freecad     # 纯 Python 参数/运动学/渲染，70 项
./scripts/run_freecad.sh tests/freecad/test_print_plate.py   # FreeCAD 测试须逐文件运行
./scripts/run_freecad.sh tests/freecad/test_battery_grip.py  # 电池手柄几何校验
./scripts/run_freecad.sh scripts/build_step_package.py       # 生成 step/ 下全部交付 STEP
./scripts/run_freecad.sh tests/freecad/test_step_package.py  # 交付 STEP 校验
./scripts/run_freecad.sh scripts/build_print_plate.py        # 生成打印床 STEP
./scripts/run_freecad.sh scripts/build_board_covers.py       # 生成盖板包
./scripts/run_freecad.sh scripts/build_board_bracket_assembly.py  # 生成整机装配
./scripts/run_freecad.sh scripts/build_battery_grip.py       # 生成电池手柄 + 下盖板装配 + 打印床
./scripts/run_freecad.sh scripts/build_exploded_view.py      # 生成爆炸动画 MP4
./scripts/run_freecad.sh tests/freecad/test_exploded_view.py # 爆炸图逻辑校验
```

`scripts/run_freecad.sh` 只接受**文件路径**（内部固定追加 `--pass "$@"` 并交给 `runpy`），因此 `-m pytest` 这类写法会失败；`tests/freecad/` 下每个测试文件都自带 `__main__` 入口。

## 5. 继续编辑时的约定

1. 先确认修改对象是 A、B、上盖板还是下盖板，避免把“上/下”理解成雷达倾斜结构的上下。
2. 修改尺寸后优先更新对应参数和窄范围几何测试，再重新生成 FCStd/STEP。
3. 保留 PLA 打印件与参考模型的区别；参考模型只用于装配检查，不应导出到打印 STEP。
4. 不要使用 FreeCAD 的 `-q` 参数；本项目脚本使用 `--console` 和 `--pass`。
5. 旧版本中的 M5、R40/R48、R85/R93、15°、30°、45°等方案均为历史方案，除非用户明确要求回退，否则以本 README 和当前源代码为准。
