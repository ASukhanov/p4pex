'''EPICS p4p-based softIocPVA of a simulated oscilloscope, similar to asyn/testAsynPortDriverApp.
'''
__version__= 'v0.1.2 2025-01-05'# Handling of Run Start/Stop. 

import argparse, time, threading
import numpy as np
import pprint
from p4p.nt import NTScalar, NTEnum
from p4p.nt.enum import ntenum
from p4p.server import Server
from p4p.server.thread import SharedPV

#`````````````````Constants```````````````````````````````````````````````````
P = 'simScope1:'# Prefix
SleepTime = 1.
EventExit = threading.Event()
MaxPoints = 100

#``````````````````Module properties``````````````````````````````````````````
class G():
    PVs = {}
    cycle = 0
    noiseLevel = 1.
    #timeArray = np.linspace(0.,1.,MaxPoints)
    timeArray = np.arange(MaxPoints)
    peaksParameters = None
    threadProc = None

    def set_noise(level):
        G.noiseLevel = level

    def set_run(vntenum):
        idx = vntenum.raw.value.index
        #print(f">set_run {idx}")
        if idx == 0:# Run
            threading.Thread(target=G.threadProc).start()

#``````````````````Argument parsing```````````````````````````````````````````
parser = argparse.ArgumentParser(description = __doc__,
  formatter_class=argparse.ArgumentDefaultsHelpFormatter,
  epilog=(f'{__version__}'))
parser.add_argument('-l', '--listPVs', action='store_true', help=\
'List all generated PVs')
parser.add_argument('-v', '--verbose', action='count', default=0, help=\
'Show more log messages (-vv: show even more)')
pargs = parser.parse_args()

#```````````````````Helper methods````````````````````````````````````````````
def printTime(): return time.strftime("%m%d:%H%M%S")
def printi(msg): print(f'inf_@{printTime()}: {msg}')
def printw(msg): print(f'WAR_@{printTime()}: {msg}')
def printe(msg): print(f'ERR_{printTime()}: {msg}')
def _printv(msg, level):
    if pargs.verbose >= level: print(f'DBG{level}: {msg}')
def printv(msg): _printv(msg, 1)
def printvv(msg): _printv(msg, 2)

#``````````````````Simulated peaks````````````````````````````````````````````
def gaussian(x, sigma):
    """Function, representing gaussian peak shape"""
    try: r = np.exp(-0.5*(x/sigma)**2) 
    except: r = np.zeros(len(x))
    return r

RankBkg = 3
def func_sum_of_peaks(xx, *par):
    """Base and sum of peaks."""
    if RankBkg == 3:
        s = par[0] + par[1]*xx + par[2]*xx**2 # if RankBkg = 3
    elif RankBkg == 1:
        s = par[0] # if RankBkg = 1
    for i in range(RankBkg,len(par),3):
        s += par[i+2]*gaussian(xx-par[i],par[i+1])
    return s

def noisyArray(size):
    return np.random.normal(scale=0.5,size=size)

def get_waveForm():
    """Generate multiple peaks and noise"""
    n = len(G.timeArray)
    v = func_sum_of_peaks(G.timeArray, *G.peaksParameters)
    return v + noisyArray(n)*G.noiseLevel

#default coeffs for --background
linmin = 1.
linmax = 30.
quadmax = 20.
def generate_pars(n):
    a = -4*quadmax/n**2
    b = -a*n + (linmax-linmin)/n
    bckPars = [linmin, round(b,6), round(a,9)]
    peakPars = [0.3*n,0.015*n,10, 0.5*n,0.020*n,40, 0.7*n,0.025*n,15]
    return bckPars + peakPars

#def str_of_numbers(numbers:list):
#    return ','.join([f'{i}' for i in numbers])

G.peaksParameters = generate_pars(MaxPoints)
print(f'peaksParameters: {G.peaksParameters}')

#``````````````````Definition of PVs``````````````````````````````````````````
typeCode = {
'F64':'d',  'F32':'f',  'I64':'l',  'I8':'b',   'U8':'B',   'I16':'h',
'U16':'H',  'I32':'i',  'U32':'I',  'I64':'l',
}
def NTS(t): return NTScalar(typeCode[t],display=True)
def NTA(t): return NTScalar('a'+typeCode[t],display=True)

