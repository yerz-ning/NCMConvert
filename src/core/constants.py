MAGIC = b"CTENFDAM"
GAP_AFTER_MAGIC = 2
GAP_AFTER_CRC = 5

# 因版权问题密钥不在此公开
CORE_KEY = b""
# 因版权问题密钥不在此公开
MODIFY_KEY = b""
KEY_XOR = 0x64
META_XOR = 0x63

KEY_PREFIX = b"neteasecloudmusic"
META_PREFIX_RAW = b"163 key(Don't modify):"
META_PREFIX_AES = b"music:"

DEFAULT_FORMAT = "mp3"
NCM_SUFFIX = ".ncm"

MAX_BLOB_LEN = 64 << 20
AUDIO_CHUNK_SIZE = 64 * 1024
AES_BLOCK_SIZE = 16
AES_KEY_LEN = 16

COVER_JPEG_EXT = "jpg"
COVER_PNG_EXT = "png"
COVER_JPEG_MAGIC = b"\xff\xd8\xff"
COVER_PNG_MAGIC = b"\x89PNG"
COVER_MAX_EXT_LEN = 16

WINDOWS_RESERVED = '<>:"/\\|?*'
MAX_BASE_RUNES = 120
DEVICE_NAMES = frozenset([
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
])

APP_NAME = "NCMConvert"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Yerz_凝"
APP_HOMEPAGE = "https://github.com/yerz-ning"
APP_LICENSE = "GNU GPLv3.0"
APP_REPO = "https://github.com/yerz-ning/NCMConvert"
APP_SUMMARY = "网易云音乐 NCM 文件解密工具"

CONFIG_DIR_NAME = "NCMConvert"
CONFIG_FILE_NAME = "settings.json"
DEFAULT_SETTINGS = {"embed_cover": True, "meta_json": False, "skip_existing": False}
LEGACY_SETTINGS_KEYS = {"keep_cover": "embed_cover"}

MIME_JPEG = "image/jpeg"
MIME_PNG = "image/png"
COVER_EXT_MIME = {COVER_JPEG_EXT: MIME_JPEG, COVER_PNG_EXT: MIME_PNG}
EMBED_AUDIO_FORMATS = frozenset(["mp3", "flac"])
EMBED_TEMP_SUFFIX = ".part"

ID3_MAGIC = b"ID3"
ID3_HEADER_SIZE = 10
ID3_FRAME_HEADER_SIZE = 10
ID3_VERSION_3 = 3
ID3_VERSION_4 = 4
ID3_TEXT_ENCODING = 1
ID3_PICTURE_TYPE_FRONT_COVER = 3
ID3_APIC_FRAME_ID = b"APIC"
ID3_OLD_IMAGE_FRAME_ID = b"PIC"
ID3_FLAG_UNSYNCHRONISATION = 0x80
ID3_FLAG_EXTENDED_HEADER = 0x40
ID3_TAG_PADDING = 256
ID3_TEXT_FRAMES = (("musicName", b"TIT2"), ("artist", b"TPE1"), ("album", b"TALB"))
MAX_ID3_TAG_SIZE = 16 << 20

FLAC_MAGIC = b"fLaC"
FLAC_BLOCK_HEADER_SIZE = 4
FLAC_BLOCK_STREAMINFO = 0
FLAC_BLOCK_PICTURE = 6
FLAC_PICTURE_TYPE_FRONT_COVER = 3
FLAC_LAST_BLOCK_FLAG = 0x80
FLAC_BLOCK_TYPE_MASK = 0x7F
MAX_FLAC_BLOCK_SIZE = 32 << 20
MAX_FLAC_BLOCK_LEN_BYTES = 0xFFFFFF
PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
PNG_IHDR_OFFSET = 16
PNG_IHDR_MIN_LEN = 26
JPEG_MARKER_PREFIX = 0xFF
JPEG_SOF_MARKERS = frozenset([0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF])
