import struct

import cv2
import torch
import pyvirtualcam
import numpy as np
import mediapipe as mp
from PIL import Image

import tha2.poser.modes.mode_20_wx
from pose import get_pose
from utils import preprocessing_image, postprocessing_image
from ezvtb_rt_interface import get_core

import errno
import json
import os
import queue
import socket
import time
import math
from pynput.mouse import Button, Controller
import re
from collections import OrderedDict
from multiprocessing import Value, Process, Queue, shared_memory

from pyanime4k import ac

from tha2.mocap.ifacialmocap_constants import *

from args import args
import copy

from tha3.util import torch_linear_to_srgb, resize_PIL_image, extract_PIL_image_from_filelike, \
    extract_pytorch_image_from_PIL_image

import collections
from PySpout import SpoutSender
from OpenGL.GL import GL_RGBA



def convert_linear_to_srgb(image: torch.Tensor) -> torch.Tensor:
    rgb_image = torch_linear_to_srgb(image[0:3, :, :])
    return torch.cat([rgb_image, image[3:4, :, :]], dim=0)


class FPS:
    def __init__(self, avarageof=50):
        self.frametimestamps = collections.deque(maxlen=avarageof)

    def __call__(self):
        self.frametimestamps.append(time.time())
        return self.view()
        
    def view(self):
        if len(self.frametimestamps) > 1:
            return len(self.frametimestamps) / (self.frametimestamps[-1] - self.frametimestamps[0] + 1e-10)
        else:
            return 0.0

    def last(self):
        if len(self.frametimestamps):
            return self.frametimestamps[-1]
        else:
            return time.time()


device = torch.device('cpu')


def create_default_blender_data():
    data = {}

    for blendshape_name in BLENDSHAPE_NAMES:
        data[blendshape_name] = 0.0

    data[HEAD_BONE_X] = 0.0
    data[HEAD_BONE_Y] = 0.0
    data[HEAD_BONE_Z] = 0.0
    data[HEAD_BONE_QUAT] = [0.0, 0.0, 0.0, 1.0]

    data[LEFT_EYE_BONE_X] = 0.0
    data[LEFT_EYE_BONE_Y] = 0.0
    data[LEFT_EYE_BONE_Z] = 0.0
    data[LEFT_EYE_BONE_QUAT] = [0.0, 0.0, 0.0, 1.0]

    data[RIGHT_EYE_BONE_X] = 0.0
    data[RIGHT_EYE_BONE_Y] = 0.0
    data[RIGHT_EYE_BONE_Z] = 0.0
    data[RIGHT_EYE_BONE_QUAT] = [0.0, 0.0, 0.0, 1.0]

    return data