PVDefs = [
['Run', 'Start/Stop the device',
    NTEnum(),#DNW:display=True),
    {'choices': ['Run','Stop'], 'index': 0},'WE',
    {'setter': G.set_run}],
['VoltOffset', 'Not operational', NTS('F32'), 0., 'WE', {'units':'V'}],
#['VoltOffset_RBV', '', NTS('F32'), 0., 'R',{}],
['VoltsPerDivSelect', 'Vertical scale',  NTEnum(),
    {'choices': ['0.1','0.2','0.5','1.0'], 'index':0}, 'WE', {'units':'V'}],
#['VoltsPerDivSelect_RBV', '', NTS('F32'), 0., 'R',{}],
['TimePerDivSelect', 'Not operational', NTEnum(),
    {'choices': '0.01 0.02 0.05 0.1 0.2 0.5 1 2 5'.split(),
    'index': 0},'WE',{'units':'s'}],
['TimePerDivSelect_RBV', 'Not operational', NTS('F32'), 0., 'R',{}],
['VertGainSelect', 'Not operational', NTS('F32'), 0., 'WE', {'units':'V/div'}],
['TriggerDelay', 'Not operational', NTS('F32'), 0., 'WE', {'units':'s'}],
['NoiseAmplitude', 'Noise level', NTS('F32'), G.noiseLevel, 'WE',
    {'setter':G.set_noise, 'limitLow':-100., 'limitHigh':100., 'units':'V'}],
['UpdateTime', 'Not operational',
    NTS('F32'), 0., 'WE', {'limitLow':0.001, 'limitHigh':10., 'units':'s'}],
['Waveform_RBV', 'Waveform array', NTA('F32'), [0.], 'R',{}],
['TimeBase_RBV', 'Timebase array, synchronous with Waveform_RBV',
    NTA('F32'), [0.], 'R',{}],
['MaxPoints_RBV', 'Number of points in Waveorm_RBV',
    NTS('U16'), MaxPoints, 'R',{}],
['MinValue_RBV', 'Waveform min', NTS('F32'), 0., 'R',{}],
['MaxValue_RBV', 'Waveform max', NTS('F32'), 0., 'R',{}],
['MeanValue_RBV', 'Waveform mean', NTS('F32'), 0., 'R',{}],
['threads', 'Number of threads running in this softIocPVA',
    NTS('U8'), 0, 'R', {'units':'threads'}],
['cycle',   'Cycle number', NTS('U32'), '0', 'R',{}],
]
ts = time.time()

#``````````````````create_PVs()```````````````````````````````````````````````
for defs in PVDefs:
    pname,desc,nt,ivalue,features,extra = defs
    writable = 'W' in features
    #print(f'creating pv {pname}, writable: {writable}, initial: {ivalue}, extra: {extra}')
    pv = SharedPV(nt=nt)
    G.PVs[P+pname] = pv
    pv.open(ivalue)
    #if isinstance(ivalue,dict):# NTEnum
    if isinstance(nt,NTEnum):# NTEnum
        pv.post(ivalue, timestamp=ts)
    else:
        v = pv._wrap(ivalue, timestamp=ts)
        #if display:
        displayFields = {'display.description':desc}
        for field in ['limitLow','limitHigh','format','units']:
            try:    displayFields[f'display.{field}'] = extra[field]
            except: pass
        for key,value in displayFields.items():
            #print(f'Trying to add {key} to {pname}')
            try:    v[key] = value
            except Exception as e:
                printe(f'in adding {key} to {pname}: {e}')
                pass
        pv.post(v)
    pv.name = pname
    pv.setter = extra.get('setter')

    if writable:
        @pv.put
        def handle(pv, op):
            ct = time.time()
            v = op.value()
            vr = v.raw.value
            if isinstance(v, ntenum):
                vr = v
            if pv.setter:
                pv.setter(vr)
            if pargs.verbose >= 1:
                printi(f'putting {pv.name} = {vr}')
            pv.post(vr, timestamp=ct) # update subscribers
            op.done()
#,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
if pargs.listPVs:
    print('List of PVs:')
    pprint.pp(list(G.PVs.keys()))

def myThread_proc():
    threads = 0
    printi('Run started')
    while not EventExit.is_set():
        G.cycle += 1
        #print(f'cycle {G.cycle}')
        tc = threading.active_count()
        if threads != tc:
            threads = tc
            G.PVs[P+'threads'].post(threads)
        G.PVs[P+'cycle'].post(G.cycle)

        # update waveform
        ts = time.time()
        wf = get_waveForm()
        #pprint.pp(wf)
        G.PVs[P+'Waveform_RBV'].post(wf, timestamp=ts)
        G.PVs[P+'TimeBase_RBV'].post(G.timeArray, timestamp=ts)
        G.PVs[P+'MinValue_RBV'].post(wf.min(), timestamp=ts)
        G.PVs[P+'MeanValue_RBV'].post(wf.mean(), timestamp=ts)
        G.PVs[P+'MaxValue_RBV'].post(wf.max(), timestamp=ts)
        if str(G.PVs[P+'Run'].current())!='Run':
            break
        EventExit.wait(SleepTime)
    printi('Run stopped')
    return

G.threadProc = myThread_proc
thread = threading.Thread(target=myThread_proc).start()

Server.forever(providers=[G.PVs]) # runs until KeyboardInterrupt

