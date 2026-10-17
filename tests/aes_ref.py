_SBOX_HEX = (
    "637c777bf26b6fc53001672bfed7ab76"
    "ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d83115"
    "04c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f84"
    "53d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa8"
    "51a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d1973"
    "60814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479"
    "e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a"
    "703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df"
    "8ca1890dbfe6426841992d0fb054bb16"
)

_SBOX = bytes.fromhex(_SBOX_HEX)
_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def sbox():
    return bytes(_SBOX)


def inv_sbox():
    table = bytearray(256)
    for index, value in enumerate(_SBOX):
        table[value] = index
    return bytes(table)


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11B
    return a & 0xFF


def _gmul(a, b):
    a &= 0xFF
    b &= 0xFF
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        a = _xtime(a)
        b >>= 1
    return result & 0xFF


def _expand(key):
    if len(key) != 16:
        raise ValueError("AES-128 需要 16 字节密钥")
    words = [list(key[4 * i:4 * i + 4]) for i in range(4)]
    for i in range(4, 44):
        temp = list(words[i - 1])
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // 4 - 1]
        words.append([words[i - 4][k] ^ temp[k] for k in range(4)])
    round_keys = []
    for round_index in range(11):
        flat = []
        for word in words[round_index * 4:(round_index + 1) * 4]:
            flat.extend(word)
        round_keys.append(flat)
    return round_keys


def _add_round_key(state, round_key):
    return [state[i] ^ round_key[i] for i in range(16)]


def _sub_bytes(state):
    return [_SBOX[b] for b in state]


def _shift_rows(state):
    out = [0] * 16
    for row in range(4):
        for column in range(4):
            out[4 * column + row] = state[4 * ((column + row) % 4) + row]
    return out


def _mix_columns(state):
    out = [0] * 16
    for column in range(4):
        a0 = state[4 * column]
        a1 = state[4 * column + 1]
        a2 = state[4 * column + 2]
        a3 = state[4 * column + 3]
        out[4 * column] = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
        out[4 * column + 1] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
        out[4 * column + 2] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
        out[4 * column + 3] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)
    return out


def encrypt(key, data):
    if len(data) == 0:
        raise ValueError("明文为空")
    if len(data) % 16 != 0:
        raise ValueError("明文长度必须是 16 的整数倍")
    round_keys = _expand(key)
    out = bytearray()
    for offset in range(0, len(data), 16):
        state = list(data[offset:offset + 16])
        state = _add_round_key(state, round_keys[0])
        for round_index in range(1, 10):
            state = _sub_bytes(state)
            state = _shift_rows(state)
            state = _mix_columns(state)
            state = _add_round_key(state, round_keys[round_index])
        state = _sub_bytes(state)
        state = _shift_rows(state)
        state = _add_round_key(state, round_keys[10])
        out += bytes(state)
    return bytes(out)


def pkcs7(data, block=16):
    pad = block - (len(data) % block)
    return data + bytes([pad]) * pad
