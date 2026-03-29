import numpy as np
import time
from .model_infer_client import ModelClientProcess
from .args import args
from .utils.preprocess import resize_to_512_center, apply_color_curves
import cv2
from .utils.shared_mem_guard import SharedMemoryGuard
from multiprocessing import shared_memory
from .utils.timer_wait import wait_until
from PIL import Image
from .utils.fps import FPS
import pyvirtualcam
from OpenGL.GL import GL_RGBA


def main():
    # Load character image
    img = Image.open(f"data/images/{args.character}.png")
    img = img.convert('RGBA')
    ow, oh = img.size
    for i, px in enumerate(img.getdata()):
        if px[3] <= 0:
            y = i // ow
            x = i % ow
            img.putpixel((x, y), (0, 0, 0, 0))
    if ow != 512 or oh != 512:
        img = resize_to_512_center(img)
    if args.alpha_clean:
        curves = {
            'a': [
                (60, 0),
                (200, 255)
            ]
        }
        img = apply_color_curves(img, curves)
    input_image = np.array(img)
    input_image = cv2.cvtColor(input_image, cv2.COLOR_RGBA2BGRA)

    print("Character Image Loaded:", args.character)

    pose_position_shm = shared_memory.SharedMemory(create=True,
                                                   size=(45 + 4) * 4)  # 45 floats for pose, 4 floats for position
    input_process = None

    if args.cam_input:
        from .face_mesh_client import FaceMeshClientProcess
        input_process = FaceMeshClientProcess(pose_position_shm)
    elif args.ifm_input is not None:
        from .i_facial_mocap_client import IFMClientProcess
        input_process = IFMClientProcess(pose_position_shm)
    elif args.osf_input is not None:
        from .open_see_face_client import OSFClientProcess
        input_process = OSFClientProcess(pose_position_shm)
    elif args.mouse_input is not None:
        from .mouse_client import MouseClientProcess
        input_process = MouseClientProcess(pose_position_shm)
    else:
        from .debug_input_client import DebugInputClientProcess
        input_process = DebugInputClientProcess(pose_position_shm)

    input_fps = input_process.fps
    input_process.daemon = True
    input_process.start()

    infer_process = ModelClientProcess(input_image, pose_position_shm, input_fps)
    infer_process.daemon = True
    infer_process.start()

    cam_width_scale = 2 if args.alpha_split else 1
    ret_channels = 3 if args.output_virtual_cam or args.output_debug else 4
    ret_batch_shm_channels = [
        SharedMemoryGuard(infer_process.ret_shared_mem, ctrl_name=f"ret_shm_ctrl_batch_{i}")
        for i in range(args.interpolation_scale)
    ]
    np_ret_shms = [
        np.ndarray((args.model_output_size, cam_width_scale * args.model_output_size, ret_channels), dtype=np.uint8,
                   buffer=infer_process.ret_shared_mem.buf[
                       i * cam_width_scale * args.model_output_size * args.model_output_size * ret_channels:
                       (i + 1) * cam_width_scale * args.model_output_size * args.model_output_size * ret_channels])
        for i in range(args.interpolation_scale)
    ]

    last_time: float = time.perf_counter()
    interval: float = 1.0 / args.frame_rate_limit if args.frame_rate_limit > 0 else 0.0

    if args.output_virtual_cam:
        virtual_cam = pyvirtualcam.Camera(width=cam_width_scale * args.model_output_size,
                                          height=args.model_output_size,
                                          fps=args.frame_rate_limit,
                                          backend='obs',
                                          fmt=pyvirtualcam.PixelFormat.RGB)
        print(f'Using virtual camera: {virtual_cam.device}')
    elif args.output_spout2:
        from PySpout import SpoutSender
        spout_sender = SpoutSender("EasyVtuber", cam_width_scale * args.model_output_size,
                                   args.model_output_size, GL_RGBA)
    else:
        print("Using OpenCV windows for output display.")

    pipeline_fps = FPS()
    last_batch_start_time = None  # 上一批就绪时间，用于周期估计
    n_frames = args.interpolation_scale
    min_period = n_frames * interval if interval > 0 else n_frames / 60.0  # 60fps 下本批最少占用时间
    default_period = 1.0 / 15.0  # 约 15fps 推理时的周期，首包无历史时使用

    print("Interval set to {:.3f} seconds".format(interval))
    while True:
        infer_process.finish_event.wait()
        infer_process.finish_event.clear()
        for i in range(n_frames):
            ret_batch_shm_channels[i].acquire()

        # 动态周期：本批就绪与上一批就绪的时间间隔，用于本批内均匀排期
        batch_start_time = time.perf_counter()
        if last_batch_start_time is not None:
            observed_period = batch_start_time - last_batch_start_time
            period = max(min_period, min(observed_period, 1.0))
        else:
            period = max(min_period, default_period)
        last_batch_start_time = batch_start_time

        for i in range(n_frames):
            # 均匀排期 + frame_rate_limit：取两者中较晚的时间发送
            target_send_time = batch_start_time + i * (period / n_frames)
            if interval > 0:
                target_send_time = max(target_send_time, last_time)
            wait_until(target_send_time)

            if args.output_virtual_cam:
                virtual_cam.send(np_ret_shms[i])
            elif args.output_spout2:
                spout_sender.send_image(np_ret_shms[i], False)
            else:
                cv2.imshow("EasyVtuber Debug Frame", np_ret_shms[i])
                cv2.waitKey(1)
            now_send = time.perf_counter()
            # 限速：下一帧最早在 last_time + interval，若已落后于当前时间则对齐到 now
            if interval > 0:
                last_time += interval
                if last_time < now_send:
                    last_time = now_send
            ret_batch_shm_channels[i].release()
        output_pipeline_fps_val = pipeline_fps() * args.interpolation_scale
        infer_process.output_pipeline_fps.value = output_pipeline_fps_val
        print(
            "Infer Process FPS: {:.2f}, Input FPS: {:.2f}, Model Avg Interval: {:.2f} ms, Cache Hit Ratio: {:.2f}%, GPU Cache Hit Ratio: {:.2f}%, Output Pipeline FPS {:.5f}".format(
                infer_process.pipeline_fps_number.value,
                input_fps.value,
                infer_process.average_model_interval.value * 1000,
                infer_process.cache_hit_ratio.value * 100,
                infer_process.gpu_cache_hit_ratio.value * 100,
                output_pipeline_fps_val
            ), end='\r', flush=True)


if __name__ == "__main__":
    main()
