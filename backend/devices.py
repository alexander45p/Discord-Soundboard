import sounddevice as sd


def input_devices():
    hostapis = sd.query_hostapis()
    result = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            result.append((i, f"{d['name']}  [{hostapis[d['hostapi']]['name']}]"))
    return result


def output_devices():
    hostapis = sd.query_hostapis()
    result = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0:
            result.append((i, f"{d['name']}  [{hostapis[d['hostapi']]['name']}]"))
    return result
