import os
import subprocess
import tkinter as tk
import tkinter.messagebox
from tkinter import ttk
import json
import sys

default_arg = {
    'character': 'lambda_00',
    'input': 2,
    'output': 2,
    'ifm': None,
    'osf': '127.0.0.1:11573',
    'is_extend_movement': False,
    'is_anime4k': False,
    'is_alpha_split': False,
    'is_bongo': False,
    'is_eyebrow': False,
    'cache_simplify': 1,
    'cache_size': 1,
    'model_type': 0,
    'auto_mouth_threshold':0
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
for item in sorted(os.listdir(dirPath), key=lambda x: -os.path.getmtime(os.path.join(dirPath, x))):
    if '.png' == item[-4:]:
        characterList.append(item[:-4])

root = tk.Tk()
root.resizable(False, False)
root.title('EasyVtuber Launcher')

launcher = ttk.Frame(root)
launcher.pack(fill='x', expand=True)


def launch():
    global p
    global launch_btn
    args = {
        'character': character.get(),
        'input': input.get(),
        'output': output.get(),
        'ifm': ifm.get(),
        'osf': osf.get(),
        'is_extend_movement': is_extend_movement.get(),
        'is_anime4k': is_anime4k.get(),
        'is_alpha_split': is_alpha_split.get(),
        'is_bongo': is_bongo.get(),
        'is_eyebrow': is_eyebrow.get(),
        'cache_simplify': cache_simplify.get(),
        'cache_size': cache_size.get(),
        'model_type': model_type.get(),
        'auto_mouth_threshold': auto_mouth_threshold.get()
    }

    if args['input'] == 0:
        if len(args['ifm']) == 0:
            tkinter.messagebox.showinfo('EasyVtuber Launcher', 'Please Input iFacialMocap IP:Port')
            return
    if args['input'] == 4:
        if len(args['osf']) == 0:
            tkinter.messagebox.showinfo('EasyVtuber Launcher', 'Please Input OpenSeeFace IP:Port')
            return

    f = open('launcher.json', mode='w')
    json.dump(args, f)
    f.close()
    if p is not None:
        subprocess.run(['taskkill', '/F', '/PID', str(p.pid), '/T'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        p = None
        launch_btn.config(text="Save & Launch")
    else:
        run_args = [sys.executable, 'main.py']
        if len(args['character']):
            run_args.append('--character')
            run_args.append(args['character'])

        if args['input'] == 0:
            if len(args['ifm']):
                run_args.append('--ifm')
                run_args.append(args['ifm'])
        elif args['input'] == 1:
            run_args.append('--input')
            run_args.append('cam')
        elif args['input'] == 2:
            run_args.append('--debug_input')
        elif args['input'] == 3:
            run_args.append('--mouse_input')
            run_args.append('0,0,' + str(root.winfo_screenwidth()) + ',' + str(root.winfo_screenheight()))
        elif args['input'] == 4:
            if len(args['osf']):
                run_args.append('--osf')
                run_args.append(args['osf'])

        if args['output'] == 0:
            run_args.append('--output_webcam')
            run_args.append('unitycapture')
        elif args['output'] == 1:
            run_args.append('--output_webcam')
            run_args.append('obs')
        elif args['output'] == 2:
            run_args.append('--debug')
        if args['is_anime4k']:
            run_args.append('--anime4k')
        if args['is_alpha_split']:
            run_args.append('--alpha_split')
        if args['is_extend_movement']:
            run_args.append('--extend_movement')
            run_args.append('1')
        if args['is_bongo']:
            run_args.append('--bongo')
        if args['is_eyebrow']:
            run_args.append('--eyebrow')
        if args['cache_simplify'] is not None:
            run_args.append('--simplify')
            run_args.append(str(args['cache_simplify']))
        if args['cache_size'] is not None:
            run_args.append('--cache')
            run_args.append(['0b', '256mb', '1gb', '2gb', '4gb', '8gb'][args['cache_size']])
            run_args.append('--gpu_cache')
            run_args.append(['0b', '128mb', '512mb', '1gb', '2gb', '4gb'][args['cache_size']])
        if args['model_type'] is not None:
            run_args.append('--model')
            model_name = ['standard_float', 'standard_half', 'separable_half'][args['model_type']]
            run_args.append(model_name)
            if not os.path.exists('data/models/' + model_name + '/face_morpher.pt'):
                tkinter.messagebox.showinfo('EasyVtuber Launcher',
                                            'Missing Model File: ' + 'data/models/' + model_name + '\nCheck link 00B or README.md for more info.')
                return
        if args['auto_mouth_threshold'] is not None:
            run_args.append('--auto_mouth_threshold')
            run_args.append(str(args['auto_mouth_threshold']))

        run_args.append('--output_size')
        run_args.append('512x512')
        print('Launched: ' + ' '.join(run_args))
        p = subprocess.Popen(run_args)
        launch_btn.config(text='Stop')


launch_btn = ttk.Button(launcher, text="Save & Launch", command=launch)
launch_btn.pack(side='bottom', fill='x', expand=True, pady=10, padx=10)

frameL = ttk.Frame(launcher)
frameL.pack(padx=10, pady=10, fill='both', side='left', expand=True)
frameR = ttk.Frame(launcher)
frameR.pack(padx=10, pady=10, fill='both', side='left', expand=True)

character = tk.StringVar(value=args['character'])
ttk.Label(frameL, text="Character").pack(fill='x', expand=True)

# ttk.Entry(frameL, textvariable=character).pack(fill='x', expand=True)
char_combo = ttk.Combobox(frameL, textvariable=character, value=characterList)
char_combo.pack(fill='x', expand=True)



def inputChange():
    i=input.get()
    if i==0:
        ifmLbl.pack(fill='x', expand=True)
        ifmEnt.pack(fill='x', expand=True)
        osfLbl.pack_forget()
        osfEnt.pack_forget()
    elif i==4:
        ifmLbl.pack_forget()
        ifmEnt.pack_forget()
        osfLbl.pack(fill='x', expand=True)
        osfEnt.pack(fill='x', expand=True)
    else:
        ifmLbl.pack_forget()
        ifmEnt.pack_forget()
        osfLbl.pack_forget()
        osfEnt.pack_forget()
        frameLTxt.configure(height=0)
input = tk.IntVar(value=args['input'])
ttk.Label(frameL, text="Face Data Source").pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='iFacialMocap', value=0, variable=input, command=inputChange).pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='OpenSeeFace', value=4, variable=input, command=inputChange).pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='Webcam(opencv)', value=1, variable=input, command=inputChange).pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='Mouse Input', value=3, variable=input, command=inputChange).pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='Initial Debug Input', value=2, variable=input, command=inputChange).pack(fill='x',
                                                                                                       expand=True)
