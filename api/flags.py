from ._storage import DATA_DIR, NotFoundError, DuplicateError

FLAGS_DIR = DATA_DIR / "country_flags"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

def _path(code):
    return FLAGS_DIR / f"{code}.png"

def _write(code, png_bytes):
    if not png_bytes.startswith(PNG_SIGNATURE):
        raise ValueError("Flag data is not a PNG image")
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    _path(code).write_bytes(png_bytes)

# --- CREATE ---
def create(code, png_bytes):
    if exists(code):
        raise DuplicateError(f"A flag for {code!r} already exists")
    _write(code, png_bytes)

# --- READ ---
def list_codes():
    """ Country codes that have a flag file, e.g. {'US', 'GB', ...} """
    return {p.stem for p in FLAGS_DIR.glob("*.png")}

def exists(code):
    return _path(code).exists()

def get(code):
    """ The flag image as bytes.= """
    if not exists(code):
        raise NotFoundError(f"No flag for {code!r}")
    return _path(code).read_bytes()

# --- UPDATE ---
def update(code, png_bytes):
    if not exists(code):
        raise NotFoundError(f"No flag for {code!r}")
    _write(code, png_bytes)

# --- DELETE ---
def delete(code):
    if not exists(code):
        raise NotFoundError(f"No flag for {code!r}")
    _path(code).unlink()