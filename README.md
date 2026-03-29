# EasyVtuber  

> 用买皮的钱，再买一张~~3080~~随便哪张显卡吧！

![OBS Record With Transparent Virtural Cam Input](assets/new_sample.gif)

Fork自 https://github.com/GunwooHan/EasyVtuber  
为解决面捕质量问题，又反向port了原版demo https://github.com/pkhungurn/talking-head-anime-2-demo 中关于ifacialmocap的ios面捕逻辑  
并且省略了ifacialmocap pc端，通过UDP直连的方式使ios面捕刷新率达到最高60fps，解决了面捕刷新率的瓶颈  
最后，给EasyVtuber中使用的OBS虚拟摄像头方案增加配套的Shader支持，解锁RGBA输出能力，无需绿背即可直接使用

[视频介绍和安装说明](https://www.bilibili.com/video/BV1rJwgeoE2j)  

Updates:  
* 使用 https://github.com/zpeng11/ezvtuber-rt/tree/main 项目转换的ONNX模型，实现TensorRT加速以及非N卡支持，在半精度和全精度下均有加速（具体取决于显卡）  
* 为A卡和I卡提供DirectML支持，人人都能玩。  
* 引入[RIFE](https://github.com/hzwer/ECCV2022-RIFE)模型进行插帧，极限帧数提升达到50%-100%，配合锁帧可以有效降低使用占用。  
* 使用 `brotli` 压缩器获得成倍缓存命中率提升，在长时间使用上显卡减负效果相当出色。  
* 使用 [waifu2x](https://github.com/nagadomi/waifu2x) 和 [real-esrgan](https://github.com/xinntao/Real-ESRGAN) 项目带来的输出超分辨率，对比anime4k效果提升显著（也使用更多gpu占用）  
* 更漂亮的 WxPython 新启动器界面，带中文介绍更加简单易用  
* 添加Spout2 支持输出原生透明通道给OBS
* 添加 [THA V4](https://github.com/pkhungurn/talking-head-anime-4-demo) 支持，拥有更好的图形输出

## Requirements  

### 硬件  

- 支持无摄像头鼠标捕获/USB网络摄像头/iPhone结构光面捕（ifacialmocap软件，需购买）  
- 任意5年内的游戏级显卡，N卡/A卡/I卡均可使用，某些性能强的核显也可尝试，请参考[性能测试结果](PerformanceTest.md)
### 软件

- 本方案在Windows 10/11上测试可用
- OBS 使用经验
- Photoshop或其他图片处理软件
- 科学上网方案，看懂英文网站和报错的能力

## 整合包版本
请使用合适方式下载整合包并自行解压：
* [夸克网盘](https://pan.quark.cn/s/cda200521df7)
* 磁力链接 magnet:?xt=urn:btih:89bee6bc129f2e146f799e6421c0d5ef3bb4b9ff
* [谷歌网盘](https://drive.google.com/drive/folders/1cYj18EfVQ2Cl348_rkCu_fgaasHTI_io?usp=drive_link)  

### 安装Spout2 OBS插件(可选)
使用Spout2插件可以提供透明通道给OBS，访问 https://github.com/Off-World-Live/obs-spout2-plugin/releases 项目，请选择与你的OBS版本兼容的插件安装exe。

### 启动项目
双击`01A.启动器.bat` 或 `01B.启动器（调试输出）.bat` 启动器，如下图启动。
![](assets/02success.png)   
之后请移步后文的输入输出&性能配置板块自行调节。如有问题请先参考本页末的FAQ再提出。

## 输入输出设备  
#### SPOUT2 OBS插件输出

目前推荐这个方案，使用透明通道效果最好也最方便。实测OBS 31.0.0支持。  
使用前请移步 https://github.com/Off-World-Live/obs-spout2-plugin/releases  安装OBS插件  
在OBS中添加源-Spout2捕获-设置，合成模式切换为预乘Alpha，即可自动接收视频输出

#### OBS Virtual Camera 无透明通道

次选方案，如果你选择自己进行抠像你可以直接仅输出RGB到OBS，使用补帧时可能也需要此方法  
使用`视频采集设备`源，设置`滤镜`,  
在`效果滤镜`添加`色值`并自定义颜色为纯黑色，多尝试调整颜色参数直到抠图合理   

#### OBS Virtual Camera 透明通道（Outdated，透明通道插件已经转收费无法下载） 

如果你需要RGBA支持则需要额外使用一个Shader  
下载并安装StreamFX https://github.com/Xaymar/obs-StreamFX  
下载Shader（感谢树根的协助） https://github.com/shugen002/shader/blob/master/merge%20alpha2.hlsl  
之后，使用`--alpha_split`参数运行
![alpha split](assets/alphasplit.png)  
你会看到这样的输出画面，透明通道单独使用灰度方式发送了  
之后对OBS中的视频采集设备添加滤镜-着色器-选择你下载的`merge alpha2.hlsl`-关闭   
这样透明通道就应用回左边的图像了  
你可能需要手动调整一下裁剪把右侧的无用画面切掉  
(看不到着色器滤镜的话就是StreamFX没装好或者OBS不是最新版)d

#### iFacialMocap 面捕

目前最推荐的方案，使用苹果结构光硬件，捕捉效果追踪准确度都最好，demo中使用了此输入。  
需要输入`ip:port`,其中`ip`会显示在手机上，`port`使用默认`49983`   
https://www.ifacialmocap.com/download/  
你大概率需要购买正式版（非广告，只是试用版不太够时长）  
购买之前确认好自己的设备支持，装好iOS端的软件即可，连接信息通过参数传入Python  
一般需要iphone与window在同一局域网下
且游戏加速器，梯子等网络工具可能会导致ip失效，请自行解决。

#### OpenSeeFace 高精度摄像头面捕

在没有苹果硬件时最推荐使用的捕捉方案，需要更多配置
https://github.com/emilianavt/OpenSeeFace/releases  
直接下载最新版本的Release包并解压，或使用整合包附带的压缩包  
之后进入解压目录的Binary文件夹  
右键编辑`run.bat`，在倒数第二行运行facetracker的命令后加上`--model 4`，切换到模型4可以wink  
`facetracker -c %cameraNum% -F %fps% -D %dcaps% -v 3 -P 1 --discard-after 0 --scan-every 0 --no-3d-adapt 1 --max-feature-updates 900 --model 4`（仅供参考）  
之后保存并双击`run.bat`运行，按照提示选择摄像头、分辨率、帧率，捕获正常的话可以看到输出画面  
最后在启动器中选择OpenSeeFace输入，或添加启动参数`--osf 127.0.0.1:11573`即可接入OpenSeeFace

#### OpenCV 低精度摄像头面捕

此输入不需要配置，会尝试开启默认的USB或笔记本电脑摄像头开始面捕，稳定性和精确度略欠佳。

#### 鼠标音频输入

隐私考虑不想使用任何摄像头可使用这个输入，定时循环眨眼和呼吸，配合音频音量控制口型，可以在无摄像头时得到不错的动态。

## 性能配置(调参必读）
### 概念须知

#### 模型&精度
本项目完全基于AI算法生成，由3类AI模型提供服务（缝合怪）：
* THA模型：指本项目的基础模型，输入静态图像和姿态信息计算出新图像，有v3_seperable, v3_standard, v4, v4_student 四种版本。
* 插帧/补帧模型：指RIFE插帧模型，输入第1帧和第2帧，输出第1.5帧，类似DLSS3或小黄鸭，此模型是整体性能提升的关键
* 超分模型：指Anime4k, waifu2x或realesrgan模型，输入一帧图像，解算出放大且更清晰的同一帧，显著提升画面效果

每一种模型提供了半精度(标记为half)和全精度(标记为full)选项，半精度通常运行速度比全精度快，但生图效果稍微逊色，且兼容性可能不好。  

#### 缓存

当我们当前的姿态与一秒前的姿态完全相同时，输入给模型的参数也完全相同，没有必要再做一次完全相同的运算得出完全相同的结果  
倘若发现姿态相同，就使用曾经的结果输出而绕过模型运行（又叫缓存命中），从而减轻显卡负担。  
本项目同时使用显存VRAM和内存RAM用作缓存目的。在内存中还对缓存的图片进行压缩。  
缓存大小（单位GB）决定了缓存最多能使用的空间大小。更大的缓存能让缓存命中率更高，长时间使用时显卡占用更小。但也会挤占其他应用或游戏的空间。  
需要自行理解并取舍。  

#### 输入简化（量化）
输入简化与上文的缓存相辅相成，我们将姿态参数分入一些区间，这样相近的参数就可以命中同一个缓存。  
举个非常简化的例子：缓存中的一个结果对应姿态参数`0.5`, 在不进行任何输入简化时，需要新输入参数完全相同于`0.5`即 `x = 0.5`才能判定命中并绕过GPU运算。  
而开启了输入简化后，只需要新输入参数 `x` $\approx$ `0.5` 就可以命中。如`x = 0.49`或 `x = 0.51`.

### 配置建议

#### 性能预设
![image](https://github.com/user-attachments/assets/f3bd65ef-e517-46ce-b456-d44c8b5dae75)

`性能预设`简化了上文中THA模型选择，缓存，和输入简化的配置工作，不想考虑可以直接按自身配置和占用需求选低中高，如需要自行调整或关闭某个缓存可以选`Custom`选项。  
注意超分和补帧独立于性能预设需要自行选择。

#### 超分
![image](https://github.com/user-attachments/assets/afa78440-5122-4b57-b586-4487e125eb2f)

超分由waifu2x和realesrgan模型的两种精度一共4种组合，外加一种Anime4K实现。  
通常选用半精度，根据使用半身或大头选择`waifu2x_x2_half`和`realesrgan_x4_half`  
超分启动时会显著增加显卡占用。  

#### 插帧/补帧
![image](https://github.com/user-attachments/assets/de392b93-139b-455b-b561-7713d26fca20)

RIFE插帧的计算消耗比起一次THA计算要少约50%且画面观感差异不大，所以插帧倍数越多，在相同帧数输出下显卡占用就越少。   
但不可避免的会导致画面延迟和一些卡涩感，这对于杂谈和唱歌节目影响较大，可能需要自行在obs对齐音画延迟    
但对于游戏直播这类观众注意力不会长期停留皮套的节目影响并不大，所以可以放心使用，给游戏本体留出更多显卡占用。  
通常选用半精度，根据能接受的插帧倍率选择`x2_half`, `x3_half`, `x4_half`  

## 脱离启动器运行本体  

`main.py` 的完全体运行命令请参考 `02B.启动器（调试输出）.bat` 的输出以及 `args.py`。 

## Installation(使用整合包请忽略)  
可使用此安装方法对本项目二次开发

### 安装Anaconda（可选）
前往https://www.anaconda.com 安装Anaconda 并保证加入环境变量命令行可以找到，如：
```
C:\Users\Eleven>conda --version
conda 24.11.3
```
以上方式可以保证conda环境被你选定的Ananconda统一管理。若没有此需求可以忽略直接运行下一步。


### 准备Conda 环境
```
conda create -y -n easyvtuber python=3.10
conda activate easyvtuber
conda install conda-forge::pycuda
conda install -c nvidia/label/cuda-12.9.1 cuda-nvcc-dev_win-64 cudnn cuda-runtime
```

### 下载 TensorRT-RTX （Nvidia开发必选）
1. Go to https://developer.nvidia.com/tensorrt-rtx download for windows cuda129
2. Unzip downloaded folder
3. Add bin folder to environment PATH
4. Activate your python environment and install like below:
```bash
pip install D:\TensorRT-RTX-1.4.0.76_cu129\python\tensorrt_rtx-1.4.0.76-cp310-none-win_amd64.whl
```
也可以在Window 环境变量管理器 GUI中将`TensorRT-RTX-1.4.0.76_cu129\bin`在`PATH`环境变量中添加来持久化

### 克隆项目和子项目
```
git clone https://github.com/yuyuyzl/EasyVtuber.git
cd EasyVtuber
git submodule init
git submodule update --recursive --remote
```

### 安装环境
```
pip install -r requirements.txt --no-warn-script-location
```

### 下载模型
前往模型 release 地址 https://drive.google.com/file/d/1pWKIpjWeqfpa3Rub185FVvxDr5H09pOi/view?usp=drive_link 并解压到`data/models`文件夹下

### Pycharm 配置（可选）
安装完成后，在Pycharm内打开本项目，右下角解释器菜单点开，`Add Interpreter...`->`Conda Environment`->`Existing environment`  
选好自己电脑上的`conda.exe`和刚才创建好的`easyvtuber`环境内的`python.exe`    
点击OK，依赖全亮即可  

### 运行启动器  
在Conda环境中执行以下命令  
`python launcher2.py`  

### 环境错误排查
当运行TensorRT构建或启动器出现错误时，请参考如下可能性：
1. 环境安装有错误（一般运行时缺少库99%的原因都是这个，pip下载并不稳定，各种网络问题都可能导致安装失败），请检查源。
2. 英伟达显卡但计算架构低于7.5（10系以及之前）不支持TensorRT

## FAQ

> Q1: 我的电脑是A卡/I卡，去除TensorRT选项后可以运行，但为什么画面扭曲/画面染色/显卡跑不满/显卡跑满但速度慢？  

A卡I卡使用 DirectML，这个框架与显卡厂商的显卡驱动及 Direct12 实现相关，很多算子实现存在数值错误或未实现并行优化被迫降级到cpu运行。方案：1. 将显卡驱动更新至最新，2. 打开调试启动器运行并检查模型或算子是否被降级到cpu实现，3.阅读上文的模型调参环节，切换不同模型和精度多尝试。 如有兴趣了解更多请参考[性能测试结果](PerformanceTest.md)末尾对DirectML的思考。

> Q2: 为什么无法找到我自己准备的Vtuber图像/使用自己的图像会报错？

1. 确认图像改为512x512的png，带Alpha透明通道即32比特位宽。
2. 确认放置位置为`data/images`，在选项中应当能看到文件名。
3. 仍然无法正确启动请尝试删除`launch.json`文件并重新启动软件。
4. 99%的错误情况都来自于准备的图像不满足模型需求

> Q3: 我开启补帧后为什么在 Spout2 输出中边缘会有些抖动？

此问题来源于封装RIFE插帧模型时基于性能考虑对透明通道的取舍，若对这样的抖动无法接受，请使用 OBS Virtual Camera 无透明通道输出方案。

> Q4: 我可以正常运行程序且显卡温度上升风扇在转，但为什么我的任务管理器 GPU 页面里没有显示负载呢？

请在GPU页面中点击`Video Decode`或`Video Processing`按钮可以看到下拉，请对这里的选项挨个尝试找到正确的程序负载，一般在 `cuda` 或 `3D` 或 `Compute_X` 或 `Graphics_X`。

> Q6: 本机有两张显卡，如何使用第二张副卡使用这个项目？

在运行前配置环境变量`EZVTB_DEVICE_ID`为你想要运行的GPU ID,此变量缺省为`0`

## References
```
@inproceedings{huang2022rife,
  title={Real-Time Intermediate Flow Estimation for Video Frame Interpolation},
  author={Huang, Zhewei and Zhang, Tianyuan and Heng, Wen and Shi, Boxin and Zhou, Shuchang},
  booktitle={Proceedings of the European Conference on Computer Vision (ECCV)},
  year={2022}
}
@misc{Khungurn:2022,
    author = {Pramook Khungurn},
    title = {Talking Head(?) Anime from a Single Image 3: Now the Body Too},
    howpublished = {\url{http://pkhungurn.github.io/talking-head-anime-3/}},
    year = 2022,
    note = {Accessed: YYYY-MM-DD},
}

@InProceedings{wang2021realesrgan,
    author    = {Xintao Wang and Liangbin Xie and Chao Dong and Ying Shan},
    title     = {Real-ESRGAN: Training Real-World Blind Super-Resolution with Pure Synthetic Data},
    booktitle = {International Conference on Computer Vision Workshops (ICCVW)},
    date      = {2021}
}
```