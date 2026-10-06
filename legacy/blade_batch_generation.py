import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import qmc
import math
import pandas as pd


# 定义二维叶栅样本空间范围
Xthick_range = (0.15, 0.45)  # 最大厚度位置范围
Tmax_range = (0.04, 0.07)  # 最大厚度范围
Metal2_range = (6, 24)  # 出口金属角范围
Solidity_range = (1, 2)  # 稠度范围
Incidence_range = (-4, 4)  # 气流攻角范围
Mach_range = (0.3, 0.7)  # 马赫数范围

# 生成六维拉丁超立方样本（直接采样六维空间）
sampler_6d = qmc.LatinHypercube(d=6, optimization="random-cd", seed=1)
n_samples = 500  # 采样点数（可以根据需要调整）

# 采样并映射到目标范围
samples = qmc.scale(sampler_6d.random(n=n_samples),
                    [Xthick_range[0], Tmax_range[0], Metal2_range[0], Solidity_range[0], Incidence_range[0], Mach_range[0]],
                    [Xthick_range[1], Tmax_range[1], Metal2_range[1], Solidity_range[1], Incidence_range[1], Mach_range[1]])

# 转为 DataFrame 并命名列
df = pd.DataFrame(samples, columns=["Xthick", "Tmax", "Metal2", "Solidity", "Incidence", "Mach"])

# 保存为 CSV 文件
df.to_csv("lhs_samples.csv", index=False)