frameLTxt = ttk.Frame(frameL)
frameLTxt.pack(fill='x', expand=True)
ifmLbl = ttk.Label(frameLTxt, text="iFacialMocap IP:Port")
ifmLbl.pack(fill='x', expand=True)

ifm = tk.StringVar(value=args['ifm'])
ifmEnt = ttk.Entry(frameLTxt, textvariable=ifm, state=False)
ifmEnt.pack(fill='x', expand=True)

osfLbl = ttk.Label(frameLTxt, text="OpenSeeFace IP:Port")
osfLbl.pack(fill='x', expand=True)
osf = tk.StringVar(value=args['osf'])
osfEnt = ttk.Entry(frameLTxt, textvariable=osf, state=False)
osfEnt.pack(fill='x', expand=True)
inputChange()

ttk.Label(frameR, text="Model Simplify").pack(fill='x', expand=True)
model_type = tk.IntVar(value=args['model_type'])
ttk.Radiobutton(frameR, text='Off', value=0, variable=model_type).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='Low', value=1, variable=model_type).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='High', value=2, variable=model_type).pack(fill='x', expand=True)

ttk.Label(frameR, text="Facial Input Simplify").pack(fill='x', expand=True)
cache_simplify = tk.IntVar(value=args['cache_simplify'])
ttk.Radiobutton(frameR, text='Off', value=0, variable=cache_simplify).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='Low', value=1, variable=cache_simplify).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='Medium', value=2, variable=cache_simplify).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='High', value=3, variable=cache_simplify).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='Higher', value=4, variable=cache_simplify).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='Highest', value=6, variable=cache_simplify).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='Gaming', value=8, variable=cache_simplify).pack(fill='x', expand=True)

