def init():
    global _g_dict
    _g_dict = {}

def IsRun():
    return _g_dict['is_run']

def Start():
    _g_dict['is_run'] = True

def Stop():
    _g_dict['is_run'] = False