# 生成叶型文件
for a, (Xthick, Tmax, Metal2, Solidity, Incidence, Mach) in enumerate(samples):
    print(f"生成第 {a + 1} 个叶型: Xthick = {Xthick:.4f}, Tmax = {Tmax:.4f}, Metal2 = {Metal2:.4f}, Solidity = {Solidity:.4f}, Incidence = {Incidence:.4f}, Mach = {Mach:.4f}")

    # 打开文件用于输出中弧线和厚度、叶型以及用于MISES的叶型
    # fid1 = open('meanline_thick_cda.dat', 'w')  # 中弧线和厚度
    fid2 = open(f'blade_sample/blade_sample_coordinates/profile_{a+1}.dat', 'w')         # 叶型
    # fid3 = open('blade.p5', 'w')                # MISES叶型

    # 参数定义
    Gridswitch = -1.0       # Gridswitch > 0 对应H型网格，Gridswitch < 0 对应O型网格
    Rsign = 1.0             # 吸力面向上为1.0，吸力面向下为-1.0
    Npoint = 101            # 叶型数据点数
    Ncirc = 4               # 前尾缘小圆点数/2
    DeltaBeta = 5           # 进口附加金属角
    Metal1 = 48 + DeltaBeta # 进口金属角，进口气流角零攻角为49度
    Metal2 = Metal2            # 出口金属角
    Xmean = 0.08            # 中弧线拐点位置
    K_m = 0.18              # Xmean处已转角占总转角比例
    Ks1 = 5              # 前缘斜率倍数
    Ks2 = 0.10              # 尾缘斜率倍数
    Xthick = Xthick         # 最大厚度位置
    Tmax = Tmax            # 最大厚度
    T1 = 0.015              # 前缘厚度
    T2 = 0.0125              # 尾缘厚度
    SS1 = 3.2               # 进口段厚度变化系数
    SS2 = 0.8               # 出口段厚度变化系数
    Nscale1 = 1.7           # 调整中弧线前部疏密
    Nscale2 = 1.7           # 调整中弧线后部疏密
    Pitch = 0.8501          # 用于MISES的栅距

    # 生成沿中弧线坐标
    xc00 = np.linspace(0, 1, Npoint)
    xc = np.zeros_like(xc00)

    for i in range(Npoint):
        if xc00[i] <= 0.5:
            xc[i] = (2 * xc00[i]) ** Nscale1 / 2
        else:
            xc[i] = 1 - (2 * (1 - xc00[i])) ** Nscale2 / 2

    # 中弧线参数计算
    Sm1 = np.tan(np.radians(Metal1))
    Sm2 = np.tan(np.radians(Metal2))
    Sm0 = np.tan(np.radians(Metal1 + (Metal2 - Metal1) * K_m))

    SSm1 = Ks1 * (Sm2 - Sm1)
    SSm2 = Ks2 * (Sm2 - Sm1)

    a1 = 1 / 2 * (-SSm1 * Xmean - Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + Xmean ** 2 * SSm2 + 3 * Xmean ** 2 * Sm1 - 3 * Xmean ** 2 * Sm2 + Sm0 - Sm1 + 2 * Xmean * Sm0 - 2 * Xmean * Sm1) / (-1 + Xmean) / Xmean ** 3
    a2 = -1 / 2 / Xmean ** 2 * (-Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + Xmean ** 2 * SSm2 + 3 * Xmean ** 2 * Sm1 - 3 * Xmean ** 2 * Sm2 + 2 * SSm1 * Xmean ** 2 - 3 * SSm1 * Xmean + 3 * Sm0 - 3 * Sm1) / (-1 + Xmean)
    a3 = SSm1
    a4 = Sm1
    a5 = -1 / 2 * (SSm1 * Xmean - 6 * Xmean * Sm1 - Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + 3 * Xmean ** 2 * Sm1 + 3 * Xmean ** 2 * SSm2 + 2 * Xmean * Sm0 - 2 * SSm1 * Xmean ** 2 - 3 * Xmean ** 2 * Sm2 + 4 * Xmean * Sm2 - 2 * SSm2 * Xmean - 3 * Sm0 + 3 * Sm1) / Xmean / (-1 + 3 * Xmean - 3 * Xmean ** 2 + Xmean ** 3)
    a6 = -1 / 2 * (-Xmean ** 3 * SSm2 + Xmean ** 3 * SSm1 + 5 * Xmean ** 2 * SSm2 - 2 * SSm1 * Xmean ** 2 + 3 * Xmean ** 2 * Sm1 - 3 * Xmean ** 2 * Sm2 - 4 * SSm2 * Xmean + SSm1 * Xmean - 6 * Xmean * Sm1 + 6 * Xmean * Sm2 + 3 * Sm1 - 3 * Sm0) / Xmean / (-1 + Xmean) ** 2
    a7 = -SSm2
    a8 = Sm2

    # 厚度参数计算
    St1 = SS1 * (Tmax / 2 - T1 / 2) / Xthick
    St2 = SS2 * (Tmax / 2 - T2 / 2) / (1 - Xthick)

    term1 = (Tmax - T1) * (1 - Xthick) ** 2
    term2 = (Tmax - T2) * Xthick ** 2
    term3 = St1 * Xthick * (1 - Xthick) ** 2
    term4 = St2 * (1 - Xthick) * Xthick ** 2

    b1 = (3 / 2 * term1 - 3 * term2 - term3 + 3 * term4) / ((1 - Xthick) ** 2 * Xthick ** 4)
    b2 = (-4 * term1 + 6 * term2 + 3 * term3 - 6 * term4) / ((1 - Xthick) ** 2 * Xthick ** 3)
    b3 = (3 * term1 - 3 * term2 - 3 * term3 + 3 * term4) / ((1 - Xthick) ** 2 * Xthick ** 2)
    b4 = St1
    b5 = T1 / 2
    b6 = (-3 / 2 * Tmax + 3 / 2 * T2 + 2 * St2 * (1 - Xthick)) / (1 - Xthick) ** 4
    b7 = (2 * Tmax - 2 * T2 - 3 * St2 * (1 - Xthick)) / (1 - Xthick) ** 3
    b8 = 0
    b9 = St2
    b10 = T2 / 2

    # 生成中弧线和厚度分布
    sc = np.zeros(Npoint)
    yc = np.zeros(Npoint)
    thick = np.zeros(Npoint)

    for i in range(Npoint):
        if xc[i] <= Xmean:
            sc[i] = a1 * xc[i] ** 3 + a2 * xc[i] ** 2 + a3 * xc[i] + a4
            yc[i] = 1 / 4 * a1 * xc[i] ** 4 + 1 / 3 * a2 * xc[i] ** 3 + 1 / 2 * a3 * xc[i] ** 2 + a4 * xc[i]
        else:
            sc[i] = a5 * (1 - xc[i]) ** 3 + a6 * (1 - xc[i]) ** 2 + a7 * (1 - xc[i]) + a8
            yc[i] = -1 / 4 * a5 * (1 - xc[i]) ** 4 - 1 / 3 * a6 * (1 - xc[i]) ** 3 - 1 / 2 * a7 * (1 - xc[i]) ** 2 - a8 * (1 - xc[i]) + (1 / 4 * a1 * Xmean ** 4 + 1 / 3 * a2 * Xmean ** 3 + 1 / 2 * a3 * Xmean ** 2 + a4 * Xmean - (-1 / 4 * a5 * (1 - Xmean) ** 4 - 1 / 3 * a6 * (1 - Xmean) ** 3 - 1 / 2 * a7 * (1 - Xmean) ** 2 - a8 * (1 - Xmean)))

        if xc[i] <= Xthick:
            thick[i] = b1 * xc[i] ** 4 + b2 * xc[i] ** 3 + b3 * xc[i] ** 2 + b4 * xc[i] + b5
        else:
            thick[i] = b6 * (1 - xc[i]) ** 4 + b7 * (1 - xc[i]) ** 3 + b8 * (1 - xc[i]) ** 2 + b9 * (1 - xc[i]) + b10

        # 输出到文件
        # fid1.write(f"{xc[i]:7.4f} {yc[i]:7.4f} {sc[i]:7.4f} {thick[i]:7.4f}\n")

    # 生成叶型
    xs = xc - thick * np.sin(np.arctan(sc))
    ys = yc + thick * np.cos(np.arctan(sc))
    xp = xc + thick * np.sin(np.arctan(sc))
    yp = yc - thick * np.cos(np.arctan(sc))

    # 关闭文件
    # fid1.close()
    fid2.close()
    # fid3.close()

    # 前缘小圆参数
    St1 = (Tmax / 2 - T1 / 2) / Xthick
    St2 = (Tmax / 2 - T2 / 2) / (1 - Xthick)

    # 计算前缘半径
    rr1 = (np.sqrt((xc[0] - xp[0]) ** 2 + (yc[0] - yp[0]) ** 2) +
           np.sqrt((xc[0] - xs[0]) ** 2 + (yc[0] - ys[0]) ** 2)) / 2

    delta1 = np.degrees(np.arctan(St1))  # delta永远为正
    r1 = rr1 / np.cos(np.radians(delta1))

    # 前缘小圆圆心
    dxc = rr1 * np.tan(np.radians(delta1))
    xc0 = xc[0] + dxc
    yc0 = (yc[1] - yc[0]) / (xc[1] - xc[0]) * (xc0 - xc[0]) + yc[0]

    # 确定起始和终止角度（Theta），并转换为0-360°
    if xc0 == xs[0]:  # 吸力面起点角度
        Theta_start = 90
    elif xs[0] > xc0:
        Theta_start = np.degrees(np.arctan((ys[0] - yc0) / (xs[0] - xc0)))
    else:
        Theta_start = np.degrees(np.arctan((ys[0] - yc0) / (xs[0] - xc0))) + 180

    if xc0 == xp[0]:  # 压力面起点角度
        Theta_end = 270
    elif xp[0] > xc0:
        Theta_end = np.degrees(np.arctan((yp[0] - yc0) / (xp[0] - xc0))) + 360
    else:
        Theta_end = np.degrees(np.arctan((yp[0] - yc0) / (xp[0] - xc0))) + 180

    # 根据网格类型生成角度
    if Gridswitch < 0:  # O型网格
        Theta_p = np.linspace((Theta_start + Theta_end) / 2, Theta_end, Ncirc + 1)
        Theta_s = np.linspace((Theta_start + Theta_end) / 2, Theta_start, Ncirc + 1)
    else:  # H型网格
        Theta_p = np.linspace(180, Theta_end, Ncirc + 1)  # 以轴向最前点为起点
        Theta_s = np.linspace(180, Theta_start, Ncirc + 1)

    # 前缘点的坐标
    xple = r1 * np.cos(np.radians(Theta_p)) + xc0  # 压力面前缘点x坐标
    yple = r1 * np.sin(np.radians(Theta_p)) + yc0  # 压力面前缘点y坐标

    xsle = r1 * np.cos(np.radians(Theta_s)) + xc0  # 吸力面前缘点x坐标
    ysle = r1 * np.sin(np.radians(Theta_s)) + yc0  # 吸力面前缘点y坐标

    # 尾缘小圆参数
    rr2 = (np.sqrt((xc[-1] - xp[-1]) ** 2 + (yc[-1] - yp[-1]) ** 2) +
           np.sqrt((xc[-1] - xs[-1]) ** 2 + (yc[-1] - ys[-1]) ** 2)) / 2

    delta2 = np.degrees(np.arctan(St2))  # delta 永远为正
    r2 = rr2 / np.cos(np.radians(delta2))

    # 尾缘小圆圆心
    dxc = rr2 * np.tan(np.radians(delta2))
    xcn = xc[-1] - dxc
    ycn = (yc[-2] - yc[-1]) / (xc[-2] - xc[-1]) * (xcn - xc[-1]) + yc[-1]

    # 确定起始和终止角度（Theta），并转换为 -180° 到 180°
    if xcn == xp[-1]:  # 压力面起点角度
        Theta_start = -90
    elif xp[-1] > xcn:
        Theta_start = np.degrees(np.arctan((yp[-1] - ycn) / (xp[-1] - xcn)))
    else:
        Theta_start = np.degrees(np.arctan((yp[-1] - ycn) / (xp[-1] - xcn))) - 180

    if xcn == xs[-1]:  # 吸力面起点角度
        Theta_end = 90
    elif xs[-1] > xcn:
        Theta_end = np.degrees(np.arctan((ys[-1] - ycn) / (xs[-1] - xcn)))
    else:
        Theta_end = np.degrees(np.arctan((ys[-1] - ycn) / (xs[-1] - xcn))) + 180

    # 根据网格类型生成角度
    if Gridswitch < 0:  # O型网格
        Theta_p = np.linspace(Theta_start, (Theta_start + Theta_end) / 2, Ncirc + 1)
        Theta_s = np.linspace(Theta_end, (Theta_start + Theta_end) / 2, Ncirc + 1)
    else:  # H型网格
        Theta_p = np.linspace(Theta_start, 0, Ncirc + 1)  # 以轴向最后点为起点
        Theta_s = np.linspace(Theta_end, 0, Ncirc + 1)

    # 尾缘点的坐标
    xpte = r2 * np.cos(np.radians(Theta_p)) + xc[-1]  # 压力面尾缘点x坐标
    ypte = r2 * np.sin(np.radians(Theta_p)) + yc[-1]  # 压力面尾缘点y坐标

    xste = r2 * np.cos(np.radians(Theta_s)) + xc[-1]  # 吸力面尾缘点x坐标
    yste = r2 * np.sin(np.radians(Theta_s)) + yc[-1]  # 吸力面尾缘点y坐标

    # 生成带前尾缘小圆的叶型
    xp1 = np.concatenate([xple[:Ncirc], xp, xpte[1:]])
    yp1 = np.concatenate([yple[:Ncirc], yp, ypte[1:]]) * Rsign

    xs1 = np.concatenate([xsle[:Ncirc], xs, xste[1:]])
    ys1 = np.concatenate([ysle[:Ncirc], ys, yste[1:]]) * Rsign

    # 保存文件
    with open(f'blade_sample/blade_sample_coordinates/profile_{a+1}.dat', 'w') as fid2:
        # 输出 profile.dat
        for i in range(len(xp1)):
            fid2.write(f'{xp1[i]:7.4f} {yp1[i]:7.4f} {xs1[i]:7.4f} {ys1[i]:7.4f}\n')

        # # 输出 blade.p5
        # fid3.write('t01\n')
        # fid3.write(f'{np.tan(np.radians(Metal1 - 8)):8.4f} {np.tan(np.radians(Metal2)):8.4f} 0.6 0.6 {Pitch:8.4f}\n')
        #
        # # 输出 MISES 适配叶型
        # for i in range(len(xs)):
        #     fid3.write(f'{xs[-i - 1]:10.6f} {ys[-i - 1]:10.6f}\n')
        # for i in range(len(xsle)):
        #     fid3.write(f'{xsle[-i - 1]:10.6f} {ysle[-i - 1]:10.6f}\n')
        # for i in range(1, len(xple)):  # for blunt LE, use 2:end
        #     fid3.write(f'{xple[i]:10.6f} {yple[i]:10.6f}\n')
        # for i in range(len(xp)):
        #     fid3.write(f'{xp[i]:10.6f} {yp[i]:10.6f}\n')

    # 生成 blade_sample_{a+1}.geomTurbo 文件
    with open(f'blade_sample/blade_sample_geomturbo/blade_sample_{a + 1}.geomTurbo', 'w') as fid_geom:
        # 将文件 blade_batch_generation_template.geomTurbo 的前14行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(14):
                fid_geom.write(f.readline())

        # 读取 profile_{a+1}.dat 文件的行数，并按比例缩放叶型到合适的尺寸
        with open(f'blade_sample/blade_sample_coordinates/profile_{a + 1}.dat', 'r') as f:
            coords = [line.split() for line in f]
        z1_ori, y1_ori = map(float, coords[0][:2])
        z2_ori, y2_ori = map(float, coords[-1][:2])
        distance = np.sqrt((z2_ori - z1_ori) ** 2 + (y2_ori - y1_ori) ** 2)
        scaling_factor = 0.06 / distance  # 计算缩放比例，将叶型的弦长缩放到0.06m
        coords_processed = [[float(value) * scaling_factor for value in line] for line in coords]  # 按比例缩放叶型到合适的尺寸
        line_count = len(coords_processed)


        # 写入固定内容(流道进出位置)
        z1 = coords_processed[0][0]  # 叶片前缘横坐标（缩放后）
        z2 = coords_processed[-1][0]  # 叶片尾缘横坐标（缩放后）
        inlet_z = z1 - (z2 - z1) * 1.5  # 流道进口横坐标
        outlet_z = z2 + (z2 - z1) * 2  # 流道出口横坐标
        fid_geom.write(f"   {inlet_z:.5f}   0\n")
        fid_geom.write(f"   {outlet_z:.5f}   0\n")

        # 将文件 blade_batch_generation_template.geomTurbo 的第17-25行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(16):  # 跳过前16行
                f.readline()
            for i in range(9):
                fid_geom.write(f.readline())

        # 写入固定内容(流道进出位置)，这里的0.003为叶高，大小为0.05倍弦长
        fid_geom.write(f"   {inlet_z:.5f}   0.003\n")
        fid_geom.write(f"   {outlet_z:.5f}   0.003\n")

        # 将文件 blade_batch_generation_template.geomTurbo 的第28-46行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(27):  # 跳过前27行
                f.readline()
            for i in range(19):
                fid_geom.write(f.readline())

        # 写入固定内容（栅距 -> 弦长/栅距=稠度，这里稠度定1.5）
        periodicity = 0.06 / Solidity
        fid_geom.write(f"  PERIODICITY			{periodicity:.5f}\n")

        # 将文件 blade_batch_generation_template.geomTurbo 的第48-77行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(47):  # 跳过前47行
                f.readline()
            for i in range(30):
                fid_geom.write(f.readline())

         # 写入 profile_{a+1}.dat 的行数
        fid_geom.write(f"{line_count}\n")

        # 写入吸力面 section 1 数据
        for line in coords_processed:
            fid_geom.write(f"0   {float(line[3]):7.7f}   {float(line[2]):7.7f}\n")

        # 将文件 blade_batch_generation_template.geomTurbo 的第247-248行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(246):  # 跳过前246行
                f.readline()
            for i in range(2):
                fid_geom.write(f.readline())

        # 写入 profile_{a+1}.dat 的行数
        fid_geom.write(f"{line_count}\n")

        # 写入吸力面 section 2 数据
        for line in coords_processed:
            fid_geom.write(f"0.003   {float(line[3]):7.7f}   {float(line[2]):7.7f}\n")

        # 将文件 blade_batch_generation_template.geomTurbo 的第418-422行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(417):  # 跳过前417行
                f.readline()
            for i in range(5):
                fid_geom.write(f.readline())

        # 写入 profile_{a+1}.dat 的行数
        fid_geom.write(f"{line_count}\n")

        # 写入压力面 section 1 数据
        for line in coords_processed:
            fid_geom.write(f"0   {float(line[1]):7.7f}   {float(line[0]):7.7f}\n")

        # 将文件 blade_batch_generation_template.geomTurbo 的第580-581行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(579):  # 跳过前579行
                f.readline()
            for i in range(2):
                fid_geom.write(f.readline())

        # 写入 profile_{a+1}.dat 的行数
        fid_geom.write(f"{line_count}\n")

        # 写入压力面 section 2 数据
        for line in coords_processed:
            fid_geom.write(f"0.003   {float(line[1]):7.7f}   {float(line[0]):7.7f}\n")

        # 将文件 blade_batch_generation_template.geomTurbo 的第739-754行内容复制到新的 geomTurbo 文件
        with open('blade_sample/blade_batch_generation_template.geomTurbo', 'r') as f:
            for i in range(738):  # 跳过前738行
                f.readline()
            for i in range(16):
                fid_geom.write(f.readline())


    # 可视化生成的叶型进行检查：
    if (a + 1) % 5 == 0:  # 检查当前的 a+1 是否是 5 的倍数
        y_coords = []  # 初始化存储 Y 坐标的列表
        z_coords = []  # 初始化存储 Z 坐标的列表
        y_79, z_79 = None, None  # 用于存储第79行的坐标
        y_187, z_187 = None, None  # 用于存储第187行的坐标

        with open(f'blade_sample/blade_sample_geomturbo/blade_sample_{a + 1}.geomTurbo', 'r') as f:
            lines = f.readlines()

            for i in range(78, 187):  # 遍历文件的第 79 行到 187 行（索引从 0 开始）
                if i < len(lines):  # 确保索引 i 不超出文件行数，防止访问越界
                    parts = lines[i].split()  # 按空格分割当前行，得到一个字符串列表
                    if len(parts) >= 3:  # 确保该行至少包含 3 列数据（X、Y、Z）
                        y_coords.append(float(parts[1]))  # 提取第二列数据（Y 坐标），转换为浮点数后存入 y_coords
                        z_coords.append(float(parts[2]))  # 提取第三列数据（Z 坐标），转换为浮点数后存入 z_coords
                        if i == 78:  # 记录第79行的坐标
                            y_79, z_79 = float(parts[1]), float(parts[2])
                        if i == 186:  # 记录第187行的坐标
                            y_187, z_187 = float(parts[1]), float(parts[2])

            for i in range(305, 414):  # 遍历文件的第 306 行到 414 行（索引从 0 开始）
                if i < len(lines):  # 确保索引 i 不超出文件行数，防止访问越界
                    parts = lines[i].split()  # 按空格分割当前行，得到一个字符串列表
                    if len(parts) >= 3:  # 确保该行至少包含 3 列数据（X、Y、Z）
                        y_coords.append(float(parts[1]))  # 提取第二列数据（Y 坐标），转换为浮点数后存入 y_coords
                        z_coords.append(float(parts[2]))  # 提取第三列数据（Z 坐标），转换为浮点数后存入 z_coords

        if y_coords and z_coords:  # 确保列表中有数据后再进行绘图

            chord_length = math.sqrt((y_187 - y_79) ** 2 + (z_187 - z_79) ** 2)  # 计算弦长（第79行与第187行的直线距离）

            # 可视化叶型数据
            plt.figure(figsize=(12, 12))  # 创建一个 6×6 英寸的绘图窗口
            plt.scatter(z_coords, y_coords, c='b', marker='o')  # 绘制散点图，颜色为蓝色（'b'），点标记为圆形（'o'）
            plt.xlabel("Z Coordinate")  # 设置 X 轴标签为 "Z Coordinate"
            plt.ylabel("Y Coordinate")  # 设置 Y 轴标签为 "Y Coordinate"
            plt.title(f"blade_sample_{a + 1}.geomTurbo")  # 设置图表标题，表明对应的叶型文件编号
            plt.grid(True)  # 显示网格，方便对比数据点
            plt.axis('equal')

            plt.text(z_79+0.05, y_79, f'Chord Length: {chord_length:.3f}', fontsize=20, color='red', ha='right')  # 添加弦长的标注

            plt.show()  # 显示绘制好的散点图