ttk.Label(frameR, text="Cache Size (RAM+VRAM)").pack(fill='x', expand=True)
cache_size = tk.IntVar(value=args['cache_size'])
ttk.Radiobutton(frameR, text='Off', value=0, variable=cache_size).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='256M+128M', value=1, variable=cache_size).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='1GB+512M', value=2, variable=cache_size).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='2GB+1GB', value=3, variable=cache_size).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='4GB+2GB', value=4, variable=cache_size).pack(fill='x', expand=True)
ttk.Radiobutton(frameR, text='8GB+4GB', value=5, variable=cache_size).pack(fill='x', expand=True)

ttk.Label(frameL, text="Extra Options").pack(fill='x', expand=True)
is_eyebrow = tk.BooleanVar(value=args['is_eyebrow'])
ttk.Checkbutton(frameL, text='Eyebrow (iFM Only)', variable=is_eyebrow).pack(fill='x', expand=True)

is_extend_movement = tk.BooleanVar(value=args['is_extend_movement'])
ttk.Checkbutton(frameL, text='Extend Movement', variable=is_extend_movement).pack(fill='x', expand=True)

is_anime4k = tk.BooleanVar(value=args['is_anime4k'])
ttk.Checkbutton(frameL, text='Anime4K', variable=is_anime4k).pack(fill='x', expand=True)

is_alpha_split = tk.BooleanVar(value=args['is_alpha_split'])
ttk.Checkbutton(frameL, text='Alpha Split', variable=is_alpha_split).pack(fill='x', expand=True)

is_bongo = tk.BooleanVar(value=args['is_bongo'])
ttk.Checkbutton(frameL, text='Bongocat Mode', variable=is_bongo).pack(fill='x', expand=True)

auto_mouth_threshold = tk.IntVar(value=args['auto_mouth_threshold'])
def validate_int(P):
    if P.isdigit():
        return True
    return False
ttk.Label(frameL, text='Auto Mouth Threshold: ').pack()
threshold_entry = ttk.Entry(frameL, textvariable=auto_mouth_threshold, validate='key', validatecommand=(root.register(validate_int), '%P'))
threshold_entry.pack(fill='x', expand=True)
    

output = tk.IntVar(value=args['output'])
ttk.Label(frameL, text="Output").pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='Unity Capture', value=0, variable=output).pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='OBS Virtual Camera', value=1, variable=output).pack(fill='x', expand=True)
ttk.Radiobutton(frameL, text='Initial Debug Output', value=2, variable=output).pack(fill='x', expand=True)


def closeWindow():
    if p is not None:
        subprocess.run(['taskkill', '/F', '/PID', str(p.pid), '/T'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    root.destroy()


def handle_focus(event):
    characterList = []
    if event.widget == root:
        for item in sorted(os.listdir(dirPath), key=lambda x: -os.path.getmtime(os.path.join(dirPath, x))):
            if '.png' == item[-4:]:
                characterList.append(item[:-4])
        char_combo.config(value=characterList)


root.bind("<FocusIn>", handle_focus)
root.protocol('WM_DELETE_WINDOW', closeWindow)
root.mainloop()
