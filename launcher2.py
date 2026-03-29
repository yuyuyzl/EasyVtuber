import ctypes
import os
import subprocess
import threading

import wx
import json
import sys

ctypes.windll.shcore.SetProcessDpiAwareness(1)
p = None
cache_simplify_map = {
    'Off': 0,
    'Low': 1,
    'Medium': 2,
    'High': 3,
    'Higher': 4,
    'Highest': 6,
    'Gaming': 8
}

cache_simplify_quality_map = {
    'Off': 100,
    'Low': 99,
    'Medium': 95,
    'High': 90,
    'Higher': 85,
    'Highest': 80,
    'Gaming': 75
}
default_arg = {
    'character': 'lambda_00',
    'input': 3,
    'output': 2,
    'ifm': None,
    'osf': '127.0.0.1:11573',
    'min_cutoff': 50,
    'beta': 80,
    'is_extend_movement': False,
    'is_alpha_split': False,
    'is_bongo': False,
    'is_alpha_clean': False,
    'is_eyebrow': False,
    'cache_simplify': 'High',
    'ram_cache_size': '2gb',
    'vram_cache_size': '2gb',
    'model_select': 'seperable_half',
    'interpolation': "Off",
    'frame_rate_limit': '30',
    'sr': "Off",
    'use_tensorrt': False,
    'preset': 'Low',
    'mouse_audio_input': False,
    'audio_sensitivity': '0.02',
    'audio_threshold': '10.0',
    'blink_interval': '5.0',
    'breath_cycle': 'inf'
}

try:
    f = open('launcher.json')
    args = json.load(f)
    default_arg.update(args)
    f.close()
except:
    pass
finally:
    args = default_arg

p = None
dirPath = 'data/images'
characterList = []
studentModelList = []
studentModelCharacterMap = {}

def is_nvidia_gpu():
    try:
        # 获取显卡名称列表
        output = subprocess.check_output("wmic path Win32_VideoController get Name", shell=True).decode('gbk')
        return "NVIDIA" in output.upper()
    except Exception:
        return False
hasTRTSupport = is_nvidia_gpu()

def refreshList():
    global characterList
    characterList = []
    for item in sorted(os.listdir(dirPath), key=lambda x: -os.path.getmtime(os.path.join(dirPath, x))):
        if '.png' == item[-4:]:
            characterList.append(item[:-4])


def scanStudentModels():
    """Scan custom_tha4_models directory for student models"""
    global studentModelList, studentModelCharacterMap
    studentModelList = []
    studentModelCharacterMap = {}

    custom_models_path = 'data/models/custom_tha4_models'
    if os.path.exists(custom_models_path):
        try:
            for model_name in os.listdir(custom_models_path):
                model_path = os.path.join(custom_models_path, model_name)
                if os.path.isdir(model_path):
                    # Check if it's a valid student model
                    face_trt = os.path.join(model_path, 'face_morpher.trt')
                    body_trt = os.path.join(model_path, 'body_morpher.trt')
                    character_png = os.path.join(model_path,
                                                 'character.png')
                    has_trt = (os.path.exists(face_trt) and
                               os.path.exists(body_trt))
                    has_character = os.path.exists(character_png)

                    if has_trt and has_character:
                        studentModelList.append(model_name)
                        studentModelCharacterMap[model_name] = model_name
        except Exception:
            pass

    # Sort alphabetically
    studentModelList.sort()


refreshList()
scanStudentModels()

def min_cutoff_mapper(value, revert=False):
    """
    非线性映射函数：0-100整数 <-> 0-100浮点数
    使用平方函数，使得越接近0数字越密集
    """
    if revert:
        # 浮点 -> 整数: 使用平方根反向映射
        return int((value / 100.0) ** 0.5 * 100)
    # 整数 -> 浮点: 使用平方映射
    return (value / 100.0) ** 2 * 100.0


def beta_mapper(value, revert=False):
    """
    非线性映射函数：0-100整数 <-> 0-1浮点数
    使用平方函数，使得越接近0数字越密集
    """
    if revert:
        # 浮点 -> 整数: 使用平方根反向映射
        return int((value ** 0.5) * 100)
    # 整数 -> 浮点: 使用平方映射
    return (value / 100.0) ** 2


