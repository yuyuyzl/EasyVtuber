import argparse
import re

def convert_to_byte(size):
    result = re.search('(\d+\.?\d*)(b|kb|mb|gb|tb)', size.lower())
    if (result and result.groups()):
        unit = result.groups()[1]
        amount = float(result.groups()[0])
        index = ['b', 'kb', 'mb', 'gb', 'tb'].index(unit)
        return amount * pow(1024, index)
    raise ValueError("Invalid size provided, value is " + size)

parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true')
parser.add_argument('--eyebrow', action='store_true')
parser.add_argument('--extend_movement', type=float)
parser.add_argument('--input', type=str, default='cam')
parser.add_argument('--character', type=str, default='y')
parser.add_argument('--output_dir', type=str)
parser.add_argument('--output_webcam', type=str)
parser.add_argument('--output_size', type=str, default='512x512')
parser.add_argument('--model', type=str, default='standard_float')
parser.add_argument('--debug_input', action='store_true')
parser.add_argument('--mouse_input', type=str)
parser.add_argument('--perf', type=str)
parser.add_argument('--skip_model', action='store_true')
parser.add_argument('--ifm', type=str)
parser.add_argument('--osf', type=str)
parser.add_argument('--anime4k', action='store_true')
parser.add_argument('--alpha_split', action='store_true')
parser.add_argument('--bongo', action='store_true')
parser.add_argument('--cache', type=str, default='256mb')
parser.add_argument('--gpu_cache', type=str, default='512mb')
parser.add_argument('--simplify', type=int, default=1)

parser.add_argument('--device_id', type=int, default=0)
parser.add_argument('--use_tensorrt', action='store_true')

parser.add_argument('--model_seperable', action='store_true')
parser.add_argument('--model_half', action='store_true')
parser.add_argument('--model_cache', action='store_true')
parser.add_argument('--model_vram_cache', action='store_true')
# parser.add_argument('--model_cache_size', type=float, default=1.0)

parser.add_argument('--use_interpolation', action='store_true')
parser.add_argument('--interpolation_scale', type=int, default=3)
parser.add_argument('--interpolation_half', action='store_true')

parser.add_argument('--use_cacher', action='store_true')
parser.add_argument('--cacher_quality', type=int, default=85)
# parser.add_argument('--cacher_ram_size', type=float, default=1.0)

parser.add_argument('--use_sr', action='store_true')
parser.add_argument('--sr_x4', action='store_true')
parser.add_argument('--sr_half', action='store_true')

parser.add_argument('--frame_rate_limit', type=int, default=30)

args = parser.parse_args()
# args.output_w = int(args.output_size.split('x')[0])
# args.output_h = int(args.output_size.split('x')[1])
if args.cache is not None:
    args.max_cache_len=convert_to_byte(args.cache)/pow(1024, 3) #In gigabytes
else:
    args.max_cache_len=0

if args.gpu_cache is not None:
    args.max_gpu_cache_len=convert_to_byte(args.gpu_cache)/pow(1024, 3) #In gigabytes
else:
    args.max_gpu_cache_len=0
if args.output_webcam is None and args.output_dir is None: args.debug = True

args.model_output_size = 1024 if args.use_sr else 512

