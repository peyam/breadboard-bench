"""ROM/RAM images in the project file: {"size": 32768, "fill": 255, "base64": "..."}.
Trailing fill bytes are left out of the base64 text, so a mostly blank EEPROM is small."""
import base64


def encode(image, fill=0xFF):
    b = bytes(image)
    end = len(b)
    while end and b[end - 1] == fill:
        end -= 1
    return {"size": len(b), "fill": fill, "base64": base64.b64encode(b[:end]).decode("ascii")}


def decode(obj):
    if isinstance(obj, (bytes, bytearray, list)):
        return bytes(obj)
    size = int(obj.get("size", 32768))
    fill = int(obj.get("fill", 0xFF))
    data = base64.b64decode(obj.get("base64", "")) if obj.get("base64") else bytes.fromhex(obj.get("hex", ""))
    if len(data) > size:
        raise ValueError("image data longer than its size")
    return data + bytes([fill]) * (size - len(data))