class OSFClientProcess(Process):
    def __init__(self):
        super().__init__()
        self.queue = Queue()
        self.should_terminate = Value('b', False)
        self.address = args.osf.split(':')[0]
        self.port = int(args.osf.split(':')[1])
        self.ifm_fps_number = Value('f', 0.0)
        self.perf_time = 0

    def run(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self.socket.bind(("", self.port))
        self.socket.settimeout(0.1)
        ifm_fps = FPS()
        while True:
            if self.should_terminate.value:
                break
            try:
                socket_bytes = self.socket.recv(8192)
            except socket.error as e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK or err == 'timed out':
                    continue
                else:
                    raise e

            # socket_string = socket_bytes.decode("utf-8")
            osf_raw = (struct.unpack('=di2f2fB1f4f3f3f68f136f210f14f', socket_bytes))
            # print(osf_raw[432:])
            data = {}
            OpenSeeDataIndex = [
                'time',
                'id',
                'cameraResolutionW',
                'cameraResolutionH',
                'rightEyeOpen',
                'leftEyeOpen',
                'got3DPoints',
                'fit3DError',
                'rawQuaternionX',
                'rawQuaternionY',
                'rawQuaternionZ',
                'rawQuaternionW',
                'rawEulerX',
                'rawEulerY',
                'rawEulerZ',
                'translationY',
                'translationX',
                'translationZ',
            ]
            for i in range(len(OpenSeeDataIndex)):
                data[OpenSeeDataIndex[i]] = osf_raw[i]
            data['translationY'] *= -1
            data['translationZ'] *= -1
            data['rotationY'] = data['rawEulerY']-10
            data['rotationX'] = (-data['rawEulerX'] + 360)%360-180
            data['rotationZ'] = (data['rawEulerZ'] - 90)
            OpenSeeFeatureIndex = [
                'EyeLeft',
                'EyeRight',
                'EyebrowSteepnessLeft',
                'EyebrowUpDownLeft',
                'EyebrowQuirkLeft',
                'EyebrowSteepnessRight',
                'EyebrowUpDownRight',
                'EyebrowQuirkRight',
                'MouthCornerUpDownLeft',
                'MouthCornerInOutLeft',
                'MouthCornerUpDownRight',
                'MouthCornerInOutRight',
                'MouthOpen',
                'MouthWide'
            ]

            for i in range(68):
                data['confidence' + str(i)] = osf_raw[i + 18]
            for i in range(68):
                data['pointsX' + str(i)] = osf_raw[i * 2 + 18 + 68]
                data['pointsY' + str(i)] = osf_raw[i * 2 + 18 + 68 + 1]
            for i in range(70):
                data['points3DX' + str(i)] = osf_raw[i * 3 + 18 + 68 + 68 * 2]
                data['points3DY' + str(i)] = osf_raw[i * 3 + 18 + 68 + 68 * 2 + 1]
                data['points3DZ' + str(i)] = osf_raw[i * 3 + 18 + 68 + 68 * 2 + 2]

            for i in range(len(OpenSeeFeatureIndex)):
                data[OpenSeeFeatureIndex[i]] = osf_raw[i + 432]
            # print(data['rotationX'],data['rotationY'],data['rotationZ'])

            a = np.array([
                data['points3DX66'] - data['points3DX68'] + data['points3DX67'] - data['points3DX69'],
                data['points3DY66'] - data['points3DY68'] + data['points3DY67'] - data['points3DY69'],
                data['points3DZ66'] - data['points3DZ68'] + data['points3DZ67'] - data['points3DZ69']
            ])
            a = (a / np.linalg.norm(a))
            data['eyeRotationX'] = a[0]
            data['eyeRotationY'] = a[1]
            try:
                self.queue.put_nowait(data)
            except queue.Full:
                pass
        self.queue.close()
        self.socket.close()


ifm_converter = tha2.poser.modes.mode_20_wx.IFacialMocapPoseConverter20()


class IFMClientProcess(Process):
    def __init__(self):
        super().__init__()
        self.queue = Queue()
        self.should_terminate = Value('b', False)
        self.address = args.ifm.split(':')[0]
        self.port = int(args.ifm.split(':')[1])
        self.ifm_fps_number = Value('f', 0.0)
        self.perf_time = 0

    def run(self):

        udpClntSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        data = "iFacialMocap_sahuasouryya9218sauhuiayeta91555dy3719"

        data = data.encode('utf-8')

        udpClntSock.sendto(data, (self.address, self.port))

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self.socket.bind(("", self.port))
        self.socket.settimeout(0.1)
        ifm_fps = FPS()
        pre_socket_string = ''
        while True:
            if self.should_terminate.value:
                break
            try:
                socket_bytes = self.socket.recv(8192)
            except socket.error as e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK or err == 'timed out':
                    continue
                else:
                    raise e
            socket_string = socket_bytes.decode("utf-8")
            if args.debug and pre_socket_string != socket_string:
                self.ifm_fps_number.value = ifm_fps()
                pre_socket_string = socket_string
            # print(socket_string)
            # blender_data = json.loads(socket_string)
            data = self.convert_from_blender_data(socket_string)

            try:
                self.queue.put_nowait(data)
            except queue.Full:
                pass
        self.queue.close()
        self.socket.close()

    @staticmethod
    def convert_from_blender_data(blender_data):
        data = {}

        for item in blender_data.split('|'):
            if item.find('#') != -1:
                k, arr = item.split('#')
                arr = [float(n) for n in arr.split(',')]
                data[k.replace("_L", "Left").replace("_R", "Right")] = arr
            elif item.find('-') != -1:
                k, v = item.split("-")
                data[k.replace("_L", "Left").replace("_R", "Right")] = float(v) / 100

        to_rad = 57.3
        data[HEAD_BONE_X] = data["=head"][0] / to_rad
        data[HEAD_BONE_Y] = data["=head"][1] / to_rad
        data[HEAD_BONE_Z] = data["=head"][2] / to_rad
        data[HEAD_BONE_QUAT] = [data["=head"][3], data["=head"][4], data["=head"][5], 1]
        # print(data[HEAD_BONE_QUAT][2],min(data[EYE_BLINK_LEFT],data[EYE_BLINK_RIGHT]))
        data[RIGHT_EYE_BONE_X] = data["rightEye"][0] / to_rad
        data[RIGHT_EYE_BONE_Y] = data["rightEye"][1] / to_rad
        data[RIGHT_EYE_BONE_Z] = data["rightEye"][2] / to_rad
        data[LEFT_EYE_BONE_X] = data["leftEye"][0] / to_rad
        data[LEFT_EYE_BONE_Y] = data["leftEye"][1] / to_rad
        data[LEFT_EYE_BONE_Z] = data["leftEye"][2] / to_rad

        return data


class MouseClientProcess(Process):
    def __init__(self):
        super().__init__()
        self.queue = Queue()

    def run(self):
        mouse = Controller()
        posLimit = [int(x) for x in args.mouse_input.split(',')]
        prev = {
            'eye_l_h_temp': 0,
            'eye_r_h_temp': 0,
            'mouth_ratio': 0,
            'eye_y_ratio': 0,
            'eye_x_ratio': 0,
            'x_angle': 0,
            'y_angle': 0,
            'z_angle': 0,
        }
        while True:
            pos = mouse.position
            # print(pos)
            eye_limit = [0.8, 0.5]
            head_eye_reduce = 0.6
            head_slowness = 0.2
            mouse_data = {
                'eye_l_h_temp': 0,
                'eye_r_h_temp': 0,
                'mouth_ratio': 0,
                'eye_y_ratio': np.interp(pos[1], [posLimit[1], posLimit[3]], [1, -1]) * eye_limit[1],
                'eye_x_ratio': np.interp(pos[0], [posLimit[0], posLimit[2]], [1, -1]) * eye_limit[0],
                'x_angle': np.interp(pos[1], [posLimit[1], posLimit[3]], [1, -1]),
                'y_angle': np.interp(pos[0], [posLimit[0], posLimit[2]], [1, -1]),
                'z_angle': 0,
            }
            mouse_data['x_angle'] = np.interp(head_slowness, [0, 1], [prev['x_angle'], mouse_data['x_angle']])
            mouse_data['y_angle'] = np.interp(head_slowness, [0, 1], [prev['y_angle'], mouse_data['y_angle']])
            mouse_data['eye_y_ratio'] -= mouse_data['x_angle'] * eye_limit[1] * head_eye_reduce
            mouse_data['eye_x_ratio'] -= mouse_data['y_angle'] * eye_limit[0] * head_eye_reduce
            if args.bongo:
                mouse_data['y_angle'] += 0.05
                mouse_data['x_angle'] += 0.05
            prev = mouse_data
            self.queue.put_nowait(mouse_data)
            time.sleep(1 / 60)


class ModelClientProcess(Process):
    def __init__(self, input_image):
        super().__init__()
        self.should_terminate = Value('b', False)
        self.updated = Value('b', False)
        self.data = None
        self.input_image = input_image
        self.output_queue = Queue()
        self.input_queue = Queue()
        self.shms = [shared_memory.SharedMemory(create=True, size=args.model_output_size * args.model_output_size * 4) for _ in range(args.interpolation_scale if args.use_interpolation else 1)]
        self.model_fps_number = Value('f', 0.0)
        self.gpu_fps_number = Value('f', 0.0)
        self.cache_hit_ratio = Value('f', 0.0)
        self.gpu_cache_hit_ratio = Value('f', 0.0)

    def run(self):
        self.model = get_core(device_id = args.device_id,
                              use_tensorrt = args.use_tensorrt,

                              model_seperable = args.model_seperable,
                              model_half=args.model_half, 
                              model_cache_size=args.max_gpu_cache_len, 
                              model_use_eyebrow=args.eyebrow,

                              use_interpolation=args.use_interpolation,
                              interpolation_scale=args.interpolation_scale,
                              interpolation_half=args.interpolation_half,

                              cacher_quality=args.cacher_quality,
                              cacher_ram_size=args.max_cache_len, 

                              use_sr = args.use_sr, 
                              sr_half= args.sr_half, 
                              sr_x4=args.sr_x4)
        self.model.setImage(self.input_image)
        input_pose = np.zeros((1,45), dtype=np.float32)

        self.shared_nps = [np.ndarray((args.model_output_size, args.model_output_size, 4), dtype=np.uint8, buffer=self.shms[i].buf) for i in range(len(self.shms))]

        model_fps = FPS()

        last_process_time = time.time()
        while True:
            model_input = None
            try:
                model_input = self.input_queue.get(block=True, timeout=1.0) # Save cpu from infinite loop
                while not self.input_queue.empty():
                    model_input = self.input_queue.get_nowait()
            except queue.Empty:
                continue
            if model_input is None: continue
            frame_interval = (1 / args.frame_rate_limit) if not args.use_interpolation else (1 / args.frame_rate_limit * args.interpolation_scale)
            now = time.time()
            if now < (frame_interval * 0.9) + last_process_time: continue #
            last_process_time = now
            simplify_arr = [1000] * ifm_converter.pose_size
            if args.simplify >= 1:
                simplify_arr = [200] * ifm_converter.pose_size
                simplify_arr[ifm_converter.eye_wink_left_index] = 50
                simplify_arr[ifm_converter.eye_wink_right_index] = 50
                simplify_arr[ifm_converter.eye_happy_wink_left_index] = 50
                simplify_arr[ifm_converter.eye_happy_wink_right_index] = 50
                simplify_arr[ifm_converter.eye_surprised_left_index] = 30
                simplify_arr[ifm_converter.eye_surprised_right_index] = 30
                simplify_arr[ifm_converter.iris_rotation_x_index] = 25
                simplify_arr[ifm_converter.iris_rotation_y_index] = 25
                simplify_arr[ifm_converter.eye_raised_lower_eyelid_left_index] = 10
                simplify_arr[ifm_converter.eye_raised_lower_eyelid_right_index] = 10
                simplify_arr[ifm_converter.mouth_lowered_corner_left_index] = 5
                simplify_arr[ifm_converter.mouth_lowered_corner_right_index] = 5
                simplify_arr[ifm_converter.mouth_raised_corner_left_index] = 5
                simplify_arr[ifm_converter.mouth_raised_corner_right_index] = 5
            if args.simplify >= 2:
                simplify_arr[ifm_converter.head_x_index] = 100
                simplify_arr[ifm_converter.head_y_index] = 100
                simplify_arr[ifm_converter.eye_surprised_left_index] = 10
                simplify_arr[ifm_converter.eye_surprised_right_index] = 10
                model_input[ifm_converter.eye_wink_left_index] += model_input[
                    ifm_converter.eye_happy_wink_left_index]
                model_input[ifm_converter.eye_happy_wink_left_index] = model_input[
                                                                           ifm_converter.eye_wink_left_index] / 2
                model_input[ifm_converter.eye_wink_left_index] = model_input[
                                                                     ifm_converter.eye_wink_left_index] / 2
                model_input[ifm_converter.eye_wink_right_index] += model_input[
                    ifm_converter.eye_happy_wink_right_index]
                model_input[ifm_converter.eye_happy_wink_right_index] = model_input[
                                                                            ifm_converter.eye_wink_right_index] / 2
                model_input[ifm_converter.eye_wink_right_index] = model_input[
                                                                      ifm_converter.eye_wink_right_index] / 2

                uosum = model_input[ifm_converter.mouth_uuu_index] + \
                        model_input[ifm_converter.mouth_ooo_index]
                model_input[ifm_converter.mouth_ooo_index] = uosum
                model_input[ifm_converter.mouth_uuu_index] = 0
                is_open = (model_input[ifm_converter.mouth_aaa_index] + model_input[
                    ifm_converter.mouth_iii_index] + uosum) > 0
                model_input[ifm_converter.mouth_lowered_corner_left_index] = 0
                model_input[ifm_converter.mouth_lowered_corner_right_index] = 0
                model_input[ifm_converter.mouth_raised_corner_left_index] = 0.5 if is_open else 0
                model_input[ifm_converter.mouth_raised_corner_right_index] = 0.5 if is_open else 0
                simplify_arr[ifm_converter.mouth_lowered_corner_left_index] = 0
                simplify_arr[ifm_converter.mouth_lowered_corner_right_index] = 0
                simplify_arr[ifm_converter.mouth_raised_corner_left_index] = 0
                simplify_arr[ifm_converter.mouth_raised_corner_right_index] = 0
            if args.simplify >= 3:
                simplify_arr[ifm_converter.iris_rotation_x_index] = 20
                simplify_arr[ifm_converter.iris_rotation_y_index] = 20
                simplify_arr[ifm_converter.eye_wink_left_index] = 32
                simplify_arr[ifm_converter.eye_wink_right_index] = 32
                simplify_arr[ifm_converter.eye_happy_wink_left_index] = 32
                simplify_arr[ifm_converter.eye_happy_wink_right_index] = 32
            if args.simplify >= 4:
                simplify_arr[ifm_converter.head_x_index] = 50
                simplify_arr[ifm_converter.head_y_index] = 50
                simplify_arr[ifm_converter.neck_z_index] = 100
                model_input[ifm_converter.eye_raised_lower_eyelid_left_index] = 0
                model_input[ifm_converter.eye_raised_lower_eyelid_right_index] = 0
                simplify_arr[ifm_converter.iris_rotation_x_index] = 10
                simplify_arr[ifm_converter.iris_rotation_y_index] = 10
                simplify_arr[ifm_converter.eye_wink_left_index] = 24
                simplify_arr[ifm_converter.eye_wink_right_index] = 24
                simplify_arr[ifm_converter.eye_happy_wink_left_index] = 24
                simplify_arr[ifm_converter.eye_happy_wink_right_index] = 24
                simplify_arr[ifm_converter.eye_surprised_left_index] = 8
                simplify_arr[ifm_converter.eye_surprised_right_index] = 8
                model_input[ifm_converter.eye_wink_left_index] += model_input[
                    ifm_converter.eye_wink_right_index]
                model_input[ifm_converter.eye_wink_right_index] = model_input[
                                                                      ifm_converter.eye_wink_left_index] / 2
                model_input[ifm_converter.eye_wink_left_index] = model_input[
                                                                     ifm_converter.eye_wink_left_index] / 2

                model_input[ifm_converter.eye_surprised_left_index] += model_input[
                    ifm_converter.eye_surprised_right_index]
                model_input[ifm_converter.eye_surprised_right_index] = model_input[
                                                                           ifm_converter.eye_surprised_left_index] / 2
                model_input[ifm_converter.eye_surprised_left_index] = model_input[
                                                                          ifm_converter.eye_surprised_left_index] / 2

                model_input[ifm_converter.eye_happy_wink_left_index] += model_input[
                    ifm_converter.eye_happy_wink_right_index]
                model_input[ifm_converter.eye_happy_wink_right_index] = model_input[
                                                                            ifm_converter.eye_happy_wink_left_index] / 2
                model_input[ifm_converter.eye_happy_wink_left_index] = model_input[
                                                                           ifm_converter.eye_happy_wink_left_index] / 2
                model_input[ifm_converter.mouth_aaa_index] = min(
                    model_input[ifm_converter.mouth_aaa_index] +
                    model_input[ifm_converter.mouth_ooo_index] / 2 +
                    model_input[ifm_converter.mouth_iii_index] / 2 +
                    model_input[ifm_converter.mouth_uuu_index] / 2, 1
                )
                model_input[ifm_converter.mouth_ooo_index] = 0
                model_input[ifm_converter.mouth_iii_index] = 0
                model_input[ifm_converter.mouth_uuu_index] = 0
            for i in range(4, args.simplify):
                simplify_arr = [max(math.ceil(x * 0.8), 5) for x in simplify_arr]
            for i in range(0, len(simplify_arr)):
                if simplify_arr[i] > 0:
                    model_input[i] = round(model_input[i] * simplify_arr[i]) / simplify_arr[i]

            if args.perf == 'model':
                tic = time.perf_counter()
            if args.eyebrow:
                for i in range(12):
                    input_pose[0, i] = model_input[i]
            for i in range(27):
                input_pose[0, i + 12] = model_input[i + 12]
            for i in range(6):
                input_pose[0, i + 12 + 27] = model_input[i + 27 + 12]

            output_images = self.model.inference(input_pose)
            
            if args.perf == 'model':
                print("postprocess", (time.perf_counter() - tic) * 1000)
                tic = time.perf_counter()

            for i in range(len(self.shared_nps)):
                np.copyto(self.shared_nps[i], output_images[i])
            self.output_queue.put_nowait(True)

            if args.debug:
                self.model_fps_number.value = model_fps()
                if self.model.cacher is not None:
                    self.cache_hit_ratio.value = self.model.cacher.hits / (self.model.cacher.hits + self.model.cacher.miss + 1)
                if args.use_tensorrt:
                    self.gpu_cache_hit_ratio.value = self.model.tha.morpher_cacher.hits / (self.model.tha.morpher_cacher.hits + self.model.tha.morpher_cacher.miss)


@torch.no_grad()
def main():
    img = Image.open(f"data/images/{args.character}.png")
    img = img.convert('RGBA')
    IMG_WIDTH = 512
    wRatio = img.size[0] / IMG_WIDTH
    img = img.resize((IMG_WIDTH, int(img.size[1] / wRatio)))
    for i, px in enumerate(img.getdata()):
        if px[3] <= 0:
            y = i // IMG_WIDTH
            x = i % IMG_WIDTH
            img.putpixel((x, y), (0, 0, 0, 0))
    input_image = np.array(img.crop((0, 0, IMG_WIDTH, IMG_WIDTH)))
    input_image = cv2.cvtColor(input_image, cv2.COLOR_RGBA2BGRA)
    extra_image = None
    if img.size[1] > IMG_WIDTH:
        extra_image = np.array(img.crop((0, IMG_WIDTH, img.size[0], img.size[1])))

    print("Character Image Loaded:", args.character)
    cap = None

    output_fps = FPS()

    if not args.debug_input:

        if args.ifm is not None:
            client_process = IFMClientProcess()
            client_process.daemon = True
            client_process.start()
            print("iFacialMocap Service Running:", args.ifm)

        elif args.osf is not None:
            client_process = OSFClientProcess()
            client_process.daemon = True
            client_process.start()
            print("OpenSeeFace Service Running:", args.osf)

        elif args.mouse_input is not None:
            client_process = MouseClientProcess()
            client_process.daemon = True
            client_process.start()
            print("Mouse Input Running")

        else:

            if args.input == 'cam':
                cap = cv2.VideoCapture(0)
                ret, frame = cap.read()
                if ret is None:
                    raise Exception("Can't find Camera")
            else:
                cap = cv2.VideoCapture(args.input)
                frame_count = 0
                os.makedirs(os.path.join('dst', args.character, args.output_dir), exist_ok=True)
                print("Webcam Input Running")

    facemesh = mp.solutions.face_mesh.FaceMesh(refine_landmarks=True)


    if args.output_webcam:
        cam_scale = 1
        cam_width_scale = 1
        if args.anime4k:
            cam_scale = 2
        if args.alpha_split:
            cam_width_scale = 2

        if args.output_webcam == 'spout':
            # Create the sender
            sender = SpoutSender("EasyVtuber", args.model_output_size * cam_scale * cam_width_scale, args.model_output_size * cam_scale, GL_RGBA)
        else:
            cam = pyvirtualcam.Camera(width=args.model_output_size * cam_scale * cam_width_scale, height=args.model_output_size * cam_scale,
                                      fps=60,
                                      backend=args.output_webcam,
                                      fmt=
                                      {'unitycapture': pyvirtualcam.PixelFormat.RGBA, 'obs': pyvirtualcam.PixelFormat.RGB}[
                                          args.output_webcam])
            print(f'Using virtual camera: {cam.device}')

    a = None

    if args.anime4k:
        parameters = ac.Parameters()
        # enable HDN for ACNet
        parameters.HDN = True

        # a = ac.AC(
        #     managerList=ac.ManagerList([ac.CUDAManager(dID=0)]),
        #     type=ac.ProcessorType.Cuda_ACNet,
        # )

        a = ac.AC(
            managerList=ac.ManagerList([ac.OpenCLACNetManager(pID=0, dID=0)]),
            type=ac.ProcessorType.OpenCL_ACNet,
        )
        a.set_arguments(parameters)
        print("Anime4K Loaded")

    position_vector = [0, 0, 0, 1]
    position_vector_0 = None
    pose_vector_0 = None

    pose_queue = []
    blender_data={}
    if(args.ifm):
        blender_data = create_default_blender_data()
    mouse_data = {
        'eye_l_h_temp': 0,
        'eye_r_h_temp': 0,
        'mouth_ratio': 0,
        'eye_y_ratio': 0,
        'eye_x_ratio': 0,
        'x_angle': 0,
        'y_angle': 0,
        'z_angle': 0,
    }

    model_output = None
    model_process = ModelClientProcess(input_image)
    model_process.daemon = True
    model_process.start()
    model_output_nps = [np.ndarray((args.model_output_size, args.model_output_size, 4), dtype=np.uint8, buffer=model_process.shms[i].buf) for i in range(len(model_process.shms))]
    model_result_read_ptr = 0
    model_return_fps = FPS(5)
    need_a_copy = True

    print("Ready. Close this console to exit.")

    mouth_eye_vector_c_hist = []

    while True:
        # ret, frame = cap.read()
        # input_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # results = facemesh.process(input_frame)

        if args.perf == 'main':
            tic = time.perf_counter()
        if args.debug_input:
            eyebrow_vector_c = [0.0] * 12
            mouth_eye_vector_c = [0.0] * 27
            pose_vector_c = [0.0] * 6

            mouth_eye_vector_c[2] = math.sin(time.perf_counter() * 3)
            mouth_eye_vector_c[3] = math.sin(time.perf_counter() * 3)

            mouth_eye_vector_c[14] = 0

            mouth_eye_vector_c[25] = math.sin(time.perf_counter() * 2.2) * 0.2
            mouth_eye_vector_c[26] = math.sin(time.perf_counter() * 3.5) * 0.8

            pose_vector_c[0] = math.sin(time.perf_counter() * 1.1)
            pose_vector_c[1] = math.sin(time.perf_counter() * 1.2)
            pose_vector_c[2] = math.sin(time.perf_counter() * 1.5)

            eyebrow_vector_c[6]=math.sin(time.perf_counter() * 1.1)
            eyebrow_vector_c[7]=math.sin(time.perf_counter() * 1.1)

        elif args.osf is not None:
            try:
                new_blender_data = blender_data
                while not client_process.should_terminate.value and not client_process.queue.empty():
                    new_blender_data = client_process.queue.get_nowait()
                blender_data = new_blender_data
            except queue.Empty:
                pass
            eyebrow_vector_c = [0.0] * 12
            mouth_eye_vector_c = [0.0] * 27
            pose_vector_c = [0.0] * 6

            if len(blender_data)!=0:
                mouth_eye_vector_c[2] = 1-blender_data['leftEyeOpen']
                mouth_eye_vector_c[3] = 1-blender_data['rightEyeOpen']

                mouth_eye_vector_c[14] = max(blender_data['MouthOpen'],0)
                # print(mouth_eye_vector_c[14])

                mouth_eye_vector_c[25] = -blender_data['eyeRotationY']*3-(blender_data['rotationX'])/57.3*1.5
                mouth_eye_vector_c[26] = blender_data['eyeRotationX']*3+(blender_data['rotationY'])/57.3
                # print(mouth_eye_vector_c[25:27])
                eyebrow_vector_c[6]=blender_data['EyebrowUpDownLeft']
                eyebrow_vector_c[7]=blender_data['EyebrowUpDownRight']
                # print(blender_data['EyebrowUpDownLeft'],blender_data['EyebrowUpDownRight'])

                # if pose_vector_0==None:
                #     pose_vector_0=[0,0,0]
                #     pose_vector_0[0] = blender_data['rotationX']
                #     pose_vector_0[1] = blender_data['rotationY']
                #     pose_vector_0[2] = blender_data['rotationZ']
                # pose_vector_c[0] = (blender_data['rotationX']-pose_vector_0[0])/57.3*3
                # pose_vector_c[1] = -(blender_data['rotationY']-pose_vector_0[1])/57.3*3
                # pose_vector_c[2] = (blender_data['rotationZ']-pose_vector_0[2])/57.3
                pose_vector_c[0] = (blender_data['rotationX'])/57.3*3
                pose_vector_c[1] = -(blender_data['rotationY'])/57.3*3
                pose_vector_c[2] = (blender_data['rotationZ'])/57.3*2
                # print(pose_vector_c)

                if position_vector_0==None:
                    position_vector_0=[0,0,0,1]
                    position_vector_0[0] = blender_data['translationX']
                    position_vector_0[1] = blender_data['translationY']
                    position_vector_0[2] = blender_data['translationZ']
                position_vector[0] = -(blender_data['translationX']-position_vector_0[0])*0.1
                position_vector[1] = -(blender_data['translationY']-position_vector_0[1])*0.1
                position_vector[2] = -(blender_data['translationZ']-position_vector_0[2])*0.1

            # Apply filter
            if len(mouth_eye_vector_c_hist) == 0:
                for _ in range(3):
                    mouth_eye_vector_c_hist.append(copy.deepcopy(mouth_eye_vector_c))
            else:
                mouth_eye_vector_c_hist.pop(0)
                mouth_eye_vector_c_hist.append(mouth_eye_vector_c)
            mouth_eye_vector_c[25] = mouth_eye_vector_c_hist[0][25] * 0.2 + mouth_eye_vector_c_hist[1][25] * 0.5 + mouth_eye_vector_c_hist[2][25] * 0.3 
            mouth_eye_vector_c[26] = mouth_eye_vector_c_hist[0][26] * 0.2 + mouth_eye_vector_c_hist[1][26] * 0.5 + mouth_eye_vector_c_hist[2][26] * 0.3 

        elif args.ifm is not None:
            # get pose from ifm
            try:
                new_blender_data = blender_data
                while not client_process.should_terminate.value and not client_process.queue.empty():
                    new_blender_data = client_process.queue.get_nowait()
                blender_data = new_blender_data
            except queue.Empty:
                pass

            ifacialmocap_pose_converted = ifm_converter.convert(blender_data)

            # ifacialmocap_pose = blender_data
            #
            # eye_l_h_temp = ifacialmocap_pose[EYE_BLINK_LEFT]
            # eye_r_h_temp = ifacialmocap_pose[EYE_BLINK_RIGHT]
            # mouth_ratio = (ifacialmocap_pose[JAW_OPEN] - 0.10)*1.3
            # x_angle = -ifacialmocap_pose[HEAD_BONE_X] * 1.5 + 1.57
            # y_angle = -ifacialmocap_pose[HEAD_BONE_Y]
            # z_angle = ifacialmocap_pose[HEAD_BONE_Z] - 1.57
            #
            # eye_x_ratio = (ifacialmocap_pose[EYE_LOOK_IN_LEFT] -
            #                ifacialmocap_pose[EYE_LOOK_OUT_LEFT] -
            #                ifacialmocap_pose[EYE_LOOK_IN_RIGHT] +
            #                ifacialmocap_pose[EYE_LOOK_OUT_RIGHT]) / 2.0 / 0.75
            #
            # eye_y_ratio = (ifacialmocap_pose[EYE_LOOK_UP_LEFT]
            #                + ifacialmocap_pose[EYE_LOOK_UP_RIGHT]
            #                - ifacialmocap_pose[EYE_LOOK_DOWN_RIGHT]
            #                + ifacialmocap_pose[EYE_LOOK_DOWN_LEFT]) / 2.0 / 0.75

            eyebrow_vector_c = [0.0] * 12
            mouth_eye_vector_c = [0.0] * 27
            pose_vector_c = [0.0] * 6
            for i in range(0, 12):
                eyebrow_vector_c[i] = ifacialmocap_pose_converted[i]
            for i in range(12, 39):
                mouth_eye_vector_c[i - 12] = ifacialmocap_pose_converted[i]
            for i in range(39, 42):
                pose_vector_c[i - 39] = ifacialmocap_pose_converted[i]

            position_vector = blender_data[HEAD_BONE_QUAT]

        elif args.mouse_input is not None:

            try:
                new_blender_data = mouse_data
                while not client_process.queue.empty():
                    new_blender_data = client_process.queue.get_nowait()
                mouse_data = new_blender_data
            except queue.Empty:
                pass

            eye_l_h_temp = mouse_data['eye_l_h_temp']
            eye_r_h_temp = mouse_data['eye_r_h_temp']
            mouth_ratio = mouse_data['mouth_ratio']
            eye_y_ratio = mouse_data['eye_y_ratio']
            eye_x_ratio = mouse_data['eye_x_ratio']
            x_angle = mouse_data['x_angle']
            y_angle = mouse_data['y_angle']
            z_angle = mouse_data['z_angle']

            eyebrow_vector_c = [0.0] * 12
            mouth_eye_vector_c = [0.0] * 27
            pose_vector_c = [0.0] * 6

            mouth_eye_vector_c[2] = eye_l_h_temp
            mouth_eye_vector_c[3] = eye_r_h_temp

            mouth_eye_vector_c[14] = mouth_ratio * 1.5

            mouth_eye_vector_c[25] = eye_y_ratio
            mouth_eye_vector_c[26] = eye_x_ratio

            pose_vector_c[0] = x_angle
            pose_vector_c[1] = y_angle
            pose_vector_c[2] = z_angle

        else:
            ret, frame = cap.read()
            input_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = facemesh.process(input_frame)

            if results.multi_face_landmarks is None:
                continue

            facial_landmarks = results.multi_face_landmarks[0].landmark

            if args.debug:
                pose, debug_image = get_pose(facial_landmarks, frame)
            else:
                pose = get_pose(facial_landmarks)

            if len(pose_queue) < 3:
                pose_queue.append(pose)
                pose_queue.append(pose)
                pose_queue.append(pose)
            else:
                pose_queue.pop(0)
                pose_queue.append(pose)

            np_pose = np.average(np.array(pose_queue), axis=0, weights=[0.6, 0.3, 0.1])

            eye_l_h_temp = np_pose[0]
            eye_r_h_temp = np_pose[1]
            mouth_ratio = np_pose[2]
            eye_y_ratio = np_pose[3]
            eye_x_ratio = np_pose[4]
            x_angle = np_pose[5]
            y_angle = np_pose[6]
            z_angle = np_pose[7]

            eyebrow_vector_c = [0.0] * 12
            mouth_eye_vector_c = [0.0] * 27
            pose_vector_c = [0.0] * 6

            mouth_eye_vector_c[2] = eye_l_h_temp
            mouth_eye_vector_c[3] = eye_r_h_temp

            mouth_eye_vector_c[14] = mouth_ratio * 1.5

            mouth_eye_vector_c[25] = eye_y_ratio
            mouth_eye_vector_c[26] = eye_x_ratio

            pose_vector_c[0] = (x_angle - 1.5) * 1.6
            pose_vector_c[1] = y_angle * 2.0  # temp weight
            pose_vector_c[2] = (z_angle + 1.5) * 2  # temp weight

        pose_vector_c[3] = pose_vector_c[1]
        pose_vector_c[4] = pose_vector_c[2]

        model_input_arr = eyebrow_vector_c
        model_input_arr.extend(mouth_eye_vector_c)
        model_input_arr.extend(pose_vector_c)

        if args.perf == 'main':
            print('===')
            print("input", time.perf_counter() - tic)
            tic = time.perf_counter()
        model_process.input_queue.put_nowait(model_input_arr)



        try:
            while not model_process.output_queue.empty():
                model_process.output_queue.get_nowait()
                model_result_read_ptr = 0
                model_return_fps()
                need_a_copy = True
        except queue.Empty:
            pass

        if need_a_copy:
            model_output = model_output_nps[model_result_read_ptr].copy()
            need_a_copy = False
        interval = 1 / (model_return_fps.view()+ 1e-10) / len(model_output_nps) * 0.8
        if model_result_read_ptr + 1 < len(model_output_nps) and time.time() >= ((model_result_read_ptr + 1) * interval + model_return_fps.last()):
            model_result_read_ptr += 1
            need_a_copy = True


        postprocessed_image = model_output
        if args.perf == 'main':
            print("Compute", time.perf_counter() - tic)
            tic = time.perf_counter()

        if extra_image is not None:
            postprocessed_image = cv2.vconcat([postprocessed_image, extra_image])

        k_scale = 1
        rotate_angle = 0
        dx = 0
        dy = 0
        if args.extend_movement:
            k_scale = position_vector[2] * math.sqrt(args.extend_movement) + 1
            rotate_angle = -position_vector[0] * 10 * args.extend_movement
            dx = position_vector[0] * 400 * k_scale * args.extend_movement
            dy = -position_vector[1] * 600 * k_scale * args.extend_movement
        if args.bongo:
            rotate_angle -= 5
        
        if args.extend_movement or args.bongo:
            rm = cv2.getRotationMatrix2D((args.model_output_size / 2, args.model_output_size / 2), rotate_angle, k_scale)
            rm[0, 2] += dx
            rm[1, 2] += dy


            postprocessed_image = cv2.warpAffine(
                postprocessed_image,
                rm,
                (args.model_output_size, args.model_output_size))

        if args.perf == 'main':
            print("postprocess", (time.perf_counter() - tic) * 1000)
            tic = time.perf_counter()

        output_fps_number = output_fps()

        if args.anime4k:
            alpha_channel = postprocessed_image[:, :, 3]
            alpha_channel = cv2.resize(alpha_channel, None, fx=2, fy=2)

            # a.load_image_from_numpy(cv2.cvtColor(postprocessed_image, cv2.COLOR_RGBA2RGB), input_type=ac.AC_INPUT_RGB)
            # img = cv2.imread("character/test41.png")
            img1 = cv2.cvtColor(postprocessed_image, cv2.COLOR_BGRA2BGR)
            # a.load_image_from_numpy(img, input_type=ac.AC_INPUT_BGR)
            a.load_image_from_numpy(img1, input_type=ac.AC_INPUT_BGR)
            a.process()
            postprocessed_image = a.save_image_to_numpy()
            postprocessed_image = cv2.merge((postprocessed_image, alpha_channel))
            if args.perf == 'main':
                print("anime4k", (time.perf_counter() - tic) * 1000)
                tic = time.perf_counter()
        if args.alpha_split:
            alpha_image = cv2.merge(
                [postprocessed_image[:, :, 3], postprocessed_image[:, :, 3], postprocessed_image[:, :, 3]])
            alpha_image = cv2.cvtColor(alpha_image, cv2.COLOR_BGR2BGRA)
            postprocessed_image = cv2.hconcat([postprocessed_image, alpha_image])

        if args.debug:
            if args.use_sr:
                time.sleep(0.000001) # Opencv is using different strategy when putting 512x512 and 1024x1024 image to imshow, 
                                    # in a way that 1024x1024 is much faster than 512x512 14msvs0.2ms(maybe using zero-copy?) so when using SR, add a delay to prevent overan
                                    # Due to windows system limitation this actually sleep 16ms
            output_frame = postprocessed_image
            # resized_frame = cv2.resize(output_frame, (np.min(debug_image.shape[:2]), np.min(debug_image.shape[:2])))
            # output_frame = np.concatenate([debug_image, resized_frame], axis=1)
            cv2.putText(output_frame, str('OUT_FPS:%.1f' % output_fps_number), (0, 16), cv2.FONT_HERSHEY_PLAIN, 1,
                        (0, 255, 0), 1)
            cv2.putText(output_frame, str(
                'GPU_FPS:%.1f' % (model_process.model_fps_number.value if not args.use_interpolation else model_process.model_fps_number.value * args.interpolation_scale)),
                        (0, 32),
                        cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0), 1)
            if args.ifm is not None:
                cv2.putText(output_frame, str('IFM_FPS:%.1f' % client_process.ifm_fps_number.value), (0, 48),
                            cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0), 1)
            if args.max_cache_len > 0:
                cv2.putText(output_frame, str('MEMCACHED:%.1f%%' % (model_process.cache_hit_ratio.value * 100)),
                            (0, 64),
                            cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0), 1)
            if args.max_gpu_cache_len > 0.0:
                cv2.putText(output_frame, str('GPUCACHED:%.1f%%' % (model_process.gpu_cache_hit_ratio.value * 100)),
                            (0, 80),
                            cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0), 1)
            cv2.imshow("frame", output_frame)
            # cv2.imshow("camera", debug_image)
            cv2.waitKey(1)
        if args.output_webcam:
            # result_image = np.zeros([720, 1280, 3], dtype=np.uint8)
            # result_image[720 - 512:, 1280 // 2 - 256:1280 // 2 + 256] = cv2.resize(
            #     cv2.cvtColor(postprocessing_image(output_image.cpu()), cv2.COLOR_RGBA2RGB), (512, 512))
            result_image = postprocessed_image
            if args.output_webcam == 'spout':
                sender.send_image(cv2.cvtColor(postprocessed_image, cv2.COLOR_BGRA2RGBA),False)
                time.sleep(0.000001)
            else:
                if args.output_webcam == 'obs':
                    result_image = cv2.cvtColor(result_image, cv2.COLOR_BGRA2RGB)
                cam.send(result_image)
                cam.sleep_until_next_frame()
        if args.perf == 'main':
            print("output", (time.perf_counter() - tic) * 1000)
            tic = time.perf_counter()


if __name__ == '__main__':
    main()