class OptionPanel(wx.Panel):
    def __init__(self, parent, title='', desc='', choices=None, mapping=None, type=0, default=None, disabled=False, mapper=min_cutoff_mapper):
        wx.Panel.__init__(self, parent)
        self.type = type
        if mapping is not None:
            self.mapping = mapping
        else:
            self.mapping = choices
        mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        leftSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(mainSizer)
        titleText = wx.StaticText(self, wx.ID_ANY, title)
        titleFont = titleText.GetFont()
        titleFont.SetWeight(wx.FONTWEIGHT_SEMIBOLD)
        titleText.SetFont(titleFont)
        leftSizer.Add(titleText, 0, wx.ALL, 0)
        descText = wx.StaticText(self, wx.ID_ANY, desc)
        descFont = descText.GetFont()
        descFont.SetWeight(wx.FONTWEIGHT_EXTRALIGHT)
        descText.SetFont(descFont)
        leftSizer.Add(descText, 0, wx.ALL, 0)
        mainSizer.Add(leftSizer, 1, wx.EXPAND | wx.ALL, 0)
        if self.type == 0:
            self.control = wx.Choice(self, wx.ID_ANY, choices=choices)
            self.control.SetMinSize(wx.Size(300, -1))
            try:
                if default is not None:
                    if self.mapping:
                        self.control.SetSelection(self.mapping.index(default))
                    else:
                        self.control.SetSelection(default)
            except:
                pass
        elif self.type == 1:
            self.control = wx.CheckBox(self, wx.ID_ANY)
            try:
                if default is not None:
                    if self.mapping:
                        self.control.SetValue(self.mapping[default])
                    else:
                        self.control.SetValue(default)

            except:
                pass
        elif self.type == 2:
            self.control = wx.TextCtrl(self, wx.ID_ANY)
            self.control.SetMinSize(wx.Size(300, -1))
            try:
                if default is not None:
                    if self.mapping:
                        self.control.SetValue(self.mapping[default])
                    else:
                        self.control.SetValue(default)
            except:
                pass
        elif self.type == 3:
            # Slider type for float values 0.0 to 1.0
            sliderSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.control = wx.Slider(self, wx.ID_ANY, value=50, minValue=0, maxValue=100, 
                                    style=wx.SL_HORIZONTAL)
            self.control.SetMinSize(wx.Size(250, -1))
            
            # Add a label to show the float value
            self.valueLabel = wx.StaticText(self, wx.ID_ANY, "0.50")
            self.valueLabel.SetMinSize(wx.Size(50, -1))
            
            try:
                if default is not None:
                    self.control.SetValue(default)
                    self.valueLabel.SetLabelText(f"{mapper(default):.4f}")
            except:
                pass
            
            # Update label when slider changes
            def onSliderChange(event):
                val = mapper(self.control.GetValue())
                self.valueLabel.SetLabelText(f"{val:.4f}")
            self.control.Bind(wx.EVT_SLIDER, onSliderChange)
            
            sliderSizer.Add(self.control, 1, wx.ALIGN_CENTER_VERTICAL)
            sliderSizer.Add(self.valueLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
            mainSizer.Add(sliderSizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
            # Skip the normal control addition below
            self.control._slider_added = True

        if not (self.type == 3 and hasattr(self.control, '_slider_added')):
            mainSizer.Add(self.control, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        # self.SetBackgroundColour('#000000') 

    def GetValue(self):
        if self.type == 0:
            ret = self.control.GetSelection()
        elif self.type == 1:
            ret = self.control.GetValue()
        elif self.type == 2:
            ret = self.control.GetValue()
        elif self.type == 3:
            ret = self.control.GetValue()
        if self.mapping is not None:
            return self.mapping[ret]
        else:
            return ret


def _important_log_line(line):
    """从 main 的一行日志中提取“重要”的简短描述，用于状态栏；无关行返回 None。"""
    line = line.strip()
    if not line:
        return None
    if line.startswith('Launched:'):
        return 'Launched'
    if 'Model Inference Ready' in line:
        return 'Model Inference Ready'
    # TRT: Building engine from ONNX: ...\filename.onnx
    if '[TRT]' in line and 'Building engine from ONNX:' in line:
        idx = line.find('Building engine from ONNX:')
        if idx != -1:
            path = line[idx + len('Building engine from ONNX:'):].strip().rstrip('\r\n')
            name = os.path.basename(path)
            if name:
                return f'Building: {name}'
    # TRT: Loading engine from file ...\filename.trt
    if '[TRT]' in line and 'Loading engine from file' in line:
        idx = line.find('Loading engine from file')
        if idx != -1:
            path = line[idx + len('Loading engine from file'):].strip().strip('.').strip().rstrip('\r\n')
            name = os.path.basename(path)
            if name:
                return f'Loading: {name}'
    # TRT: Loading ONNX file from path ...\filename.onnx
    if '[TRT]' in line and 'Loading ONNX file from path' in line:
        idx = line.find('Loading ONNX file from path')
        if idx != -1:
            path = line[idx + len('Loading ONNX file from path'):].strip().strip('.').strip().rstrip('\r\n')
            name = os.path.basename(path)
            if name:
                return f'Loading: {name}'
    # ORT: Loading ONNX model from path ...\filename.onnx
    if '[ORT]' in line and 'Loading ONNX model from path' in line:
        idx = line.find('Loading ONNX model from path')
        if idx != -1:
            path = line[idx + len('Loading ONNX model from path'):].strip().strip('.').strip().rstrip('\r\n')
            name = os.path.basename(path)
            if name:
                return f'Loading: {name}'
    # ORT: Completed loading session: xxx.onnx
    if '[ORT]' in line and 'Completed loading session:' in line:
        idx = line.find('Completed loading session:')
        if idx != -1:
            name = line[idx + len('Completed loading session:'):].strip().rstrip('\r\n')
            if name:
                return f'Loaded: {name}'
    return None


def _on_main_log_line(panel, line):
    """在子线程中调用：若该行是重要日志，则用 wx.CallAfter 更新 panel 的状态框。"""
    display = _important_log_line(line)
    if display is not None:
        wx.CallAfter(panel.statusCtrl.SetValue, display)


def _read_pipe_to_stream(pipe, dest_stream, out_lines=None, on_line_callback=None):
    """从 pipe 读行，写回 dest_stream，可选追加到 out_lines，并对每行调用 on_line_callback(line)。"""
    if pipe is None:
        return
    try:
        for raw in iter(pipe.readline, b''):
            try:
                text = raw.decode('utf-8', errors='replace')
            except Exception:
                text = raw.decode('gbk', errors='replace')
            if out_lines is not None:
                out_lines.append(text)
            if on_line_callback is not None:
                on_line_callback(text)
            # 检查dest_stream是否可用（pythonw环境下可能不可用）
            if dest_stream is not None:
                try:
                    dest_stream.write(text)
                    dest_stream.flush()
                except (AttributeError, OSError, ValueError):
                    # pythonw环境下sys.stdout/sys.stderr可能不可用，忽略错误
                    pass
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


class LauncherPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.number_of_buttons = 0
        self.frame = parent
        self.optionDict = {}
        self.main_output_lines = []   # main 的 stdout 副本
        self.main_stderr_lines = []   # main 的 stderr 副本
        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        controlSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.widgetSizer = wx.BoxSizer(wx.VERTICAL)

        stEasy = wx.StaticText(self, wx.ID_ANY, "Easy")
        f = stEasy.GetFont()
        f.SetWeight(wx.FONTWEIGHT_HEAVY)
        f = f.MakeLarger()
        stEasy.SetFont(f)
        stVtuber = wx.StaticText(self, wx.ID_ANY, "Vtuber")
        f = stVtuber.GetFont()
        f.SetWeight(wx.FONTWEIGHT_LIGHT)
        f = f.MakeLarger()
        stVtuber.SetFont(f)
        controlSizer.Add(stEasy, 0, wx.ALL | wx.CENTER, 0)
        controlSizer.Add(stVtuber, 0, wx.RIGHT | wx.CENTER, 30)

        self.statusCtrl = wx.TextCtrl(
            self, wx.ID_ANY, '',
            style=wx.TE_READONLY | wx.BORDER_NONE | wx.TE_RIGHT,
        )
        self.statusCtrl.SetHint('当前操作')
        f = self.statusCtrl.GetFont()
        self.statusCtrl.SetFont(f.Smaller())
        controlSizer.Add(self.statusCtrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 8)

        self.btnLaunch = wx.Button(self, label="Save && Launch")
        self.btnLaunch.Bind(wx.EVT_BUTTON, self.OnLaunch)
        controlSizer.Add(self.btnLaunch, 0, wx.CENTER | wx.ALL, 10)
        # self.btnAdd = wx.Button(self, label="添加") 
        # self.btnAdd.Bind(wx.EVT_BUTTON, self.OnAddWidget) 
        # controlSizer.Add(self.btnAdd, 0, wx.CENTER | wx.ALL, 5) 
        # self.btnRemove = wx.Button(self, label="删除") 
        # self.btnRemove.Bind(wx.EVT_BUTTON, self.OnRemoveWidget) 
        # controlSizer.Add(self.btnRemove, 0, wx.CENTER | wx.ALL, 5) 
        self.mainSizer.Add(self.widgetSizer, 0, wx.CENTER | wx.ALL, 10)
        self.mainSizer.Add(controlSizer, 0, wx.CENTER | wx.EXPAND | wx.LEFT, 10)
        self.mainSizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.SetSizer(self.mainSizer)
        self.optionSizer = wx.BoxSizer(wx.VERTICAL)
        self.mainSizer.Add(self.optionSizer, 0, wx.EXPAND | wx.CENTER | wx.ALL, 2)

        def addOption(key, **kwargs):
            kwargs['default'] = args[key]
            t = OptionPanel(self, **kwargs)
            self.optionSizer.Add(t, 0, wx.EXPAND | wx.ALL, 5)
            self.optionDict[key] = t
            return t

        addOption('character', title='Character', desc='选择需要使用的角色图片，位于data/images内',
                  choices=characterList)

        addOption('input', title='Input Device', desc='选择希望使用的面捕数据源',
                  choices=['iFacialMocap', 'OpenSeeFace', 'OpenCV(Webcam)', 'Mouse Input', 'Debug Input'],
                  mapping=[0, 4, 1, 3, 2])
        addOption('ifm', title='iFacialMocap IP', desc='输入iFacialMocap连接使用的IP地址，默认连接 49983 端口', type=2)
        addOption('is_eyebrow', title='Eyebrow', desc='使用眉毛输入，对性能有一定影响', type=1,
                  default=True)
        addOption('osf', title='OpenSeeFace IP:Port', desc='输入OpenSeeFace连接使用的IP:端口号', type=2)
        addOption('mouse_audio_input', title='Audio Input', desc='启用WASAPI音频输入控制嘴部动作', type=1)
        addOption('audio_sensitivity', title='Audio Sensitivity', desc='音频灵敏度，控制音频对嘴部动作的影响程度', type=2)
        addOption('audio_threshold', title='Audio Threshold', desc='音频阈值，低于此值的音频将被忽略', type=2)
        addOption('blink_interval', title='Blink Interval', desc='设置眨眼间隔时间',
                  choices=['No Blink', '3 seconds', '5 seconds', '7 seconds'],
                  mapping=['inf', '3.0', '5.0', '7.0'])
        addOption('min_cutoff', title='Min CutOff', desc='输入滤波频率截断，\n越小越平滑，越大静止时越灵敏', 
                  type=3, mapper=min_cutoff_mapper)
        addOption('beta', title='Beta', desc='输入滤波速度补偿，\n越小越平滑，越大运动时越灵敏', 
                  type=3, mapper=beta_mapper)

        addOption('breath_cycle', title='Breath Cycle', desc='设置呼吸循环时间(会增加占用)',
                  choices=['No Breath', '3 seconds', '5 seconds', '7 seconds'],
                  mapping=['inf', '3.0', '5.0', '7.0'])

        addOption('output', title='Output', desc='选择输出目标',
                  choices=['Spout2', 'OBS VirtualCam', 'Debug Output'],
                  mapping=[0, 1, 2])

        addOption('use_tensorrt', title='TensorRT加速',
                  desc='需要更长启动和预热时间（仅NVIDIA显卡支持）',
                  type=1)

        addOption('frame_rate_limit', title='FPS Limit', desc='选择帧率限制目标',
                  choices=['10', '15', '20', '30', '60'])
        addOption('preset', title='Performance Preset', desc='性能预设，注意修改后会覆盖后续配置',
                  choices=['Low', 'Medium', 'High', 'Ultra', 'Custom'])

        # Build model_select choices
        model_choices = ['Seperable Half', 'Seperable Full', 'Standard Half',
                         'Standard Full', 'THA4 Half', 'THA4 Full']
        model_mapping = ['seperable_half', 'seperable_full',
                         'standard_half', 'standard_full', 'tha4_half',
                         'tha4_full']

        # Add student models if available
        for student_model in studentModelList:
            model_choices.append(f'THA4 Student ({student_model})')
            model_mapping.append(f'tha4_student_{student_model}')

        addOption('model_select', title='Model Select',
                  desc='选择使用的模型\nStandard Full精度较高性能较低',
                  choices=model_choices,
                  mapping=model_mapping)
        addOption('ram_cache_size', title='RAM Cache Size', desc='分配内存缓存大小\n用于存储最终运算结果',
                  choices=['Off', '1GB', '2GB', '4GB', '8GB', '16GB'],
                  mapping=['0b', '1gb', '2gb', '4gb', '8gb', '16gb'])
        addOption('vram_cache_size', title='VRAM Cache Size', desc='分配显存缓存大小\n用于存储中间结果',
                  choices=['Off', '1GB', '2GB', '4GB', '8GB', '16GB'],
                  mapping=['0b', '1gb', '2gb', '4gb', '8gb', '16gb'])
        addOption('cache_simplify', title='Input Simplify',
                  desc='设置输入简化级别\n输入越简化，缓存命中率越高，动作越不平滑',
                  choices=['Off', 'Low', 'Medium', 'High', 'Higher', 'Highest', 'Gaming'])

        addOption('sr', title='SuperResolution', desc='选择使用的超分模型\n由于性能原因，real-esrgan会进行裁切',
                  choices=['Off', 'anime4k_x2', 'waifu2x_x2_half', 'real-esrgan_x4_half', 'waifu2x_x2_full',
                           'real-esrgan_x4_full'])
        addOption('interpolation', title='Frame Interpolation', desc='选择使用的补帧模型',
                  choices=['Off', 'x2_half', 'x3_half', 'x4_half', 'x2_full', 'x3_full', 'x4_full'])

        addOption('is_alpha_clean', title='Alpha Preprocessing',
                  desc='预处理Alpha通道\n代替LayerDiffusion生图后PS蒙版清理操作',
                  type=1)
        addOption('is_extend_movement', title='Extend Movement', desc='基于面捕的XY输入移动、缩放输出图像提升可动性',
                  type=1)
        addOption('is_bongo', title='Bongocat Mode', desc='适当旋转输出以适配Bongocat桌宠', type=1)
        addOption('is_alpha_split', title='Alpha Split', desc='分离透明通道到视频流右侧\n你需要自行进行后续处理',
                  type=1)

        def inputChoice(e=None):
            s = self.optionDict['input'].GetValue()
            if s != 0:
                self.optionSizer.Hide(self.optionDict['ifm'])
                self.optionSizer.Hide(self.optionDict['is_eyebrow'])
            else:
                self.optionSizer.Show(self.optionDict['ifm'])
                self.optionSizer.Show(self.optionDict['is_eyebrow'])
            if s != 4:
                self.optionSizer.Hide(self.optionDict['osf'])
            else:
                self.optionSizer.Show(self.optionDict['osf'])
                self.optionSizer.Show(self.optionDict['is_eyebrow'])
            if s != 1 and s != 4:
                self.optionSizer.Hide(self.optionDict['min_cutoff'])
                self.optionSizer.Hide(self.optionDict['beta'])
            else:
                self.optionSizer.Show(self.optionDict['min_cutoff'])
                self.optionSizer.Show(self.optionDict['beta'])
            # Show/hide audio input options for Mouse Input (s == 3)
            if s != 3:
                self.optionSizer.Hide(self.optionDict['mouse_audio_input'])
                self.optionSizer.Hide(self.optionDict['audio_sensitivity'])
                self.optionSizer.Hide(self.optionDict['audio_threshold'])
                self.optionSizer.Hide(self.optionDict['blink_interval'])
            else:
                self.optionSizer.Show(self.optionDict['mouse_audio_input'])
                self.optionSizer.Show(self.optionDict['blink_interval'])
                # Update audio fields based on checkbox state
                audioInputChoice()

            self.frame.fSizer.Layout()
            self.frame.Fit()

        def audioInputChoice(e=None):
            """Handle mouse_audio_input checkbox changes"""
            enabled = self.optionDict['mouse_audio_input'].GetValue()
            if enabled:
                self.optionSizer.Show(self.optionDict['audio_sensitivity'])
                self.optionSizer.Show(self.optionDict['audio_threshold'])
                self.optionDict['audio_sensitivity'].control.Enable(True)
                self.optionDict['audio_threshold'].control.Enable(True)
            else:
                self.optionSizer.Hide(self.optionDict['audio_sensitivity'])
                self.optionSizer.Hide(self.optionDict['audio_threshold'])
            self.frame.fSizer.Layout()
            self.frame.Fit()

        self.optionDict['input'].Bind(wx.EVT_CHOICE, inputChoice)
        self.optionDict['mouse_audio_input'].Bind(wx.EVT_CHECKBOX, audioInputChoice)
        inputChoice()

        def presetChoice(e=None):
            s = self.optionDict['preset'].GetValue()
            presetControls = [
                self.optionDict['model_select'],
                self.optionDict['ram_cache_size'],
                self.optionDict['vram_cache_size'],
                self.optionDict['cache_simplify'],
            ]
            presets = {
                'Low': [0, 1, 1, 5],
                'Medium': [1, 1, 1, 4],
                'High': [1, 2, 2, 2],
                'Ultra': [3, 3, 3, 1]
            }

            if s == 'Custom':
                for c in presetControls: self.optionSizer.Show(c)
            else:
                for c in presetControls: self.optionSizer.Hide(c)
            if s in presets:
                opt = presets[s]
                for i in range(4): presetControls[i].control.SetSelection(opt[i])

            self.frame.fSizer.Layout()
            self.frame.Fit()

        self.optionDict['preset'].Bind(wx.EVT_CHOICE, presetChoice)
        presetChoice()

        def onModelSelect(e=None):
            """Handle model selection change"""
            model_value = self.optionDict['model_select'].GetValue()
            is_student_model = 'tha4_student_' in model_value

            char_ctrl = self.optionDict['character']

            if is_student_model:
                # Disable character selection for student models
                # Student models have their own built-in character
                char_ctrl.control.Enable(False)
                char_ctrl.control.SetToolTip(
                    'Locked: Student model includes built-in character')
            else:
                # Re-enable character selection for non-student models
                char_ctrl.control.Enable(True)
                char_ctrl.control.SetToolTip(
                    'Select a character from data/images')

        self.optionDict['model_select'].Bind(
            wx.EVT_CHOICE, onModelSelect)

        # Check initial model selection and lock character if needed
        onModelSelect()

        def onActivate(e):
            global characterList
            # 用控件当前选中字符串，避免 GetValue() 用旧 mapping 按下标取导致 IndexError
            char_ctrl = self.optionDict['character'].control
            tName = char_ctrl.GetStringSelection() if char_ctrl.GetSelection() >= 0 else ''
            refreshList()
            scanStudentModels()
            self.optionDict['character'].mapping = characterList  # 同步 mapping，后续 GetValue() 才正确
            char_ctrl.SetItems(characterList)
            try:
                idx = characterList.index(tName)
                char_ctrl.SetSelection(idx)
            except (ValueError, TypeError):
                if characterList:
                    char_ctrl.SetSelection(0)
            # 重新应用“当前模型 → 是否锁定 character”的规则
            onModelSelect()

        if not hasTRTSupport:
            self.optionDict['use_tensorrt'].control.SetValue(False)
            self.optionDict['use_tensorrt'].control.Enable(False)
            self.optionDict['use_tensorrt'].control.SetToolTip(
                '需要NVIDIA显卡支持才能使用TensorRT')

        self.frame.Bind(wx.EVT_ACTIVATE, onActivate)

    def OnLaunch(self, e):
        global p
        args = {}
        for k in self.optionDict.keys():
            args[k] = self.optionDict[k].GetValue()
        f = open('launcher.json', mode='w')
        json.dump(args, f)
        f.close()
        self.btnLaunch.SetLabelText('Working...')

        if p is not None:
            creation_flags = 0
            if sys.platform == 'win32':
                # CREATE_NO_WINDOW = 0x08000000
                creation_flags = 0x08000000
            subprocess.run(['taskkill', '/F', '/PID', str(p.pid), '/T'], 
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,
                          creationflags=creation_flags)
            p = None
            self.statusCtrl.Clear()
            self.btnLaunch.SetLabelText("Save & Launch")
        else:
            # 如果启动器是用pythonw启动的，使用python.exe来启动main以便捕获控制台输出
            python_exe = sys.executable
            if 'pythonw' in python_exe.lower():
                python_exe = python_exe.replace('pythonw.exe', 'python.exe').replace('pythonw', 'python')
            run_args = [python_exe, '-m', 'src.main']
            if len(args['character']):
                run_args.append('--character')
                run_args.append(args['character'])

            if args['input'] == 0:
                if len(args['ifm']):
                    run_args.append('--ifm_input')
                    if ':' in args['ifm']:
                        run_args.append(args['ifm'])
                    else:
                        run_args.append(args['ifm'] + ':49983')
            elif args['input'] == 1:
                run_args.append('--cam_input')
            elif args['input'] == 2:
                run_args.append('--debug_input')
            elif args['input'] == 3:
                run_args.append('--mouse_input')
                run_args.append('0,0,' + str(wx.GetDisplaySize().width) + ',' + str(wx.GetDisplaySize().height))
                # Add audio input options for mouse input
                if args['mouse_audio_input']:
                    run_args.append('--mouse_audio_input')
                    if args['audio_sensitivity']:
                        run_args.append('--audio_sensitivity')
                        run_args.append(str(args['audio_sensitivity']))
                    if args['audio_threshold']:
                        run_args.append('--audio_threshold')
                        run_args.append(str(args['audio_threshold']))
                # Add blink interval for mouse input
                if args['blink_interval']:
                    run_args.append('--blink_interval')
                    run_args.append(str(args['blink_interval']))
            elif args['input'] == 4:
                if len(args['osf']):
                    run_args.append('--osf_input')
                    run_args.append(args['osf'])

            # Add breath cycle option
            if args['breath_cycle']:
                run_args.append('--breath_cycle')
                run_args.append(str(args['breath_cycle']))

            if args['output'] == 0:
                run_args.append('--output_spout2')
            elif args['output'] == 1:
                run_args.append('--output_virtual_cam')
            elif args['output'] == 2:
                run_args.append('--output_debug')

            if args['is_alpha_split']:
                run_args.append('--alpha_split')
            if args['is_extend_movement']:
                run_args.append('--extend_movement')
            if args['is_bongo']:
                run_args.append('--bongo')
            if args['is_alpha_clean']:
                run_args.append('--alpha_clean')
            if args['is_eyebrow']:
                run_args.append('--eyebrow')

            if args['cache_simplify'] is not None:
                run_args.append('--simplify')
                run_args.append(str(cache_simplify_map[args['cache_simplify']]))
            if args['ram_cache_size'] is not None:
                run_args.append('--cache')
                run_args.append(args['ram_cache_size'])
                run_args.append('--gpu_cache')
                run_args.append(args['vram_cache_size'])

            if args['interpolation'] is not None:
                if not 'Off' == args['interpolation']:
                    run_args.append('--use_interpolation')
                if 'half' in args['interpolation']:
                    run_args.append('--interpolation_half')

                if 'x2' in args['interpolation']:
                    run_args.append('--interpolation_scale')
                    run_args.append('2')
                elif 'x3' in args['interpolation']:
                    run_args.append('--interpolation_scale')
                    run_args.append('3')
                elif 'x4' in args['interpolation']:
                    run_args.append('--interpolation_scale')
                    run_args.append('4')

            if args['model_select'] is not None:
                if 'tha4_student_' in args['model_select']:
                    # Student model: tha4_student_{model_name}
                    model_name = args['model_select'].replace(
                        'tha4_student_', '')
                    run_args.append('--model_version')
                    run_args.append('v4_student')
                    run_args.append('--model_name')
                    run_args.append(model_name)
                elif 'tha4' in args['model_select']:
                    run_args.append('--model_version')
                    run_args.append('v4')
                else:
                    run_args.append('--model_version')
                    run_args.append('v3')
                if 'seperable' in args['model_select']:
                    run_args.append('--model_seperable')
                if 'half' in args['model_select']:
                    run_args.append('--model_half')

            if args['frame_rate_limit'] is not None:
                run_args.append('--frame_rate_limit')
                run_args.append(args['frame_rate_limit'])

            if args['sr'] is not None and args['sr'] != 'Off':
                run_args.append('--use_sr')
                if 'anime4k' in args['sr']:
                    run_args.append('--sr_a4k')
                if 'x4' in args['sr']:
                    run_args.append('--sr_x4')
                if 'half' in args['sr']:
                    run_args.append('--sr_half')

            if args['use_tensorrt'] is not None and args['use_tensorrt']:
                run_args.append('--use_tensorrt')

            run_args.append('--filter_min_cutoff')
            run_args.append(str(min_cutoff_mapper(args['min_cutoff'])))

            run_args.append('--filter_beta')
            run_args.append(str(beta_mapper(args['beta'])))

            print('Launched: ' + ' '.join(run_args))
            self.main_output_lines.clear()
            self.main_stderr_lines.clear()
            self.statusCtrl.SetValue('Launched')
            on_line = lambda line: _on_main_log_line(self, line)
            # 使用CREATE_NO_WINDOW标志隐藏控制台窗口，但仍可捕获输出
            creation_flags = 0
            if sys.platform == 'win32':
                # CREATE_NO_WINDOW = 0x08000000
                creation_flags = 0x08000000
            p = subprocess.Popen(
                run_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags,
            )
            threading.Thread(
                target=_read_pipe_to_stream,
                args=(p.stdout, sys.stdout, self.main_output_lines, on_line),
                daemon=True,
            ).start()
            threading.Thread(
                target=_read_pipe_to_stream,
                args=(p.stderr, sys.stderr, self.main_stderr_lines, on_line),
                daemon=True,
            ).start()
            self.btnLaunch.SetLabelText('Stop')


class MainFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(MainFrame, self).__init__(*args, **kw)
        self.InitUi()

        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnClose(self, e):
        global p
        if p is not None:
            creation_flags = 0
            if sys.platform == 'win32':
                # CREATE_NO_WINDOW = 0x08000000
                creation_flags = 0x08000000
            subprocess.run(['taskkill', '/F', '/PID', str(p.pid), '/T'], 
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,
                          creationflags=creation_flags)
        e.Skip()

    def InitUi(self):
        self.SetTitle("EasyVtuber Launcher")
        self.fSizer = wx.BoxSizer(wx.VERTICAL)
        panel = LauncherPanel(self)
        self.fSizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(self.fSizer)
        self.SetMinSize(wx.Size(600, 0))
        self.Fit()
        self.Centre()


def main():
    app = wx.App()
    sample = MainFrame(None)

    sample.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
