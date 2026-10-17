from src.core.constants import AES_BLOCK_SIZE, AUDIO_CHUNK_SIZE
from src.core.errors import NcmError


def _xtime(value):
    value <<= 1
    if value & 0x100:
        value ^= 0x11B
    return value & 0xFF


def _gmul(a, b):
    a &= 0xFF
    b &= 0xFF
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        a = _xtime(a)
        b >>= 1
    return result


def _gpow(a, n):
    result = 1
    base = a & 0xFF
    while n:
        if n & 1:
            result = _gmul(result, base)
        base = _gmul(base, base)
        n >>= 1
    return result


def _rotl8(value, n):
    return ((value << n) | (value >> (8 - n))) & 0xFF


def _build_sbox():
    inverse = [0] * 256
    for i in range(1, 256):
        inverse[i] = _gpow(i, 254)
    box = [0] * 256
    for i in range(256):
        x = inverse[i]
        box[i] = (x ^ _rotl8(x, 1) ^ _rotl8(x, 2) ^ _rotl8(x, 3) ^ _rotl8(x, 4) ^ 0x63) & 0xFF
    return box


def _mul_table(constant):
    return [_gmul(i, constant) for i in range(256)]


_SBOX = _build_sbox()
_INV_SBOX = [0] * 256
for _index, _value in enumerate(_SBOX):
    _INV_SBOX[_value] = _index
_MUL9 = _mul_table(9)
_MUL11 = _mul_table(11)
_MUL13 = _mul_table(13)
_MUL14 = _mul_table(14)
_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _expand_key(key):
    words = [list(key[i * 4:i * 4 + 4]) for i in range(4)]
    for i in range(4, 44):
        temp = list(words[i - 1])
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // 4 - 1]
        previous = words[i - 4]
        words.append([previous[k] ^ temp[k] for k in range(4)])
    round_keys = []
    for round_index in range(11):
        flat = []
        for word in words[round_index * 4:(round_index + 1) * 4]:
            flat.extend(word)
        round_keys.append(flat)
    return round_keys


def _inv_shift_rows(state):
    out = [0] * 16
    for row in range(4):
        for column in range(4):
            out[4 * column + row] = state[4 * ((column - row) % 4) + row]
    return out


def _inv_mix_columns(state):
    out = [0] * 16
    for column in range(4):
        a0 = state[4 * column]
        a1 = state[4 * column + 1]
        a2 = state[4 * column + 2]
        a3 = state[4 * column + 3]
        out[4 * column] = _MUL14[a0] ^ _MUL11[a1] ^ _MUL13[a2] ^ _MUL9[a3]
        out[4 * column + 1] = _MUL9[a0] ^ _MUL14[a1] ^ _MUL11[a2] ^ _MUL13[a3]
        out[4 * column + 2] = _MUL13[a0] ^ _MUL9[a1] ^ _MUL14[a2] ^ _MUL11[a3]
        out[4 * column + 3] = _MUL11[a0] ^ _MUL13[a1] ^ _MUL9[a2] ^ _MUL14[a3]
    return out


def _decrypt_block(round_keys, block):
    inv_sbox = _INV_SBOX
    state = [block[i] ^ round_keys[10][i] for i in range(16)]
    for round_index in range(9, 0, -1):
        state = _inv_shift_rows(state)
        state = [inv_sbox[b] for b in state]
        key_bytes = round_keys[round_index]
        state = [state[i] ^ key_bytes[i] for i in range(16)]
        state = _inv_mix_columns(state)
    state = _inv_shift_rows(state)
    state = [inv_sbox[b] for b in state]
    key_bytes = round_keys[0]
    return bytes([state[i] ^ key_bytes[i] for i in range(16)])


def aes_ecb_decrypt(key, data):
    if len(data) == 0:
        raise NcmError("AES 密文为空")
    if len(data) % AES_BLOCK_SIZE != 0:
        raise NcmError("密文长度 %d 不是 16 的整数倍" % len(data))
    round_keys = _expand_key(key)
    out = bytearray()
    for offset in range(0, len(data), AES_BLOCK_SIZE):
        out += _decrypt_block(round_keys, data[offset:offset + AES_BLOCK_SIZE])
    return bytes(out)


def aes_sbox():
    return list(_SBOX)


def build_key_box(key):
    box = list(range(256))
    key_len = len(key)
    if key_len == 0:
        return box
    last = 0
    for i in range(256):
        swap = (box[i] + last + key[i % key_len]) & 0xFF
        box[i], box[swap] = box[swap], box[i]
        last = swap
    return box


def build_keystream(box):
    stream = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        kj = box[j]
        a = box[(kj + j) & 0xFF]
        stream[i] = box[(kj + a) & 0xFF]
    return bytes(stream)


def chunk_keystream(length, offset, stream):
    start = offset & 0xFF
    rotated = stream[start:] + stream[:start]
    repeats = length // 256 + 1
    return (rotated * repeats)[:length]


def xor_bytes(data, key_data):
    length = len(data)
    left = int.from_bytes(data, "little")
    right = int.from_bytes(key_data, "little")
    return (left ^ right).to_bytes(length, "little")


def decrypt_audio_stream(src, dst, stream):
    offset = 0
    while True:
        data = src.read(AUDIO_CHUNK_SIZE)
        if not data:
            break
        key_data = chunk_keystream(len(data), offset, stream)
        dst.write(xor_bytes(data, key_data))
        offset += len(data)
